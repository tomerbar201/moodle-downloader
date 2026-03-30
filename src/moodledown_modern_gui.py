
import sys
import os
import shutil
from datetime import datetime
from typing import Optional, Dict

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QListWidget, QListWidgetItem, QStackedWidget,
                             QLineEdit, QComboBox, QProgressBar, QMessageBox, QDialog,
                             QFormLayout, QCheckBox, QFileDialog, QToolButton, QScrollArea,
                             QFrame, QAbstractItemView, QFileSystemModel, QTreeView, QSplitter, QSizePolicy)
from PyQt5.QtCore import Qt, QSettings, QSize, QDir, QUrl, QSortFilterProxyModel, QTimer
from PyQt5.QtGui import QIcon, QFont, QFontDatabase, QPalette, QColor, QStandardItem

# from qt_material import apply_stylesheet (moved to main)

# Import extracted modules
from .gui_utils import is_valid_course_url, COURSES
from .file_operations import sanitize_folder_name, setup_logging
from .gui_workers import (AutofillWorker, DownloadWorker, BatchDownloadWorker, 
                         DownloadWorkerBase)
try:
    from .chromium_setup import ensure_chromium, chromium_ready
except ImportError:
    # Fallback or assumed availability
    def ensure_chromium(): return True, ""
    def chromium_ready(): return True

try:
    import keyring
    KEYRING_AVAILABLE = True
except ImportError:
    keyring = None
    KEYRING_AVAILABLE = False

try:
    from . import unzipper
    UNZIPPER_AVAILABLE = True
except ImportError:
    try:
        import unzipper
        UNZIPPER_AVAILABLE = True
    except ImportError:
        UNZIPPER_AVAILABLE = False


def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller."""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def get_downloads_folder():
    """Returns the path to the user's Downloads folder."""
    return os.path.join(os.path.expanduser('~'), 'Downloads')

