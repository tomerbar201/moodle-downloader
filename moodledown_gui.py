"""
GUI interface for Moodle Downloader using PyQt5.
Handles user authentication, course selection, and download management.

"""

import sys
import threading
import os
import re
import subprocess
from typing import Optional, Tuple, List, Dict, Set, Any, Callable
from playwright.sync_api import sync_playwright, Error as PlaywrightError
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFileDialog, QProgressBar, QListWidget, QListWidgetItem, QAbstractItemView,
    QMessageBox, QMainWindow, QStatusBar, QDialog, QDialogButtonBox, QFormLayout, QCheckBox,
    QSplitter)
from PyQt5.QtGui import QFont, QIcon, QMouseEvent
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QSize, QSettings, QPoint, QEvent
# --- Core Module Imports ---
try:
    # Import from the new modular structure
    from main import download_course
    from file_operations import create_course_folder, setup_logging
    # We don't need to import the other modules directly as they're used by main.py
except ImportError as e:
    print("ERROR: Could not import core modules.")
    try:  # Try showing a GUI message box even if full app init fails
        app_temp = QApplication.instance() or QApplication(sys.argv)
        QMessageBox.critical(None, "Fatal Error", 
            "Could not import core modules for MoodleDown.\n"
            "Please ensure all required modules are in the correct location:\n"
            "main.py, moodle_browser.py, content_extractor.py, download_handler.py, file_operations.py, data_structures.py")
    except Exception:
        pass
    sys.exit(1)

# --- Keyring Import for Secure Password Storage ---
try:
    import keyring
    KEYRING_AVAILABLE = True
except ImportError:
    keyring = None
    KEYRING_AVAILABLE = False

# --- Unzipper Module Import ---
try:
    import unzipper
    UNZIPPER_AVAILABLE: bool = True
except ImportError:
    unzipper = None
    UNZIPPER_AVAILABLE = False

# --- Helper function to extract course ID ---
def extract_course_id_from_url(url: str) -> Optional[str]:
    """Extract Moodle course ID from URL."""
    if not url:
        return None
    match = re.search(r'[?&]id=(\d+)', url)
    return match.group(1) if match else None

# --- Initial Default Courses (Updated to use full URLs) ---
COURSES: Dict[str, str] = {
    "Introduction to Computer Science": "https://moodle.huji.ac.il/2024-25/course/view.php?id=12345",
    "Data Structures": "https://moodle.huji.ac.il/2024-25/course/view.php?id=23456"
}

# --- Worker Threads ---
class WorkerSignals(QObject):
    """
    Defines the signals available from a running worker thread.

    Supported signals are:
    - status: Emits a string to update the status message.
    - progress: Emits a float (0-100) to update the progress bar.
    - finished: Emits a boolean (success) and a string (message) when the
                task is complete.
    """
    status = pyqtSignal(str)
    progress = pyqtSignal(float)
    finished = pyqtSignal(bool, str)  # success, message

# --- Download Workers ---
class _BaseDownloadWorker(threading.Thread):
    """
    A base class for download worker threads, containing common functionality.

    This class handles the basic setup for a download thread, including
    initializing signals, reading settings, and providing a common method for
    running a single course download.

    Attributes:
        username (str): The Moodle username.
        password (str): The Moodle password.
        download_folder (str): The target directory for downloads.
        settings (QSettings): Application settings object.
        signals (WorkerSignals): Signals object for communicating with the GUI.
        browser (Optional[MoodleBrowser]): A shared browser instance.
    """
    def __init__(self, username: str, password: str, download_folder: str, settings: Optional[QSettings] = None) -> None:
        super().__init__(daemon=True)
        self.username: str = username
        self.password: str = password
        self.download_folder: str = download_folder
        self.settings: QSettings = settings or QSettings("MoodleDown", "MoodleDownApp")
        self.signals: WorkerSignals = WorkerSignals()
        # Read common settings
        self.headless: bool = self.settings.value("headless", True, bool)
        self.organize_by_section: bool = self.settings.value("organize_by_section", True, bool)
        self.full_download: bool = self.settings.value("full_download", False, bool)  # Read full_download setting
        self.year_range: str = self.settings.value("year_range", "2024-25")
        # Browser reference to be shared across downloads
        from moodle_browser import MoodleBrowser  # Local import to avoid circular dependency if MoodleBrowser imports GUI elements
        self.browser: Optional[MoodleBrowser] = None
    
    def _run_single_download(self, course_url: str, course_name: str, progress_callback: Callable[[str, float], None], shared_browser=None) -> bool:
        """Executes the download logic for a single course."""
        course_id = extract_course_id_from_url(course_url)
        if not course_id:
            progress_callback(f"Invalid URL for {course_name}, skipping.", 0)
            return False
            
        course_folder: str = create_course_folder(course_id, self.download_folder, course_name)
        # Use the new download_course function from main.py
        # Note: The 'download_course' function in main.py will need to be adapted to accept 'course_url'
        return download_course(
            course_url=course_url, 
            username=self.username, 
            password=self.password,
            download_folder=course_folder, 
            progress_callback=progress_callback,
            headless=self.headless,
            year_range=self.year_range,
            organize_by_section=self.organize_by_section,
            course_name=course_name,
            existing_browser=shared_browser,
            full_download=self.full_download
        )


