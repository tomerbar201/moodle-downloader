
import re
from typing import Dict

# --- Default Courses ---
COURSES: Dict[str, str] = {
    "Introduction to Computer Science": "https://moodle.huji.ac.il/2024-25/course/view.php?id=12345",
    "Data Structures": "https://moodle.huji.ac.il/2024-25/course/view.php?id=23456"
}

# --- Helper function to validate course URL ---
def is_valid_course_url(url: str) -> bool:
    """Check if URL is a valid Moodle course URL."""
    if not url:
        return False
    # Check if it's a course URL - look for course/view.php pattern
    return bool(re.search(r'/course/view\.php', url))
