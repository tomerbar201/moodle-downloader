import os
import re
import getpass
import logging
from typing import Optional, Callable, List, Tuple, Any

from moodle_browser import MoodleBrowser
from content_extractor import ContentExtractor
from download_handler import DownloadHandler
from file_operations import create_course_folder, setup_logging


def _extract_course_id_from_url(url: str) -> Optional[str]:
    """Helper to extract the Moodle course ID from a URL using regex."""
    if not url:
        return None
    match = re.search(r'[?&]id=(\d+)', url)
    if match:
        return match.group(1)
    return None


def download_course(course_url: str,
                    username: str,
                    password: str,
                    download_folder: str,
                    progress_callback: Optional[Callable[[str, float], None]] = None,
                    headless: bool = True,
                    year_range: str = "2024-25",
                    organize_by_section: bool = True,
                    course_name: Optional[str] = None,
                    existing_browser: Optional[MoodleBrowser] = None,
                    full_download: bool = False) -> bool:
    """Main function to download course content from Moodle"""

    browser: Optional[MoodleBrowser] = existing_browser
    should_close_browser: bool = existing_browser is None
    overall_success: bool = False
    logger: logging.Logger; log_file_path: str; central_download_log_file: str
    logger, log_file_path, central_download_log_file = setup_logging()

    def update_progress(message: str, percentage: float) -> None:
        """Forward progress updates to the callback if provided"""
        if progress_callback:
            progress_callback(message, max(0.0, min(100.0, percentage)))

    try:
        # Step 1: Initialize and Validate URL
        update_progress("Initializing...", 0)
        course_id = _extract_course_id_from_url(course_url)
        if not course_id:
            logger.error(f"Invalid course URL provided. Could not find a course ID in: {course_url}")
            update_progress("Invalid course URL", 100)
            return False

        course_folder: str = create_course_folder(course_id, os.path.dirname(download_folder),
                                                  os.path.basename(download_folder))
        logger.info(f"Target download folder for this course: {course_folder}")

        # Step 2: Verify central log is accessible
        try:
            with open(central_download_log_file, 'a', encoding='utf-8'):
                pass
            logger.info(f"Central download log file is accessible: {central_download_log_file}")
        except IOError as e:
            logger.error(f"Could not create/access central download log: {e}. Proceeding without URL filtering.")

        # Step 3: Set up browser (only if not provided)
        if browser is None:
            browser = MoodleBrowser(download_folder=course_folder, year_range=year_range, headless=headless)
            browser.setup_browser()

            # Step 4: Perform login (only if new browser)
            update_progress("Logging in...", 5)
            if not browser.login(username, password):
                update_progress("Login failed", 100)
                logger.error("Moodle login failed.")
                return False
        else:
            # Update the download folder for the existing browser
            browser.download_folder = course_folder
            logger.info("Using existing browser session")

        # Step 5: Navigate to the course
        update_progress("Navigating to course...", 15)
        if not browser.navigate_to_course(course_url):
            update_progress("Course navigation failed", 100)
            logger.error(f"Failed to navigate to course {course_id} using URL: {course_url}.")
            return False

        # Step 6: Setup content extractor and download handler
        update_progress("Analyzing course content...", 25)
        downloader: DownloadHandler = DownloadHandler(browser, central_download_log_file)
        content_extractor: ContentExtractor = ContentExtractor(browser.BASE_URL)

        # Step 7: Extract download links from page content
        html_content: str = browser.get_page_content()
        if not html_content:
            update_progress("Failed to get page content", 100)
            logger.error("Could not retrieve page content.")
            return False  # type: ignore

        # Get links and filter against previously downloaded URLs *unless* full_download is True
        urls_to_ignore = set() if full_download else downloader.get_logged_urls()

        links_to_download = content_extractor.get_download_links(
            html_content,
            browser.page.url if browser.page else browser.BASE_URL,
            urls_to_ignore
        )

        if not links_to_download:
            update_progress("No new downloadable content found.", 100)
            logger.info(f"No new items to download for course {course_id}.")
            return True  # Success if nothing new needed

        # Step 8: Download files
        update_progress(f"Found {len(links_to_download)} new items. Starting download...", 30)
        successful: List[str]; failed: List[str]
        successful, _, failed = downloader.download_files(  # type: ignore
            links_to_download,
            lambda msg, pct: update_progress(msg, 30 + pct * 0.7),  # Scale progress 30-100%
            organize_by_section
        )

        # Step 9: Finalize and report results
        overall_success = not failed  # Success if no failures
        msg: str = "Completed."
        if successful:
            msg += f" {len(successful)} downloaded/updated."
        if failed:
            msg += f" {len(failed)} failed."
        if not successful and not failed and not links_to_download:
            msg = "Completed. No new items required downloading."
        update_progress(msg, 100)
        logger.info(msg)

    except Exception as e:
        logger.exception(f"An error occurred: {e}")
        update_progress(f"Error: {e}", 100)
        overall_success = False
    except KeyboardInterrupt:
        logger.warning("Download process interrupted by user.")
        update_progress("Interrupted by user", 100)
        overall_success = False
    finally:
        # Only close the browser if we created it
        if browser and should_close_browser:
            browser.close()

    return overall_success


