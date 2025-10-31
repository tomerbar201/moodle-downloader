import os
import re
import time
import logging
import mimetypes
import http.client
from typing import Dict, Tuple, List, Optional, Callable, Set
from bs4 import BeautifulSoup
from urllib.parse import urlparse, unquote, urljoin
from playwright.sync_api import APIResponse, TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError

from .data_structures import DownloadResult
from .moodle_browser import MoodleBrowser
from .file_operations import sanitize_folder_name


class DownloadHandler:
    """Handles downloading files from Moodle and tracking download history"""
    LOG_SEPARATOR = "\t"  # Separator for URL and Filename in log

    def __init__(self, moodle_browser: MoodleBrowser, central_download_log_file: str):
        self.moodle_browser = moodle_browser
        self.api_request_context = moodle_browser.api_request_context
        self.central_download_log_file = central_download_log_file
        self.logger = logging.getLogger("MoodleDownPlaywright")
        self._logged_urls = self._load_and_verify_logged_urls()

    def _load_and_verify_logged_urls(self) -> Set[str]:
        """Load previously downloaded URLs from log, verify files exist"""
        logged_urls = set()
        valid_log_entries = []
        lines_read = 0
        removed_count = 0

        if not os.path.exists(self.central_download_log_file):
            self.logger.warning(
                f"Central download log file '{self.central_download_log_file}' not found. Starting fresh.")
            return logged_urls

        try:
            with open(self.central_download_log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    lines_read += 1
                    stripped_line = line.strip()
                    if not stripped_line:
                        continue

                    parts = stripped_line.split(self.LOG_SEPARATOR, 1)
                    if len(parts) == 2:
                        url, filepath = parts[0].strip(), parts[1].strip()
                        if url and filepath:
                            # Verify file still exists
                            if os.path.exists(filepath):
                                logged_urls.add(url)
                                valid_log_entries.append(stripped_line)  # Keep the original valid line
                            else:
                                self.logger.info(f"Logged file missing: '{filepath}'. Removing entry for URL: {url}")
                                removed_count += 1
                        else:
                            self.logger.warning(f"Skipping malformed log entry (empty url/path): {stripped_line}")
                    else:
                        self.logger.warning(f"Skipping malformed log entry (incorrect format): {stripped_line}")

            self.logger.info(
                f"Loaded {len(logged_urls)} URLs from verified entries in '{self.central_download_log_file}'.")

            # Rewrite log file only if entries were removed
            if removed_count > 0:
                self.logger.info(f"Rewriting log to remove {removed_count} entries for missing files.")
                try:
                    with open(self.central_download_log_file, 'w', encoding='utf-8') as f_rewrite:
                        for valid_line in valid_log_entries:
                            f_rewrite.write(valid_line + '\n')
                    self.logger.info("Central download log cleaned successfully.")
                except IOError as e_write:
                    self.logger.error(f"Error rewriting cleaned download log file: {e_write}")
            else:
                self.logger.info("No missing files found in log entries.")

        except IOError as e_read:
            self.logger.error(f"Error reading download log file: {e_read}")

        return logged_urls

    def get_logged_urls(self) -> Set[str]:
        """Return the set of already downloaded URLs"""
        return self._logged_urls

    def _get_filename_from_headers(self, headers: Dict) -> Optional[str]:
        """Extract filename from Content-Disposition header"""
        content_disposition = headers.get('content-disposition')
        if not content_disposition:
            return None

        # Try RFC 5987 first (UTF-8 encoding)
        match_utf8 = re.search(r"filename\*=UTF-8''([^;]+)", content_disposition, re.IGNORECASE)
        if match_utf8:
            try:
                return unquote(match_utf8.group(1), encoding='utf-8').strip()
            except Exception as e:
                self.logger.warning(f"Failed to decode RFC 5987 filename: {match_utf8.group(1)} - {e}")

        # Try standard filename="..."
        match_std = re.search(r'filename="([^"]+)"', content_disposition, re.IGNORECASE)
        if match_std:
            filename = match_std.group(1)
            try:  # Attempt decoding common issues
                if '%' in filename:
                    decoded = unquote(filename, encoding='utf-8')
                    filename = decoded if decoded != filename else filename
                else:
                    filename = filename.encode('latin-1').decode('utf-8')  # Common misconfiguration
            except (UnicodeDecodeError, UnicodeEncodeError):
                pass  # Use as is
            except Exception as e:
                self.logger.warning(f"Error processing standard filename '{filename}': {e}")
            return filename.strip()

        # Try filename=... (no quotes)
        match_noq = re.search(r'filename=([^;]+)', content_disposition, re.IGNORECASE)
        if match_noq:
            return match_noq.group(1).strip()

        self.logger.warning(f"Could not extract filename from Content-Disposition: {content_disposition}")
        return None

    def _determine_filename_and_extension(self, suggested_name: str, response: APIResponse, url: str,
                                          resource_type: str) -> Tuple[str, str]:
        """Determine appropriate filename and extension for the downloaded file"""
        filename, ext = None, None

        # Try to get filename from HTTP headers
        header_filename = self._get_filename_from_headers(response.headers)
        if header_filename:
            name_part, ext_part = os.path.splitext(header_filename)
            if ext_part:
                filename, ext = name_part, ext_part.lower().lstrip('.')
            else:
                filename = header_filename
            self.logger.info(f"Using filename from Content-Disposition: name='{filename}', ext='{ext}'")

        if not filename:
            filename = suggested_name
            self.logger.info(f"Using suggested name from page: '{filename}'")

        # Determine extension if not found in header filename
        if not ext:
            parsed_url = urlparse(response.url)  # Use final URL after redirects
            _, url_ext = os.path.splitext(parsed_url.path)
            if url_ext and len(url_ext) > 1:
                ext = url_ext.lower().lstrip('.')
                self.logger.info(f"Using extension '{ext}' from URL path.")

        # Try Content-Type if extension still not determined
        if not ext:
            content_type = response.headers.get('content-type', '').split(';')[0].strip()
            if content_type:
                guessed_ext = mimetypes.guess_extension(content_type)
                if guessed_ext:
                    ext = guessed_ext.lower().lstrip('.')
                    self.logger.info(f"Using extension '{ext}' from Content-Type: {content_type}")

        # Force .zip for folders
        if resource_type == 'folder' or 'download_folder.php' in url:
            if ext != 'zip':
                self.logger.info(f"Resource type is folder, ensuring extension is 'zip' (was '{ext}').")
                ext = 'zip'

        # Default extension if still not determined
        if not ext:
            self.logger.warning(f"Could not determine extension for '{filename}'. Defaulting to 'bin'.")
            ext = 'bin'

        # Clean the filename
        filename = re.sub(r'[<>:"/\\|?*\x00-\x1F]', '_', filename).strip('._ ')
        filename = filename if filename else "downloaded_file"  # Ensure non-empty

        return filename, ext

    def _extract_assignment_files(self, assignment_url: str) -> List[Dict]:
        """Extract intro attachments (pluginfile links) from an assignment page."""
        self.logger.info(f"Scanning assignment page for attachments: {assignment_url}")

        if not self.api_request_context:
            self.logger.warning("APIRequestContext unavailable; cannot inspect assignment attachments.")
            return []

        try:
            response = self.api_request_context.get(
                assignment_url,
                headers=self.moodle_browser.headers,
                timeout=30000
            )
            if not response.ok:
                self.logger.warning(f"Assignment page fetch failed ({response.status}).")
                return []

            soup = BeautifulSoup(response.text(), 'html.parser')
            attachment_links = []
            seen_urls: Set[str] = set()

            for anchor in soup.select('a[href*="pluginfile.php"]'):
                href = anchor['href']
                if '/mod_assign/intro' not in href and '/mod_assign/introattachment' not in href:
                    continue

                absolute_url = urljoin(response.url, href)
                if absolute_url in seen_urls:
                    continue
                seen_urls.add(absolute_url)

                display_name = anchor.get_text(strip=True)
                if not display_name:
                    img = anchor.find('img', alt=True)
                    if img and img.get('alt'):
                        display_name = img['alt'].strip()
                if not display_name:
                    sibling_img = anchor.find_previous('img', alt=True)
                    if sibling_img and sibling_img.get('alt'):
                        display_name = sibling_img['alt'].strip()
                if not display_name:
                    display_name = "assignment_file"

                attachment_links.append({
                    'url': absolute_url,
                    'name': display_name
                })
                self.logger.info(f"Queued assignment attachment: {display_name} -> {absolute_url}")

            self.logger.info(f"Found {len(attachment_links)} intro attachment(s) in assignment page.")
            return attachment_links

        except Exception as exc:
            self.logger.error(f"Error while extracting assignment attachments: {exc}")
            return []

    def download_file(self, item_info: Dict, target_filepath_base: str) -> DownloadResult:
        """Download a single file and update central log on success"""
        initial_url = item_info['url']
        suggested_name = item_info['name']
        resource_type = item_info['type']
        current_url_to_fetch = initial_url

        # Handle assignment pages - extract pluginfile URLs first
        if resource_type == 'assignment' and 'assign/view.php' in current_url_to_fetch:
            assignment_files = self._extract_assignment_files(current_url_to_fetch)

            if not assignment_files:
                self.logger.info(f"No intro attachments found in assignment: {suggested_name}")
                return DownloadResult(True, "No intro attachments in assignment", skipped=True)

            # Download all attached files from this assignment
            successes, failures = 0, 0
            for idx, file_info in enumerate(assignment_files):
                derived_name = file_info['name']
                if len(assignment_files) > 1:
                    derived_name = f"{suggested_name}_{idx+1:02d}_{derived_name}"
                file_item = {
                    'url': file_info['url'],
                    'name': derived_name,
                    'type': 'document',
                    'section': item_info.get('section', '')
                }

                # Recursive call to download the actual file
                file_result = self.download_file(file_item, target_filepath_base)
                if file_result.success:
                    successes += 1
                else:
                    failures += 1

            if successes > 0 and failures == 0:
                return DownloadResult(True, f"Downloaded {successes} assignment attachment(s)", skipped=True)
            if successes > 0:
                return DownloadResult(True, f"Downloaded {successes} assignment attachment(s), {failures} failed", skipped=True)
            return DownloadResult(False, "Failed to download assignment attachments")

        # Adjust URL for folder downloads
        if resource_type == 'folder' and 'view.php' in current_url_to_fetch and '?id=' in current_url_to_fetch:
            current_url_to_fetch = current_url_to_fetch.replace('view.php', 'download_folder.php')
            self.logger.info(f"Adjusted folder URL for download: {current_url_to_fetch}")

        self.logger.info(f"Attempting download: {suggested_name} from {current_url_to_fetch}")
        if not self.api_request_context:
            return DownloadResult(False, "APIRequestContext not available")

        response: Optional[APIResponse] = None
        final_filepath = target_filepath_base  # Will be updated with correct extension

        try:
            # Initial request
            response = self.api_request_context.get(
                current_url_to_fetch,
                headers=self.moodle_browser.headers,
                timeout=120000
            )

            # Check if response is an HTML page with embedded content (handling intermediate pages)
            response_content_type = response.headers.get('content-type', '').lower()
            is_html_page = 'text/html' in response_content_type
            is_intermediate_page = 'mod/resource/view.php' in response.url or 'mod/page/view.php' in response.url

            if response.ok and is_html_page and is_intermediate_page:
                self.logger.info(
                    f"Initial fetch returned HTML page for {suggested_name}. Checking for embedded resource...")
                soup = BeautifulSoup(response.text(), 'html.parser')

                # Look for iframe or object tag with embedded content
                iframe_src_url = None
                iframe = soup.find('iframe', id='resourceobject') or soup.find('iframe', class_='resourceworkarea')

                if not iframe:
                    obj_tag = soup.find('object', type='application/pdf')
                    iframe_src_url = obj_tag['data'] if obj_tag and obj_tag.get('data') else None

                if not iframe and not iframe_src_url:
                    main_region = soup.find(id='region-main')
                    iframe = main_region.find('iframe') if main_region else soup.find('iframe')  # Fallbacks

                if iframe and iframe.get('src'):
                    iframe_src_url = iframe['src']

                if iframe_src_url:
                    self.logger.info(f"Found embedded resource source: {iframe_src_url}")
                else:
                    # Try pluginfile link as fallback
                    plugin_link = soup.select_one('a[href*="pluginfile.php"]')
                    if plugin_link:
                        iframe_src_url = plugin_link['href']
                        self.logger.info(f"Found pluginfile link within embed page: {iframe_src_url}")
                    else:
                        self.logger.warning(f"Could not find embedded resource in HTML page for {suggested_name}.")

                if iframe_src_url:
                    # Make the URL absolute if it's relative
                    iframe_src_url = urljoin(response.url, iframe_src_url)
                    self.logger.info(f"Fetching actual resource from embedded URL: {iframe_src_url}")
                    response = self.api_request_context.get(
                        iframe_src_url,
                        headers=self.moodle_browser.headers,
                        timeout=120000
                    )

            # Check response status after potential second fetch
            if not response.ok:
                status_text = http.client.responses.get(response.status, 'Unknown Status')
                self.logger.error(f"Download failed for '{suggested_name}'. Status: {response.status} {status_text}.")

                # Log small text error bodies for debugging
                try:
                    resp_ct = response.headers.get('content-type', '').lower()
                    resp_cl = int(response.headers.get('content-length', '10000'))
                    if ('text' in resp_ct or 'json' in resp_ct) and resp_cl < 5000:
                        self.logger.error(f"Error details (partial): {response.text()[:500]}")
                except Exception:
                    pass

                return DownloadResult(False, f"HTTP error {response.status} {status_text}")

            # Determine final filename and save
            base_filename, extension = self._determine_filename_and_extension(
                suggested_name, response, response.url, resource_type
            )

            target_dir = os.path.dirname(target_filepath_base)
            final_filename = f"{base_filename}.{extension}"
            final_filepath = os.path.join(target_dir, final_filename)

            # Ensure the directory exists
            os.makedirs(target_dir, exist_ok=True)

            # Write file
            file_content = response.body()
            self.logger.info(f"Saving file to: {final_filepath} (overwriting if exists)")
            with open(final_filepath, 'wb') as f:
                f.write(file_content)

            filesize = len(file_content)

            # Determine result
            if filesize > 0:
                result = DownloadResult(True, "Download successful", final_filepath, filesize)
            elif response.headers.get('content-length') == '0':
                result = DownloadResult(True, "Download successful (zero bytes)", final_filepath, 0)
            else:
                result = DownloadResult(False, "Empty file downloaded", final_filepath)
                self.logger.warning(
                    f"Downloaded file is empty but server didn't indicate 0 length: '{final_filename}'.")

            # Log successful downloads to central file
            if result.success:
                try:
                    # Log the original URL and the final file path
                    log_entry = f"{initial_url}{self.LOG_SEPARATOR}{result.filepath}\n"
                    with open(self.central_download_log_file, 'a', encoding='utf-8') as f_log:
                        f_log.write(log_entry)
                    self._logged_urls.add(initial_url)  # Add to in-memory set too
                    self.logger.info(f"Added to central log: {initial_url} -> {result.filepath}")
                except IOError as e:
                    self.logger.error(f"Failed to write to central log file: {e}")

            return result

        except (PlaywrightTimeoutError, PlaywrightError) as e:
            err_type = "Timeout" if isinstance(e, PlaywrightTimeoutError) else f"Network error: {e.__class__.__name__}"
            failed_url = response.url if response else current_url_to_fetch
            self.logger.error(f"{err_type} downloading {suggested_name} from {failed_url}: {str(e)}")
            return DownloadResult(False, err_type)
        except IOError as e:
            self.logger.error(f"File system error saving {suggested_name} to {final_filepath}: {str(e)}")
            return DownloadResult(False, f"File system error: {e}")
        except Exception as e:
            failed_url = response.url if response else current_url_to_fetch
            self.logger.exception(f"Unexpected error downloading {suggested_name} ({failed_url}): {str(e)}")
            return DownloadResult(False, f"Unexpected error: {e}")

    def download_files(self,
                       to_download: Dict[str, Dict],
                       progress_callback: Optional[Callable[[str, float], None]] = None,
                       organize_by_section: bool = True) -> Tuple[List[str], List[str], List[str]]:
        """Download all files, organizing by section if requested"""
        failed, successful, skipped = [], [], []
        total_files = len(to_download)

        if total_files == 0:
            self.logger.info("No new items to download after checking central log.")
            return [], [], []

        processed_count = 0
        self.logger.info(f"Starting download process for {total_files} items.")

        # Prepare section folders
        section_folders = {}
        base_download_folder = self.moodle_browser.download_folder

        if organize_by_section:
            # Create folders for each section
            unique_sections = set(info.get('section', 'Course Materials') for info in to_download.values())
            for section_name in unique_sections:
                section_folder_name = sanitize_folder_name(section_name)
                section_path = os.path.join(base_download_folder, section_folder_name)
                try:
                    os.makedirs(section_path, exist_ok=True)
                    section_folders[section_name] = section_path
                except OSError as e:
                    self.logger.error(f"Failed to create section folder '{section_path}': {e}. Using base folder.")
                    section_folders[section_name] = base_download_folder
        else:
            # Just ensure the base course folder exists
            try:
                os.makedirs(base_download_folder, exist_ok=True)
            except OSError as e:
                self.logger.error(f"Failed to create base download folder '{base_download_folder}': {e}.")

        # Sort items by section and name for organized downloading
        sorted_items = sorted(to_download.items(),
                              key=lambda item: (item[1].get('section', ''), item[1].get('name', '')))

        for url, item_info in sorted_items:
            processed_count += 1
            doc_name = item_info.get('name', 'Unknown Name')
            section = item_info.get('section', 'Course Materials')
            resource_type = item_info.get('type', 'unknown')

            self.logger.info(
                f"Processing item {processed_count}/{total_files}: '{doc_name}' (Type: {resource_type}, Section: {section})")

            # Update progress display
            current_progress = (processed_count - 1) / total_files * 100 if total_files > 0 else 0
            if progress_callback:
                progress_callback(f"Processing: {doc_name}", current_progress)

            # Determine target directory (section or base folder)
            target_dir = section_folders.get(section,
                                             base_download_folder) if organize_by_section else base_download_folder
            sanitized_base_name = re.sub(r'[<>:"/\\|?*\x00-\x1F]', '_', doc_name).strip('._ ')

            # Base path without extension
            initial_filepath_suggestion = os.path.join(target_dir, sanitized_base_name)

            if progress_callback:
                progress_callback(f"Starting download: {doc_name}",
                                  current_progress + (20.0 / total_files) if total_files > 0 else current_progress)

            # Download the file
            result = self.download_file(item_info, initial_filepath_suggestion)
            final_doc_name = os.path.basename(result.filepath) if result.filepath else f"{sanitized_base_name}_FAILED"
            progress_pct_done = processed_count / total_files * 100 if total_files > 0 else 100

            if result.success:
                self.logger.info(f"Success {processed_count}/{total_files}: Downloaded '{final_doc_name}'")
                successful.append(final_doc_name)
                if progress_callback:
                    progress_callback(f"Downloaded: {final_doc_name}", progress_pct_done)
            else:
                self.logger.error(f"Failed {processed_count}/{total_files}: '{doc_name}' - Reason: {result.message}")
                original_url_for_error = item_info.get('url', 'N/A')
                failed.append(f"'{doc_name}' (Section: {section}, URL: {original_url_for_error}) - {result.message}")
                if progress_callback:
                    progress_callback(f"Failed: {doc_name} - {result.message}", progress_pct_done)

            # Small delay between downloads
            time.sleep(0.8)

        # Final report
        self.logger.info(f"Download process finished for {total_files} items.")
        self.logger.info(f"Summary: {len(successful)} files downloaded. {len(failed)} download attempts failed.")

        if failed:
            self.logger.warning("--- Failed Downloads ---")
            for failure in failed:
                self.logger.warning(f"- {failure}")
            self.logger.warning("--- End of Failed Downloads ---")

        return successful, [], failed