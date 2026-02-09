import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

class BrowserManager:
    """Manages Selenium WebDriver with a persistent Chrome profile."""
    
    def __init__(self):
        # Define profile path within auto_keys directory
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.profile_path = os.path.join(self.base_dir, "chrome_profile")
        
        if not os.path.exists(self.profile_path):
            os.makedirs(self.profile_path)
            
    def get_driver(self):
        """Initializes and returns a Chrome WebDriver instance."""
        chrome_options = Options()
        chrome_options.add_argument(f"user-data-dir={self.profile_path}")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        # Disable notifications and info bars
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--disable-popup-blocking")
        
        # Add experimental options to suppress permission prompts
        prefs = {
            "profile.default_content_setting_values.notifications": 2,
            "profile.default_content_setting_values.media_stream_mic": 1,
            "profile.default_content_setting_values.media_stream_camera": 1,
            "profile.default_content_setting_values.geolocation": 2
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.maximize_window()
        return driver

