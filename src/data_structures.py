
from dataclasses import dataclass
from typing import Optional

@dataclass
class DownloadResult:
    """Class to store the result of a download operation"""
    success: bool
    message: str
    filepath: Optional[str] = None
    filesize: Optional[int] = 0