class SettingsDialog(QDialog):
    def __init__(self, parent=None, settings=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(400, 400)
        self.settings = settings or QSettings("MoodleDown", "MoodleDownApp")
        
        layout = QVBoxLayout(self)
        
        form_layout = QFormLayout()
        
        self.username_input = QLineEdit(self.settings.value("username", ""))
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.save_password_cb = QCheckBox("Save Password")
        self.save_password_cb.setChecked(self.settings.value("save_password", False, bool))
        self.save_password_cb.setEnabled(KEYRING_AVAILABLE)
        
        if self.settings.value("save_password", False, bool) and KEYRING_AVAILABLE:
            try:
                pw = keyring.get_password("MoodleDownApp", self.username_input.text())
                if pw: self.password_input.setText(pw)
            except: pass

        self.path_input = QLineEdit(self.settings.value("default_location", get_downloads_folder()))
        self.browse_btn = QPushButton("Browse")
        self.browse_btn.clicked.connect(self.browse_path)
        
        path_layout = QHBoxLayout()
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(self.browse_btn)

        self.headless_cb = QCheckBox("Headless Mode (Background Browser)")
        self.headless_cb.setChecked(self.settings.value("headless", True, bool))
        
        self.full_download_cb = QCheckBox("Full Download (Force re-download all)")
        self.full_download_cb.setChecked(self.settings.value("full_download", False, bool))
        
        self.unzip_cb = QCheckBox("Auto-Unzip New Files")
        self.unzip_cb.setChecked(self.settings.value("unzip_after", True, bool))
        self.unzip_cb.setEnabled(UNZIPPER_AVAILABLE)

        # Fix checkbox layout - use checkboxes directly in VBox/Form to ensure they are independent
        # Removing from form layout row and adding to main vertical layout for better control if needed, 
        # but FormLayout rows should verify independent behavior.
        # The issue described "only choose 1 checkbox" implies they are in a QButtonGroup or similar, but here they are not.
        # However, qt-material might be styling them as radio buttons if not careful, or maybe user is confused by the UI.
        # Let's ensure no auto-exclusive behavior is inherited.
        self.save_password_cb.setAutoExclusive(False)
        self.headless_cb.setAutoExclusive(False)
        self.full_download_cb.setAutoExclusive(False)
        self.unzip_cb.setAutoExclusive(False)

        settings_layout = QVBoxLayout()
        settings_layout.addWidget(self.headless_cb)
        settings_layout.addWidget(self.full_download_cb)
        settings_layout.addWidget(self.unzip_cb)

        form_layout.addRow("Username:", self.username_input)
        form_layout.addRow("Password:", self.password_input)
        form_layout.addRow("", self.save_password_cb)
        form_layout.addRow("Download Path:", path_layout)
        form_layout.addRow(QLabel("Options:"))
        form_layout.addRow(settings_layout) # Nest checkboxes cleanly
        
        layout.addLayout(form_layout)
        
        save_btn = QPushButton("Save Settings")
        save_btn.clicked.connect(self.save_settings)
        # Apply themes to dialog button
        save_btn.setProperty('class', 'success') 
        
        layout.addStretch()
        layout.addWidget(save_btn)

    def browse_path(self):
        d = QFileDialog.getExistingDirectory(self, "Select Download Folder", self.path_input.text())
        if d: self.path_input.setText(d)

    def save_settings(self):
        user = self.username_input.text().strip()
        pw = self.password_input.text()
        
        self.settings.setValue("username", user)
        self.settings.setValue("default_location", self.path_input.text())
        self.settings.setValue("headless", self.headless_cb.isChecked())
        self.settings.setValue("full_download", self.full_download_cb.isChecked())
        self.settings.setValue("unzip_after", self.unzip_cb.isChecked())
        self.settings.setValue("save_password", self.save_password_cb.isChecked())
        
        if KEYRING_AVAILABLE:
            if self.save_password_cb.isChecked() and user and pw:
                keyring.set_password("MoodleDownApp", user, pw)
            elif not self.save_password_cb.isChecked() and user:
                try: keyring.delete_password("MoodleDownApp", user)
                except: pass
        
        self.accept()

    def get_credentials(self):
        return self.username_input.text().strip(), self.password_input.text()


class DownloadSummaryDialog(QDialog):
    def __init__(self, summary: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Download Summary")
        self.resize(500, 600)
        
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("Download Complete" if summary.get("success") else "Download Finished with Errors")
        header.setStyleSheet(f"font-size: 18pt; font-weight: bold; color: {'#4caf50' if summary.get('success') else '#f44336'};")
        layout.addWidget(header)
        
        msg_label = QLabel(summary.get("message", ""))
        msg_label.setWordWrap(True)
        layout.addWidget(msg_label)

        # Scroll Area for lists
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        
        successful = summary.get("successful_downloads", [])
        if successful:
            succ_label = QLabel(f"✅ Successful Downloads ({len(successful)}):")
            succ_label.setStyleSheet("font-weight: bold; color: #4caf50; margin-top: 10px;")
            scroll_layout.addWidget(succ_label)
            
            succ_list = QListWidget()
            succ_list.addItems(successful)
            succ_list.setStyleSheet("QListWidget { border: 1px solid #4caf50; border-radius: 5px; background-color: rgba(76, 175, 80, 0.05); }")
            succ_list.setMaximumHeight(200)
            scroll_layout.addWidget(succ_list)
            
        failed = summary.get("failed_downloads", [])
        if failed:
            fail_label = QLabel(f"❌ Failed Downloads/Errors ({len(failed)}):")
            fail_label.setStyleSheet("font-weight: bold; color: #f44336; margin-top: 10px;")
            scroll_layout.addWidget(fail_label)
            
            fail_list = QListWidget()
            fail_list.addItems(failed)
            fail_list.setStyleSheet("QListWidget { border: 1px solid #f44336; border-radius: 5px; background-color: rgba(244, 67, 54, 0.05); }")
            fail_list.setWordWrap(True)
            fail_list.setMaximumHeight(200)
            scroll_layout.addWidget(fail_list)
            
        if not successful and not failed:
            empty_label = QLabel("No new files were downloaded.")
            empty_label.setStyleSheet("color: #b0bec5; font-style: italic;")
            scroll_layout.addWidget(empty_label)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)
        
        btn_box = QHBoxLayout()
        btn_box.addStretch()
        close_btn = QPushButton("Close window")
        if summary.get("success"):
            close_btn.setProperty('class', 'success')
        else:
            close_btn.setProperty('class', 'danger')
        close_btn.clicked.connect(self.accept)
        btn_box.addWidget(close_btn)
        
        layout.addLayout(btn_box)


class CourseCard(QFrame):
    """Custom widget to display course info in the list with a modern look"""
    def __init__(self, name, url, last_updated=None, parent=None):
        super().__init__(parent)
        self.course_name = name
        self.course_url = url
        self.last_updated = last_updated
        
        # Let's add some custom styling to the card itself via ID for the external CSS or inline fallback
        self.setObjectName("CourseCard")
        self.setStyleSheet("""
            QFrame#CourseCard {
                border-radius: 12px;
                background-color: #263238; /* Slightly lighter than main bg */
                border: 1px solid rgba(255, 255, 255, 0.05);
            }
            QFrame#CourseCard:hover {
                background-color: #37474f;
                border: 1px solid #00bcd4;
            }
        """)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 12, 15, 12)
        layout.setSpacing(15)
        
        # Icon
        icon_label = QLabel("📂")
        icon_label.setFont(QFont("Segoe UI Emoji", 28)) # Slightly larger icon
        layout.addWidget(icon_label)
        
        text_layout = QVBoxLayout()
        name_label = QLabel(self.course_name)
        name_label.setStyleSheet("font-weight: bold; font-size: 14pt; color: #ffffff; border: none; background: transparent;")
        name_label.setWordWrap(True)
        
        # Extract short ID if possible
        course_id = url.split("id=")[-1] if "id=" in url else "N/A"
        course_id = url.split("id=")[-1] if "id=" in url else "N/A"
        id_text = f"Course ID: {course_id}"
        if self.last_updated:
            id_text += f"  •  Last updated: {self.last_updated}"
        
        id_label = QLabel(id_text)
        id_label.setStyleSheet("color: #00bcd4; font-size: 9pt; border: none; background: transparent;")
        
        text_layout.addWidget(name_label)
        text_layout.addWidget(id_label)
        layout.addLayout(text_layout)
        
        layout.addStretch()
        # Removed arrow button since clicking the card opens details
        
        # Adjust layout ratios to prevent text overflow
        layout.setStretch(0, 0) # Icon
        layout.setStretch(1, 1) # Text
        layout.setStretch(2, 0) # Stretch


