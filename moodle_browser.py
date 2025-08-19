import logging
import re
from typing import Optional, Dict
from playwright.sync_api import sync_playwright, Playwright, Browser, BrowserContext, Page, APIRequestContext
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError


class MoodleBrowser:
    """Handles browser session, authentication and navigation for Moodle.

    Args:
        download_folder: Base folder used for downloads.
        year_range: Academic year segment appearing in Moodle URLs (e.g. '2024-25', '2025-26').
        headless: Whether to launch the browser headless.

    Notes:
        Historically the constructor order was (download_folder, year_range, headless). Some call
        sites (now fixed) passed a boolean second positional argument assuming it was *headless*.
        To remain backward compatible we keep the original ordering but strongly encourage callers
        to use keyword arguments.
    """
    BASE_URL_TEMPLATE = "https://moodle.huji.ac.il/{}"

    def __init__(self, download_folder: str, year_range: str = "2024-25", headless: bool = False) -> None:
        self.download_folder: str = download_folder
        self.year_range: str = str(year_range)
        # Normalise common user inputs like '2025-2026' -> '2025-26'
        self.year_range = self._normalize_year_range(self.year_range)
        self.base_url: str = self.BASE_URL_TEMPLATE.format(self.year_range)
        # Backwards compatibility: existing code referenced .BASE_URL
        self.BASE_URL: str = self.base_url  # noqa: N815 (maintain legacy attribute casing)
        self.headless: bool = bool(headless)
        self._playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.api_request_context: Optional[APIRequestContext] = None
        self.headers: Dict[str, str] = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"}
        self.logger = logging.getLogger("MoodleDownPlaywright")

    @staticmethod
    def _normalize_year_range(year_text: str) -> str:
        """Normalize various year range formats to the canonical 'YYYY-YY'.

        Accepts inputs like '2025-2026', '2025-26', '2025/2026'. If parsing fails it returns
        the original string unchanged so the user can still attempt navigation.
        """
        try:
            import re as _re
            m = _re.match(r"^(20\d{2})[-/](20)?(\d{2})$", year_text.strip())
            if not m:
                return year_text.strip()
            first = int(m.group(1))
            last_two = int(m.group(3)) if m.group(3) else (first + 1) % 100
            # Ensure rollover logic: if last_two seems inconsistent adjust heuristically
            if last_two != (first + 1) % 100:
                # Accept as-is if user deliberately entered something else
                pass
            return f"{first}-{last_two:02d}"
        except Exception:
            return year_text.strip()

    def setup_browser(self) -> None:
        """Initialize and configure the browser"""
        try:
            self._playwright = sync_playwright().start()
            try:
                self.browser = self._playwright.chromium.launch(headless=self.headless)
                self.logger.info("Launched Chromium browser")
            except Exception:
                self.logger.warning("Chromium launch failed, trying system Chrome")
                self.browser = self._playwright.chromium.launch(channel="chrome", headless=self.headless)
                self.logger.info("Launched system Chrome browser")

            self.context = self.browser.new_context(user_agent=self.headers["User-Agent"])
            self.logger.info("Browser context created")
            # Bypass some bot detection
            self.context.add_init_script(
                "navigator.webdriver = false; Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
            self.page = self.context.new_page()
            self.logger.info("New page created in context")
            self.page.set_default_timeout(30000)  # 30 seconds
            self.context.set_default_timeout(30000)
            self.api_request_context = self.context.request
            self.logger.info("API Request Context created, linked to browser state.")
            self.logger.info("Playwright browser initialized successfully")
        except PlaywrightError as e:
            self.logger.error(f"Failed to setup Playwright browser: {str(e)}")
            self.close()
            raise
        except Exception as e:
            self.logger.error(f"An unexpected error occurred during browser setup: {str(e)}")
            self.close()
            raise

    def login(self, username: str, password: str) -> bool:
        """Log in to Moodle with provided credentials"""
        if not self.page or not self.context:
            self.logger.error("Browser not set up correctly. Call setup_browser() first.")
            return False
        login_url: str = f"{self.BASE_URL}/login/index.php"
        dashboard_url_pattern: str = f"{self.BASE_URL}/my/*"

        try:
            self.logger.info(f"Navigating to login page: {login_url}")
            self.page.goto(login_url)

            self.logger.info("Attempting to click email login tab")
            email_tab_selector: str = "a[href='#pills-email']"
            self.page.locator(email_tab_selector).wait_for(state="visible", timeout=10000)
            self.page.locator(email_tab_selector).click()
            self.logger.info("Clicked email login tab.")

            # Form selectors
            email_form_selector: str = "form#f3"
            username_selector: str = f"{email_form_selector} #username"
            password_selector: str = f"{email_form_selector} #password"
            submit_button_selector: str = f"{email_form_selector} button.btn.btn-primary.g-recaptcha"

            self.page.locator(email_form_selector).wait_for(state="visible", timeout=10000)
            self.logger.info("Login form visible.")

            # Fill username and password fields directly
            self.page.locator(username_selector).wait_for(state="visible")
            self.page.locator(username_selector).fill(username)
            self.page.locator(password_selector).wait_for(state="visible")
            self.page.locator(password_selector).fill(password)

            self.logger.info(f"Entered credentials for user: {username}")

            # Click submit
            self.page.locator(submit_button_selector).wait_for(state="visible")
            self.page.locator(submit_button_selector).click()
            self.logger.info("Login form submitted.")

            # Verify login success
            try:
                self.page.wait_for_url(dashboard_url_pattern, timeout=25000)
                self.logger.info("Login successful: Navigated to dashboard.")
                return True
            except PlaywrightTimeoutError:
                current_url: str = self.page.url
                if dashboard_url_pattern.replace("*", "") in current_url:
                    self.logger.warning(
                        "Timeout waiting for full dashboard load, but URL seems correct. Assuming login success.")
                    return True
                else:
                    # Check for error messages as before
                    error_message_content = ""
                    try:  # type: ignore
                        error_locator = self.page.locator(
                            f"{email_form_selector} .loginerrors .error, .loginerrors .error, #loginerrormessage")
                        if error_locator.is_visible(timeout=1000):
                            error_message_content = error_locator.first.text_content(timeout=1000)
                    except PlaywrightTimeoutError:
                        pass
                    log_msg = f"Login failed. Error message found: {error_message_content.strip()}" if error_message_content else f"Login failed. Did not navigate to dashboard. Current URL: {current_url}"
                    self.logger.error(log_msg)
                    return False
        except PlaywrightTimeoutError as e:
            self.logger.error(f"Login timeout: {str(e)}\nCurrent URL: {self.page.url}")
            return False
        except PlaywrightError as e:
            self.logger.exception(f"Playwright error during login: {str(e)}")
            return False
        except Exception as e:
            self.logger.exception(f"Unexpected error during login: {str(e)}")
            return False

    def navigate_to_course(self, course_url: str) -> bool:
        """Navigate to a specific Moodle course page using its full URL"""
        if not self.page:
            self.logger.error("Page not available for navigation.")
            return False

        # Extract course ID from URL for verification and search
        course_id_match = re.search(r'[?&]id=(\d+)', course_url)
        if not course_id_match:
            self.logger.error(f"Could not extract a numeric course ID from the URL: {course_url}")
            return False
        course_id = course_id_match.group(1)
        dashboard_url: str = f"{self.BASE_URL}/my/"

        try:
            # Attempt 1: Direct Navigation
            self.logger.info(f"Attempting direct navigation to course: {course_url}")
            try:
                self.page.goto(course_url, wait_until='networkidle', timeout=20000)
                if f"id={course_id}" in self.page.url:
                    self.logger.info("Successfully navigated to course page via direct URL.")
                    course_title_selector: str = "h1"  # Often the course name is in H1
                    if self.page.locator(course_title_selector).first.is_visible(timeout=5000):
                        self.logger.info("Course title element found, navigation confirmed.")
                        return True
                    else:
                        self.logger.warning("Direct URL seemed correct, but course title element not found quickly.")
                else:
                    self.logger.info("Direct URL navigation resulted in a different page.")
            except (PlaywrightTimeoutError, PlaywrightError) as e:
                self.logger.warning(f"Issue during direct course navigation attempt: {e}")

            # Attempt 2: Search from Dashboard
            self.logger.info("Attempting navigation via dashboard search.")
            self.page.goto(dashboard_url, wait_until='networkidle')
            search_box_selector: str = "#searchinput"

            try:
                search_box = self.page.locator(search_box_selector)
                if search_box.is_visible(timeout=10000):
                    self.logger.info("Filling search box with course ID.")
                    search_box.fill(course_id)
                    search_box.press("Enter")
                    self.logger.info("Submitted search.")

                    self.page.wait_for_load_state('networkidle', timeout=15000)
                    course_link_selector: str = f"a[href*='course/view.php?id={course_id}']"
                    course_link = self.page.locator(course_link_selector).first

                    if course_link.is_visible(timeout=10000):
                        self.logger.info("Found course link in search results. Clicking...")
                        course_link.click()
                        self.page.wait_for_url(f"**/*id={course_id}*", wait_until='networkidle', timeout=15000)

                        if f"id={course_id}" in self.page.url:
                            self.logger.info("Successfully navigated to course page via search.")
                            return True
                        else:
                            self.logger.warning("Clicked search result, but didn't land on expected course URL.")
                    else:
                        self.logger.info("Course link not found in search results.")
                else:
                    self.logger.warning("Dashboard search box not found.")
            except (PlaywrightTimeoutError, PlaywrightError) as e:
                self.logger.warning(f"Issue during search-based navigation: {e}")

            # Fallback check
            if f"id={course_id}" in self.page.url and "/course/view.php" in self.page.url:
                self.logger.info("Navigation check: Already on the correct course page.")
                return True

            self.logger.error(
                f"Failed to navigate to course {course_id} using all methods.\nCurrent URL: {self.page.url}")
            return False
        except PlaywrightError as e:
            self.logger.exception(f"Playwright error during course navigation: {str(e)}")
            return False
        except Exception as e:
            self.logger.exception(f"Unexpected error during course navigation: {str(e)}")
            return False

    def get_page_content(self) -> str:
        """Fetch HTML content of the current page"""
        if not self.page:
            self.logger.error("Page not available.")
            return ""
        try:
            return self.page.content()
        except PlaywrightError as e:
            self.logger.error(f"Failed to get page content: {e}")
            return ""

    def close(self) -> None:
        """Close browser and clean up resources"""
        self.logger.info("Closing Playwright browser and resources...")
        for resource, name in [(self.context, "context"), (self.browser, "browser"), (self._playwright, "Playwright")]:
            if resource:
                try:
                    if name == "Playwright":
                        resource.stop()
                    else:
                        resource.close()
                    self.logger.info(f"{name.capitalize()} closed/stopped.")
                except Exception as e:
                    self.logger.warning(f"Error closing/stopping {name}: {e}")
        self.page, self.context, self.browser, self._playwright, self.api_request_context = None, None, None, None, None
        self.logger.info("Cleanup complete.")