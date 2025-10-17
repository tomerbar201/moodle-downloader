"""
GUI interface for Moodle Downloader using PyQt5.
Handles user authentication, course selection, and download management.
"""

import sys
import threading
import os
import re
import time  # Added for unzip timing
import zipfile  # Added for selective unzip
from typing import Optional, Tuple, List, Dict, Set, Any, Callable
# Playwright imports are handled inside chromium_setup when needed
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QProgressBar, QListWidget, QListWidgetItem, QAbstractItemView,
    QMessageBox, QMainWindow, QStatusBar, QDialog, QDialogButtonBox, QFormLayout, QCheckBox,
    QSplitter, QComboBox)
from PyQt5.QtGui import QFont, QIcon, QMouseEvent
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QSize, QSettings, QPoint, QEvent

from .chromium_setup import chromium_ready, ensure_chromium

# --- Dark Theme Import ---
try:
    import qdarkstyle
    QDARKSTYLE_AVAILABLE = True
except ImportError:
    qdarkstyle = None
    QDARKSTYLE_AVAILABLE = False

# --- Core Module Imports ---
try:
    from .main import download_course
    from .file_operations import create_course_folder, setup_logging
except ImportError as e:
    print("ERROR: Could not import core modules.")
    try:
        app_temp = QApplication.instance() or QApplication(sys.argv)
        QMessageBox.critical(None, "Fatal Error", 
            "Could not import core modules for MoodleDown.\n"
            "Please ensure all required modules are in the correct location:\n"
            "main.py, moodle_browser.py, content_extractor.py, download_handler.py, file_operations.py, data_structures.py")
    except Exception:
        pass
    sys.exit(1)

# --- Optional Imports ---
try:
    import keyring
    KEYRING_AVAILABLE = True
except ImportError:
    keyring = None
    KEYRING_AVAILABLE = False

_unzipper_mod = None
try:
    from . import unzipper as _unzipper_mod
except ImportError:
    try:
        import unzipper as _unzipper_mod
    except ImportError:
        try:
            from src import unzipper as _unzipper_mod
        except ImportError:
            _unzipper_mod = None

if _unzipper_mod is not None:
    unzipper = _unzipper_mod
    UNZIPPER_AVAILABLE = True
else:
    unzipper = None
    UNZIPPER_AVAILABLE = False

def ensure_chromium_available(parent: QWidget) -> bool:
    """
    Ensure Playwright Chromium browser is installed, prompting the user if needed.
    """
    if chromium_ready():
        return True

    reply = QMessageBox.question(parent, "Chromium Required",
        "The Playwright Chromium browser is not installed or is corrupted.\n"
        "It must be downloaded to continue (~120MB, one-time).\n\n"
        "Do you want to install it now?",
        QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)

    if reply == QMessageBox.No:
        return False

    QApplication.setOverrideCursor(Qt.WaitCursor)
    QApplication.processEvents()
    success, message = ensure_chromium()
    QApplication.restoreOverrideCursor()

    if not success:
        QMessageBox.warning(parent, "Installation Failed", message)
        return False

    QMessageBox.information(parent, "Installation Complete", "Chromium is now installed and ready.")
    return True

# --- Helper function to validate course URL ---
def is_valid_course_url(url: str) -> bool:
    """Check if URL is a valid Moodle course URL."""
    if not url:
        return False
    # Check if it's a course URL - look for course/view.php pattern
    return bool(re.search(r'/course/view\.php', url))

# --- Default Courses ---
COURSES: Dict[str, str] = {
    "Introduction to Computer Science": "https://moodle.huji.ac.il/2024-25/course/view.php?id=12345",
    "Data Structures": "https://moodle.huji.ac.il/2024-25/course/view.php?id=23456"
}

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
        self.year_range = self.settings.value("year_range", "2024-25")
    
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
            year_range=self.year_range
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
                
            for i, (course_url, course_name) in enumerate(self.courses):
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