class ElidedLabel(QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._full_text = text
        self.setMinimumWidth(100)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        
    def setText(self, text):
        self._full_text = text
        self.updateElidedText()
        
    def setText_safe(self, text):
        self.setText(text)

    def updateElidedText(self):
        metrics = self.fontMetrics()
        elided = metrics.elidedText(self._full_text, Qt.ElideRight, self.width())
        super().setText(elided)
        
        # Add a tooltip so the user can still read the full text
        if elided != self._full_text:
            self.setToolTip(self._full_text)
        else:
            self.setToolTip("")

    def resizeEvent(self, event):
        self.updateElidedText()
        super().resizeEvent(event)
        
    def minimumSizeHint(self):
        return QSize(100, super().minimumSizeHint().height())
        
    def sizeHint(self):
        return QSize(200, super().sizeHint().height())

# Custom Proxy Model to filter out ZIP files and sort by history
class HistorySortProxyModel(QSortFilterProxyModel):
    def __init__(self, history_dict=None, parent=None):
        super().__init__(parent)
        self.history_dict = history_dict or {}
        self.setSortCaseSensitivity(Qt.CaseInsensitive)
        self.setDynamicSortFilter(True)

    def filterAcceptsRow(self, source_row, source_parent):
        # get source model index
        index = self.sourceModel().index(source_row, 0, source_parent)
        # get file name
        file_name = self.sourceModel().fileName(index)
        
        # Check if it's a file and ends with .zip (case insensitive)
        if self.sourceModel().isDir(index):
            return True
            
        if file_name.lower().endswith('.zip'):
             return False
             
        return True

    def lessThan(self, left, right):
        # Get file paths
        left_path = self.sourceModel().filePath(left)
        right_path = self.sourceModel().filePath(right)

        # Normalize paths for comparison
        left_idx = self.history_dict.get(os.path.normpath(left_path).lower(), float('inf'))
        right_idx = self.history_dict.get(os.path.normpath(right_path).lower(), float('inf'))
        
        # If both present, sort by index
        if left_idx != float('inf') and right_idx != float('inf'):
            return left_idx < right_idx
            
        # If one present, prioritize it
        if left_idx != float('inf'):
            return True
        if right_idx != float('inf'):
            return False
            
        # Fallback to alphabetical
        left_data = self.sourceModel().fileName(left)
        right_data = self.sourceModel().fileName(right)
        return left_data.lower() < right_data.lower()

    def set_history(self, history_dict):
        self.history_dict = history_dict
        self.invalidate() # Trigger resort/refilter



class ModernMoodleApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MoodleDown Modern")
        self.resize(600, 750) # Thinner window, taller for list

        
        self.settings = QSettings("MoodleDown", "MoodleDownApp")
        self.all_courses = {}
        self.current_course = None
        self.file_history = {}
        
        self.load_history()
        self.init_data()
        self.setup_ui()
        self.check_browser()

    def load_history(self):
        try:
            _, _, log_file = setup_logging()
            self.file_history = {}
            if os.path.exists(log_file):
                with open(log_file, 'r', encoding='utf-8') as f:
                    for idx, line in enumerate(f):
                        parts = line.strip().split('\t')
                        if len(parts) >= 2:
                            path = parts[1].strip()
                            norm_path = os.path.normpath(path).lower()
                            if norm_path not in self.file_history:
                                self.file_history[norm_path] = idx
        except Exception as e:
            print(f"Error loading history for sorting: {e}")

    def init_data(self):
        # Load courses
        courses_data = self.settings.value("courses", [])
        # Handle format extracted from loop in original: list of tuples/lists
        self.all_courses = {str(item[0]): str(item[1]) for item in courses_data if isinstance(item, (list, tuple)) and len(item) == 2}
        if not self.all_courses:
            self.all_courses = COURSES.copy()

    def check_browser(self):
        if not chromium_ready():
             QMessageBox.warning(self, "Browser Missing", "Chromium browser is not installed. Please try to run the original GUI or command line once to install it, or wait for auto-fill to prompt you.")

    def setup_ui(self):
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        
        self.dashboard = self.create_dashboard()
        self.course_view = self.create_course_view()
        
        self.stack.addWidget(self.dashboard)
        self.stack.addWidget(self.course_view)

    def create_dashboard(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        # Header
        header = QHBoxLayout()
        header.setContentsMargins(0, 10, 0, 20)
        logo = QLabel("🎓 MoodleDown")
        logo.setStyleSheet("font-size: 28px; font-weight: bold; color: #00bcd4; font-family: 'Segoe UI', sans-serif;") 
        header.addWidget(logo)
        header.addStretch()
        
        settings_btn = QPushButton("Settings")
        settings_btn.setIcon(QIcon.fromTheme("preferences-system"))
        settings_btn.clicked.connect(self.open_settings)
        header.addWidget(settings_btn)
        layout.addLayout(header)
        
        # Controls
        controls = QHBoxLayout()
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search courses...")
        self.search_input.textChanged.connect(self.filter_courses)
        
        self.year_combo = QComboBox()
        self.year_combo.addItems([
            "All Years", 
            "2023-24", "2024-25", "2025-26", "2026-27", 
            "2027-28", "2028-29", "2029-30", "2030-31", 
            "2031-32", "2032-33", "2033-34", "2034-35", 
            "2035-36", "2036-37"
        ])
        saved_year = self.settings.value("year_range", "2025-26")
        idx = self.year_combo.findText(saved_year)
        if idx >= 0: self.year_combo.setCurrentIndex(idx)
        else: self.year_combo.setCurrentText("2025-26") # Default
        self.year_combo.currentTextChanged.connect(self.filter_courses)
        
        autofill_btn = QPushButton("Auto-fill from Moodle")
        autofill_btn.setProperty('class', 'primary')
        autofill_btn.clicked.connect(self.run_autofill)
        
        controls.addWidget(self.search_input, 2)
        controls.addWidget(self.year_combo, 1)
        controls.addWidget(autofill_btn)
        layout.addLayout(controls)
        
        # Course List
        self.course_list_widget = QListWidget()
        self.course_list_widget.setSelectionMode(QAbstractItemView.ExtendedSelection) # Allow multiple selection
        # Ensure we can select multiple items by drag or ctrl+click
        self.course_list_widget.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.course_list_widget.itemDoubleClicked.connect(self.open_course_detail)
        self.course_list_widget.itemSelectionChanged.connect(self.update_dashboard_actions)
        layout.addWidget(self.course_list_widget)
        
        # Populate list
        self.refresh_course_list()
        
        # Dashboard Actions
        action_bar = QHBoxLayout()
        self.status_label = ElidedLabel("Ready")
        action_bar.addWidget(self.status_label, 1)
        
        self.download_selected_btn = QPushButton("Download Selected")
        self.download_selected_btn.setEnabled(False)
        self.download_selected_btn.setProperty('class', 'success')
        self.download_selected_btn.clicked.connect(self.download_selected)
        action_bar.addWidget(self.download_selected_btn)
        
        layout.addLayout(action_bar)
        
        # Progress Bar (hidden by default)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        return page

    def create_course_view(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        
        # Header
        header = QHBoxLayout()
        back_btn = QPushButton("Back")
        back_btn.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        header.addWidget(back_btn)
        
        self.detail_title = QLabel("Course Name")
        self.detail_title.setStyleSheet("font-size: 20px; font-weight: bold;")
        header.addWidget(self.detail_title)
        header.addStretch()

        self.download_course_btn = QPushButton("Download/Update Course")
        self.download_course_btn.setProperty('class', 'success')
        self.download_course_btn.clicked.connect(lambda: self.download_selected(single_course=True))
        
        open_folder_btn = QPushButton("Open Folder")
        open_folder_btn.clicked.connect(self.open_current_folder)
        
        header.addWidget(self.download_course_btn)
        header.addWidget(open_folder_btn)
        
        layout.addLayout(header)
        
        # Content - File Tree only
        self.file_model = QFileSystemModel()
        self.file_model.setRootPath(QDir.rootPath())
        
        # Setup Proxy Model for ZIP filtering and History sorting
        self.proxy_model = HistorySortProxyModel(history_dict=self.file_history)
        self.proxy_model.setSourceModel(self.file_model)
        
        self.tree_view = QTreeView()
        self.tree_view.setModel(self.proxy_model)
        self.tree_view.setSortingEnabled(True)
        self.tree_view.sortByColumn(0, Qt.AscendingOrder)
        self.tree_view.setColumnWidth(0, 500)
        self.tree_view.setColumnHidden(1, True) # Hide Size
        self.tree_view.setColumnHidden(2, True) # Hide Type
        self.tree_view.doubleClicked.connect(self.open_file) # Note: index will be proxy index, need mapping in handler
        
        # Connect to directoryLoaded to handle expansion after async load
        self.file_model.directoryLoaded.connect(self.on_directory_loaded)
        
        layout.addWidget(self.tree_view)
        
        return page
        
        return page

    def refresh_course_list(self):
        self.course_list_widget.clear()
        search = self.search_input.text().lower()
        year = self.year_combo.currentText()
        if year == "All Years": year = ""
        
        for name in sorted(self.all_courses.keys()):
            url = self.all_courses[name]
            
            # Simple Filter
            if search and search not in name.lower(): continue
            if year and year not in url: continue
            
            # Use custom widget item
            item = QListWidgetItem()
            # item.setText(name) # Text handled by widget, but needed for sorting/searching if using default
            item.setData(Qt.UserRole, (name, url)) # Store data
            item.setSizeHint(QSize(0, 100)) # Card height
            
            # Try to find last updated time
            last_updated_str = None
            base_path = self.settings.value("default_location", get_downloads_folder())
            
            # Reconstruct folder name logic: name or id fallback
            safe_name = sanitize_folder_name(name)
            folder_path = os.path.join(base_path, safe_name)
            
            # If folder doesn't exist by name, maybe try ID? 
            # (Current logic in file_operations mostly relies on name if passed, or ID if not. 
            #  Here we assume name is main key)
            if os.path.isdir(folder_path):
                try:
                    mtime = os.path.getmtime(folder_path)
                    dt = datetime.fromtimestamp(mtime)
                    last_updated_str = dt.strftime("%Y-%m-%d")
                except:
                    pass

            self.course_list_widget.addItem(item)
            
            # Create Card Widget
            card = CourseCard(name, url, last_updated=last_updated_str)
            self.course_list_widget.setItemWidget(item, card)

    def filter_courses(self):
        self.refresh_course_list()

    def update_dashboard_actions(self):
        count = len(self.course_list_widget.selectedItems())
        self.download_selected_btn.setEnabled(count > 0)
        self.download_selected_btn.setText(f"Download ({count})")

    def open_settings(self):
        dlg = SettingsDialog(self, self.settings)
        dlg.exec_()
        # Refresh logic potentially needed if saving impacts UI directly

    def run_autofill(self):
        # Check credentials
        user = self.settings.value("username", "")
        if not user:
            self.open_settings()
            user = self.settings.value("username", "")
            if not user: return

        # Get credentials securely
        pw = ""
        if KEYRING_AVAILABLE and self.settings.value("save_password", False, bool):
             try: pw = keyring.get_password("MoodleDownApp", user)
             except: pass
        
        if not pw:
            # Ask for password if not saved
            dlg = SettingsDialog(self, self.settings) # Reuse settings dialog for now or simple input?
            # Reusing settings dialog logic to ensure we get a password
            if dlg.exec_() != QDialog.Accepted: return
            user, pw = dlg.get_credentials()

        if not pw: 
            QMessageBox.warning(self, "Error", "Password required for auto-fill.")
            return

        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0) # Indeterminate
        self.status_label.setText("Autofilling...")
        
        self.worker = AutofillWorker(
            user, pw, 
            self.year_combo.currentText() if "All" not in self.year_combo.currentText() else "2025-26",
            self.settings.value("default_location", get_downloads_folder()),
            self.settings.value("headless", True, bool)
        )
        self.worker.signals.finished.connect(self.on_autofill_finished)
        self.worker.signals.status.connect(self.status_label.setText_safe)
        # Use int casting for progress if added later
        self.worker.start()

    def on_autofill_finished(self, success, msg, courses):
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 100)
        self.status_label.setText(msg)
        
        if success:
            added = 0
            for c in courses:
                if c['name'] not in self.all_courses:
                    self.all_courses[c['name']] = c['href']
                    added += 1
            
            if added > 0:
                self.settings.setValue("courses", list(self.all_courses.items()))
                self.refresh_course_list()
                QMessageBox.information(self, "Success", f"Added {added} new courses.")
            else:
                QMessageBox.information(self, "No New Courses", "No new courses found.")
        else:
            QMessageBox.warning(self, "Failed", msg)

    def download_selected(self, single_course=False):
        user, pw = self.get_credentials()
        if not user or not pw: return

        path = self.settings.value("default_location", get_downloads_folder())
        
        if single_course and self.current_course:
             targets = [self.current_course]
        else:
            selected_items = self.course_list_widget.selectedItems()
            targets = [item.data(Qt.UserRole) for item in selected_items]

        if not targets: return

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        if len(targets) == 1:
            name, url = targets[0]
            self.worker = DownloadWorker(url, name, user, pw, path, self.settings)
        else:
             # Ensure targets are (name, url) tuples
            self.worker = BatchDownloadWorker(targets, user, pw, path, self.settings)
            
        self.set_interface_enabled(False)
        self.worker.signals.progress.connect(lambda v: self.progress_bar.setValue(int(v)))
        self.worker.signals.status.connect(self.status_label.setText_safe)
        self.worker.signals.finished.connect(self.on_download_finished)
        self.worker.start()

    def set_interface_enabled(self, enabled):
        self.download_selected_btn.setEnabled(enabled)
        self.download_course_btn.setEnabled(enabled)
        # We could disable other things too, but mainly the download triggers
        if enabled:
            self.update_dashboard_actions() # Re-check selection state

    def on_download_finished(self, success, msg, summary=None):
        self.set_interface_enabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText("Ready")
        
        if summary is None:
            QMessageBox.information(self, "Done" if success else "Error", msg)
        else:
            dlg = DownloadSummaryDialog(summary, parent=self)
            dlg.exec_()
        
        # Reload history to capture new files
        self.load_history()
        self.proxy_model.set_history(self.file_history)

        # If in detail view, refresh file tree?
        if self.stack.currentIndex() == 1:
            self.update_file_tree(self.current_course[0])

    def get_credentials(self):
        user = self.settings.value("username", "")
        pw = ""
        if KEYRING_AVAILABLE and self.settings.value("save_password", False, bool) and user:
            try: pw = keyring.get_password("MoodleDownApp", user)
            except: pass
        
        if not user or not pw:
            dlg = SettingsDialog(self, self.settings)
            if dlg.exec_() == QDialog.Accepted:
                return dlg.get_credentials()
            return None, None
        return user, pw

    def open_course_detail(self, item):
        name, url = item.data(Qt.UserRole)
        self.current_course = (name, url)
        
        self.detail_title.setText(name)
        self.update_file_tree(name)
        
        self.stack.setCurrentIndex(1)

    def update_file_tree(self, course_name):
        base_path = self.settings.value("default_location", get_downloads_folder())
        # We need to find the folder name. It usually matches the course name but sanitized.
        # But we don't have the sanitizer function exposed easily here without importing 'create_course_folder' logic or 'sanitize_filename'.
        # We can iterate the directory to find a matching folder or just rely on 'create_course_folder' logic.
        # Let's import sanitize_filename from somewhere? content_extractor has it?
        # Actually create_course_folder in file_operations returns the path. 
        # But we need the URL to call it, which we have.
        
        from .file_operations import create_course_folder
        course_path = create_course_folder(self.current_course[1], base_path, course_name)
        
        if not os.path.exists(course_path):
             # Just show root with warning maybe? Or create it?
             # For viewing, we just want to see if it exists.
             # If not, maybe show empty or root.
             pass

        # Update proxy with current history
        self.proxy_model.set_history(self.file_history)

        # Map source index to proxy index
        root_index = self.file_model.index(course_path)
        proxy_root_index = self.proxy_model.mapFromSource(root_index)
        
        self.tree_view.setRootIndex(proxy_root_index)
        self.current_course_path = course_path
        
        # We can't just expandAll immediate because of async load, 
        # but if it was already loaded it might work.
        # The signal handler `on_directory_loaded` will ensure expansion happens.
        if self.file_model.isDir(root_index):
             self.tree_view.expandAll()
             # Force a delayed expansion to ensure view is ready
             QTimer.singleShot(200, self.tree_view.expandAll)
             QTimer.singleShot(1000, self.tree_view.expandAll) # Increased reliability

    def on_directory_loaded(self, path):
        # When a directory is loaded, if it is within our current view, expand it.
        # Check if the loaded path is our current root or a child of it.
        # Normalize paths for comparison
        if hasattr(self, 'current_course_path') and self.current_course_path:
             norm_path = os.path.normpath(path)
             norm_root = os.path.normpath(self.current_course_path)
             if norm_path.startswith(norm_root):
                 self.tree_view.expandAll()

    def open_file(self, index):
        # Map proxy index back to source index to get file path
        source_index = self.proxy_model.mapToSource(index)
        path = self.file_model.filePath(source_index)
        if os.path.isfile(path):
            os.startfile(path) # Windows only

    def open_current_folder(self):
        if hasattr(self, 'current_course_path') and os.path.isdir(self.current_course_path):
            os.startfile(self.current_course_path)

def main():
    # High DPI scaling
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
    
    app = QApplication(sys.argv)
    
    # Apply qt-material theme and then layer our custom CSS overrides.
    try:
        from qt_material import apply_stylesheet
        # The 'dark_teal.xml' theme looks premium and modern.
        apply_stylesheet(app, theme='dark_teal.xml')

        # qt-material 2.x does not auto-register the 'icon:' path for PyQt5.
        # Register it explicitly so SVG assets like icon:/primary/downarrow.svg resolve.
        qt_material_icons_path = os.path.join(os.path.expanduser('~'), '.qt_material', 'theme')
        if os.path.isdir(qt_material_icons_path):
            QDir.addSearchPath('icon', qt_material_icons_path)
        
        # Apply custom CSS on top
        css_path = get_resource_path('custom.css')
        with open(css_path, 'r') as f:
            custom_style = f.read()
            app.setStyleSheet(app.styleSheet() + custom_style)
            
    except Exception as e:
        print(f"Warning: Could not apply themes: {e}")
    
    window = ModernMoodleApp()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
