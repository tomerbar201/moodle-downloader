
import threading
import os
from typing import Optional, Tuple, List, Dict, Callable
from PyQt5.QtCore import QObject, pyqtSignal, QSettings

from .gui_utils import is_valid_course_url
from .main import download_course
from .file_operations import create_course_folder

# --- Worker Signals ---
class WorkerSignals(QObject):
    status = pyqtSignal(str)
    progress = pyqtSignal(float)
    finished = pyqtSignal(bool, str)

class AutofillSignals(QObject):
    status = pyqtSignal(str)
    finished = pyqtSignal(bool, str, list)  # success, message, courses_list

# --- Auto-fill Worker ---
class AutofillWorker(threading.Thread):
    def __init__(self, username: str, password: str, year_range: str, download_folder: str, headless: bool):
        super().__init__(daemon=True)
        self.username = username
        self.password = password
        self.year_range = year_range
        self.download_folder = download_folder
        self.headless = headless
        self.signals = AutofillSignals()
    
    def run(self):
        try:
            from .moodle_browser import MoodleBrowser
            from .course_extractor import extract_courses
            
            # Create browser instance
            self.signals.status.emit("Setting up browser...")
            browser = MoodleBrowser(
                download_folder=self.download_folder, 
                year_range=self.year_range, 
                headless=self.headless
            )
            browser.setup_browser()
            
            # Login
            self.signals.status.emit("Logging in to Moodle...")
            if not browser.login(self.username, self.password):
                self.signals.finished.emit(False, "Failed to log in to Moodle. Please check your credentials.", [])
                browser.close()
                return
            
            # Navigate to dashboard
            self.signals.status.emit("Navigating to dashboard...")
            if not browser.navigate_to_dashboard():
                self.signals.finished.emit(False, "Failed to navigate to dashboard.", [])
                browser.close()
                return
            
            # Extract courses
            self.signals.status.emit("Extracting course list...")
            html_content = browser.get_page_content()
            courses = extract_courses(html_content)
            
            browser.close()
            
            if not courses:
                self.signals.finished.emit(True, "No courses found on your dashboard.", [])
                return
            
            self.signals.finished.emit(True, f"Successfully extracted {len(courses)} courses.", courses)
            
        except Exception as e:
            self.signals.finished.emit(False, f"An error occurred: {str(e)}", [])

# --- Base Download Worker ---
class DownloadWorkerBase(threading.Thread):
    def __init__(self, username: str, password: str, download_folder: str, settings: Optional[QSettings] = None):
        super().__init__(daemon=True)
        self.username = username
        self.password = password
        self.download_folder = download_folder
        self.settings = settings or QSettings("MoodleDown", "MoodleDownApp")
        self.signals = WorkerSignals()
        
        # Read settings
        self.headless = self.settings.value("headless", True, bool)
        self.organize_by_section = True  # Always True
        self.full_download = self.settings.value("full_download", False, bool)
        self.year_range = self.settings.value("year_range", "2025-26")
    
    def _download_single_course(self, course_url: str, course_name: str, progress_callback: Callable[[str, float], None], shared_browser=None) -> bool:
        if not is_valid_course_url(course_url):
            progress_callback(f"Invalid URL for {course_name}, skipping.", 0)
            return False
            
        course_folder = create_course_folder(course_url, self.download_folder, course_name)
        return download_course(
            course_url=course_url, 
            username=self.username, 
            password=self.password,
            download_folder=course_folder, 
            progress_callback=progress_callback,
            headless=self.headless,
            organize_by_section=self.organize_by_section,
            course_name=course_name,
            year_range=self.year_range,
            existing_browser=shared_browser,
            assume_logged_in=shared_browser is not None,
            full_download=self.full_download
        )

# --- Single Course Download Worker ---
class DownloadWorker(DownloadWorkerBase):
    def __init__(self, course_url: str, course_name: str, username: str, password: str, download_folder: str, settings: Optional[QSettings] = None):
        super().__init__(username, password, download_folder, settings)
        self.course_url = course_url
        self.course_name = course_name

    def run(self):
        try:
            def progress_callback(message: str, percent: float):
                self.signals.status.emit(f"{self.course_name}: {message}")
                self.signals.progress.emit(percent)
            
            success = self._download_single_course(self.course_url, self.course_name, progress_callback)
            msg = f"{'Successfully downloaded' if success else 'Failed to complete download for'} {self.course_name}"
            self.signals.finished.emit(success, msg)
        except Exception as e:
            self.signals.status.emit(f"Error: {str(e)}")
            self.signals.finished.emit(False, f"Error downloading {self.course_name}: {str(e)}")

# --- Batch Download Worker ---
class BatchDownloadWorker(DownloadWorkerBase):
    def __init__(self, courses: List[Tuple[str, str]], username: str, password: str, download_folder: str, settings: Optional[QSettings] = None):
        super().__init__(username, password, download_folder, settings)
        # courses is expected to be list of (name, url) tuples
        self.courses = courses

    def run(self):
        total_courses = len(self.courses)
        successful_courses = 0
        
        try:
            from .moodle_browser import MoodleBrowser
            browser = MoodleBrowser(download_folder=self.download_folder, year_range=self.year_range, headless=self.headless)
            browser.setup_browser()
            
            self.signals.status.emit("Logging in to Moodle...")
            if not browser.login(self.username, self.password):
                self.signals.finished.emit(False, "Failed to login to Moodle")
                return
                
            # Iterate (name, url) format from GUI
            for i, (course_name, course_url) in enumerate(self.courses):
                self.signals.status.emit(f"[{i+1}/{total_courses}] Starting: {course_name}")
                course_progress_base = (i / total_courses) * 100
                course_progress_weight = 100 / total_courses

                def progress_callback(message: str, percent: float):
                    self.signals.status.emit(f"[{i+1}/{total_courses}] {course_name}: {message}")
                    overall_progress = course_progress_base + (percent / 100) * course_progress_weight
                    self.signals.progress.emit(overall_progress)
                    
                if self._download_single_course(course_url, course_name, progress_callback, browser):
                    successful_courses += 1

            self.signals.progress.emit(100)
            if successful_courses == total_courses:
                self.signals.finished.emit(True, f"Successfully downloaded all {total_courses} courses")
            else:
                self.signals.finished.emit(successful_courses > 0, f"Downloaded {successful_courses}/{total_courses} courses")
        except Exception as e:
            self.signals.finished.emit(False, f"Error during batch download: {str(e)}")
        finally:
            try:
                browser.close()
            except:
                pass
