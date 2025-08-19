from dataclasses import dataclass

@dataclass
class DownloadResult:
    """Stores information about a downloaded file"""
    success: bool
    message: str
    filepath: str = ""
    filesize: int = 0
    skipped: bool = False