# Command Line Interface
if __name__ == "__main__":
    logger: logging.Logger; log_file_path: str; central_download_log_file: str
    logger, log_file_path, central_download_log_file = setup_logging()  # type: ignore

    print("MoodleDown Playwright Edition - Course Downloader")
    print("-" * 49)

    try:
        # Get user inputs
        course_url = input("Enter Moodle Course URL: ").strip()
        course_id = _extract_course_id_from_url(course_url)
        if not course_id:
            print("Error: Invalid Moodle URL. It must contain a course ID like '?id=12345'.")
            exit(1)

        base_download_dir: str = input(
            "Enter base download directory (leave blank for current dir): ").strip() or os.getcwd()
        course_name_input: str = input("Enter Course Name (optional, for folder name): ").strip()

        # Determine download path
        folder_name: str = course_name_input if course_name_input else str(course_id)
        folder_name = folder_name.replace(r'[<>:"/\\|?*]', '_').strip().strip('. ')
        folder_name = re.sub(r'[\s_]+', '_', folder_name)
        folder_name = folder_name if folder_name else f"moodle_course_{course_id}"
        intended_download_folder_path: str = os.path.join(base_download_dir, folder_name)

        # Get authentication details
        username: str = input("Enter Moodle Username: ").strip()
        password: str = getpass.getpass("Enter Moodle Password: ")

        # Configuration options
        headless_mode = input("Run in headless mode? (Y/n): ").strip().lower() != 'n'
        organize_sections = input("Organize downloads by section? (Y/n): ").strip().lower() != 'n'
        full_download_mode = input("Perform full download (ignore history)? (y/N): ").strip().lower() == 'y'

        # Display summary before starting
        print(f"\nStarting download process...")
        print(f"Course URL: {course_url}")
        print(f"Course ID: {course_id}")
        print(f"Username: {username}")
        print(f"Course Download Location: {intended_download_folder_path}")
        print(f"Headless Mode: {headless_mode}")
        print(f"Organize by Section: {organize_sections}")
        print(f"Full Download Mode: {full_download_mode}")
        print(f"App Log File: {log_file_path}")
        print(f"Central History Log: {central_download_log_file}")
        print("-" * 20)
        print()  # Start progress on its own line

        # Progress callback for console output
        last_msg: List[str] = [""]  # Use list for mutable reference

        def console_progress(message: str, percentage: float) -> None:
            print(f"\rProgress: {percentage:.1f}% - {message.ljust(80)}", end="")
            last_msg[0] = message

        # Call the main download function
        success = download_course(
            course_url=course_url,
            username=username,
            password=password,
            download_folder=intended_download_folder_path,
            progress_callback=console_progress,
            headless=headless_mode,
            organize_by_section=organize_sections,
            course_name=course_name_input,
            full_download=full_download_mode
        )

        print()  # Newline after progress bar

        # Display final result
        if success:
            print(f"\nDownload process completed successfully for this course.")
            print(f"Files saved in/updated: {intended_download_folder_path}")
            print(f"Download history is tracked centrally in: {central_download_log_file}")
        else:
            print("\nDownload process failed or encountered significant errors for this course.")

        print(f"Please check the main log file '{log_file_path}' for details.")

    except KeyboardInterrupt:
        print("\n\nProcess interrupted by user.")
    except Exception as e:
        print(f"\n\nAn unexpected error occurred: {e}")
        logging.exception("Unhandled exception in main execution block.")

    # Display options to the user
    print("\n--- How to use this program ---")
    print("1. Find the main page URL for each course you want to download (it's recommended to add all at once).")
    print("2. Enter your Moodle email and password when prompted.")
    print("3. Select the courses you want to download from the list.")