# --- Add Course Dialog ---
class AddCourseDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Course")
        layout = QFormLayout(self)
        
        self.course_name = QLineEdit()
        self.course_url_input = QLineEdit()
        self.course_url_input.setPlaceholderText("e.g., https://moodle.../course/view.php?id=12345")
        
        layout.addRow("Course Name:", self.course_name)
        layout.addRow("Course URL:", self.course_url_input)
        
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addRow(button_box)

    def accept(self):
        name = self.course_name.text().strip()
        url = self.course_url_input.text().strip()
        if not name or not url:
            QMessageBox.warning(self, "Input Error", "Both Course Name and Course URL are required.")
            return
        if not is_valid_course_url(url):
            QMessageBox.warning(self, "Input Error", "The URL must be a valid Moodle course URL (should contain '/course/view.php').")
            return
        super().accept()

    def get_course_data(self):
        return self.course_name.text().strip(), self.course_url_input.text().strip()

# --- Main Application Window ---
class MoodleDownloaderApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MoodleDown - Playwright Edition")
        self.resize(600, 500) 
        self.settings = QSettings("MoodleDown", "MoodleDownApp")
        self.settings.setValue("organize_by_section", True)  # Force always True
        
        self.selected_courses = set()
        self.all_courses = {}
        self.current_worker = None
        self.autofill_worker = None
        self.download_start_time: float = 0.0  # Track download start for selective unzip
        
        self.browser_ready = False
        self.setup_ui()
        self.load_data()
        # Attempt ensuring browser availability *after* widgets exist so dialogs have a parent
        self.browser_ready = ensure_chromium_available(self)
        if not self.browser_ready:
            self.status_label.setText("Browser missing. Click 'Start Download' after installing.")
        self.update_selection()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Create horizontal splitter
        splitter = QSplitter(Qt.Horizontal)
        
        # Left panel for controls
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # Credentials
        left_layout.addWidget(QLabel("Credentials:"))
        self.username_input = QLineEdit(self.settings.value("username", ""))
        self.username_input.setPlaceholderText("Username / Email")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.Password)
        left_layout.addWidget(self.username_input)
        left_layout.addWidget(self.password_input)
        
        # Save password checkbox
        self.save_password_cb = QCheckBox("Save password")
        self.save_password_cb.setChecked(self.settings.value("save_password", False, bool))
        self.save_password_cb.setEnabled(KEYRING_AVAILABLE)
        left_layout.addWidget(self.save_password_cb)
        
        # Download location
        left_layout.addWidget(QLabel("Download Location:"))
        location_layout = QHBoxLayout()
        self.location_input = QLineEdit(self.settings.value("default_location", os.getcwd()))
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.browse_folder)
        location_layout.addWidget(self.location_input)
        location_layout.addWidget(browse_btn)
        left_layout.addLayout(location_layout)
        
        # Download button
        self.download_btn = QPushButton("Start Download")
        self.download_btn.clicked.connect(self.start_download)
        self.download_btn.setEnabled(False)
        left_layout.addWidget(self.download_btn)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        left_layout.addWidget(self.progress_bar)
        
        # Status label
        self.status_label = QLabel("Ready")
        self.status_label.setWordWrap(True)
        left_layout.addWidget(self.status_label)
        
        # Removed explicit unzip button, replaced by option below
        # self.unzip_button = QPushButton("Unzip Folder Content\n (recomended after downloads)")
        # self.unzip_button.clicked.connect(self.trigger_unzip)
        # self.unzip_button.setEnabled(UNZIPPER_AVAILABLE)
        # left_layout.addWidget(self.unzip_button)
        
        # Options
        left_layout.addWidget(QLabel("Options:"))
        self.headless_cb = QCheckBox("Headless mode")
        self.headless_cb.setChecked(self.settings.value("headless", True, bool))
        self.organize_cb = QCheckBox("Organize by section (always on)")
        self.organize_cb.setChecked(True)
        self.organize_cb.setEnabled(False)
        self.full_download_cb = QCheckBox("Full download")
        self.full_download_cb.setChecked(self.settings.value("full_download", False, bool))
        self.unzip_after_cb = QCheckBox("Unzip newly downloaded .zip files after completion")  # New option
        self.unzip_after_cb.setChecked(self.settings.value("unzip_after", False, bool))
        self.unzip_after_cb.setEnabled(UNZIPPER_AVAILABLE)
        left_layout.addWidget(self.headless_cb)
        left_layout.addWidget(self.organize_cb)
        left_layout.addWidget(self.full_download_cb)
        left_layout.addWidget(self.unzip_after_cb)
        
        left_layout.addStretch()
        
        # Right panel for course list
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # Academic Year above search
        right_layout.addWidget(QLabel("Academic Year:"))
        self.year_combo = QComboBox()
        self.year_combo.addItems(["2023-24", "2024-25", "2025-26", "2026-27"])
        self.year_combo.setCurrentText(self.settings.value("year_range", "2024-25"))
        right_layout.addWidget(self.year_combo)
        
        # Search above course list
        right_layout.addWidget(QLabel("Available Courses:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search name or ID...")
        self.search_input.textChanged.connect(self.filter_courses)
        right_layout.addWidget(self.search_input)
        
        # Course list (made more compact)
        self.course_list = QListWidget()
        self.course_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self.course_list.itemSelectionChanged.connect(self.update_selection)
        self.course_list.setMaximumHeight(300)  # Compact height
        right_layout.addWidget(self.course_list)
        
        # Auto-fill button (full width, above other buttons)
        self.autofill_btn = QPushButton("Auto-fill Courses from Moodle")
        self.autofill_btn.clicked.connect(self.autofill_courses)
        self.autofill_btn.setToolTip("Automatically extract all courses from Moodle dashboard")
        right_layout.addWidget(self.autofill_btn)
        
        # Course management buttons below list (add/remove in a row)
        course_buttons = QHBoxLayout()
        add_btn = QPushButton("Add Course")
        add_btn.clicked.connect(self.add_course)
        self.remove_btn = QPushButton("Remove Selected")
        self.remove_btn.clicked.connect(self.remove_courses)
        self.remove_btn.setEnabled(False)
        course_buttons.addWidget(add_btn)
        course_buttons.addWidget(self.remove_btn)
        right_layout.addLayout(course_buttons)
        
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([400, 400])
        
        layout.addWidget(splitter)
        
        # Status bar
        self.statusBar().showMessage("Ready")

    def load_data(self):
        # Load credentials
        username = self.username_input.text()
        if self.save_password_cb.isChecked() and KEYRING_AVAILABLE and username:
            try:
                password = keyring.get_password("MoodleDownApp", username)
                if password:
                    self.password_input.setText(password)
            except:
                pass
        
        # Load courses
        try:
            saved_data = self.settings.value("courses", [])
            self.all_courses = {str(item[0]): str(item[1]) for item in saved_data if isinstance(item, (list, tuple)) and len(item) == 2}
            if not self.all_courses:
                self.all_courses = COURSES.copy()
            self.refresh_course_list()
        except:
            self.all_courses = COURSES.copy()
            self.refresh_course_list()
        
        # Remove first-time user suggestion
        # if not saved_data or len(saved_data) == 0:
        #     from PyQt5.QtCore import QTimer
        #     QTimer.singleShot(500, self.suggest_autofill)

    def refresh_course_list(self):
        self.course_list.clear()
        for course_name in sorted(self.all_courses.keys()):
            course_url = self.all_courses[course_name]
            item = QListWidgetItem(f"{course_name}")
            item.setData(Qt.UserRole, course_url)
            item.setToolTip(f"Name: {course_name}\nURL: {course_url}")
            self.course_list.addItem(item)

    def filter_courses(self):
        search_term = self.search_input.text().lower()
        for i in range(self.course_list.count()):
            item = self.course_list.item(i)
            item.setHidden(search_term not in item.text().lower())

    def update_selection(self):
        """Refresh selection-dependent UI state."""
        self.selected_courses = {item.text().split(" [ID: ")[0] for item in self.course_list.selectedItems()}
        count = len(self.selected_courses)
        is_downloading = self.current_worker and self.current_worker.is_alive()
        ready = getattr(self, 'browser_ready', False)
        
        # Simplified: Enable download button only if courses are selected
        self.download_btn.setEnabled(count > 0 and not is_downloading and ready)
        self.remove_btn.setEnabled(count > 0 and not is_downloading)
        
        if count > 0:
            self.statusBar().showMessage(f"Selected {count} course{'s' if count != 1 else ''}")
        else:
            self.statusBar().showMessage("Ready")

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Download Location", self.location_input.text())
        if folder:
            self.location_input.setText(folder)

    def add_course(self):
        dialog = AddCourseDialog(self)
        if dialog.exec_():
            name, url = dialog.get_course_data()
            if name in self.all_courses:
                QMessageBox.warning(self, "Duplicate", f"Course '{name}' already exists.")
                return
            if url in self.all_courses.values():
                QMessageBox.warning(self, "Duplicate URL", "That URL is already used by another course.")
                return
            
            self.all_courses[name] = url
            self.refresh_course_list()
            self.save_courses()

    def remove_courses(self):
        items = self.course_list.selectedItems()
        if not items:
            return
        
        if QMessageBox.question(self, "Confirm", f"Remove {len(items)} selected course(s)?") == QMessageBox.Yes:
            for item in items:
                name = item.text().split(" [ID: ")[0]
                if name in self.all_courses:
                    del self.all_courses[name]
                self.course_list.takeItem(self.course_list.row(item))
            self.save_courses()
            self.update_selection()

    def save_courses(self):
        self.settings.setValue("courses", list(self.all_courses.items()))

    def start_download(self):
        if self.current_worker and self.current_worker.is_alive():
            QMessageBox.warning(self, "Busy", "Download already running.")
            return
        if not getattr(self, 'browser_ready', False):
            if ensure_chromium_available(self):
                self.browser_ready = True
                self.update_selection()
            else:
                QMessageBox.warning(self, "Browser Missing", "Chromium must be installed before downloading.")
                return
        
        username = self.username_input.text().strip()
        password = self.password_input.text()
        download_folder = self.location_input.text().strip()
        
        if not all([username, password, download_folder]):
            QMessageBox.warning(self, "Missing Info", "Please fill in username, password, and download location.")
            return
        
        # Remove auto-fill before download logic
        if len(self.selected_courses) == 0:
            QMessageBox.warning(self, "No Courses Selected", "Please select at least one course to download.")
            return
        
        if not os.path.isdir(download_folder):
            if QMessageBox.question(self, "Create Folder", f"Create folder '{download_folder}'?") == QMessageBox.Yes:
                try:
                    os.makedirs(download_folder, exist_ok=True)
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Could not create folder: {e}")
                    return
            else:
                return
        
        # Save settings
        self.settings.setValue("username", username)
        self.settings.setValue("default_location", download_folder)
        self.settings.setValue("year_range", self.year_combo.currentText())
        self.settings.setValue("headless", self.headless_cb.isChecked())
        self.settings.setValue("full_download", self.full_download_cb.isChecked())
        self.settings.setValue("save_password", self.save_password_cb.isChecked())
        self.settings.setValue("unzip_after", self.unzip_after_cb.isChecked())
        
        # Handle password saving
        if KEYRING_AVAILABLE:
            try:
                if self.save_password_cb.isChecked():
                    keyring.set_password("MoodleDownApp", username, password)
                else:
                    keyring.delete_password("MoodleDownApp", username)
            except:
                pass
        
        # Prepare course data
        course_data = [(self.all_courses[name], name) for name in self.selected_courses if name in self.all_courses]
        if not course_data:
            return
        
        # Mark start time for selective unzip logic
        self.download_start_time = time.time()
        
        # Start worker
        if len(course_data) == 1:
            self.current_worker = DownloadWorker(course_data[0][0], course_data[0][1], username, password, download_folder, self.settings)
        else:
            self.current_worker = BatchDownloadWorker(course_data, username, password, download_folder, self.settings)
        
        self.current_worker.signals.status.connect(self.update_status)
        self.current_worker.signals.progress.connect(self.update_progress)
        self.current_worker.signals.finished.connect(self.download_finished)
        
        self.set_downloading_state(True)
        self.current_worker.start()

    def set_downloading_state(self, downloading):
        self.download_btn.setEnabled(not downloading and bool(self.selected_courses))
        self.remove_btn.setEnabled(not downloading and bool(self.selected_courses))
        self.course_list.setEnabled(not downloading)

    def update_status(self, message):
        self.statusBar().showMessage(message)
        self.status_label.setText(message[:100] + "..." if len(message) > 100 else message)

    def update_progress(self, value):
        self.progress_bar.setValue(int(value))

    def download_finished(self, success, message):
        self.set_downloading_state(False)
        self.progress_bar.setValue(100 if success else 0)
        self.status_label.setText("Complete" if success else "Failed")
        
        if success:
            QMessageBox.information(self, "Complete", message)
        else:
            # Differentiate login failures
            if "login" in message.lower() or "authentication" in message.lower():
                QMessageBox.warning(self, "Authentication Failed", 
                    f"{message}\n\nPlease verify your username and password.")
                # Clear password field for security
                self.password_input.clear()
                self.password_input.setFocus()
                # Remove saved wrong password
                if KEYRING_AVAILABLE:
                    try:
                        keyring.delete_password("MoodleDownApp", self.username_input.text().strip())
                        self.save_password_cb.setChecked(False)
                    except:
                        pass
            else:
                QMessageBox.warning(self, "Failed", message)
        
        # Perform selective unzip if requested and module available
        if self.unzip_after_cb.isChecked() and UNZIPPER_AVAILABLE:
            try:
                self.statusBar().showMessage("Unzipping newly downloaded archives...")
                QApplication.processEvents()
                self._unzip_new_archives()
                self.statusBar().showMessage("Unzip complete")
            except Exception as e:
                QMessageBox.warning(self, "Unzip Error", f"Selective unzip failed: {e}")
        
        self.current_worker = None
        self.update_selection()

    def _unzip_new_archives(self):
        """Unzip only .zip files created/modified during this download session for selected courses."""
        if not self.download_start_time:
            return
        base_download_dir = self.location_input.text().strip()
        if not os.path.isdir(base_download_dir):
            return
        # Build list of course folders that were part of this session
        target_folders = []
        for course_name in self.selected_courses:
            url = self.all_courses.get(course_name)
            if not url:
                continue
            if not is_valid_course_url(url):
                continue
            # Replicate folder naming logic used during download
            folder_path = create_course_folder(url, base_download_dir, course_name)
            if os.path.isdir(folder_path):
                target_folders.append(folder_path)
        processed = 0
        extracted = 0
        errors = 0
        cutoff = self.download_start_time - 2  # Small grace period
        for folder in target_folders:
            for root, _, files in os.walk(folder):
                for f in files:
                    if not f.lower().endswith('.zip'):
                        continue
                    path = os.path.join(root, f)
                    try:
                        mtime = os.path.getmtime(path)
                        if mtime < cutoff:
                            continue  # Skip old archives
                        processed += 1
                        with zipfile.ZipFile(path, 'r') as zf:
                            zf.extractall(root)
                        extracted += 1
                        # Optionally delete after extraction (disabled)
                        # os.remove(path)
                        self.statusBar().showMessage(f"Unzipped: {os.path.relpath(path, folder)}")
                        QApplication.processEvents()
                    except Exception:
                        errors += 1
        summary = f"Selective unzip done. New archives: {processed}, Extracted: {extracted}, Errors: {errors}"
        self.status_label.setText(summary)
        if errors:
            QMessageBox.warning(self, "Unzip Completed with Errors", summary)
        else:
            QMessageBox.information(self, "Unzip Completed", summary)

    def autofill_courses(self):
        """Automatically extract courses from Moodle dashboard and add them to the course list."""
        if self.current_worker and self.current_worker.is_alive():
            QMessageBox.warning(self, "Busy", "Please wait for the current operation to complete.")
            return
        
        if hasattr(self, 'autofill_worker') and self.autofill_worker and self.autofill_worker.is_alive():
            QMessageBox.warning(self, "Busy", "Auto-fill operation already in progress.")
            return
        
        if not getattr(self, 'browser_ready', False):
            if ensure_chromium_available(self):
                self.browser_ready = True
            else:
                QMessageBox.warning(self, "Browser Missing", "Chromium must be installed before auto-filling courses.")
                return
        
        username = self.username_input.text().strip()
        password = self.password_input.text()
        
        if not username or not password:
            QMessageBox.warning(self, "Missing Credentials", "Please enter your username and password first.")
            return
        
        # Remove the replace/merge dialog - always merge
        # Simplified: Just start the worker
        username = self.username_input.text().strip()
        password = self.password_input.text()
        year_range = self.year_combo.currentText()
        download_folder = self.location_input.text().strip() or os.getcwd()
        
        self.autofill_worker = AutofillWorker(
            username=username,
            password=password,
            year_range=year_range,
            download_folder=download_folder,
            headless=self.headless_cb.isChecked()
        )
        
        self.autofill_worker.signals.status.connect(self.update_autofill_status)
        self.autofill_worker.signals.finished.connect(self.autofill_finished)
        
        self.set_autofill_state(True)
        self.autofill_worker.start()
    
    def set_autofill_state(self, running: bool):
        """Enable/disable UI elements during autofill operation."""
        self.autofill_btn.setEnabled(not running)
        self.download_btn.setEnabled(not running)
        if running:
            self.status_label.setText("Auto-filling courses from Moodle...")
    
    def update_autofill_status(self, message: str):
        """Update status during autofill operation."""
        self.statusBar().showMessage(message)
        self.status_label.setText(message)
    
    def autofill_finished(self, success: bool, message: str, courses: List[Dict[str, str]]):
        """Handle completion of autofill operation."""
        self.set_autofill_state(False)
        
        if not success:
            if "log in" in message.lower() or "credentials" in message.lower():
                QMessageBox.warning(self, "Login Failed", 
                    f"{message}\n\nPlease verify your username and password.")
                self.password_input.clear()
                self.password_input.setFocus()
            else:
                QMessageBox.warning(self, "Auto-fill Failed", message)
            self.status_label.setText("Auto-fill failed")
            self.statusBar().showMessage("Ready")
            return
        
        if not courses:
            QMessageBox.information(self, "No Courses", message)
            self.status_label.setText("No courses found")
            self.statusBar().showMessage("Ready")
            return
        
        # Always merge (add new courses without removing existing ones)
        added = 0
        skipped = 0
        for course in courses:
            name = course['name']
            url = course['href']
            
            # Skip if already exists
            if name in self.all_courses:
                skipped += 1
                continue
            
            self.all_courses[name] = url
            added += 1
        
        self.refresh_course_list()
        self.save_courses()
        
        # Show results
        result_msg = f"Successfully extracted {len(courses)} courses.\n"
        result_msg += f"Added: {added}"
        if skipped > 0:
            result_msg += f", Skipped (duplicates): {skipped}"
        
        QMessageBox.information(self, "Auto-fill Complete", result_msg)
        
        self.status_label.setText("Auto-fill complete")
        self.statusBar().showMessage("Ready")
        
        self.autofill_worker = None


def main():
    """Main function for launching the GUI application."""
    QApplication.setOrganizationName("MoodleDown")
    QApplication.setApplicationName("MoodleDownApp")
    app = QApplication(sys.argv)
    # Apply dark theme if available
    if QDARKSTYLE_AVAILABLE:
        app.setStyleSheet(qdarkstyle.load_stylesheet_pyqt5())

    window = MoodleDownloaderApp()
    window.show()
    window.raise_()
    window.activateWindow()
    
    return app.exec_()

# --- Main Execution ---
if __name__ == "__main__":
    sys.exit(main())

