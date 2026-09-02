import os
from typing import Optional
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5 import uic
from PyQt5.QtCore import QDate
import sys
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

class MyWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi("D:/coding/suspend/downloader.ui", self)
        self.setWindowTitle("Downloader")
        
        # Set default date to 19 Feb 2026
        self.date_edit.setDate(QDate(2026, 2, 19))

        
        self.btn_run.clicked.connect(self.btn_run_clicked)
        
    def setup_chrome_options(self, download_path):
        """Setup Chrome options for automatic downloading"""
        chrome_options = Options()
        prefs = {
            "download.default_directory": download_path,
            "download.prompt_for_download": False,
            "plugins.always_open_pdf_externally": True,
            "profile.default_content_setting_values.popups": 0,
            "profile.default_content_setting_values.automatic_downloads": 1,
        }
        chrome_options.add_experimental_option("prefs", prefs)
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--start-maximized")
        # Add user agent to avoid detection
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        return chrome_options
    
    def wait_for_download_complete(self, download_path, timeout=30):
        """Wait for download to complete"""
        seconds = 0
        while seconds < timeout:
            # Check if any .crdownload or .part files exist (downloading files)
            downloading = any(f.endswith(('.crdownload', '.part')) for f in os.listdir(download_path))
            if not downloading:
                return True
            time.sleep(1)
            seconds += 1
        return False
    
    def btn_run_clicked(self):
        # Setup download directory
        download_path = os.path.abspath("D:/download_uma")
        if not os.path.exists(download_path):
            os.makedirs(download_path)
        
        # Get selected date from UI
        selected_date = self.date_edit.date()
        target_date = selected_date.toString("dd MMM yyyy")
        print(f"Target date: {target_date}")
        
        # Setup Chrome options
        chrome_options = self.setup_chrome_options(download_path)
        
        # Initialize driver
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()), 
            options=chrome_options
        )
        
        try:
            # Navigate to UMA page
            url = "https://www.idx.co.id/id/berita/unusual-market-activity-uma/"
            driver.get(url)
            
            # Wait for page to load
            wait = WebDriverWait(driver, 30)
            time.sleep(5)  # Additional wait for dynamic content
            
            # Click "Terapkan" button to load the table
            try:
                # Try multiple possible selectors for the Terapkan button
                terapkan_selectors = [
                    "//tbody/tr[1]/td[1]/span[1]",
                    "//button[contains(text(), 'Terapkan')]",
                    "//span[contains(text(), 'Terapkan')]",
                    "//*[contains(text(), 'Terapkan')]"
                ]
                
                terapkan_button = None
                for selector in terapkan_selectors:
                    try:
                        terapkan_button = wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                        if terapkan_button:
                            break
                    except:
                        continue
                
                if terapkan_button:
                    terapkan_button.click()
                    print("Clicked Terapkan button")
                    time.sleep(3)
                else:
                    print("Terapkan button not found, continuing anyway...")
                    
            except Exception as e:
                print(f"Error clicking Terapkan button: {e}")
            
            # Wait for table to load
            time.sleep(3)
            
            # Find all rows in the table
            rows = driver.find_elements(By.XPATH, '//table[@id="vgt-table"]/tbody/tr')
            print(f"Total rows found: {len(rows)}")
            
            # Process each row
            downloads_found = 0
            for i, row in enumerate(rows, 1):
                try:
                    # Get date from the row
                    date_element = row.find_element(By.XPATH, './/td[1]/span')
                    row_date = date_element.text.strip()
                    print(f"Row {i}: Date = {row_date}")
                    
                    # Check if date matches target (19 Feb 2026)
                    if target_date.lower() in row_date.lower():
                        print(f"Found matching date: {row_date}")
                        
                        # Find download link in this row
                        try:
                            # Look for PDF download link
                            download_link = row.find_element(By.XPATH, './/a[contains(@href, ".pdf")]')
                            
                            if download_link:
                                # Get announcement text for filename
                                announcement = row.find_element(By.XPATH, './/td[2]/span').text.strip()
                                
                                # Create filename
                                safe_announcement = "".join(c for c in announcement if c.isalnum() or c in (' ', '-', '_')).rstrip()
                                filename = f"{row_date} - {safe_announcement}.pdf"
                                
                                print(f"Downloading: {filename}")
                                
                                # Click download link
                                download_link.click()
                                downloads_found += 1
                                
                                # Wait for download to start and complete
                                time.sleep(3)
                                self.wait_for_download_complete(download_path, timeout=30)
                                
                                # Rename downloaded file
                                downloaded_files = [f for f in os.listdir(download_path) if f.endswith('.pdf')]
                                if downloaded_files:
                                    latest_file = max([os.path.join(download_path, f) for f in downloaded_files], key=os.path.getctime)
                                    new_file_path = os.path.join(download_path, filename)
                                    
                                    # If file exists, add number suffix
                                    counter = 1
                                    while os.path.exists(new_file_path):
                                        name, ext = os.path.splitext(filename)
                                        new_file_path = os.path.join(download_path, f"{name}_{counter}{ext}")
                                        counter += 1
                                    
                                    os.rename(latest_file, new_file_path)
                                    print(f"Saved as: {os.path.basename(new_file_path)}")
                                
                                time.sleep(2)  # Delay between downloads
                                
                        except Exception as e:
                            print(f"Error finding download link in row {i}: {e}")
                            
                except Exception as e:
                    print(f"Error processing row {i}: {e}")
                    continue
            
            print(f"\n=== Download Summary ===")
            print(f"Total files downloaded for {target_date}: {downloads_found}")
            print(f"Files saved in: {download_path}")
            
        except Exception as e:
            print(f"Error during execution: {e}")
            
        finally:
            # Keep browser open for a moment to ensure downloads complete
            time.sleep(5)
            driver.quit()

        

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MyWindow()
    window.show()
    sys.exit(app.exec_())