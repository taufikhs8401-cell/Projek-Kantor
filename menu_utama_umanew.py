import os
import sys
import time
from datetime import datetime
import sqlite3

import pdfplumber
from PyQt5 import QtCore, QtGui, QtWidgets, uic
from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import QApplication, QFileDialog, QMainWindow, QMessageBox
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager


class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(637, 173)
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 637, 18))
        self.menubar.setObjectName("menubar")
        self.menuUMA = QtWidgets.QMenu(self.menubar)
        self.menuUMA.setObjectName("menuUMA")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(MainWindow)
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)
        self.actionUMA = QtWidgets.QAction(MainWindow)
        self.actionUMA.setObjectName("actionUMA")
        self.actionSUSPEND = QtWidgets.QAction(MainWindow)
        self.actionSUSPEND.setObjectName("actionSUSPEND")
        self.actionUNSUSPEND = QtWidgets.QAction(MainWindow)
        self.actionUNSUSPEND.setObjectName("actionUNSUSPEND")
        self.actionInsert = QtWidgets.QAction(MainWindow)
        self.actionInsert.setObjectName("actionInsert")
        self.actionEdit = QtWidgets.QAction(MainWindow)
        self.actionEdit.setObjectName("actionEdit")
        self.actionDownloader = QtWidgets.QAction(MainWindow)
        self.actionDownloader.setObjectName("actionDownloader")
        self.actionBatch_Insert = QtWidgets.QAction(MainWindow)
        self.actionBatch_Insert.setObjectName("actionBatch_Insert")
        self.actionEXPORT = QtWidgets.QAction(MainWindow)
        self.actionEXPORT.setObjectName("actionEXPORT")
        self.menuUMA.addAction(self.actionInsert)
        self.menuUMA.addAction(self.actionEdit)
        self.menuUMA.addAction(self.actionDownloader)
        self.menuUMA.addAction(self.actionBatch_Insert)
        self.menuUMA.addAction(self.actionEXPORT)
        self.menubar.addAction(self.menuUMA.menuAction())

        self.MainWindow = MainWindow

        self.form_export = None
        self.form_downloader = None
        self.form_batch_insert = None
        self.form_edit = None
        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)
        

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "MainWindow"))
        self.menuUMA.setTitle(_translate("MainWindow", "UMA"))
        self.actionUMA.setText(_translate("MainWindow", "UMA"))
        self.actionSUSPEND.setText(_translate("MainWindow", "SUSPEND"))
        self.actionUNSUSPEND.setText(_translate("MainWindow", "UNSUSPEND"))
        self.actionInsert.setText(_translate("MainWindow", "Insert"))
        self.actionEdit.setText(_translate("MainWindow", "Edit"))
        self.actionDownloader.setText(_translate("MainWindow", "Downloader"))
        self.actionBatch_Insert.setText(_translate("MainWindow", "Batch Insert"))
        self.actionEXPORT.setText(_translate("MainWindow", "EXPORT"))
        
        #untuk menghubungan menu dengan fungsi
        self.actionEXPORT.triggered.connect(self.buka_data_export)
        self.actionDownloader.triggered.connect(self.buka_data_downloader)
        self.actionBatch_Insert.triggered.connect(self.buka_data_batch_insert)
        self.actionEdit.triggered.connect(self.buka_data_edit)

    def hide_all_forms(self):

        if self.form_export is not None:
            self.form_export.hide()

        if self.form_downloader is not None:
            self.form_downloader.hide()

        if self.form_batch_insert is not None:
            self.form_batch_insert.hide()

        if self.form_edit is not None:
            self.form_edit.hide()


    def buka_data_export(self):

    # Sembunyikan semua form lain
        self.hide_all_forms()

        # Sembunyikan Main Menu
        self.MainWindow.hide()

    # Jika Export belum pernah dibuat
        if self.form_export is None:
            self.form_export = ExportWindow()
            self.form_export.setWindowTitle("Export Data")

        # Jika sudah ada, cukup tampilkan lagi
        self.form_export.show()
        self.form_export.raise_()
        self.form_export.activateWindow()
        
        
    def buka_data_downloader(self):

        self.hide_all_forms()

        self.MainWindow.hide()

        if self.form_downloader is None:
            self.form_downloader = DownloaderWindow()
            self.form_downloader.setWindowTitle("UMA Downloader")

        self.form_downloader.show()
        self.form_downloader.raise_()
        self.form_downloader.activateWindow()

    def buka_data_batch_insert(self):
        
        self.hide_all_forms()

        self.MainWindow.hide()

        if self.form_batch_insert is None:
            self.form_batch_insert = BatchInsertWindow()
            self.form_batch_insert.setWindowTitle("Batch Insert")

        self.form_batch_insert.show()
        self.form_batch_insert.raise_()
        self.form_batch_insert.activateWindow()

    def buka_data_edit(self):
        self.hide_all_forms()

        self.MainWindow.hide()

        if self.form_edit is None:
            self.form_edit = EditWindow()
            self.form_edit.setWindowTitle("Edit Data")

        self.form_edit.show()
        self.form_edit.raise_()
        self.form_edit.activateWindow()

        



class ExportWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super(ExportWindow, self).__init__()
        uic.loadUi("D:/CODING/suspend/export.ui", self)
        self.setWindowTitle("Export Data")

        self.actionDownloader.triggered.connect(self.buka_data_downloader)
        self.actionBatch_Insert.triggered.connect(self.buka_data_batch_insert)
        self.actionEdit.triggered.connect(self.buka_data_edit)

        # Inisialisasi folder
        self.source_folder = r"D:/UMA/download_uma"
        self.output_folder = r"D:/UMA/txt_uma"
        
        # Hubungkan tombol
        self.btn_export.clicked.connect(self.btn_export_clicked)
        
        # Optional: tampilkan folder di UI jika ada label
        if hasattr(self, 'lbl_source'):
            self.lbl_source.setText(self.source_folder)
        if hasattr(self, 'lbl_target'):
            self.lbl_target.setText(self.output_folder)

    
    def buka_data_downloader(self):
        self.form_downloader 
        self.form_downloader = DownloaderWindow()
        self.form_downloader.setWindowTitle("UMA Downloader")
        self.form_downloader.show()
            

    def buka_data_batch_insert(self):
        self.form_batch_insert = BatchInsertWindow()
        self.form_batch_insert.setWindowTitle("Batch Insert")
        self.form_batch_insert.show()


    def buka_data_edit(self):
        self.form_edit = EditWindow()
        self.form_edit.setWindowTitle("Edit Data")
        self.form_edit.show()

    


    

    def btn_export_clicked(self):
        """Konversi semua file PDF dari folder sumber ke TXT di folder tujuan"""
        
        # Update folder dari UI jika ada (misal ada lineEdit)
        if hasattr(self, 'lineEdit_source'):
            self.source_folder = self.lineEdit_source.text()
        if hasattr(self, 'lineEdit_target'):
            self.output_folder = self.lineEdit_target.text()
        
        # Buat folder tujuan jika belum ada
        os.makedirs(self.output_folder, exist_ok=True)
        
        # Cek apakah folder sumber ada
        if not os.path.exists(self.source_folder):
            QMessageBox.warning(self, "Error", f"Folder sumber tidak ditemukan:\n{self.source_folder}")
            return
        
        # Cari semua file PDF di folder sumber
        pdf_files = [f for f in os.listdir(self.source_folder) if f.lower().endswith('.pdf')]
        
        if not pdf_files:
            QMessageBox.warning(self, "Info", f"Tidak ada file PDF di folder:\n{self.source_folder}")
            return
        
        success_count = 0
        fail_count = 0
        results = []
        
        # Proses setiap file PDF
        for filename in pdf_files:
            pdf_path = os.path.join(self.source_folder, filename)
            txt_filename = filename[:-4] + ".txt"  # ganti .pdf dengan .txt
            txt_path = os.path.join(self.output_folder, txt_filename)
            
            try:
                # Baca PDF dan ekstrak teks
                with pdfplumber.open(pdf_path) as pdf:
                    full_text = []
                    for page_num, page in enumerate(pdf.pages, start=1):
                        text = page.extract_text()
                        if text:
                            full_text.append(f"===== Page {page_num} =====\n{text}")
                        else:
                            full_text.append(f"===== Page {page_num} =====\n[No text extracted]")
                
                # Simpan ke file TXT
                with open(txt_path, "w", encoding="utf-8") as txt_file:
                    txt_file.write("\n\n".join(full_text))
                os.remove(pdf_path)
                
                success_count += 1
                
                
                
            except Exception as e:
                fail_count += 1
                
        
        # Tampilkan hasil
        summary = f"Konversi Selesai!\n\n Berhasil: {success_count} file\n\n Gagal: {fail_count}"
        
        if results:
            detail = "\n\n" + "\n".join(results[-50:])  # tampilkan max 50 file terakhir
            if len(results) > 50:
                detail = "\n\n" + "\n".join(results[:5]) + f"\n... dan {len(results)-50} file lainnya\n" + "\n".join(results[-5:])
            summary += detail
        
        QMessageBox.information(self, "Hasil Konversi", summary)
        
        # Print ke console untuk debugging
        print(summary)


class DownloaderWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super(DownloaderWindow, self).__init__()
        uic.loadUi("D:/CODING/suspend/downloader.ui", self)
        self.setWindowTitle("UMA Downloader")
        # Set default date to current date
        self.date_edit.setDate(QDate.currentDate())

        self.btn_run.clicked.connect(self.btn_run_clicked)
       
        self.MainWindow = MainWindow
        self.form_export = None
        
        self.form_batch_insert = None
        self.form_edit = None
        self.actionEXPORT.triggered.connect(self.buka_data_export)
        self.actionBatch_Insert.triggered.connect(self.buka_data_batch_insert)
        self.actionEdit.triggered.connect(self.buka_data_edit)

    def buka_data_export(self):
        self.form_export 
        self.form_export = ExportWindow()
        self.form_export.setWindowTitle("Export Data")
        self.form_export.show()
        
        
        

    def buka_data_batch_insert(self):
        self.form_batch_insert = BatchInsertWindow()
        self.form_batch_insert.setWindowTitle("Batch Insert")
        self.form_batch_insert.show()

        

    def buka_data_edit(self):
        self.form_edit = EditWindow()
        self.form_edit.setWindowTitle("Edit Data")
        self.form_edit.show()


        
        
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
    
    def rename_latest_pdf(folder, new_filename):
        pdf_files = [
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if f.lower().endswith(".pdf")
        ]

        if not pdf_files:
            return

        latest_file = max(pdf_files, key=os.path.getctime)

        safe_filename = "".join(
            c for c in new_filename
            if c.isalnum() or c in (" ", "-", "_", ".")
        )

        new_path = os.path.join(folder, safe_filename)

        counter = 1
        while os.path.exists(new_path):
            name, ext = os.path.splitext(safe_filename)
            new_path = os.path.join(
                folder,
                f"{name}_{counter}{ext}"
            )
            counter += 1

        os.rename(latest_file, new_path)

        print(f"Saved : {os.path.basename(new_path)}")

    def btn_run_clicked(self):
        # Setup download directory
        download_path = os.path.abspath("D:/UMA/download_uma")
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
                    "//*[contains(text(), 'Terapkan')]",
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
        

class BatchInsertWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super() .__init__()
        uic.loadUi("D:/CODING/suspend/batch_insert.ui", self)
        self.setWindowTitle("Batch Insert")

        self.MainWindow = MainWindow
        self.form_export = None
        self.form_downloader = None
        
        self.form_edit = None
        self.actionEXPORT.triggered.connect(self.buka_data_export)
        self.actionDownloader.triggered.connect(self.buka_data_downloader)
        self.actionEdit.triggered.connect(self.buka_data_edit)

    def buka_data_export(self):
        self.form_export 
        self.form_export = ExportWindow()
        self.form_export.setWindowTitle("Export Data")
        self.form_export.show()
        
        
        
        
    def buka_data_downloader(self):
        self.form_downloader 
        self.form_downloader = DownloaderWindow()
        self.form_downloader.setWindowTitle("UMA Downloader")
        self.form_downloader.show()
            
        
    def buka_data_edit(self):
        self.form_edit = EditWindow()
        self.form_edit.setWindowTitle("Edit Data")
        self.form_edit.show()

        
        self.btn_import.clicked.connect(self.browse_folder)

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Pilih Folder"
        )

        if folder:
            self.txt_path.setText(folder)
        

       

class EditWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super() .__init__()
        uic.loadUi("D:/CODING/suspend/menu_edit.ui", self)
        self.setWindowTitle("Edit Data")

        self.MainWindow = MainWindow
        self.form_export = None
        self.form_downloader = None
        self.form_batch_insert = None
        
        self.actionEXPORT.triggered.connect(self.buka_data_export)
        self.actionDownloader.triggered.connect(self.buka_data_downloader)
        self.actionBatch_Insert.triggered.connect(self.buka_data_batch_insert)
    
    def buka_data_export(self):
        self.form_export 
        self.form_export = ExportWindow()
        self.form_export.setWindowTitle("Export Data")
        self.form_export.show()
        
        
        
        
        
    def buka_data_downloader(self):
        self.form_downloader 
        self.form_downloader = DownloaderWindow()
        self.form_downloader.setWindowTitle("UMA Downloader")
        self.form_downloader.show()
            
        
        

    def buka_data_batch_insert(self):
        self.form_batch_insert = BatchInsertWindow()
        self.form_batch_insert.setWindowTitle("Batch Insert")
        self.form_batch_insert.show()

        
        


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    MainWindow = QtWidgets.QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(MainWindow)
    MainWindow.show()
    sys.exit(app.exec_())
