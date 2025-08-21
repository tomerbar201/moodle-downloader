"""
Data structures for the Moodle Downloader application.
Uses dataclasses to organize information cleanly.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class DownloadResult:
    """Stores the result of a file download operation."""
    success: bool
    message: str
    filepath: str = ""
    filesize: int = 0
    skipped: bool = False


@dataclass
class Course:
    """Represents a Moodle course with name and URL."""
    name: str
    url: str


@dataclass
class AppState:
    """Manages the GUI application state including credentials and settings."""
    username: str = ""
    password: str = ""
    courses: List[Course] = field(default_factory=list)
    download_folder: str = ""
    is_downloading: bool = False