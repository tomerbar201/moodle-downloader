"""
Course extraction module for Moodle Downloader.
Extracts course list from Moodle dashboard HTML.
"""

from bs4 import BeautifulSoup
from typing import List, Dict


def extract_courses(html_content: str) -> list[dict]:
    """
    Parses HTML from a Moodle page to find the 'myoverview' block
    and extract the course names and their links.

    Args:
        html_content: A string containing the HTML of the page.

    Returns:
        A list of dictionaries, where each dictionary contains the 'name'
        and 'href' of a course. Returns an empty list if the block is not found.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    course_list = []

    # 1. Find the main section container using the data-block attribute
    overview_section = soup.find('section', attrs={'data-block': 'myoverview'})
    if overview_section:
        # 2. Find all list items that represent a course
        # The class 'course-listitem' is a good identifier for each row
        course_rows = overview_section.find_all('li', class_='course-listitem')

        for row in course_rows:
            # 3. Within each row, find the anchor tag (<a>) with the course name
            link_tag = row.find('a', class_='coursename')
            
            # 4. Extract the name and href if the tag is found
            if link_tag and link_tag.has_attr('href'):
                course_name = link_tag.get_text(strip=True)
                course_href = link_tag['href']
                
                course_list.append({
                    'name': course_name,
                    'href': course_href
                })

    return course_list
