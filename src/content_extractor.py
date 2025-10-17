import re
import logging
import os
from typing import Dict, List, Set
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin


class ContentExtractor:
    """Extracts and processes content from Moodle pages"""

    def __init__(self, base_url: str):
        self.logger = logging.getLogger("MoodleDownPlaywright")
        self.base_url = base_url

    def extract_course_sections(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract course sections/categories from the Moodle page"""
        sections = []
        try:
            # Try various selectors for section elements
            section_elements = soup.find_all(['li', 'div'], class_=lambda c: c and (
                        'section' in c.split() or 'topic' in c.split() or 'week' in c.split()) and 'main' in c.split())
            if not section_elements:
                section_elements = soup.select('div.course-content > ul > li.section')
            if not section_elements:
                section_elements = soup.select('div#region-main .section')

            for section_idx, section_elem in enumerate(section_elements):
                section_name = None
                section_id = section_elem.get('id', f'section-{section_idx}')

                # Try to find section name
                name_candidates = section_elem.select(
                    'h3.sectionname, h4.sectionname, .section-title span.inplaceeditable')
                if name_candidates:
                    section_name = name_candidates[0].get_text(strip=True)
                else:
                    section_name = section_elem.get('aria-label')  # Fallback

                # Default/General section handling
                if not section_name:
                    if section_idx == 0:
                        general_keywords = ['כללי', 'general']
                        section_summary = section_elem.find(class_='summarytext')
                        is_general = section_summary and any(
                            kw in section_summary.get_text(strip=True).lower() for kw in general_keywords)
                        section_name = "General" if is_general else f"Section {section_idx}"
                    else:
                        section_name = f"Section {section_idx}"

                section_name = re.sub(r'[<>:"/\\|?*]', '_', section_name).strip()
                section_name = section_name if section_name else f"Section_{section_idx}"  # Ensure non-empty
                sections.append({'id': section_id, 'name': section_name, 'index': section_idx, 'element': section_elem})

            if not sections:  # Handle case where no specific sections found
                self.logger.warning("Could not find specific section elements. Treating entire page as one section.")
                sections.append({'id': 'course-content', 'name': 'Course Materials', 'index': 0, 'element': soup})

            self.logger.info(f"Found {len(sections)} sections in the course page.")
        except Exception as e:
            self.logger.exception(f"Error extracting course sections: {str(e)}")
            if not sections:
                sections.append({'id': 'default', 'name': 'Course Materials', 'index': 0, 'element': soup})

        return sections

    def extract_section_resources(self, section_elem, section_name: str, current_url: str) -> List[Dict]:
        """Extract downloadable resources from a course section"""
        resources = []
        activities = section_elem.find_all(['li', 'div'], class_=lambda c: c and 'activity' in c.split())

        for activity in activities:
            link = activity.find('a', href=True)
            if not link:
                continue

            url = link['href']
            if not url.startswith('http'):
                url = urljoin(current_url, url)

            resource_type = self._detect_resource_type(link, url)
            if resource_type in ['ignore', 'unknown', 'assignment', 'quiz', 'forum', 'url', 'feedback', 'choice',
                                 'questionnaire', 'hvp']:
                continue

            instance_name = ""
            instance_element = link.find('span', class_='instancename')
            if instance_element:
                instance_name = instance_element.get_text(strip=True)
                if not instance_name:  # Check nested span
                    nested_span = instance_element.find('span')
                    if nested_span:
                        instance_name = nested_span.get_text(strip=True)
            if not instance_name:
                instance_name = link.get_text(strip=True)  # Fallback to link text

            if instance_name:  # Clean name
                instance_name = re.sub(r"^(File|Folder| קובץ | תיקייה)\s*[:-]?\s*", "", instance_name,
                                       flags=re.IGNORECASE).strip()
                instance_name = re.sub(r'[<>:"/\\|?*\x00-\x1F]', '_', instance_name).strip('._ ')

            if instance_name and url and not url.endswith('#'):
                resources.append({
                    'name': instance_name,
                    'url': url,
                    'section': section_name,
                    'type': resource_type
                })

        return resources

    def _detect_resource_type(self, link_elem, url):
        """Detect resource type from link element and URL"""
        href = url.lower()

        # Check URL patterns
        if 'folder/view.php' in href or '/folder/' in href:
            return 'folder'
        if 'assign/view.php' in href:
            return 'assignment'  # Ignore
        if 'quiz/view.php' in href:
            return 'quiz'  # Ignore
        if 'forum/view.php' in href:
            return 'forum'  # Ignore
        if 'url/view.php' in href:
            return 'url'  # External link

        # Check parent element classes
        activity_instance = link_elem.find_parent(class_=lambda c: c and 'activityinstance' in c)
        if activity_instance:
            parent_classes = activity_instance.get('class', [])
            for pc in parent_classes:
                if pc == 'modtype_folder':
                    return 'folder'
                if pc == 'modtype_url':
                    return 'url'
                if pc in ['modtype_assign', 'modtype_quiz', 'modtype_forum', 'modtype_feedback', 'modtype_choice',
                          'modtype_questionnaire', 'modtype_hvp']:
                    return 'ignore'

        # Check icon for clues
        img = link_elem.find('img', class_='activityicon')
        if img and 'src' in img.attrs:
            doc_type = self._detect_doc_type_from_icon(img['src'].lower())
            if doc_type:
                return doc_type

        # Check file extension
        parsed_path = urlparse(href).path
        if parsed_path:
            _, ext = os.path.splitext(parsed_path)
            if ext and len(ext) > 1:
                ext_lower = ext.lower()[1:]
                common_exts = ['pdf', 'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx', 'zip', 'rar', '7z', 'txt', 'csv',
                               'jpg', 'jpeg', 'png', 'gif', 'mp4', 'mp3', 'mov']
                if ext_lower in common_exts:
                    return ext_lower

        if 'resource/view.php' in href:
            return 'document'  # Default for generic resource

        return 'unknown'  # Default if unsure

    def _detect_doc_type_from_icon(self, icon_src):
        """Identify document type based on icon URL"""
        if not icon_src:
            return None

        # Specific icon matches
        if '/pdf-' in icon_src:
            return 'pdf'
        if '/powerpoint-' in icon_src:
            return 'powerpoint'
        if '/document-' in icon_src:
            return 'word'
        if '/spreadsheet-' in icon_src:
            return 'excel'
        if '/archive-' in icon_src:
            return 'archive'
        if '/folder-' in icon_src:
            return 'folder'
        if '/text-' in icon_src:
            return 'text'
        if '/url-' in icon_src:
            return 'url'

        # Fallback patterns
        icon_patterns = {
            '/pdf': 'pdf',
            '/document': 'document',
            '/word': 'word',
            '/powerpoint': 'powerpoint',
            '/spreadsheet': 'excel',
            '/excel': 'excel',
            '/archive': 'archive',
            '/zip': 'archive',
            '/folder': 'folder'
        }

        for pattern, doc_type in icon_patterns.items():
            if pattern in icon_src:
                return doc_type

        return None

    def get_download_links(self, html_content: str, current_url: str, logged_urls: Set[str]) -> Dict[str, Dict]:
        """Extract downloadable links from page and filter against already downloaded URLs"""
        to_download = {}
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            sections = self.extract_course_sections(soup)

            if not sections:
                self.logger.error("No sections extracted from the page.")
                return {}

            for section in sections:
                section_resources = self.extract_section_resources(section['element'], section['name'], current_url)
                for resource in section_resources:
                    url = resource['url']
                    if url not in to_download:
                        to_download[url] = resource

            self.logger.info(f"Found {len(to_download)} potential downloadable items across {len(sections)} sections.")

            # Filter out already downloaded items
            initial_count = len(to_download)
            filtered_downloads = {url: item for url, item in to_download.items() if url not in logged_urls}
            filtered_count = initial_count - len(filtered_downloads)

            if filtered_count > 0:
                self.logger.info(f"Filtered out {filtered_count} items found in the verified central log.")
            else:
                self.logger.info("No items filtered based on the verified central log.")

            self.logger.info(f"{len(filtered_downloads)} items remain after filtering.")
            return filtered_downloads

        except Exception as e:
            self.logger.exception(f"Error extracting download links: {str(e)}")
            return {}