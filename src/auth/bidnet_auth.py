import time
import logging
import json
import os
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
import requests

from config import Config

class BidNetAuthenticator:
    def __init__(self):
        self.session = requests.Session()
        self.driver = None
        self.authenticated = False
        self.logger = logging.getLogger(__name__)
        self.cookies_file = Path(Config.DATA_DIR) / "bidnet_cookies.json"
        
    def setup_driver(self):
        """Set up Chrome WebDriver with appropriate options"""
        chrome_options = Options()
        
        if Config.BROWSER_SETTINGS["headless"]:
            chrome_options.add_argument("--headless")
            
        chrome_options.add_argument(f"--window-size={Config.BROWSER_SETTINGS['window_size'][0]},{Config.BROWSER_SETTINGS['window_size'][1]}")
        chrome_options.add_argument(f"--user-agent={Config.BROWSER_SETTINGS['user_agent']}")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-extensions")
        
        # Initialize the driver with webdriver-manager
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.driver.implicitly_wait(10)
        
    def save_cookies(self):
        """Save cookies to file for reuse"""
        try:
            # Ensure data directory exists
            Path(Config.DATA_DIR).mkdir(exist_ok=True)
            
            # Get cookies from both Selenium and requests session
            selenium_cookies = self.driver.get_cookies() if self.driver else []
            requests_cookies = dict(self.session.cookies)
            
            cookie_data = {
                "selenium_cookies": selenium_cookies,
                "requests_cookies": requests_cookies,
                "timestamp": time.time()
            }
            
            with open(self.cookies_file, 'w') as f:
                json.dump(cookie_data, f, indent=2)
                
            self.logger.info(f"Cookies saved to {self.cookies_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save cookies: {str(e)}")
            return False
            
    def load_cookies(self):
        """Load cookies from file if they exist and are recent"""
        try:
            if not self.cookies_file.exists():
                self.logger.info("No saved cookies found")
                return False
                
            with open(self.cookies_file, 'r') as f:
                cookie_data = json.load(f)
                
            # Check if cookies are less than 24 hours old
            cookie_age = time.time() - cookie_data.get("timestamp", 0)
            if cookie_age > 86400:  # 24 hours
                self.logger.info("Saved cookies are too old, will re-authenticate")
                return False
                
            # Load cookies into requests session
            for name, value in cookie_data.get("requests_cookies", {}).items():
                self.session.cookies.set(name, value)
                
            self.logger.info("Cookies loaded from file")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to load cookies: {str(e)}")
            return False
            
    def load_cookies_to_selenium(self):
        """Load saved cookies into Selenium driver"""
        try:
            if not self.cookies_file.exists():
                return False
                
            with open(self.cookies_file, 'r') as f:
                cookie_data = json.load(f)
                
            selenium_cookies = cookie_data.get("selenium_cookies", [])
            
            # Navigate to domain first before setting cookies
            self.driver.get(Config.BASE_URL)
            
            # Add each cookie to the driver
            for cookie in selenium_cookies:
                try:
                    # Remove keys that Selenium doesn't accept
                    cookie_clean = {k: v for k, v in cookie.items() 
                                  if k in ['name', 'value', 'domain', 'path', 'secure', 'httpOnly']}
                    self.driver.add_cookie(cookie_clean)
                except Exception as e:
                    self.logger.debug(f"Could not add cookie {cookie.get('name', 'unknown')}: {str(e)}")
                    
            self.logger.info("Cookies loaded into Selenium driver")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to load cookies to Selenium: {str(e)}")
            return False
        
    def login(self):
        """Authenticate with BidNet Direct using SAML SSO"""
        if not Config.USERNAME or not Config.PASSWORD:
            raise ValueError("Username and password must be set in environment variables")
            
        try:
            self.setup_driver()
            self.logger.info("Starting BidNet Direct authentication")
            
            # Navigate to main page first
            self.driver.get(Config.BASE_URL)
            self.logger.info(f"Navigated to main page: {Config.BASE_URL}")
            
            # Wait for page to load
            wait = WebDriverWait(self.driver, 20)
            
            # Debug: Print page title and URL
            self.logger.info(f"Page title: {self.driver.title}")
            self.logger.info(f"Current URL: {self.driver.current_url}")
            
            # Find and click the Login button
            login_link_selectors = [
                "a[href*='login']",
                "a:contains('Login')",
                "button:contains('Login')",
                ".login",
                "#login",
                "[data-testid*='login']",
                "a[title*='Login']"
            ]
            
            login_link = None
            for selector in login_link_selectors:
                try:
                    if ":contains(" in selector:
                        # Use XPath for text-based selectors
                        xpath = f"//a[contains(text(), 'Login')] | //button[contains(text(), 'Login')]"
                        login_link = self.driver.find_element(By.XPATH, xpath)
                    else:
                        login_link = self.driver.find_element(By.CSS_SELECTOR, selector)
                    break
                except NoSuchElementException:
                    continue
                    
            if not login_link:
                self.logger.error("Could not find login button on main page")
                return False
                
            # Wait for login button to be clickable and click
            self.logger.info("Found login button, waiting for it to be clickable...")
            try:
                clickable_login = wait.until(EC.element_to_be_clickable(login_link))
                clickable_login.click()
            except TimeoutException:
                # Try JavaScript click as fallback
                self.logger.info("Normal click failed, trying JavaScript click...")
                self.driver.execute_script("arguments[0].click();", login_link)
            
            # Wait for redirect to login page
            time.sleep(3)
            
            self.logger.info(f"After login click - Current URL: {self.driver.current_url}")
            self.logger.info(f"After login click - Page title: {self.driver.title}")
            
            # Now look for username field on the login page
            username_selectors = [
                "input[name='j_username']",  # BidNet specific
                "input[id='j_username']",    # BidNet specific
                "input[name='username']",
                "input[type='email']",
                "input[id*='username']",
                "input[id*='email']",
                "input[class*='username']",
                "#username",
                "#email"
            ]
            
            username_field = None
            for selector in username_selectors:
                try:
                    username_field = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                    break
                except TimeoutException:
                    continue
                    
            if not username_field:
                self.logger.error("Could not find username field")
                return False
                
            # Look for password field
            password_selectors = [
                "input[name='j_password']",  # BidNet specific
                "input[id='j_password']",    # BidNet specific
                "input[name='password']",
                "input[type='password']", 
                "input[id*='password']",
                "#password"
            ]
            
            password_field = None
            for selector in password_selectors:
                try:
                    password_field = self.driver.find_element(By.CSS_SELECTOR, selector)
                    break
                except NoSuchElementException:
                    continue
                    
            if not password_field:
                self.logger.error("Could not find password field")
                return False
                
            # Enter credentials
            self.logger.info("Entering credentials")
            username_field.clear()
            username_field.send_keys(Config.USERNAME)
            
            password_field.clear() 
            password_field.send_keys(Config.PASSWORD)
            
            # Find and click login button
            login_selectors = [
                "button[type='submit']",
                "input[type='submit']",
                "button[id*='login']",
                "button[class*='login']",
                ".login-button",
                "#login-button"
            ]
            
            login_button = None
            for selector in login_selectors:
                try:
                    login_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                    break
                except NoSuchElementException:
                    continue
                    
            if not login_button:
                self.logger.error("Could not find login button")
                return False
                
            # Click login
            self.logger.info("Clicking login button")
            login_button.click()
            
            # Wait for redirect/authentication to complete
            time.sleep(5)
            
            # Check if we're successfully authenticated
            current_url = self.driver.current_url
            self.logger.info(f"Current URL after login: {current_url}")
            
            # Transfer cookies to requests session
            selenium_cookies = self.driver.get_cookies()
            for cookie in selenium_cookies:
                self.session.cookies.set(cookie['name'], cookie['value'])
                
            self.authenticated = True
            self.logger.info("Authentication successful")
            
            # Save cookies for future use
            self.save_cookies()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Authentication failed: {str(e)}")
            return False
        finally:
            if self.driver:
                self.driver.quit()
                
    def authenticate_with_cookies(self):
        """Try to authenticate using saved cookies"""
        self.logger.info("Attempting authentication with saved cookies...")
        
        # Try to load cookies into requests session
        if not self.load_cookies():
            return False
            
        # Test if the cookies work
        try:
            response = self.session.get(Config.SEARCH_URL)
            
            # Check if we're redirected to login (indicating auth failed)
            if "login" in response.url.lower() or response.status_code == 401:
                self.logger.info("Saved cookies are invalid, need fresh login")
                return False
                
            self.authenticated = True
            self.logger.info("✅ Authentication successful using saved cookies!")
            return True
            
        except Exception as e:
            self.logger.warning(f"Cookie authentication test failed: {str(e)}")
            return False
    
    def get_authenticated_session(self):
        """Return the authenticated requests session"""
        if not self.authenticated:
            # Try cookie authentication first
            if not self.authenticate_with_cookies():
                # Fall back to full login if cookies don't work
                if not self.login():
                    raise Exception("Authentication failed")
        return self.session
        
    def test_authentication(self):
        """Test if authentication is working by accessing a protected page"""
        if not self.authenticated:
            return False
            
        try:
            # Try to access the main dashboard or search page
            response = self.session.get(Config.SEARCH_URL)
            
            # Check if we're redirected to login (indicating auth failed)
            if "login" in response.url.lower() or response.status_code == 401:
                self.logger.warning("Authentication appears to have failed")
                return False
                
            self.logger.info("Authentication test successful")
            return True
            
        except Exception as e:
            self.logger.error(f"Authentication test failed: {str(e)}")
            return False
    
    def is_login_page(self, driver_or_url=None):
        """Detect if current page is a login page"""
        try:
            if driver_or_url is None and hasattr(self, 'driver') and self.driver:
                # Check current Selenium page
                current_url = self.driver.current_url
                page_title = self.driver.title
                page_source = self.driver.page_source
            elif isinstance(driver_or_url, str):
                # URL string provided
                current_url = driver_or_url
                page_title = ""
                page_source = ""
            else:
                # WebDriver provided
                current_url = driver_or_url.current_url
                page_title = driver_or_url.title
                page_source = driver_or_url.page_source
            
            # Check URL patterns
            login_url_patterns = [
                "login",
                "authentication", 
                "sso",
                "signin",
                "SAML2"
            ]
            
            # Check title patterns
            login_title_patterns = [
                "login",
                "sign in",
                "authentication",
                "sso"
            ]
            
            # Check if URL indicates login page
            for pattern in login_url_patterns:
                if pattern.lower() in current_url.lower():
                    return True
                    
            # Check if title indicates login page  
            for pattern in login_title_patterns:
                if pattern.lower() in page_title.lower():
                    return True
                    
            # Check for login form elements in page source
            if page_source and any(pattern in page_source.lower() for pattern in ['j_username', 'j_password', 'name="username"', 'type="password"']):
                return True
                
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking login page: {str(e)}")
            return False
    
    def auto_login_if_needed(self, driver=None):
        """Automatically login if we detect we're on a login page"""
        try:
            target_driver = driver or self.driver
            if not target_driver:
                self.logger.error("No driver available for auto-login")
                return False
                
            if self.is_login_page(target_driver):
                self.logger.info("🔄 Login page detected - attempting automatic login")
                
                # Use existing login logic but with current driver
                old_driver = self.driver
                self.driver = target_driver
                
                try:
                    success = self._perform_login_on_current_page()
                    if success:
                        self.logger.info("✅ Auto-login successful")
                        return True
                    else:
                        self.logger.error("❌ Auto-login failed")
                        return False
                finally:
                    self.driver = old_driver
            else:
                # Not on login page, we're good
                return True
                
        except Exception as e:
            self.logger.error(f"Auto-login error: {str(e)}")
            return False
    
    def _perform_login_on_current_page(self):
        """Perform login on current page (assumes we're already on login page)"""
        try:
            wait = WebDriverWait(self.driver, 20)
            
            # Look for username field
            username_selectors = [
                "input[name='j_username']",
                "input[id='j_username']",
                "input[name='username']",
                "input[type='email']",
                "input[id*='username']",
                "#username"
            ]
            
            username_field = None
            for selector in username_selectors:
                try:
                    username_field = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                    break
                except TimeoutException:
                    continue
                    
            if not username_field:
                self.logger.error("Could not find username field")
                return False
                
            # Look for password field
            password_selectors = [
                "input[name='j_password']",
                "input[id='j_password']", 
                "input[name='password']",
                "input[type='password']",
                "#password"
            ]
            
            password_field = None
            for selector in password_selectors:
                try:
                    password_field = self.driver.find_element(By.CSS_SELECTOR, selector)
                    break
                except:
                    continue
                    
            if not password_field:
                self.logger.error("Could not find password field")
                return False
                
            # Enter credentials
            self.logger.info("Entering credentials")
            username_field.clear()
            username_field.send_keys(Config.USERNAME)
            
            password_field.clear() 
            password_field.send_keys(Config.PASSWORD)
            
            # Find and click submit button
            submit_selectors = [
                "input[type='submit']",
                "button[type='submit']", 
                "button:contains('Sign In')",
                "button:contains('Login')",
                ".login-button",
                "#loginButton"
            ]
            
            submit_button = None
            for selector in submit_selectors:
                try:
                    submit_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                    break
                except:
                    continue
                    
            if submit_button:
                self.logger.info("Clicking login button")
                submit_button.click()
            else:
                # Try form submission
                password_field.submit()
                
            # Wait for redirect
            time.sleep(5)
            
            # Check if login was successful
            if not self.is_login_page(self.driver):
                self.logger.info("Login successful - no longer on login page")
                return True
            else:
                self.logger.error("Login may have failed - still on login page")
                return False
                
        except Exception as e:
            self.logger.error(f"Login on current page failed: {str(e)}")
            return False