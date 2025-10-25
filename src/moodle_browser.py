import logging
from typing import Optional
from playwright.sync_api import sync_playwright, Playwright, Browser, BrowserContext, Page, APIRequestContext
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError


class MoodleBrowser:
    """Handles browser session, authentication and navigation for Moodle"""
    BASE_URL = "https://moodle.huji.ac.il/2024-25"

    def __init__(self, download_folder: str, headless: bool = False, year_range: str = "2024-25"):
        self.download_folder = download_folder
        self.headless = headless
        self.year_range = year_range
        self.BASE_URL = f"https://moodle.huji.ac.il/{year_range}"
        self._playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.api_request_context: Optional[APIRequestContext] = None
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"}
        self.logger = logging.getLogger("MoodleDownPlaywright")

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

        login_url = f"{self.BASE_URL}/login/index.php"
        dashboard_url_pattern = f"{self.BASE_URL}/my/*"

        try:
            import random
            import time

            # Random delay before navigating to login page (1-3 seconds)
            time.sleep(random.uniform(0.2, 0.35))
            self.logger.info(f"Navigating to login page: {login_url}")
            self.page.goto(login_url)

            # Wait for a random time as a human would do while the page loads
            time.sleep(random.uniform(0.21, 0.32))

            # Click email login tab with human-like delay and randomized timing
            self.logger.info("Attempting to click email login tab")
            email_tab_selector = "a[href='#pills-email']"
            self.page.locator(email_tab_selector).wait_for(state="visible", timeout=10000)

            # Move mouse to tab with human-like motion before clicking
            self.page.locator(email_tab_selector).hover()
            time.sleep(random.uniform(0.3, 0.8))
            self.page.locator(email_tab_selector).click()
            self.logger.info("Clicked email login tab.")

            # Slight delay after clicking tab (as a human would wait for UI to update)
            time.sleep(random.uniform(0.5, 1.2))

            # Form selectors
            email_form_selector = "form#f3"
            username_selector = f"{email_form_selector} #username"
            password_selector = f"{email_form_selector} #password"
            submit_button_selector = f"{email_form_selector} button.btn.btn-primary.g-recaptcha"

            self.page.locator(email_form_selector).wait_for(state="visible", timeout=10000)
            self.logger.info("Login form visible.")

            # Fill username with human-like typing speed (not too fast)
            self.page.locator(username_selector).wait_for(state="visible")
            self.page.locator(username_selector).click()
            for char in username:
                self.page.locator(username_selector).type(char, delay=random.uniform(80, 150))
                time.sleep(random.uniform(0.02, 0.08))

            # Small pause between username and password (as a human would do)
            time.sleep(random.uniform(0.4, 1.0))

            # Focus on password field before typing (human behavior)
            self.page.locator(password_selector).wait_for(state="visible")
            self.page.locator(password_selector).click()

            # Type password with variable speed (some keys faster than others)
            for char in password:
                # Type a bit faster on letters, slower on symbols/numbers (human behavior)
                delay = random.uniform(60, 130) if char.isalpha() else random.uniform(90, 160)
                self.page.locator(password_selector).type(char, delay=delay)
                time.sleep(random.uniform(0.01, 0.05))

            self.logger.info(f"Entered credentials for user: {username}")

            # Short pause before clicking submit (decision time for a human)
            time.sleep(random.uniform(0.7, 1.8))

            # Hover over submit button before clicking (human behavior)
            self.page.locator(submit_button_selector).wait_for(state="visible")
            self.page.locator(submit_button_selector).hover()
            time.sleep(random.uniform(0.2, 0.6))
            self.page.locator(submit_button_selector).click()
            self.logger.info("Login form submitted.")

            # Verify login success
            try:
                # Increase timeout a bit since we're mimicking human behavior
                self.page.wait_for_url(dashboard_url_pattern, timeout=25000)
                self.logger.info("Login successful: Navigated to dashboard.")
                return True
            except PlaywrightTimeoutError:
                current_url = self.page.url
                if dashboard_url_pattern.replace("*", "") in current_url:
                    self.logger.warning(
                        "Timeout waiting for full dashboard load, but URL seems correct. Assuming login success.")
                    return True
                else:
                    # Check for error messages as before
                    error_message_content = ""
                    try:
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
        """Navigate to a specific Moodle course page using the course URL"""
        if not self.page:
            self.logger.error("Page not available for navigation.")
            return False

        if not course_url:
            self.logger.error("Course URL is empty.")
            return False

        try:
            # Direct Navigation to the provided course URL
            self.logger.info(f"Navigating to course: {course_url}")
            try:
                self.page.goto(course_url, wait_until='networkidle', timeout=20000)
                
                # Verify we're on a course page
                if "/course/view.php" in self.page.url:
                    self.logger.info("Successfully navigated to course page.")
                    course_title_selector = "h1"  # Often the course name is in H1
                    if self.page.locator(course_title_selector).first.is_visible(timeout=5000):
                        self.logger.info("Course title element found, navigation confirmed.")
                        return True
                    else:
                        self.logger.warning("Navigation seemed successful, but course title element not found quickly.")
                        return True  # Still consider success if we're on course page
                else:
                    self.logger.warning(f"Navigation resulted in unexpected page: {self.page.url}")
                    return False
            except (PlaywrightTimeoutError, PlaywrightError) as e:
                self.logger.error(f"Failed to navigate to course URL: {e}")
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

    def navigate_to_dashboard(self) -> bool:
        """Navigate to the Moodle dashboard page after login"""
        if not self.page:
            self.logger.error("Page not available for navigation.")
            return False
        
        dashboard_url = f"{self.BASE_URL}/my/"
        
        try:
            self.logger.info(f"Navigating to dashboard: {dashboard_url}")
            self.page.goto(dashboard_url, wait_until='networkidle', timeout=20000)
            
            # Verify we're on the dashboard
            if "/my/" in self.page.url:
                self.logger.info("Successfully navigated to dashboard.")
                return True
            else:
                self.logger.warning(f"Navigation resulted in unexpected page: {self.page.url}")
                return False
        except (PlaywrightTimeoutError, PlaywrightError) as e:
            self.logger.error(f"Failed to navigate to dashboard: {e}")
            return False

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