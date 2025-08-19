import os
import re
import logging
from typing import Optional, Tuple


# --- Logging Configuration ---
def setup_logging() -> Tuple[logging.Logger, str, str]:
    """Sets up logging for the application"""
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
    """Clean folder name by removing invalid characters"""
    sanitized: str = re.sub(r'[<>:"/\\|?*]', '_', folder_name).strip().strip('.')
    sanitized = re.sub(r'\s+', '_', sanitized)
    return sanitized if sanitized else "Section"


def sanitize_filename(filename: str) -> str:
    """Clean filename by removing invalid characters"""
    sanitized: str = re.sub(r'[<>:"/\\|?*\x00-\x1F]', '_', filename).strip('._ ')
    return sanitized if sanitized else "file"


def create_course_folder(course_id: str, base_dir: Optional[str] = None, course_name: Optional[str] = None) -> str:
    """Create and return folder path for storing course files"""
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