class DownloadWorker(_BaseDownloadWorker):
    """
    A worker thread for downloading a single course.
    """
    def __init__(self, course_url: str, course_name: str, username: str, password: str, download_folder: str, settings: Optional[QSettings] = None) -> None:
        """
        Initializes the single-course download worker.

        Args:
            course_url (str): The URL of the course to download.
            course_name (str): The name of the course.
            username (str): The Moodle username.
            password (str): The Moodle password.
            download_folder (str): The target directory for downloads.
            settings (Optional[QSettings]): Application settings object.
        """
        super().__init__(username, password, download_folder, settings)
        self.course_url: str = course_url
        self.course_name: str = course_name

    def run(self) -> None:
        """The main entry point for the thread's execution."""
        try:
            def progress_callback(message: str, percent: float) -> None:
                self.signals.status.emit(f"{self.course_name}: {message}")
                self.signals.progress.emit(percent)
            success = self._run_single_download(self.course_url, self.course_name, progress_callback)
            msg = f"{'Successfully downloaded' if success else 'Failed to complete download for'} {self.course_name}"
            self.signals.finished.emit(success, msg)
        except Exception as e:
            self.signals.status.emit(f"Error: {str(e)}")
            self.signals.finished.emit(False, f"Error downloading {self.course_name}: {str(e)}")


class BatchDownloadWorker(_BaseDownloadWorker):
    """
    A worker thread for downloading multiple courses in a single batch.

    This worker manages a single browser session to log in once and then
    iterates through the selected courses, downloading them sequentially.
    """
    def __init__(self, courses: List[Tuple[str, str]], username: str, password: str, download_folder: str, settings: Optional[QSettings] = None) -> None:
        """
        Initializes the batch download worker.

        Args:
            courses (List[Tuple[str, str]]): A list of (course_url, course_name)
                                             tuples to download.
            username (str): The Moodle username.
            password (str): The Moodle password.
            download_folder (str): The target directory for downloads.
            settings (Optional[QSettings]): Application settings object.
        """
        super().__init__(username, password, download_folder, settings)
        self.courses: List[Tuple[str, str]] = courses  # List of (course_url, course_name) tuples

    def run(self) -> None:
        """
        The main entry point for the thread's execution.

        It logs in once, then iterates through the courses, providing progress
        updates for the entire batch.
        """
        total_courses: int = len(self.courses)
        successful_courses: int = 0
        
        try:
            # Create one browser instance for all courses
            from moodle_browser import MoodleBrowser
            self.browser = MoodleBrowser(download_folder=self.download_folder, year_range=self.year_range, headless=self.headless)
            self.browser.setup_browser()
            
            # Perform login once
            self.signals.status.emit("Logging in to Moodle...")
            login_success = self.browser.login(self.username, self.password)
            if not login_success:
                self.signals.status.emit("Failed to login to Moodle")
                self.signals.finished.emit(False, "Failed to login to Moodle")
                return
                
            self.signals.status.emit("Login successful, starting downloads...")
            
            for i, (course_url, course_name) in enumerate(self.courses):
                self.signals.status.emit(f"[{i+1}/{total_courses}] Starting: {course_name}")
                self.signals.progress.emit((i / total_courses) * 100)
                course_progress_base: float = (i / total_courses) * 100
                course_progress_weight: float = 100 / total_courses

                def progress_callback(message: str, percent: float) -> None:
                    self.signals.status.emit(f"[{i+1}/{total_courses}] {course_name}: {message}")
                    overall_progress = course_progress_base + (percent / 100) * course_progress_weight
                    self.signals.progress.emit(overall_progress)
                    
                # Pass the shared browser instance
                success = self._run_single_download(course_url, course_name, progress_callback, self.browser)
                if success:
                    successful_courses += 1
                status = "Completed" if success else "Failed"
                self.signals.status.emit(f"[{i+1}/{total_courses}] {status}: {course_name}")

            self.signals.progress.emit(100)
            if successful_courses == total_courses:
                self.signals.finished.emit(True, f"Successfully downloaded all {total_courses} courses")
            else:
                self.signals.finished.emit(successful_courses > 0, f"Downloaded {successful_courses}/{total_courses} courses")
        except Exception as e:
            self.signals.status.emit(f"Error in batch download: {str(e)}")
            self.signals.finished.emit(False, f"Error during batch download: {str(e)}")
        finally:
            # Close the browser at the end of all downloads
            if self.browser:
                try:
                    self.browser.close()
                except Exception as e:
                    pass

