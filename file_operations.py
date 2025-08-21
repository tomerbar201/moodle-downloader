"""
This module provides utility functions for file and folder operations, which are
essential for organizing downloaded content and managing application data. It
includes functions for setting up logging, sanitizing names for files and
folders to be compatible with the filesystem, and creating directories for
storing course materials.

These helpers ensure that the application handles file-related tasks in a
consistent and safe manner.
"""

import os
import re
import logging
from typing import Optional, Tuple


# --- Logging Configuration ---
def setup_logging() -> Tuple[logging.Logger, str, str]:
    """
    Sets up the logging configuration for the application.

    This function configures a logger that writes to both a file and the console.
    It creates a dedicated log directory in the user's local application data
    folder to store log files and a history of downloaded files.

    Returns:
        Tuple[logging.Logger, str, str]: A tuple containing the configured
                                         logger instance, the path to the main
                                         log file, and the path to the central
                                         download history log.
    """
    APP_NAME: str = "MoodleDown"
    COMPANY_NAME: str = "MoodleDown"
    log_base_dir = os.getenv('LOCALAPPDATA')
    log_dir: str = os.path.join(log_base_dir, COMPANY_NAME, APP_NAME, 'Logs') if log_base_dir else os.path.join(
        os.path.expanduser("~"), f".{APP_NAME.lower()}", 'logs')

    try:
        os.makedirs(log_dir, exist_ok=True)
        log_file_path: str = os.path.join(log_dir, "moodledown_playwright.log")
        CENTRAL_DOWNLOAD_LOG_FILE: str = os.path.join(log_dir, "download_history.log")
    except OSError as e:
        print(f"WARNING: Could not create log directory '{log_dir}': {e}. Logging to current directory instead.")
        log_file_path = "moodledown_playwright.log"
        CENTRAL_DOWNLOAD_LOG_FILE = "download_history.log"

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.FileHandler(log_file_path, encoding='utf-8'), logging.StreamHandler()]
    )
    logger: logging.Logger = logging.getLogger("MoodleDownPlaywright")
    logger.info(f"Logging initialized. Main log: {log_file_path}")
    logger.info(f"Using central download history log: {CENTRAL_DOWNLOAD_LOG_FILE}")

    return logger, log_file_path, CENTRAL_DOWNLOAD_LOG_FILE


def sanitize_folder_name(folder_name: str) -> str:
    """
    Cleans a folder name by removing characters that are invalid in directory
    names on most operating systems.

    Args:
        folder_name (str): The original name of the folder.

    Returns:
        str: The sanitized folder name, safe to use for creating a directory.
    """
    sanitized: str = re.sub(r'[<>:"/\\|?*]', '_', folder_name).strip().strip('.')
    sanitized = re.sub(r'\s+', '_', sanitized)
    return sanitized if sanitized else "Section"


def sanitize_filename(filename: str) -> str:
    """
    Cleans a filename by removing characters that are invalid in filenames on
    most operating systems.

    Args:
        filename (str): The original name of the file.

    Returns:
        str: The sanitized filename.
    """
    sanitized: str = re.sub(r'[<>:"/\\|?*\x00-\x1F]', '_', filename).strip('._ ')
    return sanitized if sanitized else "file"


def create_course_folder(course_id: str, base_dir: Optional[str] = None, course_name: Optional[str] = None) -> str:
    """
    Creates a directory for storing the files of a specific course.

    The folder will be named after the course name if provided; otherwise, it
    will be named after the course ID. The name is sanitized to ensure it is a
    valid directory name.

    Args:
        course_id (str): The unique identifier for the course.
        base_dir (Optional[str]): The base directory where the course folder
                                  will be created. Defaults to the current
                                  working directory.
        course_name (Optional[str]): The name of the course, used for the
                                     folder name.

    Returns:
        str: The absolute path to the created course folder.

    Raises:
        OSError: If the directory could not be created due to a system error.
    """
    base_dir = base_dir or os.getcwd()
    folder_name: str = course_name if course_name else str(course_id)

    # Sanitize folder name
    folder_name = sanitize_folder_name(folder_name)
    folder_name = folder_name if folder_name else f"moodle_course_{course_id}"

    folder_path: str = os.path.join(base_dir, folder_name)
    logger: logging.Logger = logging.getLogger("MoodleDownPlaywright")

    try:
        os.makedirs(folder_path, exist_ok=True)
        logger.info(f"Ensured course download folder exists: '{folder_path}'")
    except OSError as e:
        logger.error(f"Fatal: Could not create download folder '{folder_path}': {e}")
        raise

    return folder_path