"""
Basic tests for the Moodle Downloader.
"""

import unittest
import re
from src.data_structures import Course, DownloadResult


def is_valid_course_url(url: str) -> bool:
    """Check if URL is a valid Moodle course URL."""
    if not url:
        return False
    # Check if it's a course URL - look for course/view.php pattern
    return bool(re.search(r'/course/view\.php', url))


class TestMoodleDownloader(unittest.TestCase):
    
    def test_is_valid_course_url(self):
        """Test course URL validation."""
        # Valid URLs
        self.assertTrue(is_valid_course_url(
            "https://moodle.huji.ac.il/2024-25/course/view.php?id=12345"))
        self.assertTrue(is_valid_course_url(
            "https://example.com/course/view.php?section=1&id=67890"))
        
        # Invalid URLs
        self.assertFalse(is_valid_course_url(""))
        self.assertFalse(is_valid_course_url("https://example.com/course"))
        self.assertFalse(is_valid_course_url("https://example.com/?name=test"))
        self.assertFalse(is_valid_course_url("https://example.com/course.php?id=123"))
    
    def test_course_dataclass(self):
        """Test Course data structure."""
        course = Course("Test Course", "https://example.com/course/view.php?id=123")
        self.assertEqual(course.name, "Test Course")
        self.assertEqual(course.url, "https://example.com/course/view.php?id=123")
    
    def test_download_result_dataclass(self):
        """Test DownloadResult data structure."""
        result = DownloadResult(True, "Success", "/path/to/file.pdf", 1024)
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Success")
        self.assertEqual(result.filepath, "/path/to/file.pdf")
        self.assertEqual(result.filesize, 1024)
        self.assertFalse(result.skipped)


if __name__ == '__main__':
    unittest.main()
