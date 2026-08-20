import os
import sys
import time
from datetime import datetime
import sqlite3
import re
import requests
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
from selenium.common.exceptions import (TimeoutException, NoSuchElementException, StaleElementReferenceException)



class Ui_MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi("D:/CODING/suspend/menu_utama_uma.ui", self)
        self.setWindowTitle("Menu Utama UMA")

        self.form_export = None
        self.form_downloader = None
        self.form_batch_insert = None
        self.form_edit = None
        self.form_downloader_teoretis = None
        self.form_export_2 = None
       
        #untuk menghubungan menu dengan fungsi
        self.actionEXPORT.triggered.connect(self.buka_data_export)
        self.actionDownloader.triggered.connect(self.buka_data_downloader)
        self.actionBatch_Insert.triggered.connect(self.buka_data_batch_insert)
        self.actionEdit.triggered.connect(self.buka_data_edit)
        self.actionDownloader_Teoretis.triggered.connect(self.buka_data_downloader_teoretis)
        self.actionEXPORT_Teoretis.triggered.connect(self.buka_data_export_teoretis)      


    def buka_data_export(self):
        if self.form_export is None:
            self.form_export = ExportWindow()

        self.form_export.show()
        self.hide()
        
    def buka_data_downloader(self):
        if self.form_downloader is None:
            self.form_downloader = DownloaderWindow()

        self.form_downloader.show()
        self.hide()

    def buka_data_batch_insert(self):
        if self.form_batch_insert is None:
            self.form_batch_insert = BatchInsertWindow()

        self.form_batch_insert.show()
        self.hide()

    def buka_data_edit(self):
        if self.form_edit is None:
            self.form_edit = EditWindow()

        self.form_edit.show()
        self.hide()

    def buka_data_downloader_teoretis(self):
        if self.form_downloader_teoretis is None:
            self.form_downloader_teoretis = DownloaderTeoretisWindow()

        self.form_downloader_teoretis.show()
        self.hide()

    def buka_data_export_teoretis(self):
        if self.form_export_teoretis is None:
            self.form_export_teoretis = ExportWindow()

        self.form_export_teoretis.show()
        self.hide()


class ExportWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super(ExportWindow, self).__init__()
        uic.loadUi("D:/CODING/suspend/export.ui", self)
        self.setWindowTitle("Export Data")
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
        
        self.form_downloader = None
        self.form_downloader_teoretis = None
        self.form_batch_insert = None
        self.form_edit = None
        self.form_export_teoretis = None
        
        self.actionDownloader.triggered.connect(self.buka_data_downloader)
        self.actionBatch_Insert.triggered.connect(self.buka_data_batch_insert)
        self.actionEdit.triggered.connect(self.buka_data_edit)
        self.actionDownloader_Teoretis.triggered.connect(self.buka_data_downloader_teoretis)
        self.actionEXPORT_Teoretis.triggered.connect(self.buka_data_export_teoretis)
        

    def buka_data_downloader(self):
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

    def buka_data_downloader_teoretis(self):
        self.form_downloader_teoretis = DownloaderTeoretisWindow()
        self.form_downloader_teoretis.setWindowTitle("Downloader Teoretis")
        self.form_downloader_teoretis.show()

    def buka_data_export_teoretis(self):
        self.form_export_teoretis = ExportTeoretisWindow()
        self.form_export_teoretis.setWindowTitle("Export Teoretis")
        self.form_export_teoretis.show()

    def rapikan_teks(self, text):
        # Gabungkan semua baris menjadi satu
        text = text.replace("\n", " ")
        text = re.sub(r"\s+", " ", text)

        # Pecah menjadi paragraf
        text = text.replace(
            "Dalam rangka perlindungan Investor",
            "\n\nDalam rangka perlindungan Investor"
        )

        text = text.replace(
            "Pengumuman Unusual Market Activity",
            "\n\nPengumuman Unusual Market Activity"
        )

        text = text.replace(
            "Sehubungan dengan terjadinya Unusual Market Activity",
            "\n\nSehubungan dengan terjadinya Unusual Market Activity"
        )

        # Poin tetap per baris
        text = re.sub(r"\s([a-d]\.)", r"\n\1", text)

        # Kalimat terakhir dibuat paragraf baru
        text = text.replace(
            "Seluruh keterbukaan informasi",
            "\n\nSeluruh keterbukaan informasi"
        )

        return text.strip()
    
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
                    if len(pdf.pages) >= 2:

                        page = pdf.pages[1]          # Halaman Bahasa Indonesia
                        text = page.extract_text()

                        if text:

                            # Awal teks yang ingin diambil
                            start = text.find("PENGUMUMAN")

                            # Akhir teks yang ingin diambil
                            end = text.find("website Bursa (www.idx.co.id).")

                            if start != -1 and end != -1:
                                hasil = text[start:end + len("website Bursa (www.idx.co.id).")]

                                hasil = self.rapikan_teks(hasil)

                                full_text.append(hasil)
                       
                
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
       
        self.form_export = None
        self.form_downloader_teoretis = None
        self.form_batch_insert = None
        self.form_edit = None
        self.form_export_teoretis = None
        
        self.actionEXPORT.triggered.connect(self.buka_data_export)
        self.actionDownloader_Teoretis.triggered.connect(self.buka_data_downloader_teoretis)
        self.actionBatch_Insert.triggered.connect(self.buka_data_batch_insert)
        self.actionEdit.triggered.connect(self.buka_data_edit)
        self.actionEXPORT_Teoretis.triggered.connect(self.buka_data_export_teoretis)
       
    def buka_data_export(self):
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

    def buka_data_downloader_teoretis(self):
        self.form_downloader_teoretis = DownloaderTeoretisWindow()
        self.form_downloader_teoretis.setWindowTitle("Downloader Teoretis")
        self.form_downloader_teoretis.show()

    def buka_data_export_teoretis(self):
        self.form_export_teoretis = ExportTeoretisWindow()
        self.form_export_teoretis.setWindowTitle("Export Teoretis")
        self.form_export_teoretis.show()


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

        #konversi target_date ke format yang sesuai dengan halaman web
        bulan_inggris = {
            "Jan": "Jan",
            "Feb": "Feb",
            "Mar": "Mar",
            "Apr": "Apr",
            "May": "Mei",
            "Jun": "Jun",
            "Jul": "Jul",
            "Aug": "Agt",
            "Sep": "Sep",
            "Oct": "Okt",
            "Nov": "Nov",
            "Dec": "Des"
        }

        for en, idn in bulan_inggris.items():
            target_date = target_date.replace(en, idn)
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
        self.btn_import.clicked.connect(self.browse_folder)

        self.form_export = None
        self.form_downloader_teoretis = None
        self.form_downloader = None
        self.form_edit = None
        self.form_export_teoretis = None
        
        self.actionEXPORT.triggered.connect(self.buka_data_export)
        self.actionDownloader_Teoretis.triggered.connect(self.buka_data_downloader_teoretis)
        self.actionDownloader.triggered.connect(self.buka_data_downloader)
        self.actionEdit.triggered.connect(self.buka_data_edit)
        self.actionEXPORT_Teoretis.triggered.connect(self.buka_data_export_teoretis)

    def buka_data_export(self):
        self.form_export 
        self.form_export = ExportWindow()
        self.form_export.setWindowTitle("Export Data")
        self.form_export.show()

    def buka_data_downloader_teoretis(self):
        self.form_downloader_teoretis = DownloaderTeoretisWindow()
        self.form_downloader_teoretis.setWindowTitle("Downloader Teoretis")
        self.form_downloader_teoretis.show()
        
    def buka_data_downloader(self):
        self.form_downloader 
        self.form_downloader = DownloaderWindow()
        self.form_downloader.setWindowTitle("UMA Downloader")
        self.form_downloader.show()
            
    def buka_data_edit(self):
        self.form_edit = EditWindow()
        self.form_edit.setWindowTitle("Edit Data")
        self.form_edit.show()

    def buka_data_export_teoretis(self):
        self.form_export_teoretis = ExportTeoretisWindow()
        self.form_export_teoretis.setWindowTitle("Export Teoretis")
        self.form_export_teoretis.show()


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

        self.form_export = None
        self.form_downloader_teoretis = None
        self.form_downloader = None
        self.form_batch_insert = None
        self.form_export_teoretis = None
        
        self.actionEXPORT.triggered.connect(self.buka_data_export)
        self.actionDownloader_Teoretis.triggered.connect(self.buka_data_downloader_teoretis)
        self.actionDownloader.triggered.connect(self.buka_data_downloader)
        self.actionBatch_Insert.triggered.connect(self.buka_data_batch_insert)
        self.actionEXPORT_Teoretis.triggered.connect(self.buka_data_export_teoretis)
    
    def buka_data_export(self):
        self.form_export 
        self.form_export = ExportWindow()
        self.form_export.setWindowTitle("Export Data")
        self.form_export.show()

    def buka_data_downloader_teoretis(self):
        self.form_downloader_teoretis = DownloaderTeoretisWindow()
        self.form_downloader_teoretis.setWindowTitle("Downloader Teoretis")
        self.form_downloader_teoretis.show()
        
    def buka_data_downloader(self):
        self.form_downloader 
        self.form_downloader = DownloaderWindow()
        self.form_downloader.setWindowTitle("UMA Downloader")
        self.form_downloader.show()
            
    def buka_data_batch_insert(self):
        self.form_batch_insert = BatchInsertWindow()
        self.form_batch_insert.setWindowTitle("Batch Insert")
        self.form_batch_insert.show()

    def buka_data_export_teoretis(self):
        self.form_export_teoretis = ExportTeoretisWindow()
        self.form_export_teoretis.setWindowTitle("Export Teoretis")
        self.form_export_teoretis.show()


class DownloaderTeoretisWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super(DownloaderTeoretisWindow, self).__init__()
        uic.loadUi("D:/CODING/suspend/downloader_teoretis.ui", self)
        self.setWindowTitle("Downloader Teoretis")
        # Set default date to current date
        self.date_edit.setDate(QDate.currentDate())
        self.btn_run_2.clicked.connect(self.btn_run_2_clicked)

        self.form_export = None
        self.form_batch_insert = None
        self.form_downloader = None
        self.form_edit = None
        self.form_export_teoretis = None
        
        self.actionEXPORT.triggered.connect(self.buka_data_export)
        self.actionBatch_Insert.triggered.connect(self.buka_data_batch_insert)
        self.actionDownloader.triggered.connect(self.buka_data_downloader)
        self.actionEdit.triggered.connect(self.buka_data_edit)
        self.actionEXPORT_Teoretis.triggered.connect(self.buka_data_export_teoretis)
        
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

    def buka_data_downloader(self):
        self.form_downloader 
        self.form_downloader = DownloaderWindow()
        self.form_downloader.setWindowTitle("UMA Downloader")
        self.form_downloader.show()

    def buka_data_export_teoretis(self):
        self.form_export_teoretis = ExportTeoretisWindow()
        self.form_export_teoretis.setWindowTitle("Export Teoretis")
        self.form_export_teoretis.show()

    def wait_for_download_complete(self, folder, timeout=30):
        """
        Menunggu sampai proses download PDF selesai.
        """

        start_time = time.time()

        while time.time() - start_time < timeout:

            # Cek apakah masih ada file .crdownload
            downloading_files = [
                f for f in os.listdir(folder)
                if f.lower().endswith(".crdownload")
            ]

            # Ambil file PDF
            pdf_files = [
                f for f in os.listdir(folder)
                if f.lower().endswith(".pdf")
            ]

            # Jika tidak ada proses download yang sedang berjalan
            # dan sudah ada file PDF
            if not downloading_files and pdf_files:
                print("Download selesai.")
                return True

            time.sleep(1)

        print("Timeout: Download tidak selesai dalam waktu yang ditentukan.")
        return False

    def setup_chrome_options(self, download_path):
        """Setup Chrome options for automatic downloading"""
        chrome_options = Options()

        prefs = {
            "download.default_directory": download_path,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "plugins.always_open_pdf_externally": True,
            "profile.default_content_setting_values.popups": 0,
            "profile.default_content_setting_values.automatic_downloads": 1
        }

        chrome_options.add_experimental_option("prefs", prefs)
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--start-maximized")
        # Add user agent to avoid detection
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
                
        return chrome_options
    
    def rename_latest_pdf(folder, kode_saham):
        pdf_files = [
            os.path.join(folder, f)
            for f in os.listdir(folder)
            if f.lower().endswith(".pdf")
        ]

        if not pdf_files:
            print("Tidak ada file PDF ditemukan.")
            return

        # Ambil file PDF yang paling baru
        latest_file = max(pdf_files, key=os.path.getctime)

        # Buat nama file
        new_filename = f"Harga Teoretis_{kode_saham}.pdf"

        # Bersihkan nama file
        safe_filename = "".join(
            c for c in new_filename
            if c.isalnum() or c in (" ", "-", "_", ".")
        )

        new_path = os.path.join(folder, safe_filename)

        # Jika file sudah ada
        counter = 1

        while os.path.exists(new_path):
            name, ext = os.path.splitext(safe_filename)

            new_path = os.path.join(folder, f"{name}_{counter}{ext}")

            counter += 1
        # Rename
        os.rename(latest_file, new_path)

        print(f"Saved: {os.path.basename(new_path)}")
        
    
    
    def btn_run_2_clicked(self):
        # KONFIGURASI
        keywords = ["Harga Teoretis"]

        download_path = os.path.abspath("D:/Teoretis/download_teoretis")

        os.makedirs(download_path, exist_ok=True)

        # AMBIL TANGGAL DARI UI
        selected_date = self.date_edit.date()
        target_date = selected_date.toString("dd MMM yyyy")
       
        # KONVERSI BULAN INGGRIS -> INDONESIA
        bulan_lengkap = {
            "Jan": "Januari",
            "Feb": "Februari",
            "Mar": "Maret",
            "Apr": "April",
            "May": "Mei",
            "Jun": "Juni",
            "Jul": "Juli",
            "Aug": "Agustus",
            "Sep": "September",
            "Oct": "Oktober",
            "Nov": "November",
            "Dec": "Desember"
        }

        for en, idn in bulan_lengkap.items():

            target_date = target_date.replace(en, idn)
        print(f"Target date: {target_date}")
       
        # SETUP CHROME
        chrome_options = self.setup_chrome_options(download_path)

        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        wait = WebDriverWait(driver, 30)

        # VARIABLE
        download_found = 0
        found = False

        try:
            # BUKA WEBSITE IDX
            url = ("https://www.idx.co.id/id/perusahaan-tercatat/keterbukaan-informasi/")
            driver.get(url)
            print("Membuka halaman IDX...")
            time.sleep(5)

            # INPUT KEYWORD
            for keyword in keywords:
                print(
                    f"\nMencari: {keyword} | "
                    f"Tanggal: {target_date}"
                )

                try:
                    keyword_input = wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@placeholder='Kata kunci...']")))
                    keyword_input.clear()
                    keyword_input.send_keys(keyword)

                    print(
                        f"Keyword '{keyword}' "
                        f"berhasil dimasukkan"
                    )

                    # TEKAN ENTER
                    keyword_input.send_keys("\n")
                    time.sleep(3)

                except Exception as e:
                    print(f"Input keyword tidak ditemukan: "f"{e}")

            
            # KLIK TERAPKAN
            terapkan_selectors = [
                "//button[contains("
                "normalize-space(.),"
                "'Terapkan')]",

                "//span[contains("
                "normalize-space(.),"
                "'Terapkan')]",

                "//*[contains("
                "normalize-space(.),"
                "'Terapkan')]"
            ]

            terapkan_clicked = False

            for selector in terapkan_selectors:
                try:
                    button = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, selector)))
                    driver.execute_script("arguments[0].click();", button)

                    print("Tombol Terapkan berhasil diklik.")
                    terapkan_clicked = True
                    time.sleep(5)

                    break
                except Exception:
                    continue

            if not terapkan_clicked:
                print("Tombol Terapkan tidak ditemukan.")

            

                # AMBIL SEMUA ELEMEN TIME
                time_elements = driver.find_elements(By.XPATH,"//time")

                print(f"Total elemen tanggal ditemukan: "f"{len(time_elements)}")

                if not time_elements:
                    print("Tidak ada elemen tanggal ""di halaman ini.")

                # LOOP SETIAP DATA
                for i, time_element in enumerate(time_elements, 1):
                    try:
                        # AMBIL TANGGAL
                        row_date = (time_element.text.strip())

                        print(f"Row {i}: Date = "f"{row_date}")

                        # =========================================
                        # AMBIL TANGGAL SAJA
                        #
                        # Contoh:
                        #
                        # 20 Juli 2026 21:00:00
                        #
                        # menjadi:
                        #
                        # 20 Juli 2026
                        # =========================================

                        match_date = re.search(
                            r'(\d{1,2}\s+'
                            r'[A-Za-z]+\s+'
                            r'\d{4})',
                            row_date
                        )

                        if not match_date:
                            print("Format tanggal tidak ""dikenali.")
                            continue

                        row_date_only = (match_date.group(1).strip())

                        print(f"Row {i}: Date Only = "f"{row_date_only}")

                        
                        # BANDINGKAN TANGGAL
                        if (row_date_only.lower()!= target_date.lower()):

                            print(f"Row {i}: "f"tanggal tidak sesuai.")
                            continue

                        # TANGGAL DITEMUKAN
                        print(f"\n*** TANGGAL DITEMUKAN ***")

                        print(f"Target : {target_date}")

                        print(f"Found  : {row_date_only}")

                        # CARI CONTAINER DATA
                        try:
                            row = time_element.find_element(
                                By.XPATH,
                                "./ancestor::div["
                                ".//a[contains("
                                "@href,'.pdf') "
                                "or contains("
                                "@href,'.PDF')]"
                                "][1]"
                            )

                        except NoSuchElementException:

                            print("Container data tidak ""ditemukan.")
                            continue

                        # AMBIL TEKS ROW
                        row_text = row.text.strip()

                        print(f"Data row:\n{row_text}")

                        # AMBIL KODE SAHAM
                        # Contoh:
                        # (MLPT)

                        kode_saham = None

                        match = re.search(
                            r'\(([A-Z]{4})\)',
                            row_text
                        )

                        if match:
                            kode_saham = (match.group(1))
                        else:
                            match = re.search(
                                r'\[([A-Z]{4})\]',
                                row_text
                            )

                            if match:
                                kode_saham = (match.group(1))

                        if not kode_saham:
                            print("Kode saham tidak ""ditemukan.")
                            continue

                        print(f"Kode saham: "f"{kode_saham}")
                        
                        # CARI LINK PDF
                        try:
                            download_link = (row.find_element(By.XPATH,
                                    ".//a[contains("
                                    "@href,'.pdf') "
                                    "or contains("
                                    "@href,'.PDF')]"
                                )
                            )

                        except NoSuchElementException:
                            print("Link PDF tidak ditemukan.")
                            continue

                        print("Link PDF ditemukan.")

                        
                        # NAMA FILE
                        filename = (f"Harga Teoretis_"f"{kode_saham}.pdf")

                        print(f"Downloading: {filename}")

                        # SIMPAN FILE SEBELUM DOWNLOAD
                        existing_files = set(os.listdir(download_path))

                        # KLIK PDF
                        driver.execute_script("arguments[0].click();", download_link)

                        print("Download dimulai...")

                        # TUNGGU DOWNLOAD
                        downloaded_file = (self.wait_for_download_complete(download_path, existing_files, timeout=30))

                        if not downloaded_file:
                            print("Download gagal ""atau timeout.")

                            continue

                        print(f"Download selesai: "f"{os.path.basename(downloaded_file)}")

                        # RENAME
                        renamed_file = (
                            self.rename_latest_pdf(download_path, kode_saham, downloaded_file))

                        if renamed_file:

                            download_found += 1
                            print(f"Saved: "f"{os.path.basename(renamed_file)}")

                        found = True

                        break

                    except (StaleElementReferenceException) as e:

                        print(f"Row {i} berubah: {e}")

                        continue

                    except Exception as e:

                        print(f"Error processing row "f"{i}: {e}")

                        continue


                # JIKA SUDAH DITEMUKAN
                if found:
                    print("\nTanggal target berhasil ""ditemukan.")

                    

            # HASIL AKHIR
            print(" DOWNLOAD SUMMARY ")

            print(f"Target tanggal : {target_date}")

            print(
                f"Total files downloaded: "
                f"{download_found}"
            )

            print(
                f"Files saved in: "
                f"{download_path}"
            )

            if not found:
                print(
                    f"\nData dengan tanggal "
                    f"{target_date} tidak ditemukan."
                )

        except Exception as e:
            print(f"Error during execution: {e}")

        finally:
            time.sleep(2)
            driver.quit()
            print("Selesai!")


class ExportTeoretisWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super(ExportTeoretisWindow, self).__init__()
        uic.loadUi("D:/CODING/suspend/export_teoretis.ui", self)
        self.setWindowTitle("Export Teoretis")

        self.form_export = None
        self.form_downloader = None
        self.form_batch_insert = None
        self.form_edit = None
        self.form_downloader_teoretis = None
        
        self.actionEXPORT.triggered.connect(self.buka_data_export)
        self.actionBatch_Insert.triggered.connect(self.buka_data_batch_insert)
        self.actionEdit.triggered.connect(self.buka_data_edit)
        self.actionDownloader.triggered.connect(self.buka_data_downloader)
        self.actionDownloader_Teoretis.triggered.connect(self.buka_data_downloader_teoretis)
    
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

    def buka_data_downloader(self):
        self.form_downloader 
        self.form_downloader = DownloaderWindow()
        self.form_downloader.setWindowTitle("UMA Downloader")
        self.form_downloader.show()

    def buka_data_downloader_teoretis(self):
        self.form_downloader_teoretis = DownloaderTeoretisWindow()
        self.form_downloader_teoretis.setWindowTitle("Downloader Teoretis")
        self.form_downloader_teoretis.show()

    
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)

    window = Ui_MainWindow()
    window.show()

    sys.exit(app.exec_())
