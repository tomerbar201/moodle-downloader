"""
Basic tests for the Moodle Downloader.
"""

import unittest
import re
from data_structures import Course, DownloadResult


def extract_course_id_from_url(url: str):
    """Helper to extract the Moodle course ID from a URL using regex."""
    if not url:
        return None
    match = re.search(r'[?&]id=(\d+)', url)
    return match.group(1) if match else None


class TestMoodleDownloader(unittest.TestCase):
    
    def test_extract_course_id_from_url(self):
        """Test course ID extraction from various URL formats."""
        # Valid URLs
        self.assertEqual(extract_course_id_from_url(
            "https://moodle.huji.ac.il/2024-25/course/view.php?id=12345"), "12345")
        self.assertEqual(extract_course_id_from_url(
            "https://example.com/course.php?section=1&id=67890"), "67890")
        
        # Invalid URLs
        self.assertIsNone(extract_course_id_from_url(""))
        self.assertIsNone(extract_course_id_from_url("https://example.com/course"))
        self.assertIsNone(extract_course_id_from_url("https://example.com/?name=test"))
    
    def test_course_dataclass(self):
        """Test Course data structure."""
        course = Course("Test Course", "https://example.com/course?id=123")
        self.assertEqual(course.name, "Test Course")
        self.assertEqual(course.url, "https://example.com/course?id=123")
    
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
