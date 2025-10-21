import os
import re
import getpass
import logging
from typing import Optional, Callable, List, Tuple

from .moodle_browser import MoodleBrowser
from .content_extractor import ContentExtractor
from .download_handler import DownloadHandler
from .file_operations import create_course_folder, setup_logging
from .chromium_setup import ensure_chromium_once


def download_course(course_url: str,
                    username: str,
                    password: str,
                    download_folder: str,
                    progress_callback: Optional[Callable[[str, float], None]] = None,
                    headless: bool = True,
                    organize_by_section: bool = True,
                    course_name: Optional[str] = None,
                    year_range: str = "2024-25",
                    existing_browser: Optional[MoodleBrowser] = None,
                    assume_logged_in: bool = False) -> bool:
    """Main function to download course content from Moodle.

    When ``existing_browser`` is provided, the function reuses the supplied
    Playwright session instead of launching a new browser. Set
    ``assume_logged_in`` to ``True`` if the shared browser already completed
    authentication.
    """

    browser = existing_browser
    created_browser = False
    overall_success = False
    logger, log_file_path, central_download_log_file = setup_logging()

    def update_progress(message: str, percentage: float):
        """Forward progress updates to the callback if provided"""
        if progress_callback:
            progress_callback(message, max(0.0, min(100.0, percentage)))

    if browser is None:
        chromium_ok, chromium_message = ensure_chromium_once()
        if not chromium_ok:
            update_progress("Chromium setup failed", 100)
            logger.error(f"Chromium unavailable: {chromium_message}")
            return False
    else:
        logger.info("Reusing existing MoodleBrowser instance for course download.")

    try:
        # Step 1: Initialize
        update_progress("Initializing...", 0)
        course_folder = create_course_folder(course_url, os.path.dirname(download_folder),
                                             os.path.basename(download_folder))
        logger.info(f"Target download folder for this course: {course_folder}")

        # Step 2: Verify central log is accessible
        try:
            with open(central_download_log_file, 'a', encoding='utf-8'):
                pass
            logger.info(f"Central download log file is accessible: {central_download_log_file}")
        except IOError as e:
            logger.error(f"Could not create/access central download log: {e}. Proceeding without URL filtering.")

        # Step 3: Set up browser
        if browser is None:
            browser = MoodleBrowser(course_folder, headless, year_range)
            browser.setup_browser()
            created_browser = True
        else:
            browser.download_folder = course_folder
            browser.year_range = year_range
            browser.BASE_URL = f"https://moodle.huji.ac.il/{year_range}"

        # Step 4: Perform login
        if assume_logged_in:
            update_progress("Reusing existing session...", 5)
        else:
            update_progress("Logging in...", 5)
            if not browser.login(username, password):
                update_progress("Login failed", 100)
                logger.error("Moodle login failed.")
                return False

        # Step 5: Navigate to the course
        update_progress("Navigating to course...", 15)
        if not browser.navigate_to_course(course_url):
            update_progress("Course navigation failed", 100)
            logger.error(f"Failed to navigate to course {course_url}.")
            return False

        # Step 6: Setup content extractor and download handler
        update_progress("Analyzing course content...", 25)
        downloader = DownloadHandler(browser, central_download_log_file)
        content_extractor = ContentExtractor(browser.BASE_URL)

        # Step 7: Extract download links from page content
        html_content = browser.get_page_content()
        if not html_content:
            update_progress("Failed to get page content", 100)
            logger.error("Could not retrieve page content.")
            return False

        # Get links and filter against previously downloaded URLs
        links_to_download = content_extractor.get_download_links(
            html_content,
            browser.page.url if browser.page else browser.BASE_URL,
            downloader.get_logged_urls()
        )

        if not links_to_download:
            update_progress("No new downloadable content found.", 100)
            logger.info(f"No new items to download for course {course_url}.")
            return True  # Success if nothing new needed

        # Step 8: Download files
        update_progress(f"Found {len(links_to_download)} new items. Starting download...", 30)
        successful, _, failed = downloader.download_files(
            links_to_download,
            lambda msg, pct: update_progress(msg, 30 + pct * 0.7),  # Scale progress 30-100%
            organize_by_section
        )

        # Step 9: Finalize and report results
        overall_success = not failed  # Success if no failures
        msg = "Completed."
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
        if created_browser and browser:
            browser.close()

    return overall_success


# Command Line Interface
if __name__ == "__main__":
    logger, log_file_path, central_download_log_file = setup_logging()

    print("MoodleDown Playwright Edition - Course Downloader")
    print("-" * 49)

    try:
        # Get user inputs
        course_url = input("Enter Moodle Course URL: ").strip()
        if not course_url:
            print("Error: Course URL is required.")
            exit(1)

        base_download_dir = input(
            "Enter base download directory (leave blank for current dir): ").strip() or os.getcwd()
        course_name_input = input("Enter Course Name (optional, for folder name): ").strip()

        # Determine download path
        folder_name = course_name_input if course_name_input else "moodle_course"
        folder_name = folder_name.replace(r'[<>:"/\\|?*]', '_').strip().strip('. ')
        folder_name = re.sub(r'[\s_]+', '_', folder_name)
        folder_name = folder_name if folder_name else "moodle_course"
        intended_download_folder_path = os.path.join(base_download_dir, folder_name)

        # Get authentication details
        username = input("Enter Moodle Username: ").strip()
        password = input("Enter Moodle Password: ")

        # Configuration options
        headless_mode = input("Run in headless mode? (Y/n): ").strip().lower() != 'n'
        organize_sections = input("Organize downloads by section? (Y/n): ").strip().lower() != 'n'

        # Display summary before starting
        print(f"\nStarting download process...")
        print(f"Course URL: {course_url}")
        print(f"Username: {username}")
        print(f"Course Download Location: {intended_download_folder_path}")
        print(f"Headless Mode: {headless_mode}")
        print(f"Organize by Section: {organize_sections}")
        print(f"App Log File: {log_file_path}")
        print(f"Central History Log: {central_download_log_file}")
        print("-" * 20)
        print()  # Start progress on its own line

        # Progress callback for console output
        last_msg = [""]  # Use list for mutable reference


        def console_progress(message: str, percentage: float):
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
            course_name=course_name_input
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