# --- Dialogs ---
class AddCourseDialog(QDialog):
    """
    A dialog window for adding a new course to the list.

    It provides input fields for the course name and URL and includes validation
    to ensure the inputs are valid before closing.
    """
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initializes the dialog."""
        super().__init__(parent)
        self.setWindowTitle("Add Course")
        layout = QFormLayout(self)
        self.course_name: QLineEdit = QLineEdit()
        self.course_url_input: QLineEdit = QLineEdit()
        self.course_url_input.setPlaceholderText("e.g., https://moodle.../course/view.php?id=12345")
        layout.addRow("Course Name:", self.course_name)
        layout.addRow("Course URL:", self.course_url_input)
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addRow(button_box)  # type: ignore

    def accept(self):
        """
        Overrides the default accept behavior to add validation.
        """
        name = self.course_name.text().strip()
        url = self.course_url_input.text().strip()
        if not name or not url:
            QMessageBox.warning(self, "Input Error", "Both Course Name and Course URL are required.")
            return
        if not extract_course_id_from_url(url):
            QMessageBox.warning(self, "Input Error", "The URL must be a valid Moodle course URL containing an 'id' parameter (e.g., ...?id=12345).")
            return
        super().accept()

    def get_course_data(self) -> Tuple[str, str]:
        """
        Returns the entered course name and URL.

        Returns:
            Tuple[str, str]: The course name and URL.
        """
        return self.course_name.text().strip(), self.course_url_input.text().strip()

# --- Main Application Window ---
class MoodleDownloaderApp(QMainWindow):
    """
    The main application window for the Moodle Downloader.

    This class sets up the entire GUI, manages user interactions, handles
    application state and settings, and launches worker threads for downloads.
    """
    def __init__(self) -> None:
        """Initializes the main application window."""
        super().__init__()
        print("Initializing MoodleDown GUI...")
        self.setWindowTitle("MoodleDown - Playwright Edition")
        print("Setting up main window...")
        self.resize(750, 600)
        self.settings: QSettings = QSettings("MoodleDown", "MoodleDownApp")
        self.apply_dark_theme()
        self.selected_courses: Set[str] = set()
        self.all_courses: Dict[str, str] = {}
        self.current_worker: Optional[threading.Thread] = None
        self.setup_ui()
        self.load_credentials()
        self.load_courses()
        self.restore_geometry_settings()
    
    def setup_ui(self):
        """
        Initializes and arranges all the UI widgets in the main window.
        """
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        self.splitter = QSplitter(Qt.Horizontal)

        # Left panel
        form_panel = QWidget()
        form_layout = QVBoxLayout(form_panel)
        form_layout.setSpacing(8)

        def add_section_label(text: str) -> None:
            form_layout.addWidget(QLabel(text))

        # Search
        add_section_label("Search Courses:")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search name or ID...")
        self.search_input.textChanged.connect(self.filter_courses)
        form_layout.addWidget(self.search_input)

        # Credentials
        add_section_label("Moodle Credentials: (make sure they are correct)")
        self.username_input = QLineEdit(self.settings.value("username", ""))
        self.username_input.setPlaceholderText("Username / Email")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.Password)
        form_layout.addWidget(self.username_input)
        form_layout.addWidget(self.password_input)

        # Academic Year
        add_section_label("Academic Year (e.g. 2024-25 or 2025-2026):")
        self.year_input = QLineEdit(self.settings.value("year_range", "2024-25"))
        self.year_input.setPlaceholderText("2024-25")
        form_layout.addWidget(self.year_input)

        # Password save option
        self.save_password_cb = QCheckBox("Save password (in system keychain)")
        self.save_password_cb.setChecked(self.settings.value("save_password", False, bool))
        self.save_password_cb.setToolTip("Securely save your password using the system's credential manager.\nRequires the 'keyring' package.")
        self.save_password_cb.stateChanged.connect(lambda state: self.settings.setValue("save_password", state == Qt.Checked))
        if not KEYRING_AVAILABLE:
            self.save_password_cb.setEnabled(False)
            self.save_password_cb.setToolTip("Feature disabled: 'keyring' module not found. Run: pip install keyring")
        form_layout.addWidget(self.save_password_cb)

        # Download location
        add_section_label("Download Location:")
        location_layout = QHBoxLayout()
        self.location_input = QLineEdit(self.settings.value("default_location", os.getcwd()))
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self.browse_folder)
        location_layout.addWidget(self.location_input)
        location_layout.addWidget(self.browse_btn)
        form_layout.addLayout(location_layout)

        # Unzip button
        self.unzip_button = QPushButton(QIcon.fromTheme("archive-extract"), "Unzip Folder Content")
        self.unzip_button.setToolTip("Recursively unzip all archives in the 'Download Location' folder")
        self.unzip_button.clicked.connect(self.trigger_manual_unzip)
        self.unzip_button.setEnabled(UNZIPPER_AVAILABLE)
        if not UNZIPPER_AVAILABLE:
            self.unzip_button.setToolTip("Feature disabled: 'unzipper' module not found")
        form_layout.addWidget(self.unzip_button)

        # Course management
        course_mgmt_layout = QHBoxLayout()
        self.add_course_btn = QPushButton(QIcon.fromTheme("list-add"), "Add a course")
        self.add_course_btn.setToolTip("Add a new course (Ctrl+N)")
        self.add_course_btn.setShortcut("Ctrl+N")
        self.add_course_btn.clicked.connect(self.add_course)
        self.remove_course_btn = QPushButton(QIcon.fromTheme("list-remove"), "Remove courses")
        self.remove_course_btn.setToolTip("Remove selected courses")
        self.remove_course_btn.clicked.connect(self.remove_selected_courses)
        self.remove_course_btn.setEnabled(False)
        course_mgmt_layout.addWidget(self.add_course_btn)
        course_mgmt_layout.addWidget(self.remove_course_btn)
        course_mgmt_layout.addStretch()
        form_layout.addLayout(course_mgmt_layout)

        # Download button
        self.download_btn = QPushButton(QIcon.fromTheme("download"), "Download Selected")
        self.download_btn.setToolTip("Download materials for selected courses")
        self.download_btn.clicked.connect(self.start_download)
        self.download_btn.setEnabled(False)
        form_layout.addWidget(self.download_btn)

        # Progress & status
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        form_layout.addWidget(self.progress_bar)
        self.status_label = QLabel("Ready")
        self.status_label.setWordWrap(True)
        self.status_label.setFixedHeight(35)
        self.status_label.setTextFormat(Qt.PlainText)
        self.status_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        form_layout.addWidget(self.status_label)

        # Options
        add_section_label("Options:")
        self.headless_mode_cb = QCheckBox("Headless mode (recommended)")
        self.headless_mode_cb.setChecked(self.settings.value("headless", True, bool))
        self.headless_mode_cb.setToolTip("Run browser invisibly")
        self.headless_mode_cb.stateChanged.connect(lambda state: self.settings.setValue("headless", state == Qt.Checked))
        self.organize_cb = QCheckBox("Organize by section (recommended)")
        self.organize_cb.setChecked(self.settings.value("organize_by_section", True, bool))
        self.organize_cb.setToolTip("Create subfolders for Moodle sections")
        self.organize_cb.stateChanged.connect(lambda state: self.settings.setValue("organize_by_section", state == Qt.Checked))
        self.full_download_cb = QCheckBox("Full download")
        self.full_download_cb.setChecked(self.settings.value("full_download", False, bool))
        self.full_download_cb.setToolTip("Ignore download history (needs core support)")
        self.full_download_cb.stateChanged.connect(lambda state: self.settings.setValue("full_download", state == Qt.Checked))
        form_layout.addWidget(self.headless_mode_cb)
        form_layout.addWidget(self.organize_cb)
        form_layout.addWidget(self.full_download_cb)
        form_layout.addStretch(1)

        guide_label = QLabel(
            "<b>How to use:</b><br>"
            "1. <b>Add  your courses main page URLs</b> (recommended to add all at once).<br>"
            "2. Enter your <b>Moodle email</b> and <b>password</b>.<br>"
            "3. Select the courses you want to download from the list.<br>"
            "4. Click <b>Download Selected</b>.<br><br>"
            "<i>Tip: The course main page URL looks like:<br>"
            "https://moodle.huji.ac.il/2024-25/course/view.php?id=XXXXX</i>"
        )
        guide_label.setWordWrap(True)
        guide_label.setStyleSheet("color: #bdbdbd; font-size: 9pt; margin-top: 10px; margin-bottom: 5px;")
        form_layout.addWidget(guide_label)

        # Right panel (course list)
        list_panel = QWidget()
        list_layout = QVBoxLayout(list_panel)
        list_layout.setSpacing(5)
        list_layout.addWidget(QLabel("Available Courses:"))
        self.course_list = QListWidget()
        self.course_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self.course_list.itemSelectionChanged.connect(self.update_selection)
        list_layout.addWidget(self.course_list)

        self.splitter.addWidget(form_panel)
        self.splitter.addWidget(list_panel)
        main_layout.addWidget(self.splitter)

        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("Ready")

    def apply_dark_theme(self) -> None:
        """Applies a custom dark theme stylesheet to the application."""
        self.setStyleSheet("""
            QWidget { background-color: #212121; color: #f5f5f5; font-size: 9pt; }
            QLineEdit, QListWidget { background-color: #424242; border: 1px solid #616161; padding: 4px; border-radius: 3px; color: #f5f5f5; }
            QPushButton { background-color: #2196F3; color: white; border-radius: 3px; padding: 5px 10px; font-weight: bold; border: none; }
            QPushButton:hover { background-color: #1976D2; }
            QPushButton:pressed { background-color: #0D47A1; }
            QPushButton:disabled { background-color: #757575; color: #bdbdbd; }
            QProgressBar { border: 1px solid #616161; border-radius: 3px; text-align: center; background-color: #424242; color: #f5f5f5; height: 18px; }
            QProgressBar::chunk { background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1976D2, stop:1 #2196F3); border-radius: 3px; }
            QListWidget::item { padding: 4px 2px; }
            QListWidget::item:selected { background-color: #1976D2; color: white; }
            QListWidget::item:hover:!selected { background-color: #37474F; }
            QStatusBar { background-color: #37474F; color: #eceff1; }
            QStatusBar::item { border: none; }
            QDialog { background-color: #2b2b2b; color: #f5f5f5; }
            QDialog QLineEdit { background-color: #424242; border: 1px solid #616161; padding: 5px; border-radius: 4px; color: #f5f5f5; }
            QDialogButtonBox > QPushButton { background-color: #2196F3; color: white; border-radius: 4px; padding: 6px 15px; font-weight: bold; min-width: 80px; }
            QCheckBox { color: #f5f5f5; spacing: 5px; padding: 2px 0; }
            QCheckBox::indicator { border: 1px solid #616161; background-color: #424242; width: 14px; height: 14px; border-radius: 3px; }
            QCheckBox::indicator:checked { background-color: #2196F3; border: 1px solid #1976D2; }
            QCheckBox::indicator:disabled { background-color: #616161; border: 1px solid #757575;}
            QLabel { color: #f5f5f5; background-color: transparent; padding: 1px 0; }
            QLabel:contains("Options:"), QLabel:contains("Moodle Credentials:"),
            QLabel:contains("Download Location:"), QLabel:contains("Search Courses:"),
            QLabel:contains("Unzip Folder Content") { /* Style the new button if needed */ }
            QLabel:contains("Options:"), QLabel:contains("Moodle Credentials:"),
            QLabel:contains("Download Location:"), QLabel:contains("Search Courses:") {
                 font-weight: bold; padding-bottom: 2px; border-bottom: 1px solid #424242; margin-top: 3px;
            }
            QSplitter::handle { background-color: #455A64; border: 1px solid #616161; width: 4px; }
            QSplitter::handle:horizontal:hover { background-color: #546E7A; }
        """)

    def load_credentials(self) -> None:
        """
        Loads the username from settings and the password from the system
        keyring if the 'Save password' option is enabled.
        """
        # Username is already loaded in setup_ui from settings
        username = self.username_input.text()

        # Only try to load password if the user previously chose to save it
        if self.save_password_cb.isChecked() and KEYRING_AVAILABLE and username:
            try:
                password = keyring.get_password("MoodleDownApp", username)
                if password:
                    self.password_input.setText(password)
            except Exception as e:
                pass  # Silently handle keyring errors
                self.statusBar.showMessage("Could not retrieve saved password.")

    def load_courses(self) -> None:
        """
        Loads the list of courses from the application settings and populates
        the course list widget.
        """
        try:
            saved_data: Any = self.settings.value("courses", [])
            # Use dict comprehension for loading, handling potential errors
            self.all_courses = {str(item[0]): str(item[1]) for item in saved_data
                                if isinstance(item, (list, tuple)) and len(item) == 2}
            if not self.all_courses and not saved_data:  # Only load defaults if nothing was saved
                self.all_courses = COURSES.copy()
            self.course_list.clear()
            for course_name in sorted(self.all_courses.keys()):
                course_url = self.all_courses[course_name]
                course_id = extract_course_id_from_url(course_url) or "N/A"
                item: QListWidgetItem = QListWidgetItem(f"{course_name} [ID: {course_id}]")
                item.setData(Qt.UserRole, course_url)  # Store the full URL
                item.setToolTip(f"Name: {course_name}\nURL: {course_url}")
                if course_name in self.selected_courses:
                    item.setSelected(True)
                self.course_list.addItem(item)
            self.statusBar.showMessage(f"Loaded {len(self.all_courses)} courses")
        except Exception as e:
            QMessageBox.warning(self, "Error Loading Courses", f"Failed to load courses: {e}")
            self.all_courses = COURSES.copy()  # Fallback safely
            self.load_courses()  # Attempt to reload UI with defaults

    def filter_courses(self) -> None:
        """
        Filters the visible items in the course list based on the text in the
        search input field.
        """
        search_term: str = self.search_input.text().lower().strip()
        for i in range(self.course_list.count()):
            item = self.course_list.item(i)
            item.setHidden(search_term not in item.text().lower())

    def update_selection(self) -> None:
        """
        Updates the set of selected courses and enables/disables UI elements
        like the 'Download' and 'Remove' buttons based on the selection.
        """
        self.selected_courses = {item.text().split(" [ID: ")[0] for item in self.course_list.selectedItems()}
        count: int = len(self.selected_courses)
        is_downloading: bool = self.current_worker is not None and self.current_worker.is_alive()
        can_interact: bool = count > 0 and not is_downloading
        self.download_btn.setEnabled(can_interact)
        self.remove_course_btn.setEnabled(can_interact)
        self.statusBar.showMessage(f"Selected {count} course{'s' if count != 1 else ''}")

    def browse_folder(self) -> None:
        """
        Opens a file dialog to allow the user to select a download location.
        """
        current: str = self.location_input.text() or os.getcwd()
        folder: str = QFileDialog.getExistingDirectory(self, "Select Download Location", current)
        if folder:
            self.location_input.setText(folder)
            self.settings.setValue("default_location", folder)

    def add_course(self) -> None:
        """
        Opens the AddCourseDialog to allow the user to add a new course to the
        list.
        """
        dialog = AddCourseDialog(self)
        if dialog.exec_():
            name, url = dialog.get_course_data()
            if name in self.all_courses:
                QMessageBox.warning(self, "Duplicate", f"Course '{name}' already exists.")
                return
            if url in self.all_courses.values():
                existing = next((n for n, u in self.all_courses.items() if u == url), None)
                QMessageBox.warning(self, "Duplicate URL", f"That URL is already used by '{existing}'.")
                return
            self.all_courses[name] = url
            course_id = extract_course_id_from_url(url) or "N/A"
            item: QListWidgetItem = QListWidgetItem(f"{name} [ID: {course_id}]")
            item.setData(Qt.UserRole, url)
            item.setToolTip(f"Name: {name}\nURL: {url}")
            self.course_list.addItem(item)
            self.course_list.sortItems()
            self.save_courses_to_settings()
            self.statusBar.showMessage(f"Added course: {name}")

    def remove_selected_courses(self) -> None:
        """
        Removes the currently selected courses from the list after a confirmation
        dialog.
        """
        items: List[QListWidgetItem] = self.course_list.selectedItems()
        if not items:
            return
        count: int = len(items)
        reply = QMessageBox.question(self, "Confirm Removal", f"Remove {count} selected course(s)?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            removed_count = 0
            for item in list(items):  # Iterate over copy
                name = item.text().split(" [ID: ")[0]
                self.course_list.takeItem(self.course_list.row(item))
                if name in self.all_courses:
                    del self.all_courses[name]
                    removed_count += 1
                self.selected_courses.discard(name)
            if removed_count > 0:
                self.save_courses_to_settings()
                self.update_selection()
            self.statusBar.showMessage(f"Removed {removed_count} course(s)")

    def save_courses_to_settings(self) -> None:
        """Saves the current list of courses to the application settings."""
        try:
            self.settings.setValue("courses", list(self.all_courses.items()))
        except Exception as e:
            QMessageBox.warning(self, "Save Error", f"Could not save course list: {e}")

    def start_download(self) -> None:
        """
        Validates user inputs and starts the download process by creating and
        running a worker thread.
        """
        if self.current_worker and self.current_worker.is_alive():
            QMessageBox.warning(self, "Busy", "Download already running.")
            return
        if not self.selected_courses:
            QMessageBox.warning(self, "No Selection", "Select course(s) to download.")
            return

        username = self.username_input.text().strip()
        password = self.password_input.text()
        dl_folder = self.location_input.text().strip()

        if not username or not password or not dl_folder:
            QMessageBox.warning(self, "Input Missing", "Enter username, password, and download location.")
            return
        if not os.path.isdir(dl_folder):
            if QMessageBox.question(self, "Create Folder?", f"Location '{dl_folder}' missing. Create it?",
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes) == QMessageBox.Yes:
                try:
                    os.makedirs(dl_folder, exist_ok=True)
                except OSError as e:
                    QMessageBox.critical(self, "Error", f"Could not create folder:\n{e}")
                    return
            else:
                return

        # Persist basics
        self.settings.setValue("username", username)
        self.settings.setValue("default_location", dl_folder)
        self.settings.setValue("year_range", self.year_input.text().strip() or "2024-25")

        # Password storage
        if KEYRING_AVAILABLE:
            try:
                if self.save_password_cb.isChecked():
                    keyring.set_password("MoodleDownApp", username, password)
                else:
                    keyring.delete_password("MoodleDownApp", username)
            except Exception:
                self.statusBar.showMessage("Could not save password to keychain.")

        # Prepare course data
        course_data: List[Tuple[str, str]] = [
            (self.all_courses[name], name)
            for name in sorted(self.selected_courses)
            if name in self.all_courses
        ]
        if not course_data:
            QMessageBox.warning(self, "Error", "Could not find URLs for selected courses.")
            return

        WorkerClass = DownloadWorker if len(course_data) == 1 else BatchDownloadWorker
        args = (course_data[0][0], course_data[0][1], username, password, dl_folder, self.settings) \
            if len(course_data) == 1 else (course_data, username, password, dl_folder, self.settings)
        self.current_worker = WorkerClass(*args)

        self.current_worker.signals.status.connect(self.update_status)
        self.current_worker.signals.progress.connect(self.update_progress)
        self.current_worker.signals.finished.connect(self.download_finished)
        self.set_ui_downloading_state(True)
        start_msg = f"Starting download for {len(course_data)} course{'s' if len(course_data) != 1 else ''}..."
        self.status_label.setText(start_msg)
        self.statusBar.showMessage(start_msg)
        self.current_worker.start()

    def set_ui_downloading_state(self, downloading: bool) -> None:
        """
        Enables or disables UI elements based on whether a download is in
        progress.

        Args:
            downloading (bool): True to disable controls for downloading, False
                                to re-enable them.
        """
        enabled: bool = not downloading
        has_selection: bool = bool(self.selected_courses)
        self.download_btn.setEnabled(enabled and has_selection)
        self.remove_course_btn.setEnabled(enabled and has_selection)
        self.course_list.setEnabled(enabled)
        self.search_input.setEnabled(enabled)
        self.add_course_btn.setEnabled(enabled)
        self.username_input.setEnabled(enabled)
        self.password_input.setEnabled(enabled)
        self.location_input.setEnabled(enabled)
        self.browse_btn.setEnabled(enabled)
        self.unzip_button.setEnabled(enabled and UNZIPPER_AVAILABLE)  # Also disable/enable unzip button
        self.headless_mode_cb.setEnabled(enabled)
        self.organize_cb.setEnabled(enabled)
        self.full_download_cb.setEnabled(enabled)

    def update_status(self, message: str) -> None:
        """
        Updates the status label and status bar with a message from a worker
        thread.

        Args:
            message (str): The status message to display.
        """
        self.statusBar.showMessage(message)
        self.status_label.setText(message[:100] + "..." if len(message) > 100 else message)  # Truncate long status

    def update_progress(self, value: float) -> None:
        """
        Updates the progress bar with a value from a worker thread.

        Args:
            value (float): The progress value (0-100).
        """
        self.progress_bar.setValue(int(value))

    def download_finished(self, success: bool, message: str) -> None:
        """
        Handles the completion of a download, showing a summary message and
        re-enabling the UI.

        Args:
            success (bool): True if the download was successful, False otherwise.
            message (str): The final message from the worker.
        """
        self.set_ui_downloading_state(False)
        final_status: str = ""
        if success:
            self.progress_bar.setValue(100)
            final_status = "Download complete."
            self.status_label.setText("Download complete.")
            self.statusBar.showMessage(final_status)
            QMessageBox.information(self, "Download Complete", f"{message}\n{final_status}")
        else:
            self.progress_bar.setValue(0)
            self.status_label.setText("Download failed.")
            self.statusBar.showMessage("Download failed.")
            QMessageBox.warning(self, "Download Failed", message)
        self.current_worker = None
        self.update_selection()  # Refresh button states

    def trigger_manual_unzip(self) -> None:
        """
        Initiates the manual unzipping process for all archives in the
        specified download folder.
        """
        if not UNZIPPER_AVAILABLE:
            QMessageBox.warning(self, "Unavailable", "The 'unzipper' module is required for this feature but was not found.")
            return

        target_folder: str = self.location_input.text().strip()
        if not target_folder:  # type: ignore
            QMessageBox.warning(self, "Input Missing", "Please specify a valid 'Download Location' to unzip.")
            return
        if not os.path.isdir(target_folder):
            QMessageBox.warning(self, "Invalid Path", f"The specified location is not a valid folder:\n{target_folder}")
            return

        # Define the callback for status updates from the unzipper module
        def report_unzip_status(message: str) -> None:
            # Update UI elements - use short messages for status label
            short_msg: str = message[:90] + '...' if len(message) > 90 else message
            self.statusBar.showMessage(f"Unzip: {message}")
            self.status_label.setText(f"Unzip: {short_msg}")
            QApplication.processEvents()  # Allow the UI to refresh during processing

        # Confirmation dialog
        reply = QMessageBox.question(self, "Confirm Unzip",
                                     f"Recursively unzip all *.zip files found within:\n{target_folder}\n\nThis might take a while. Proceed?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if reply == QMessageBox.No:
            return

        # Disable button and show initial status
        self.unzip_button.setEnabled(False)
        self.statusBar.showMessage(f"Starting recursive unzip in {target_folder}...")
        self.status_label.setText("Starting unzip process...")
        QApplication.processEvents()

        try:
            # Call the external unzipper function with the callback
            # This runs in the main thread, which might freeze the GUI for large operations.
            # For a truly non-blocking experience, this should also be in a thread.
            found: int; extracted: int; errors: int
            found, extracted, errors = unzipper.unzip_recursive(target_folder, status_callback=report_unzip_status)

            # Report results
            summary_msg: str = f"Unzip finished. Found: {found}, Extracted: {extracted}, Errors: {errors}."
            self.statusBar.showMessage(summary_msg)
            self.status_label.setText("Unzip process complete.")  # Keep final status brief
            if errors > 0:
                QMessageBox.warning(self, "Unzip Complete with Errors", f"{summary_msg}\nCheck status messages or console for details on errors.")
            else:
                QMessageBox.information(self, "Unzip Complete", summary_msg)

        except Exception as e:
            err_msg: str = f"An unexpected error occurred during the unzip process: {e}"
            self.statusBar.showMessage(err_msg)
            self.status_label.setText("Unzip Error.")
            QMessageBox.critical(self, "Unzip Error", err_msg)
            # Also log to console for more details potentially
            print(f"ERROR during manual unzip: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()

        finally:
            # Re-enable button regardless of outcome
            self.unzip_button.setEnabled(True)

    def save_geometry_settings(self) -> None:
        """Saves the window's current size, position, and splitter state."""
        self.settings.setValue("window_size", self.size())
        self.settings.setValue("window_pos", self.pos())
        if hasattr(self, 'splitter') and len(self.splitter.sizes()) == 2:
            self.settings.setValue("splitter_sizes", self.splitter.sizes())

    def restore_geometry_settings(self) -> None:
        """
        Restores the window's size, position, and splitter state from the last
        session, ensuring it remains visible on the screen.
        """
        try:
            # Get screen dimensions to ensure window is visible
            available_geometry = QApplication.desktop().availableGeometry()
            screen_width = available_geometry.width()
            screen_height = available_geometry.height()
            
            # Load saved size, but ensure it's reasonable
            saved_size: QSize = self.settings.value("window_size", QSize(750, 600))
            window_width = min(saved_size.width(), screen_width - 100)
            window_height = min(saved_size.height(), screen_height - 100)
            self.resize(window_width, window_height)
            
            # Load saved position, but ensure it's on screen
            saved_pos: QPoint = self.settings.value("window_pos", QPoint(100, 100))
            window_x: int = saved_pos.x()
            window_y: int = saved_pos.y()
            
            # Check if window would be off-screen
            if window_x < 0 or window_x > screen_width - 200 or window_y < 0 or window_y > screen_height - 200:
                print(f"Invalid window position detected: ({window_x}, {window_y}). Using default.")
                window_x = min(100, screen_width - window_width)
                window_y = min(100, screen_height - window_height)
            
            self.move(window_x, window_y)
            print(f"Screen dimensions: {screen_width}x{screen_height}")
            print(f"Window positioned at: ({window_x}, {window_y}) with size {window_width}x{window_height}")
            
            # Restore splitter if available
            splitter_sizes: List[int] = self.settings.value("splitter_sizes", [300, 450])
            if hasattr(self, 'splitter') and isinstance(splitter_sizes, list) and len(splitter_sizes) == 2:
                self.splitter.setSizes([int(s) for s in splitter_sizes])
        except Exception as e:
            print(f"Warning: Could not restore geometry: {e}")
            # Fallback to center screen
            self.resize(750, 600)
            self.center_on_screen()

    def center_on_screen(self) -> None:
        """Centers the window on the primary screen."""
        available_geometry = QApplication.desktop().availableGeometry()
        frame_geometry = self.frameGeometry()
        center_point = available_geometry.center()
        frame_geometry.moveCenter(center_point)
        self.move(frame_geometry.topLeft())
        print(f"Window centered on screen at {frame_geometry.topLeft().x()}, {frame_geometry.topLeft().y()}")

    def closeEvent(self, event: QEvent) -> None:
        """
        Handles the window close event, saving geometry and prompting the user
        if a download is in progress.
        """
        if self.current_worker and self.current_worker.is_alive():
            if QMessageBox.question(self, "Busy", "Download running. Exit anyway?",
                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.No:
                event.ignore()
                return
        self.save_geometry_settings()
        event.accept()

# --- Playwright Check ---
def check_and_install_playwright_browsers(parent_app: Optional[QApplication] = None) -> bool:
    """
    Checks if Playwright's browser dependencies are installed and prompts the
    user to install them if they are missing.

    Args:
        parent_app (Optional[QApplication]): The main application instance,
                                             required for showing dialogs.

    Returns:
        bool: True if browsers are installed or were successfully installed,
              False otherwise.
    """
    print("Checking for Playwright browsers...")
    try:
        with sync_playwright() as p:
            p.chromium.launch(headless=True).close()
        return True  # Browsers likely installed
    except PlaywrightError as e:
        err_str = str(e).lower()
        if "executable doesn't exist" in err_str and "run 'playwright install'" in err_str:
            if not parent_app:
                print("ERROR: QApplication needed for prompt.")
                return False
            if QMessageBox.question(parent_app, "Install Browsers?",
                                  "MoodleDown needs browser components.\nInstall automatically (may take minutes)?",
                                  QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes) == QMessageBox.No:
                QMessageBox.warning(parent_app, "Cancelled", "Browser install cancelled. App cannot function.")
                return False

            progress_msg: QMessageBox = QMessageBox(parent_app)
            progress_msg.setWindowTitle("Installing Browsers")
            progress_msg.setText("Downloading/installing...\nPlease wait.")
            progress_msg.setStandardButtons(QMessageBox.NoButton)
            progress_msg.setStyleSheet(parent_app.styleSheet())
            progress_msg.show()
            parent_app.processEvents()
            try:
                cmd: List[str] = [sys.executable, "-m", "playwright", "install", "--with-deps"]
                print(f"Running: {' '.join(cmd)}")
                si = subprocess.STARTUPINFO() if os.name == 'nt' else None
                if si:
                    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    si.wShowWindow = subprocess.SW_HIDE
                result = subprocess.run(cmd, capture_output=True, text=True, check=False,
                                     startupinfo=si, encoding='utf-8', errors='ignore')
                progress_msg.close()
                if result.returncode == 0:
                    QMessageBox.information(parent_app, "Success", "Browsers installed.")
                    return True
                else:
                    QMessageBox.critical(parent_app, "Install Failed",
                                      f"Failed (Code {result.returncode}):\n{result.stderr or result.stdout or 'Unknown error'}\n\n"
                                      "Try manual: python -m playwright install --with-deps")
                    return False
            except Exception as install_err:
                progress_msg.close()
                QMessageBox.critical(parent_app, "Install Error", f"Unexpected install error:\n{install_err}")
                return False
        else:
            QMessageBox.critical(None, "Playwright Error", f"Unexpected Playwright setup error:\n{e}")
            return False
    except ImportError:
        QMessageBox.critical(None, "Fatal Error", "'playwright' missing. Run 'pip install playwright'.")
        return False
    except Exception as general_err:
        QMessageBox.critical(None, "Error", f"Unexpected setup error:\n{general_err}")
        return False

# --- Main Execution ---
if __name__ == "__main__":
    # Main entry point for the application.
    # It initializes the QApplication, performs a check for Playwright
    # components, and runs the main GUI window.
    QApplication.setOrganizationName("MoodleDown")
    QApplication.setApplicationName("MoodleDownApp")
    app: QApplication = QApplication(sys.argv)

    # --- Simplified startup check for the bundled application ---
    try:
        # A quick, silent check to ensure Playwright can initialize.
        # This will fail if the bundled browsers are missing or corrupted.
        with sync_playwright():
            pass
    except Exception as e:
        # Provide a user-friendly error if something is wrong with the package
        QMessageBox.critical(None, "Application Error",
                                  "A required component is missing or could not be loaded.\n"
                                  "Please try reinstalling the application.\n\n"
                                  f"Error: {e}")
        sys.exit(1)

    print("Playwright components verified.")
    print("Starting MoodleDown GUI...")
    window = MoodleDownloaderApp()

    # Use a more robust window display sequence
    window.show()
    window.raise_()  # Bring window to front
    window.activateWindow()  # Give window focus

    # Additional steps to ensure visibility
    QApplication.processEvents()

    # Move to front and give focus again after processing events
    window.raise_()
    window.activateWindow()

    # Diagnostic info after positioning
    print(f"Window geometry: {window.geometry().x()}, {window.geometry().y()}, "
          f"{window.geometry().width()}, {window.geometry().height()}")
    print(f"Window is visible: {window.isVisible()}")

    sys.exit(app.exec_())

