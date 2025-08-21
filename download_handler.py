"""
This module defines the DownloadHandler class, which is responsible for managing
the entire file download process. It handles the logic for fetching files from
Moodle, including handling different resource types (e.g., files, folders),
managing download history to avoid re-downloading files, and organizing the
downloaded files into a structured directory.

The class uses Playwright for making network requests and BeautifulSoup for
parsing HTML when necessary (e.g., to find embedded resources). It also maintains
a central log file to keep track of downloaded files across sessions.
"""

import os
import re
import time
import logging
import mimetypes
import http.client
from typing import Dict, Tuple, List, Optional, Callable, Set, Any
from bs4 import BeautifulSoup
from bs4.element import Tag
from urllib.parse import urlparse, unquote, urljoin
from playwright.sync_api import APIResponse, TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError, APIRequestContext

from data_structures import DownloadResult
from moodle_browser import MoodleBrowser
from file_operations import sanitize_folder_name


class DownloadHandler:
    """
    Handles the downloading of files from Moodle and tracks download history.

    This class orchestrates the process of downloading files, from adjusting URLs
    for different resource types to saving the content and logging the download.
    It maintains a log of downloaded files to prevent duplicates and can verify
    the integrity of the log by checking for the existence of logged files.

    Attributes:
        moodle_browser (MoodleBrowser): An instance of MoodleBrowser to interact
                                        with the browser and make requests.
        api_request_context (Optional[APIRequestContext]): The Playwright context
                                                           for making API requests.
        central_download_log_file (str): The path to the central log file that
                                         tracks all downloaded files.
        logger (logging.Logger): A logger instance for logging messages.
        _logged_urls (Set[str]): A set of URLs that have been successfully
                                 downloaded, loaded from the log file.
    """

    LOG_SEPARATOR = "\t"  # Separator for URL and Filename in log

    def __init__(self, moodle_browser: MoodleBrowser, central_download_log_file: str) -> None:
        """
        Initializes the DownloadHandler.

        Args:
            moodle_browser (MoodleBrowser): The MoodleBrowser instance to use for
                                            downloads.
            central_download_log_file (str): Path to the file used for logging
                                             downloaded URLs.
        """
        self.moodle_browser: MoodleBrowser = moodle_browser
        self.api_request_context: Optional[APIRequestContext] = moodle_browser.api_request_context
        self.central_download_log_file: str = central_download_log_file
        self.logger: logging.Logger = logging.getLogger("MoodleDownPlaywright")
        self._logged_urls = self._load_and_verify_logged_urls()

    def _read_log_lines(self) -> List[str]:
        """
        Reads all lines from the central download log file.

        Returns:
            List[str]: A list of lines from the log file. Returns an empty list
                       if the file doesn't exist or an error occurs.
        """
        if not os.path.exists(self.central_download_log_file):
            self.logger.warning(
                f"Central download log file '{self.central_download_log_file}' not found. Starting fresh.")
            return []
        try:
            with open(self.central_download_log_file, 'r', encoding='utf-8') as f:
                return f.readlines()
        except IOError as e_read:
            self.logger.error(f"Error reading download log file: {e_read}")
            return []

    def _process_log_line(self, line: str) -> Optional[Tuple[str, str]]:
        """
        Processes a single log line, verifies file existence, and returns the URL
        and the original line if the entry is valid.

        Args:
            line (str): A single line from the log file.

        Returns:
            Optional[Tuple[str, str]]: A tuple containing the URL and the valid
                                      log line if the file exists, otherwise None.
        """
        stripped_line: str = line.strip()
        if not stripped_line:
            return None

        parts = stripped_line.split(self.LOG_SEPARATOR, 1)
        if len(parts) == 2:
            url, filepath = parts[0].strip(), parts[1].strip()
            if url and filepath:
                if os.path.exists(filepath):
                    return url, stripped_line
                else:
                    self.logger.info(f"Logged file missing: '{filepath}'. Removing entry for URL: {url}")
                    return None  # Indicate removal needed
            else:
                self.logger.warning(f"Skipping malformed log entry (empty url/path): {stripped_line}")
        else:
            self.logger.warning(f"Skipping malformed log entry (incorrect format): {stripped_line}")
        return None

    def _rewrite_cleaned_log(self, valid_log_entries: List[str], removed_count: int) -> None:
        """
        Rewrites the log file with only the valid entries, removing entries for
        files that no longer exist.

        Args:
            valid_log_entries (List[str]): A list of log lines that have been
                                           verified as valid.
            removed_count (int): The number of entries that were removed.
        """
        if removed_count == 0:
            self.logger.info("No missing files found in log entries. Log file not rewritten.")
            return

        self.logger.info(f"Rewriting log to remove {removed_count} entries for missing files.")
        try:
            with open(self.central_download_log_file, 'w', encoding='utf-8') as f_rewrite:
                for valid_line in valid_log_entries:
                    f_rewrite.write(valid_line + '\n')
            self.logger.info("Central download log cleaned successfully.")
        except IOError as e_write:
            self.logger.error(f"Error rewriting cleaned download log file: {e_write}")

    def _load_and_verify_logged_urls(self) -> Set[str]:
        """
        Loads previously downloaded URLs from the log file and verifies that the
        corresponding files still exist on disk.

        This method cleans the log file by removing entries for which the file is
        missing, ensuring the log remains accurate.

        Returns:
            Set[str]: A set of URLs corresponding to files that have been
                      downloaded and still exist.
        """
        logged_urls: Set[str] = set()
        valid_log_entries: List[str] = []
        removed_count: int = 0
        lines: List[str] = self._read_log_lines()

        for line in lines:
            result = self._process_log_line(line)
            if result:
                url, valid_line = result
                logged_urls.add(url)
                valid_log_entries.append(valid_line)
            elif line.strip():
                parts = line.strip().split(self.LOG_SEPARATOR, 1)
                if len(parts) == 2 and parts[0].strip() and parts[1].strip():
                    removed_count += 1

        self.logger.info(
            f"Loaded {len(logged_urls)} URLs from verified entries in '{self.central_download_log_file}'.")

        self._rewrite_cleaned_log(valid_log_entries, removed_count)
        return logged_urls

    def get_logged_urls(self) -> Set[str]:
        """
        Returns the set of already downloaded URLs.

        Returns:
            Set[str]: A set of URLs that have been successfully downloaded.
        """
        return self._logged_urls

    def _get_filename_from_headers(self, headers: Dict[str, str]) -> Optional[str]:
        """
        Extracts the filename from the 'Content-Disposition' header of an HTTP
        response.

        It supports both standard and RFC 5987 encoded filenames.

        Args:
            headers (Dict[str, str]): A dictionary of HTTP response headers.

        Returns:
            Optional[str]: The extracted filename, or None if not found.
        """
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
            try:
                if '%' in filename:
                    decoded = unquote(filename, encoding='utf-8')
                    filename = decoded if decoded != filename else filename
                else:
                    try:
                        filename = filename.encode('latin-1').decode('utf-8')
                    except (UnicodeDecodeError, UnicodeEncodeError):
                        pass
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
                                          resource_type: str) -> Tuple[str, Optional[str]]:
        """
        Determines the appropriate filename and extension for a downloaded file.

        It prioritizes the 'Content-Disposition' header, but falls back to using
        the suggested name from the page, the URL, and the content type.

        Args:
            suggested_name (str): The name of the resource as it appears on the
                                  Moodle page.
            response (APIResponse): The Playwright response object.
            url (str): The final URL from which the content was downloaded.
            resource_type (str): The type of the resource (e.g., 'folder', 'pdf').

        Returns:
            Tuple[str, Optional[str]]: A tuple containing the cleaned base
                                       filename and the file extension.
        """
        filename: Optional[str] = None
        ext: Optional[str] = None

        # 1. Try Content-Disposition Header
        header_filename = self._get_filename_from_headers(response.headers)
        if header_filename:
            name_part, ext_part = os.path.splitext(header_filename)
            filename = name_part if name_part else header_filename
            if ext_part:
                ext = ext_part.lower().lstrip('.')
            self.logger.info(f"Using filename from Content-Disposition: name='{filename}', ext='{ext}'")

        # 2. Use suggested name if header didn't provide one
        if not filename:
            filename = suggested_name
            self.logger.info(f"Using suggested name from page: '{filename}'")

        # 3. Determine extension if not found yet (URL, Content-Type)
        if not ext:
            parsed_url = urlparse(response.url)
            _, url_ext = os.path.splitext(parsed_url.path)
            if url_ext and len(url_ext) > 1:
                ext = url_ext.lower().lstrip('.')
                self.logger.info(f"Using extension '{ext}' from URL path.")
            else:
                content_type = response.headers.get('content-type', '').split(';')[0].strip()
                guessed_ext = mimetypes.guess_extension(content_type) if content_type else None
                if guessed_ext:
                    ext = guessed_ext.lower().lstrip('.')
                    self.logger.info(f"Using extension '{ext}' from Content-Type: {content_type}")

        # 4. Force .zip for folders
        if resource_type == 'folder' or 'download_folder.php' in url:
            if ext != 'zip':
                self.logger.info(f"Resource type is folder, ensuring extension is 'zip' (was '{ext}').")
                ext = 'zip'

        # 5. Default extension and clean filename
        if not ext:
            self.logger.warning(f"Could not determine extension for '{filename}'. Defaulting to 'bin'.")
            ext = 'bin'
        filename = re.sub(r'[<>:"/\\|?*\x00-\x1F]', '_', filename).strip('._ ')
        filename = filename if filename else "downloaded_file"

        return filename, ext

    def _adjust_folder_url(self, url: str, resource_type: str) -> str:
        """
        Adjusts the URL for downloading a folder.

        Moodle folders are downloaded as zip files, and this method converts the
        folder view URL to the appropriate download URL.

        Args:
            url (str): The original URL of the resource.
            resource_type (str): The type of the resource.

        Returns:
            str: The adjusted URL for downloading, or the original URL if no
                 adjustment is needed.
        """
        if resource_type == 'folder' and 'view.php' in url and '?id=' in url:
            adjusted_url = url.replace('view.php', 'download_folder.php')
            self.logger.info(f"Adjusted folder URL for download: {adjusted_url}")
            return adjusted_url
        return url

    def _fetch_initial_response(self, url: str) -> Optional[APIResponse]:
        """
        Fetches the initial response from the given URL using Playwright's API
        request context.

        Args:
            url (str): The URL to fetch.

        Returns:
            Optional[APIResponse]: The response object, or None if an error occurs.
        """
        try:
            return self.api_request_context.get(
                url,
                headers=self.moodle_browser.headers,
                timeout=120000
            )
        except (PlaywrightTimeoutError, PlaywrightError) as e:
            err_type = "Timeout" if isinstance(e, PlaywrightTimeoutError) else "Network error"
            self.logger.error(f"{err_type} during initial fetch from {url}: {str(e)}")
            return None
        except Exception as e:
            self.logger.exception(f"Unexpected error during initial fetch from {url}: {str(e)}")
            return None

    def _find_embedded_resource_url(self, soup: BeautifulSoup, base_url: str) -> Optional[str]:
        """
        Searches the HTML of an intermediate page for an embedded resource URL,
        such as in an iframe or object tag.

        Args:
            soup (BeautifulSoup): The parsed HTML of the page.
            base_url (str): The base URL for resolving relative links.

        Returns:
            Optional[str]: The URL of the embedded resource, or None if not found.
        """
        iframe: Optional[Tag] = soup.find('iframe', id='resourceobject') or soup.find('iframe', class_='resourceworkarea')
        if iframe and iframe.get('src'):
            return urljoin(base_url, iframe['src'])

        obj_tag: Optional[Tag] = soup.find('object', type='application/pdf')
        if obj_tag and obj_tag.get('data'):
            return urljoin(base_url, obj_tag['data'])

        main_region: Optional[Tag] = soup.find(id='region-main')
        iframe = main_region.find('iframe') if main_region else soup.find('iframe')
        if iframe and iframe.get('src'):
            return urljoin(base_url, iframe['src'])

        plugin_link = soup.select_one('a[href*="pluginfile.php"]')
        if plugin_link and plugin_link.get('href'):
            return urljoin(base_url, plugin_link['href'])

        return None

    def _handle_intermediate_page(self, response: APIResponse, suggested_name: str) -> Optional[APIResponse]:
        """
        Handles cases where the initial response is an HTML page that may embed
        the actual resource, rather than the resource itself.

        This is common for Moodle resources, which are often displayed within a
        viewer page.

        Args:
            response (APIResponse): The initial response from the server.
            suggested_name (str): The name of the resource being downloaded.

        Returns:
            Optional[APIResponse]: The final response containing the actual file
                                   content, or the original response if no
                                   embedding is detected, or None on error.
        """
        response_content_type: str = response.headers.get('content-type', '').lower()
        is_html: bool = 'text/html' in response_content_type
        is_intermediate_url: bool = 'mod/resource/view.php' in response.url or 'mod/page/view.php' in response.url

        if not (response.ok and is_html and is_intermediate_url):
            return response

        self.logger.info(f"Initial fetch returned HTML for {suggested_name}. Checking for embedded resource...")
        try:
            soup = BeautifulSoup(response.text(), 'html.parser')
            embedded_url: Optional[str] = self._find_embedded_resource_url(soup, response.url)

            if embedded_url:
                self.logger.info(f"Found embedded resource. Fetching actual content from: {embedded_url}")
                return self._fetch_initial_response(embedded_url)
            else:
                self.logger.warning(f"Could not find embedded resource in HTML page for {suggested_name}.")
                return None
        except Exception as e:
            self.logger.exception(f"Error parsing intermediate HTML page for {suggested_name}: {e}")
            return None

    def _check_response_status(self, response: Optional[APIResponse], suggested_name: str) -> bool:
        """
        Checks if the final APIResponse is valid (i.e., it exists and has a
        successful status code).

        Args:
            response (Optional[APIResponse]): The response to check.
            suggested_name (str): The name of the resource for logging purposes.

        Returns:
            bool: True if the response is valid, False otherwise.
        """
        if not response:
            self.logger.error(f"Download failed for '{suggested_name}'. No valid response received.")
            return False

        if not response.ok:
            status_text: str = http.client.responses.get(response.status, 'Unknown Status')
            self.logger.error(f"Download failed for '{suggested_name}'. Status: {response.status} {status_text}.")
            try:
                resp_ct = response.headers.get('content-type', '').lower()
                resp_cl = int(response.headers.get('content-length', '10000'))
                if ('text' in resp_ct or 'json' in resp_ct) and resp_cl < 5000:
                    self.logger.error(f"Error details (partial): {response.text()[:500]}")
            except Exception:
                pass
            return False
        return True

    def _save_response_content(self, response: APIResponse, target_filepath: str) -> Tuple[bool, int]:
        """
        Saves the content of the response to a file.

        Args:
            response (APIResponse): The response containing the file content.
            target_filepath (str): The full path where the file should be saved.

        Returns:
            Tuple[bool, int]: A tuple containing a boolean indicating success and
                              an integer for the file size.
        """
        try:
            os.makedirs(os.path.dirname(target_filepath), exist_ok=True)
            file_content: bytes = response.body()
            self.logger.info(f"Saving file to: {target_filepath} (overwriting if exists)")
            with open(target_filepath, 'wb') as f:
                f.write(file_content)
            filesize = len(file_content)

            if filesize > 0:
                return True, filesize
            elif response.headers.get('content-length') == '0':
                self.logger.info(f"Saved zero-byte file: {target_filepath}")
                return True, 0
            else:
                self.logger.warning(f"Downloaded file is empty: '{target_filepath}'.")
                return False, 0
        except IOError as e:
            self.logger.error(f"File system error saving to {target_filepath}: {str(e)}")
            return False, 0
        except Exception as e:
            self.logger.exception(f"Unexpected error saving file {target_filepath}: {str(e)}")
            return False, 0

    def _log_successful_download(self, original_url: str, filepath: str) -> None:
        """
        Appends a record of a successful download to the central log file.

        Args:
            original_url (str): The original URL of the downloaded item.
            filepath (str): The path to the saved file.
        """
        try:
            log_entry: str = f"{original_url}{self.LOG_SEPARATOR}{filepath}\n"
            with open(self.central_download_log_file, 'a', encoding='utf-8') as f_log:
                f_log.write(log_entry)
            self._logged_urls.add(original_url)
            self.logger.info(f"Added to central log: {original_url} -> {filepath}")
        except IOError as e:
            self.logger.error(f"Failed to write to central log file: {e}")

    def download_file(self, item_info: Dict[str, Any], target_filepath_base: str) -> DownloadResult:
        """
        Downloads a single file, handling all steps from URL adjustment to saving
        and logging.

        Args:
            item_info (Dict[str, Any]): A dictionary containing information about
                                        the item to download (URL, name, type).
            target_filepath_base (str): The base path for the downloaded file.

        Returns:
            DownloadResult: An object containing the result of the download.
        """
        initial_url: str = item_info['url']
        suggested_name: str = item_info['name']
        resource_type: str = item_info['type']
        
        if not self.api_request_context:
            return DownloadResult(False, "APIRequestContext not available")

        current_url_to_fetch = self._adjust_folder_url(initial_url, resource_type)
        self.logger.info(f"Attempting download: {suggested_name} from {current_url_to_fetch}")

        response = self._fetch_initial_response(current_url_to_fetch)
        if response: # type: ignore
            response = self._handle_intermediate_page(response, suggested_name)

        if not self._check_response_status(response, suggested_name):
            status: int | str = response.status if response else 'N/A'
            status_text = http.client.responses.get(status, '') if response else 'No Response'
            return DownloadResult(False, f"HTTP error {status} {status_text}")

        base_filename, extension = self._determine_filename_and_extension(
            suggested_name, response, response.url, resource_type
        )
        final_filename = f"{base_filename}.{extension}"
        final_filepath: str = os.path.join(os.path.dirname(target_filepath_base), final_filename)

        saved_ok, filesize = self._save_response_content(response, final_filepath)
        
        if saved_ok:
            self._log_successful_download(initial_url, final_filepath)
            msg = "Download successful" + (" (zero bytes)" if filesize == 0 else "")
            return DownloadResult(True, msg, final_filepath, filesize)
        else:
            msg = "File system error" if not os.path.exists(os.path.dirname(final_filepath)) else "Empty file downloaded"
            return DownloadResult(False, msg, final_filepath)

    def download_files(self,
                       to_download: Dict[str, Dict[str, Any]],
                       progress_callback: Optional[Callable[[str, float], None]] = None,
                       organize_by_section: bool = True) -> Tuple[List[str], List[str], List[str]]:
        """
        Downloads all files from a given dictionary of items to download.

        It organizes files by section if requested and provides progress updates
        through a callback.

        Args:
            to_download (Dict[str, Dict[str, Any]]): A dictionary of items to
                                                     download.
            progress_callback (Optional[Callable[[str, float], None]]): A function
                to call with progress updates.
            organize_by_section (bool): Whether to create subdirectories for each
                                        course section.

        Returns:
            Tuple[List[str], List[str], List[str]]: A tuple containing lists of
                successful, skipped, and failed downloads.
        """
        failed: List[str] = [] ; successful: List[str] = [] ; skipped: List[str] = []
        total_files = len(to_download)

        if total_files == 0:
            self.logger.info("No new items to download after checking central log.")
            return [], [], []

        processed_count = 0
        self.logger.info(f"Starting download process for {total_files} items.")

        section_folders: Dict[str, str] = {}
        base_download_folder: str = self.moodle_browser.download_folder

        if organize_by_section:
            unique_sections = set(info.get('section', 'Course Materials') for info in to_download.values())
            for section_name in unique_sections:
                section_folder_name: str = sanitize_folder_name(section_name)
                section_path: str = os.path.join(base_download_folder, section_folder_name)
                try:
                    os.makedirs(section_path, exist_ok=True)
                    section_folders[section_name] = section_path
                except OSError as e:
                    self.logger.error(f"Failed to create section folder '{section_path}': {e}. Using base folder.")
                    section_folders[section_name] = base_download_folder
        else:
            try:
                os.makedirs(base_download_folder, exist_ok=True)
            except OSError as e:
                self.logger.error(f"Failed to create base download folder '{base_download_folder}': {e}.")

        sorted_items: List[Tuple[str, Dict[str, Any]]] = sorted(to_download.items(),
                              key=lambda item: (item[1].get('section', ''), item[1].get('name', '')))

        for url, item_info in sorted_items:
            processed_count += 1
            doc_name = item_info.get('name', 'Unknown Name')
            section = item_info.get('section', 'Course Materials')
            resource_type = item_info.get('type', 'unknown')

            self.logger.info(
                f"Processing item {processed_count}/{total_files}: '{doc_name}' (Type: {resource_type}, Section: {section})")

            current_progress: float = (processed_count - 1) / total_files * 100 if total_files > 0 else 0
            if progress_callback:
                progress_callback(f"Processing: {doc_name}", current_progress)

            target_dir: str = section_folders.get(section, base_download_folder) if organize_by_section else base_download_folder
            sanitized_base_name: str = re.sub(r'[<>:"/\\|?*\x00-\x1F]', '_', doc_name).strip('._ ')
            initial_filepath_suggestion: str = os.path.join(target_dir, sanitized_base_name)

            if progress_callback:
                progress_callback(f"Starting download: {doc_name}", current_progress)

            result: DownloadResult = self.download_file(item_info, initial_filepath_suggestion)
            final_doc_name: str = os.path.basename(result.filepath) if result.filepath else f"{sanitized_base_name}_FAILED"
            progress_pct_done: float = processed_count / total_files * 100 if total_files > 0 else 100

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

            time.sleep(0.5)

        self.logger.info(f"Download process finished for {total_files} items.")
        self.logger.info(f"Summary: {len(successful)} files downloaded. {len(failed)} download attempts failed.")
        print(F"Download process completed.{successful}")

        if failed:
            self.logger.warning("--- Failed Downloads ---")
            for failure in failed:
                self.logger.warning(f"- {failure}")
            self.logger.warning("--- End of Failed Downloads ---")

        return successful, [], failed