import os
import sys
import time
from datetime import datetime
import sqlite3
import re
import traceback
from datetime import datetime as _dt
import mysql.connector
from mysql.connector import Error
import shutil
import requests
import xml.etree.ElementTree as ET
import pdfplumber
from PyQt5 import QtCore, QtGui, QtWidgets, uic
from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import QApplication, QFileDialog, QMainWindow, QMessageBox, QTableWidgetItem
from PyQt5.QtCore import Qt, QThread, pyqtSignal

from selenium import webdriver
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import (TimeoutException, NoSuchElementException, StaleElementReferenceException)
import logging
import xml.etree.ElementTree as ET

import traceback

# ==============================================================
# KONFIGURASI LOGGING YANG LEBIH ROBUST (untuk EXE)
# ==============================================================

def get_app_dir():
    """Dapatkan folder aplikasi (works untuk dev & PyInstaller EXE)."""
    if getattr(sys, 'frozen', False):
        # Mode EXE (PyInstaller)
        return os.path.dirname(sys.executable)
    else:
        # Mode script Python
        return os.path.dirname(os.path.abspath(__file__))

def get_log_dir():
    """Dapatkan folder log yang bisa ditulis (fallback berlapis)."""
    candidates = [
        os.path.join(get_app_dir(), "logs"),                        # folder EXE/logs
        os.path.join(os.path.expanduser("~"), "CPCA_Logs"),         # ~/CPCA_Logs
        os.path.join(os.environ.get("TEMP", "."), "CPCA_Logs"),     # %TEMP%\CPCA_Logs
    ]
    for path in candidates:
        try:
            os.makedirs(path, exist_ok=True)
            # Test write
            test_file = os.path.join(path, ".write_test")
            with open(test_file, "w") as f:
                f.write("ok")
            os.remove(test_file)
            return path
        except Exception:
            continue
    return "."  # fallback terakhir

LOG_DIR = get_log_dir()
LOG_FILE = os.path.join(
    LOG_DIR,
    f"cpca_{datetime.now().strftime('%Y%m%d')}.log"
)

# Simpan path log ke variabel global agar bisa diakses di mana saja
GLOBAL_LOG_FILE = LOG_FILE
APP_DIR = get_app_dir()

# Setup logger
logger = logging.getLogger("CPCA")
logger.setLevel(logging.DEBUG)

if logger.handlers:
    logger.handlers.clear()

from logging.handlers import RotatingFileHandler

try:
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
except Exception as e:
    # Kalau tidak bisa tulis log file, fallback ke console
    print(f"WARNING: Tidak bisa membuat log file di {LOG_FILE}: {e}")
    file_handler = logging.NullHandler()

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

formatter = logging.Formatter(
    '%(asctime)s | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)

logger.info("=" * 70)
logger.info("CPCA Scanner - Application Started")
logger.info(f"Frozen (EXE) : {getattr(sys, 'frozen', False)}")
logger.info(f"App Dir      : {APP_DIR}")
logger.info(f"Log File     : {LOG_FILE}")
logger.info(f"Python       : {sys.version}")
logger.info(f"CWD          : {os.getcwd()}")
logger.info("=" * 70)

def resource_path(relative_path):
    """ Dapatkan path absolut ke resource, bekerja untuk dev dan PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# ==============================================================
# ERROR HANDLER YANG LEBIH BAIK
# ==============================================================

class ErrorReporter:
    """Class untuk report error ke user, log file, dan MessageBox."""

    # Path file khusus untuk crash log (agar mudah ditemukan)
    CRASH_LOG = os.path.join(APP_DIR, "crash_report.txt")

    @staticmethod
    def _write_crash_file(error_type, error_msg, tb, context=""):
        """Tulis crash report ke file di folder EXE — mudah ditemukan user."""
        try:
            with open(ErrorReporter.CRASH_LOG, "a", encoding="utf-8") as f:
                f.write("=" * 70 + "\n")
                f.write(f"WAKTU     : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"ERROR     : {error_type}\n")
                f.write(f"PESAN     : {error_msg}\n")
                f.write(f"KONTEKS   : {context}\n")
                f.write(f"LOG FILE  : {GLOBAL_LOG_FILE}\n")
                f.write("-" * 70 + "\n")
                f.write("TRACEBACK:\n")
                f.write(tb + "\n")
                f.write("=" * 70 + "\n\n")
        except Exception:
            pass  # jangan sampai error handling-nya error

    @staticmethod
    def show_error_dialog(parent, title, error, context=""):
        """Tampilkan dialog error yang informatif."""
        error_type = type(error).__name__
        error_msg = str(error)
        tb = traceback.format_exc()

        # Log ke file
        logger.error(f"{context} | {error_type}: {error_msg}")
        logger.error(f"Traceback:\n{tb}")

        # Tulis crash file
        ErrorReporter._write_crash_file(error_type, error_msg, tb, context)

        # Tampilkan dialog
        try:
            msg = QtWidgets.QMessageBox(parent)
            msg.setIcon(QtWidgets.QMessageBox.Critical)
            msg.setWindowTitle(f"❌ {title}")
            msg.setText(f"<b>{error_type}</b>")
            msg.setInformativeText(error_msg[:500])
            msg.setDetailedText(
                f"Context: {context}\n\n"
                f"Error: {error_type}\n\n"
                f"Message: {error_msg}\n\n"
                f"Traceback:\n{tb}\n\n"
                f"Log file   : {GLOBAL_LOG_FILE}\n"
                f"Crash file : {ErrorReporter.CRASH_LOG}"
            )

            copy_btn = msg.addButton("📋 Copy Error", QtWidgets.QMessageBox.ActionRole)
            msg.addButton("Tutup", QtWidgets.QMessageBox.AcceptRole)

            msg.exec_()

            if msg.clickedButton() == copy_btn:
                clipboard = QtWidgets.QApplication.clipboard()
                clipboard.setText(f"{error_type}: {error_msg}\n\n{tb}")
        except Exception as e:
            print(f"Gagal tampil dialog: {e}")
            print(f"Original error: {error_type}: {error_msg}")

    @staticmethod
    def install_global_handler():
        """Install global exception handler untuk SEMUA error (main thread & thread)."""

        def global_handler(exctype, value, tb):
            error_msg = "".join(traceback.format_exception(exctype, value, tb))
            logger.critical(f"UNCAUGHT EXCEPTION:\n{error_msg}")

            # Tulis ke crash file
            ErrorReporter._write_crash_file(
                exctype.__name__, str(value), error_msg,
                context="Global uncaught exception"
            )

            # Tampilkan MessageBox jika app Qt sudah ada
            try:
                app = QtWidgets.QApplication.instance()
                if app:
                    msg = QtWidgets.QMessageBox()
                    msg.setIcon(QtWidgets.QMessageBox.Critical)
                    msg.setWindowTitle("❌ Aplikasi Error")
                    msg.setText(f"Terjadi kesalahan: {exctype.__name__}")
                    msg.setInformativeText(str(value)[:300])
                    msg.setDetailedText(
                        f"{error_msg}\n\n"
                        f"Log file   : {GLOBAL_LOG_FILE}\n"
                        f"Crash file : {ErrorReporter.CRASH_LOG}"
                    )
                    msg.exec_()
                else:
                    # Belum ada app Qt — print ke console
                    print("=" * 70, file=sys.stderr)
                    print("UNCAUGHT EXCEPTION (before Qt init):", file=sys.stderr)
                    print(error_msg, file=sys.stderr)
                    print("=" * 70, file=sys.stderr)
            except Exception:
                print(error_msg, file=sys.stderr)

            try:
                sys.__excepthook__(exctype, value, tb)
            except Exception:
                pass

        sys.excepthook = global_handler

        # Tambahan: handler untuk thread (Python 3.8+)
        try:
            import threading
            def thread_handler(args):
                global_handler(args.exc_type, args.exc_value, args.exc_traceback)
            threading.excepthook = thread_handler
        except Exception:
            pass


# Install global handler SEGERA
ErrorReporter.install_global_handler()

# ==============================================================
# INFO STARTUP — CEK FILE & FOLDER PENTING
# ==============================================================

def check_required_files():
    """Cek file .ui penting yang harus ada di folder EXE/script."""
    required_ui = [
        "menu_utama_uma.ui",
        "insert_uma.ui", "edit_uma.ui", "export.ui", "downloader.ui",
        "batch_insert.ui",
        "insert_etf.ui", "edit_etf.ui", "batch_etf.ui", "export_etf.ui",
        "insert_suspend.ui", "edit_suspend.ui",
        "downloader_suspend.ui", "batch_suspend.ui", "export_suspend.ui",
        "downloader_teoretis.ui",
    ]
    missing = []
    for ui in required_ui:
        path = resource_path(ui)
        if not os.path.exists(path):
            missing.append(ui)
    return missing

def print_startup_info():
    """Cetak info penting ke console & log saat aplikasi dijalankan."""
    print("=" * 70)
    print("  CPCA SCANNER DATA IQ PLUS")
    print("=" * 70)
    print(f"  Frozen (EXE) : {getattr(sys, 'frozen', False)}")
    print(f"  App Dir      : {APP_DIR}")
    print(f"  Log File     : {GLOBAL_LOG_FILE}")
    print(f"  Crash File   : {ErrorReporter.CRASH_LOG}")
    print(f"  Python       : {sys.version.split()[0]}")
    print(f"  CWD          : {os.getcwd()}")
    print("-" * 70)

    missing = check_required_files()
    if missing:
        print("  ⚠ FILE .ui BERIKUT TIDAK DITEMUKAN:")
        for m in missing:
            print(f"     - {m}")
        print("  ⚠ Aplikasi mungkin tidak berjalan dengan benar!")
    else:
        print("  ✓ Semua file .ui ditemukan")
    print("=" * 70)
    print()

print_startup_info()

# ==============================================================
# KONFIGURASI
# ==============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UI_FILE = os.path.join(BASE_DIR, "batch_etf.ui")
UI_EXPORT = os.path.join(BASE_DIR, "export_etf.ui")

# Konfigurasi Database MySQL - Server Remote 192.168.33.244
DB_CONFIG = {
    'host': '192.168.33.244',   # <-- Diubah dari localhost
    'database': 'cpca',
    'user': 'taufik',           # <-- User yang sudah dibuat di server
    'password': 'taufik',       # <-- Password user taufik
    'port': 3306,
    'charset': 'utf8mb4',
    'use_unicode': True,
    'autocommit': False
}

# BULAN INDONESIA → ANGKA
    # ============================================
BULAN_ID = {
    'januari': 1, 'februari': 2, 'maret': 3, 'april': 4,
    'mei': 5, 'juni': 6, 'juli': 7, 'agustus': 8,
    'september': 9, 'oktober': 10, 'november': 11, 'desember': 12
}

FOLDER_PATH = r'D:\IDX_Data\Suspend\downloads_suspend'


class BaseWindow(QtWidgets.QMainWindow):
    """
    Class induk untuk semua window.
    - Satu dict `self.forms` untuk semua form.
    - `wire_menu_actions()` otomatis connect semua action menu.
    - `buka_form(key)` untuk membuka form generik.
    """

    # Mapping: action name → (class name, window title, form key)
    FORM_MAP = {
         # ----- Menu UMA -----
        'actionInsert':              ('InsertUmaWindow',          'Insert UMA',          'insert_uma'),
        'actionEXPORT':              ('ExportWindow',             'Export Data',         'export'),
        'actionDownloader':          ('DownloaderWindow',         'UMA Downloader',      'downloader'),
        'actionBatch_Insert':        ('BatchInsertWindow',        'Batch Insert',        'batch_insert'),
        'actionEdit':                ('EditWindow',               'Edit Data',           'edit_uma'),

         # ----- Menu Teoretis -----
        'actionDownloader_Teoretis': ('DownloaderTeoretisWindow', 'Downloader Teoretis', 'downloader_teoretis'),
        'actionEXPORT_Teoretis':     ('ExportTeoretisWindow',     'Export Teoretis',     'export_teoretis'),

        #menu ETF
        'actionInsert_2':            ('InsertETFWindow',          'Insert ETF',          'insert_etf'),
        'actionEdit_2':              ('EditETFWindow',            'Edit ETF',            'edit_etf'),
        'actionBatch_Insert_2':      ('BatchETFWindow',           'Batch Insert ETF',    'batch_etf'),
        'actionExport':              ('ExportETFWindow',          'Export ETF',          'export_etf'),

        #menu Suspend
        'actionDownloader_3':        ('DownloaderSuspendWindow',  'Downloader Suspend',  'downloader_suspend'),
        'actionBatch_Insert_3':      ('BatchSuspendWindow',       'Batch Suspend',       'batch_suspend'),
        'actionExport_3':            ('ExportSuspendWindow',      'Export Suspend',      'export_suspend'),
        'actionInsert_3':            ('InsertSuspendWindow',      'Insert Suspend',      'insert_suspend'),
        'actionEdit_3':              ('EditSuspendWindow',        'Edit Suspend',        'edit_suspend'),
    }

    def __init__(self):
        super().__init__()  # panggil QMainWindow.__init__
        self.forms = {}     # dict: {form_key: instance_window}
        self.allowed_actions = None     # None = boleh akses semua action. Set list untuk batasi.

    # Otomatis connect semua QAction ke buka_form.
    def wire_menu_actions(self):
        """Hubungkan action menu ke handler generik `buka_form`."""
        for action_name, (_, _, key) in self.FORM_MAP.items():
            if not hasattr(self, action_name):
                continue
            if self.allowed_actions and action_name not in self.allowed_actions:
                continue

            action = getattr(self, action_name)
            try:
                action.triggered.disconnect()
            except TypeError:
                pass
            action.triggered.connect(
                lambda checked=False, k=key: self.buka_form(k)
            )

    # Buka form berdasarkan key.
    def buka_form(self, key):
        """Buka form berdasarkan key. Sembunyikan window saat ini."""
        conf = None
        for action_name, (cls_name, title, k) in self.FORM_MAP.items():
            if k == key:
                conf = (cls_name, title, k)
                break

        if not conf:
            print(f"⚠ Form key tidak dikenal: {key}")
            return

        cls_name, title, k = conf
        self.tutup_semua_form(kecuali=k)

        if self.forms.get(k) is None:
            cls = globals().get(cls_name)
            if cls is None:
                print(f"⚠ Class {cls_name} tidak ditemukan di module")
                return
            self.forms[k] = cls()
            self.forms[k].setWindowTitle(title)
            # ⭐ Simpan referensi window pemanggil (parent menu)
            self.forms[k].parent_window = self

        self.forms[k].show()
        self.hide()      # ← Tetap hide, tapi nanti akan di-show kembali

    # Tutup semua form yang sedang terbuka. kecuali : form_key yang TIDAK boleh ditutup (opsional)
    def tutup_semua_form(self, kecuali=None):
        """Tutup semua form kecuali yang disebutkan."""
        for key, form in list(self.forms.items()):
            if key == kecuali:
                continue
            if form is not None:
                try:
                    form.close()
                except Exception:
                    pass
                self.forms[key] = None

    def _kembali_ke_parent(self):
        """Tampilkan kembali window pemanggil (parent) saat window ini ditutup."""
        parent = getattr(self, "parent_window", None)
        if parent is not None:
            try:
                parent.show()
                parent.raise_()
                parent.activateWindow()
            except Exception as e:
                print(f"⚠ Gagal show parent: {e}")
        else:
            # Fallback: cari Menu Utama di top-level widgets
            try:
                for widget in QtWidgets.QApplication.topLevelWidgets():
                    if widget.__class__.__name__ == "Ui_MainWindow":
                        widget.show()
                        widget.raise_()
                        widget.activateWindow()
                        break
            except Exception as e:
                print(f"⚠ Gagal fallback show: {e}")


#menu utama
class Ui_MainWindow(BaseWindow):
    def __init__(self):
        super().__init__()
        ui_path = resource_path("menu_utama_uma.ui")
        uic.loadUi(ui_path, self)
        self.setWindowTitle("Menu Utama")

        # Auto-connect semua menu action ke handler generik
        self.wire_menu_actions()

class InsertUmaWindow(BaseWindow):
    def __init__(self):
        super(InsertUmaWindow, self).__init__()
        current_dir = os.path.dirname(os.path.abspath(__file__))
        ui_path = resource_path("insert_uma.ui")
        uic.loadUi(ui_path, self)
        self.setWindowTitle("Insert UMA")

        # Auto-connect semua menu action ke handler generik
        self.wire_menu_actions()
        #defoult date
        self.date.setDate(QDate.currentDate())
        #tombol hendler add & clear
        self.pushButton.clicked.connect(self.pushButton_clicked)
        self.btn_clear.clicked.connect(self.btn_clear_clicked)

    def pushButton_clicked(self):
        # Mengambil data dari UI (nama variabel di UI tidak perlu diubah)
        isi_code = self.code.text()
        isi_company = self.company.text()
        isi_letter_number = self.letter_number.text()
        isi_date = self.date.date().toString("yyyy-MM-dd")

        print (isi_code)
        print (isi_company)
        print (isi_letter_number)
        print (isi_date)

        if not isi_code or not isi_company or not isi_letter_number or not isi_date:
                
            QMessageBox.warning(self, "Peringatan", "data harus di isi dengan lengkap.")
            return
        
        pesan = "Apakah data sudah benar?\n\n"
        result = QMessageBox.question(self, 'Konfirmasi', pesan,
                                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if result != QMessageBox.Yes:
            return   # FIX: jangan lanjut kalau No

        koneksi = None  # Inisialisasi di luar try agar bisa diakses di finally
        try:
            # =======================================================
            # KONEKSI KE DATABASE MYSQL
            # =======================================================
            koneksi = mysql.connector.connect(**DB_CONFIG)
            cursor = koneksi.cursor()

            # QUERY INSERT DISESUAIKAN DENGAN FIELD DATABASE MYSQL
            perintahSQL = """
                INSERT INTO ca_uma (
                    code,
                    company,
                    letter_number,
                    date
                ) VALUES (%s, %s, %s, %s)
            """
            
            # Data yang akan dimasukkan (urutan harus sama dengan kolom di atas)
            values = (
                isi_code,
                isi_company,
                isi_letter_number,
                isi_date
            )
            
            cursor.execute(perintahSQL, values)
            koneksi.commit()
            
            QMessageBox.information(self, "Sukses", "Data Berhasil Disimpan")
            
        except mysql.connector.Error as e:
            QMessageBox.critical(self, "Error Database", f"Gagal menyimpan data:\n\n{e}")
            print("Gagal menyimpan data :", e)

        finally:
            if koneksi and koneksi.is_connected():
                koneksi.close()

    def btn_clear_clicked(self):
        self.code.clear()
        self.company.clear()
        self.letter_number.clear()
        self.date.clear()

class EditWindow(BaseWindow):
    def __init__(self):
        super() .__init__()
        ui_path = resource_path("edit_uma.ui")
        uic.loadUi(ui_path, self)
        self.setWindowTitle("Edit Data")

        # Auto-connect semua menu action ke handler generik
        self.wire_menu_actions()

        # Handler tombol
        self.btn_clear.clicked.connect(self.clear_form)
        self.pushButton.clicked.connect(self.save_change_clicked)
        if hasattr(self, "check_id"):
            self.check_id.clicked.connect(self.check_id_clicked)

        self.current_uma_id = None
        self.set_form_locked(True)
        

    # ============================================================
    # DATABASE HELPER
    # ============================================================
    def get_connection(self):
        """Buat koneksi ke database MySQL server remote dengan timeout."""
        config = dict(DB_CONFIG)
        config['connection_timeout'] = 5   # ← 5 detik timeout
        return mysql.connector.connect(**config)

    def fetch_uma_by_id(self, uma_id):
        """Ambil data dari ca_uma berdasarkan ID."""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM ca_uma WHERE id = %s", (uma_id,))
            row = cursor.fetchone()
            cursor.close()
            return row
        except Exception as e:
            import traceback
            err = traceback.format_exc()
            print("=== ERROR fetch_uma_by_id ===")
            print(err)
            QtWidgets.QMessageBox.critical(
                self, "Database Error",
                f"Gagal membaca data:\n\n{type(e).__name__}: {e}"
            )
            return None
        finally:
            if conn:
                try:
                    if conn.is_connected():
                        conn.close()
                except Exception:
                    pass

    def update_uma(self, uma_id, data: dict) -> bool:
        """Update data di ca_uma berdasarkan ID."""
        if not data:
            return False

        set_clause = ", ".join([f"`{k}` = %s" for k in data.keys()])
        values = list(data.values()) + [uma_id]
        query = f"UPDATE ca_uma SET {set_clause}, revised_date = NOW() WHERE id = %s"

        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(query, values)
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            import traceback
            err = traceback.format_exc()
            print("=== ERROR update_uma ===")
            print(err)
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            QtWidgets.QMessageBox.critical(
                self, "Database Error",
                f"Gagal update data:\n\n{type(e).__name__}: {e}"
            )
            return False
        finally:
            if conn:
                try:
                    if conn.is_connected():
                        conn.close()
                except Exception:
                    pass

    # ============================================================
    # FORM LOCK / POPULATE / CLEAR
    # ============================================================
    def set_form_locked(self, locked=True):
        """Kunci/buka field input."""
        fields = ["code", "company", "letter_number", "date"]
        for name in fields:
            w = getattr(self, name, None)
            if w is not None:
                w.setEnabled(not locked)

        id_widget = getattr(self, "id", None)
        if id_widget is not None:
            id_widget.setEnabled(self.current_uma_id is None)

        if hasattr(self, "check_id"):
            self.check_id.setEnabled(self.current_uma_id is None)

        if hasattr(self, "pushButton"):
            self.pushButton.setEnabled(not locked)

    def populate_form(self, data: dict):
        print("=== populate_form data ===")
        for k, v in data.items():
            print(f"  {k!r}: {v!r}")

        if hasattr(self, "code"):
            self.code.setText(str(data.get("code") or ""))

        if hasattr(self, "company"):
            self.company.setText(str(data.get("company") or ""))

        if hasattr(self, "letter_number"):
            self.letter_number.setText(str(data.get("letter_number") or ""))

        if hasattr(self, "date") and data.get("date"):
            try:
                tgl = data["date"]
                if hasattr(tgl, "year"):
                    self.date.setDate(QDate(tgl.year, tgl.month, tgl.day))
                else:
                    self.date.setDate(QDate.fromString(str(tgl), "yyyy-MM-dd"))
            except Exception as e:
                print(f"  ⚠ Gagal set tanggal: {e}")

    def collect_form_data(self) -> dict:
        data = {}
        mapping = {
            "code": "code",
            "company": "company",
            "letter_number": "letter_number",
        }
        for widget_name, db_col in mapping.items():
            w = getattr(self, widget_name, None)
            if w is not None:
                if hasattr(w, "text"):
                    data[db_col] = w.text().strip()
                elif hasattr(w, "currentText"):
                    data[db_col] = w.currentText().strip()

        if hasattr(self, "date"):
            data["date"] = self.date.date().toString("yyyy-MM-dd")

        return data

    def clear_form(self):
        for name in ["code", "company", "letter_number"]:
            w = getattr(self, name, None)
            if w is not None and hasattr(w, "clear"):
                w.clear()

        if hasattr(self, "date"):
            self.date.setDate(QDate.currentDate())

        self.current_uma_id = None
        self.set_form_locked(True)

        id_widget = getattr(self, "id", None)
        if id_widget is not None:
            id_widget.clear()
            id_widget.setEnabled(True)

        if hasattr(self, "check_id"):
            self.check_id.setEnabled(True)

    # ============================================================
    # HANDLERS
    # ============================================================
    def check_id_clicked(self):
        """Handler tombol Check ID dengan error handling menyeluruh."""
        try:
            id_widget = getattr(self, "id", None)
            if id_widget is None:
                QtWidgets.QMessageBox.warning(
                    self, "Warning", "Widget ID tidak ditemukan di edit_uma.ui."
                )
                return

            uma_id_text = id_widget.text().strip()
            if not uma_id_text:
                QtWidgets.QMessageBox.warning(self, "Warning", "ID UMA tidak boleh kosong!")
                return

            try:
                uma_id = int(uma_id_text)
            except ValueError:
                QtWidgets.QMessageBox.warning(self, "Warning", "ID harus berupa angka!")
                return

            # Coba koneksi ke database
            try:
                data = self.fetch_uma_by_id(uma_id)
            except Exception as db_err:
                # Tangkap error koneksi / query secara spesifik
                err_msg = f"{type(db_err).__name__}: {db_err}"
                logger.error(f"DB Error di check_id_clicked: {err_msg}")
                logger.error(traceback.format_exc())

                QtWidgets.QMessageBox.critical(
                    self, "Database Error",
                    f"<b>Gagal membaca data dari database</b><br><br>"
                    f"{err_msg}<br><br>"
                    f"Pastikan:<br>"
                    f"1. Server MySQL di 192.168.33.244 aktif<br>"
                    f"2. Jaringan terhubung<br>"
                    f"3. User/password benar"
                )
                return

            if data is None:
                self.set_form_locked(True)
                self.current_uma_id = None
                QtWidgets.QMessageBox.information(
                    self, "Info", f"Data UMA dengan ID {uma_id} tidak ditemukan."
                )
                return

            self.current_uma_id = uma_id
            self.populate_form(data)
            self.set_form_locked(False)

        except Exception as e:
            err = traceback.format_exc()
            logger.critical(f"FATAL check_id_clicked:\n{err}")

            # Coba tampilkan dialog, tapi jangan sampai crash
            try:
                QtWidgets.QMessageBox.critical(
                    self, "Error",
                    f"Terjadi kesalahan:\n\n{type(e).__name__}: {e}\n\n"
                    f"Detail tersimpan di log:\n{LOG_FILE}"
                )
            except Exception:
                print(f"FATAL ERROR: {err}")

    def save_change_clicked(self):
        try:
            if self.current_uma_id is None:
                QtWidgets.QMessageBox.warning(
                    self, "Warning", "Tidak ada data yang sedang diedit."
                )
                return

            if not self.validate_input():
                return

            reply = QtWidgets.QMessageBox.question(
                self, "Konfirmasi",
                f"Simpan perubahan untuk UMA ID {self.current_uma_id}?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )
            if reply != QtWidgets.QMessageBox.Yes:
                return

            data = self.collect_form_data()
            success = self.update_uma(self.current_uma_id, data)

            if success:
                QtWidgets.QMessageBox.information(
                    self, "Sukses",
                    f"Data UMA ID {self.current_uma_id} berhasil diperbarui."
                )
                self.set_form_locked(True)
            else:
                QtWidgets.QMessageBox.warning(
                    self, "Gagal",
                    "Tidak ada perubahan yang disimpan atau terjadi kesalahan."
                )
        except Exception as e:
            import traceback
            err = traceback.format_exc()
            print("=== ERROR save_change_clicked ===")
            print(err)
            QtWidgets.QMessageBox.critical(
                self, "Error",
                f"Terjadi kesalahan:\n\n{type(e).__name__}: {e}"
            )

    def validate_input(self) -> bool:
        if hasattr(self, "code") and not self.code.text().strip():
            QtWidgets.QMessageBox.warning(self, "Validasi", "Code tidak boleh kosong!")
            return False
        if hasattr(self, "company") and not self.company.text().strip():
            QtWidgets.QMessageBox.warning(self, "Validasi", "Company tidak boleh kosong!")
            return False
        return True

    def closeEvent(self, event):
        if hasattr(self, "tutup_semua_form"):
            self.tutup_semua_form()
        if hasattr(self, "forms"):
            self.forms.clear()
        event.accept()

#menu UMA
class ExportWindow(BaseWindow):
    def __init__(self):
        super(ExportWindow, self).__init__()
        current_dir = os.path.dirname(os.path.abspath(__file__))
        ui_path = resource_path("export.ui")
        uic.loadUi(ui_path, self)
        self.setWindowTitle("Export UMA")

        # Auto-connect semua menu action ke handler generik
        self.wire_menu_actions()

        # Inisialisasi folder
        self.source_folder = r"D:/IDX_Data/UMA/downloads_uma"
        self.output_folder = r"D:/IDX_Data/UMA/txt_uma"
        
        # Hubungkan tombol
        self.btn_export.clicked.connect(self.btn_export_clicked)
        
        # Optional: tampilkan folder di UI jika ada label
        if hasattr(self, 'lbl_source'):
            self.lbl_source.setText(self.source_folder)
        if hasattr(self, 'lbl_target'):
            self.lbl_target.setText(self.output_folder)
        
        

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


class DownloaderWindow(BaseWindow):
    def __init__(self):
        super(DownloaderWindow, self).__init__()
        current_dir = os.path.dirname(os.path.abspath(__file__))
        ui_path = resource_path("downloader.ui")
        uic.loadUi(ui_path, self)
        self.setWindowTitle("Downloader UMA")

        # Auto-connect semua menu action ke handler generik
        self.wire_menu_actions()

        # Set default date to current date
        self.start_date.setDate(QDate.currentDate())
        self.end_date.setDate(QDate.currentDate())

        self.btn_run.clicked.connect(self.btn_run_clicked)
       
    # =========================================================
    # SETUP CHROME
    # =========================================================
    def setup_chrome_options(self, download_path):
        """Setup Chrome options for automatic downloading (undetected-chromedriver)"""
        chrome_options = uc.ChromeOptions()   # ← Ganti ke uc.ChromeOptions()
        
        prefs = {
            "download.default_directory": download_path,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "plugins.always_open_pdf_externally": True,
            "profile.default_content_setting_values.popups": 0,
            "profile.default_content_setting_values.automatic_downloads": 1,
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        # Opsi dasar - TETAP DIPAKAI
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--start-maximized")
        
        # ❌ HAPUS baris user-agent!
        # UCD sudah handle fingerprint secara otomatis.
        # Menambah user-agent manual malah bisa bikin terdeteksi.
        
        return chrome_options

    def _init_chrome_driver(self, chrome_options):
        """
        Init Chrome via undetected-chromedriver.
        Versi Chrome: 152 (sesuaikan kalau Chrome Anda update)
        """
        try:
            print("=" * 60)
            print("Membuka Chrome via undetected-chromedriver...")
            print("Chrome version: 152")
            print("=" * 60)
            
            driver = uc.Chrome(
                options=chrome_options,
                version_main=152,        # ← INI KUNCINYA: paksa versi 152
                use_subprocess=True,
            )
            print("✓ Chrome berhasil dibuka")
            return driver
            
        except Exception as e:
            tb = traceback.format_exc()
            print(f"✗ Gagal: {type(e).__name__}: {e}")
            print(tb)
            
            # Cek kalau error masih sama (versi mismatch)
            err_msg = str(e)
            if "only supports Chrome version" in err_msg:
                # Ekstrak versi dari error
                match = re.search(r'only supports Chrome version (\d+)', err_msg)
                supports = match.group(1) if match else "?"
                
                match2 = re.search(r'Current browser version is (\d+)', err_msg)
                current = match2.group(1) if match2 else "?"
                
                QMessageBox.critical(
                    self, "Versi Chrome Tidak Cocok",
                    f"Versi ChromeDriver ({supports}) tidak cocok\n"
                    f"dengan Chrome Anda ({current}).\n\n"
                    f"Solusi:\n"
                    f"Ubah version_main di kode menjadi {current}\n\n"
                    f"File: menu_utama_umanew.py\n"
                    f"Cari: version_main=...\n"
                    f"Ganti jadi: version_main={current}"
                )
            else:
                QMessageBox.critical(
                    self, "Chrome Error",
                    f"{type(e).__name__}: {e}\n\n"
                    f"Cek log: ~/Desktop/cpca_error.log"
                )
            return None

    # =========================================================
    # WAIT FOR DOWNLOAD
    # =========================================================
    def wait_for_download_complete(self, download_path, existing_files=None, timeout=60):
        """
        Tunggu download selesai dengan membandingkan file baru vs existing.
        Return: path file PDF baru, atau None jika timeout.
        """
        if existing_files is None:
            existing_files = set()

        start_time = time.time()

        while time.time() - start_time < timeout:
            # Cek file .crdownload (sedang download)
            downloading = [
                f for f in os.listdir(download_path)
                if f.lower().endswith(('.crdownload', '.part'))
            ]

            # File PDF saat ini
            current_pdfs = set(
                f for f in os.listdir(download_path)
                if f.lower().endswith(".pdf")
            )

            # File baru = ada sekarang tapi tidak ada sebelumnya
            new_files = current_pdfs - existing_files

            # Jika tidak ada download berjalan & ada file baru
            if not downloading and new_files:
                newest = max(
                    new_files,
                    key=lambda f: os.path.getctime(os.path.join(download_path, f))
                )
                print(f"  Download selesai: {newest}")
                return os.path.join(download_path, newest)

            time.sleep(1)

        print(f"  Timeout: Download tidak selesai dalam {timeout} detik.")
        return None

    # =========================================================
    # RENAME FILE
    # =========================================================
    def rename_pdf(self, file_path, kode_saham, tanggal):
        """Rename file PDF ke format: Suspensi_<KODE>_<YYYY-MM-DD>.pdf"""
        if not file_path or not os.path.exists(file_path):
            return None

        folder = os.path.dirname(file_path)

        # Nama file baru
        new_filename = f"Suspensi_{kode_saham}_{tanggal}.pdf"

        # Bersihkan karakter ilegal
        safe_filename = "".join(
            c for c in new_filename
            if c.isalnum() or c in (" ", "-", "_", ".")
        ).strip()

        new_path = os.path.join(folder, safe_filename)

        # Jika sudah ada, tambah counter
        counter = 1
        while os.path.exists(new_path):
            name, ext = os.path.splitext(safe_filename)
            new_path = os.path.join(folder, f"{name}_{counter}{ext}")
            counter += 1

        try:
            os.rename(file_path, new_path)
            print(f"Renamed: {os.path.basename(new_path)}")
            return new_path
        except Exception as e:
            print(f"Gagal rename: {e}")
            return file_path

    def _build_uma_filename(self, row_date, announcement):
        """
        Bangun nama file UMA.
        Format: <YYYYMMDD> - UMA <KODE>.pdf
        Contoh: 20260923 - UMA PKPK.pdf
        """
        import re as _re
        from datetime import datetime

        # 1) Ekstrak kode saham dari tanda kurung, mis. (PKPK)
        match = _re.search(r'\(([A-Z]{4})\)', announcement)
        kode_saham = match.group(1) if match else "UNKNOWN"

        # 2) Konversi tanggal "23 Sep 2026" → "20260923"
        row_date_norm = row_date
        for idn, en in [("Mei", "May"), ("Agt", "Aug"),
                        ("Okt", "Oct"), ("Des", "Dec")]:
            row_date_norm = row_date_norm.replace(idn, en)

        try:
            dt = datetime.strptime(row_date_norm, "%d %b %Y")
            tanggal_file = dt.strftime("%Y%m%d")
        except ValueError:
            tanggal_file = row_date

        # 3) Susun nama file — pakai "UMA", bukan "Suspend"
        raw_filename = f"{tanggal_file} - UMA {kode_saham}.pdf"

        # 4) Bersihkan karakter ilegal
        safe_filename = "".join(
            c for c in raw_filename
            if c.isalnum() or c in (" ", "-", "_", ".")
        ).strip()

        return safe_filename
   

    # =========================================================
    # MAIN PROCESS
    # =========================================================
    def btn_run_clicked(self):
        """Handler tombol Run - download semua PDF suspensi dalam rentang tanggal"""

        # ============ KONFIGURASI ============
        download_path = os.path.abspath("D:/IDX_Data/UMA/downloads_uma")
        os.makedirs(download_path, exist_ok=True)

        # ============ AMBIL TANGGAL DARI UI ============
        start_qdate = self.start_date.date()
        end_qdate = self.end_date.date()

        # Konversi ke format Indonesia
        bulan_map = {
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

        target_start = start_qdate.toString("dd MMM yyyy")
        target_end = end_qdate.toString("dd MMM yyyy")

        for en, idn in bulan_map.items():
            target_start = target_start.replace(en, idn)
            target_end = target_end.replace(en, idn)
        print(f"Target Start: {target_start}, Target End: {target_end}")

        # Validasi tanggal
        if start_qdate > end_qdate:
            QMessageBox.warning(
                self, "Peringatan",
                "Start date tidak boleh lebih besar dari End date!"
            )
            return

        print(f"=== DOWNLOADER SUSPEND ===")
        print(f"Start date: {target_start}")
        print(f"End date  : {target_end}")
        print(f"Folder    : {download_path}")

        # ============ SETUP CHROME ============
        chrome_options = self.setup_chrome_options(download_path)

        # Init driver via helper (fallback berlapis)
        driver = self._init_chrome_driver(chrome_options)

        if driver is None:
            # Error sudah ditampilkan di _init_chrome_driver
            print("Driver None — error sudah ditampilkan sebelumnya")
            return

        wait = WebDriverWait(driver, 30)
        downloads_count = 0

        try:
            # ============ BUKA HALAMAN SUSPENSI ============
            url = "https://www.idx.co.id/id/berita/unusual-market-activity-uma/"
            driver.get(url)
            print("Membuka halaman Suspensi IDX...")
            time.sleep(5)

            # =====================================================
            # LANGKAH 1: ISI FILTER TANGGAL (START & END DATE)
            # =====================================================
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

                if not terapkan_button:
                    terapkan_button.click()
                    print("Clicked Terapkan button.")
                    time.sleep(2)

                else:
                    print("Terapkan button not found, continuing anyway...")

            except Exception as e:
                print(f"Error saat klik Terapkan: {e}")
                # Lanjutkan meskipun error

            time.sleep(2)

            # =====================================================
            # LANGKAH 1B: SET DROPDOWN "BARIS" KE "All"
            # =====================================================
            try:
                # Cari elemen <select> dropdown Baris
                # Berdasarkan HTML: id="vgt-select-rpp-..." atau class "vgt-select"
                dropdown_selectors = [
                    "//select[contains(@id, 'vgt-select-rpp')]",
                    "//select[contains(@class, 'vgt-select')]",
                    "//select[.//option[contains(text(), 'All')]]",
                    "//select[.//option[contains(text(), 'Semua')]]",
                ]

                baris_select = None
                for selector in dropdown_selectors:
                    try:
                        baris_select = wait.until(EC.presence_of_element_located((By.XPATH, selector)))
                        if baris_select:
                            break
                    except:
                        continue

                if baris_select:
                    # Pakai Select dari Selenium untuk pilih "All"
                    from selenium.webdriver.support.ui import Select
                    sel = Select(baris_select)

                    # Coba pilih berdasarkan teks "All" dulu
                    selected = False
                    for opt in sel.options:
                        opt_text = (opt.text or "").strip().lower()
                        if opt_text in ("all", "semua"):
                            sel.select_by_visible_text(opt.text.strip())
                            selected = True
                            print(f"  ✓ Dropdown Baris di-set ke: {opt.text.strip()}")
                            break

                    # Fallback: pilih opsi terakhir (biasanya "All")
                    if not selected and sel.options:
                        last_opt = sel.options[-1]
                        sel.select_by_visible_text(last_opt.text.strip())
                        print(f"  ✓ Dropdown Baris di-set ke opsi terakhir: {last_opt.text.strip()}")

                    # Trigger event change via JS untuk memastikan Vue merespon
                    driver.execute_script(
                        """
                        arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
                        """,
                        baris_select
                    )

                    time.sleep(2)  # Tunggu tabel refresh menampilkan semua baris
                else:
                    print("  ⚠ Dropdown Baris tidak ditemukan, lanjut dengan default.")

            except Exception as e:
                print(f"  ⚠ Gagal set dropdown Baris: {e}")

            time.sleep(2)

            # Find all rows in the table
            rows = driver.find_elements(By.XPATH, '//table[@id="vgt-table"]/tbody/tr')
            print(f"Total rows found in table: {len(rows)}")

            #Process each row
            downloads_found = 0
            for i, row in enumerate(rows, 1):
                try:
                    # Get date from the row
                    date_element = row.find_element(By.XPATH, './td[1]')
                    row_date = date_element.text.strip()
                    

                    # Check if date matches target (bandingkan sebagai datetime)
                    try:
                        row_dt = _dt.strptime(row_date, "%d %b %Y")
                    except ValueError:
                        # Coba format dengan bulan Indonesia
                        row_date_norm = row_date
                        for idn, en in [("Mei","May"),("Agt","Aug"),("Okt","Oct"),("Des","Dec")]:
                            row_date_norm = row_date_norm.replace(idn, en)
                        try:
                            row_dt = _dt.strptime(row_date_norm, "%d %b %Y")
                        except ValueError:
                            row_dt = None

                    try:
                        start_dt = _dt.strptime(target_start, "%d %b %Y")
                        end_dt = _dt.strptime(target_end, "%d %b %Y")
                    except ValueError:
                        start_dt = end_dt = None

                    # Bandingkan pakai datetime; fallback ke string kalau gagal parse
                    if row_dt and start_dt and end_dt:
                        date_in_range = start_dt <= row_dt <= end_dt
                    else:
                        date_in_range = target_start <= row_date <= target_end

                    if date_in_range:
                        print(f"Row {i}: Date = {row_date}  ← dalam rentang, diproses")

                        # Find the PDF link in the row
                        try:
                            download_link = row.find_element(By.XPATH, './/a[contains(@href, ".pdf")]')

                            if download_link:
                                announcement = row.find_element(By.XPATH, './/td[2]/span').text.strip()

                                # Create filename
                                filename = self._build_uma_filename(row_date, announcement)

                                print(f"Downloading: {filename})")

                                    # ── Scroll + klik langsung via JS ──
                                driver.execute_script(
                                    "arguments[0].scrollIntoView({block:'center'});",
                                    download_link
                                )
                                time.sleep(1)
                                driver.execute_script("arguments[0].click();", download_link)

                                download_link.click()

                                downloads_found += 1
                                
                                # Wait for download to start and complete
                                time.sleep(3)
                                self.wait_for_download_complete(download_path, timeout=30)
                                
                                # Rename downloaded file
                                renamed = False
                                for attempt in range(5):
                                    time.sleep(2)

                                    # Cari PDF baru (bukan file lama)
                                    current_pdfs = [
                                        f for f in os.listdir(download_path)
                                        if f.lower().endswith(".pdf")
                                    ]
                                    # Skip file yang sudah punya format " - Suspend"/" - Unsuspend"
                                    candidates = [
                                        f for f in current_pdfs
                                        if " - Suspend " not in f and " - Unsuspend " not in f
                                    ]

                                    if candidates:
                                        latest_file = max(
                                            [os.path.join(download_path, f) for f in candidates],
                                            key=os.path.getctime
                                        )
                                        new_file_path = os.path.join(download_path, filename)

                                        counter = 1
                                        while os.path.exists(new_file_path):
                                            name, ext = os.path.splitext(filename)
                                            new_file_path = os.path.join(download_path, f"{name}_{counter}{ext}")
                                            counter += 1

                                        try:
                                            os.rename(latest_file, new_file_path)
                                            print(f"Saved as: {os.path.basename(new_file_path)}")
                                            renamed = True
                                            break
                                        except Exception as e:
                                            print(f"  Rename gagal (attempt {attempt+1}): {e}")

                                if not renamed:
                                    print(f"  ⚠ Rename gagal untuk: {filename}")
                                
                                time.sleep(2)  # Delay between downloads
                                
                        except Exception as e:
                            print(f"Error finding download link in row {i}: {e}")
                            
                except Exception as e:
                    print(f"Error processing row {i}: {e}")
                    continue

            print(f"\n=== Download Summary ===")
            print(f"Total files downloaded for {target_start}: {downloads_found}")
            print(f"Files saved in: {download_path}")
            
        except Exception as e:
            print(f"Error during execution: {e}")
            
        finally:
            # Keep browser open for a moment to ensure downloads complete
            time.sleep(2)
            try:
                for f in os.listdir(download_path):
                    if f.lower().endswith(".pdf") and " - Suspend " not in f and " - Unsuspend " not in f:
                        print(f"⚠ Sisa file belum direname: {f}")
            except Exception:
                pass
            driver.quit()

    # =========================================================
    #HELPER:SET DATE INPUT
    # =========================================================
    def _set_date_input(self, driver, element, date_str):
        """
        Isi date picker dengan date_str.
        Coba via JS dulu (paling reliable untuk date picker kompleks),
        lalu fallback ke send_keys.
        """
        try:
            # Strategi 1: Set value via JavaScript + trigger events
            driver.execute_script(
                """
                arguments[0].value = arguments[1];
                arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
                arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
                arguments[0].dispatchEvent(new Event('blur', { bubbles: true }));
                """,
                element, date_str
            )
            print(f"  Set tanggal via JS: {date_str}")
            return True
        except Exception as e:
            print(f"  Gagal set via JS: {e}")

        # Fallback: clear + send_keys
        try:
            element.click()
            time.sleep(0.5)
            element.clear()
            element.send_keys(date_str)
            time.sleep(0.5)
            # Tekan Escape untuk tutup kalender popup
            from selenium.webdriver.common.keys import Keys
            element.send_keys(Keys.ESCAPE)
            print(f"  Set tanggal via send_keys: {date_str}")
            return True
        except Exception as e:
            print(f"  Gagal set via send_keys: {e}")
            return False
    
# ============================================================
# WORKER THREAD UNTUK BATCH UMA
# ============================================================
class UmaProcessWorker(QThread):
    """Thread untuk memproses file PDF UMA di background."""

    progress_updated = pyqtSignal(int, str)
    statistics_updated = pyqtSignal(int, int, int, int)
    row_added = pyqtSignal(int, str, dict, str, str)
    finished = pyqtSignal(int, int, int, list)

    def __init__(self, folder_path):
        super().__init__()
        self.folder_path = folder_path
        self.is_running = True

    # ==========================================================
    # NORMALISASI TEKS
    # ==========================================================
    def normalisasi_teks(self, teks):
        """Bersihkan teks dari karakter aneh PDF."""
        if not teks:
            return ""
        teks = teks.replace('\xa0', ' ')
        teks = teks.replace('\u200b', '')
        teks = teks.replace('\ufeff', '')
        teks = teks.replace('**', '')
        teks = teks.replace('__', '')
        teks = re.sub(r'[ \t]+', ' ', teks)
        teks = re.sub(r'\n\s*\n', '\n', teks)
        return teks

    # ==========================================================
    # PARSE TANGGAL
    # ==========================================================
    def parse_tanggal(self, teks_tanggal):
        """Parse berbagai format tanggal → datetime.date."""
        if not teks_tanggal:
            return None

        bulan_map = {
            # Indonesia
            'januari': 1, 'februari': 2, 'maret': 3, 'april': 4,
            'mei': 5, 'juni': 6, 'juli': 7, 'agustus': 8,
            'september': 9, 'oktober': 10, 'november': 11, 'desember': 12,
            # Inggris singkat
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
            'may': 5, 'jun': 6, 'jul': 7, 'aug': 8,
            'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
            # Inggris panjang
            'january': 1, 'february': 2, 'march': 3,
            'june': 6, 'july': 7, 'august': 8,
            'october': 10, 'december': 12,
        }

        teks_tanggal = str(teks_tanggal).strip()

        # Format: "23 September 2026"
        match = re.search(r'(\d{1,2})\s+(\w+)\s+(\d{4})', teks_tanggal)
        if match:
            hari, bulan_str, tahun = match.groups()
            bulan = bulan_map.get(bulan_str.lower())
            if bulan:
                try:
                    return datetime(int(tahun), bulan, int(hari)).date()
                except ValueError:
                    pass

        # Format: "September 23, 2026"
        match = re.search(r'(\w+)\s+(\d{1,2}),?\s+(\d{4})', teks_tanggal)
        if match:
            bulan_str, hari, tahun = match.groups()
            bulan = bulan_map.get(bulan_str.lower())
            if bulan:
                try:
                    return datetime(int(tahun), bulan, int(hari)).date()
                except ValueError:
                    pass

        return None

    # ==========================================================
    # BACA PDF
    # ==========================================================
    def baca_pdf_teks(self, path):
        """Extract semua teks dari PDF."""
        teks = ""
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                teks += page.extract_text() or ""
                teks += "\n"
        return teks

    # ==========================================================
    # EKSTRAK DATA UMA
    # ==========================================================
    def extract_data_uma(self, teks):
        """
        Parse PDF UMA untuk mendapatkan:
        - code          : kode saham (mis. PKPK)
        - company       : nama perusahaan (mis. PT Paragon Karya Perkasa Tbk)
        - letter_number : nomor surat (mis. Peng-UMA-00307/BEI.WAS/09-2026)
        - date          : tanggal pengumuman
        """
        teks = self.normalisasi_teks(teks)

        # ============================================================
        # 1. EKSTRAK KODE SAHAM — dari tanda kurung (PKPK)
        # ============================================================
        code = None
        matches = re.findall(r'\(([A-Z]{4})\)', teks)
        if matches:
            blacklist = {'BEI', 'OJK', 'KSEI', 'KPEI', 'TBK', 'IDX', 'WAS'}
            for m in matches:
                if m not in blacklist:
                    code = m
                    break

        # Fallback: cari kode 4 huruf kapital yang muncul setelah "Tbk"
        if not code:
            match = re.search(r'Tbk\s*\(([A-Z]{4})\)', teks)
            if match:
                code = match.group(1)

        # ============================================================
        # 2. EKSTRAK NAMA PERUSAHAAN
        # ============================================================
        company = None
        patterns_nama = [
            r'PT\s+[A-Za-z\s\.]+?Tbk',                    # "PT Paragon Karya Perkasa Tbk"
            r'PT\s+[A-Za-z\s\.]+?\s*\(',                  # fallback
        ]
        for pattern in patterns_nama:
            match = re.search(pattern, teks)
            if match:
                company = match.group(0).strip()
                # Bersihkan tanda kurung jika ada
                company = re.sub(r'\s*\(.*$', '', company).strip()
                break

        # ============================================================
        # 3. EKSTRAK NOMOR SURAT (letter_number)
        # Format: Peng-UMA-00307/BEI.WAS/09-2026
        # ============================================================
        letter_number = None
        match = re.search(
            r'(Peng-UMA-\d+/BEI[\w\.]*/\d{2}-\d{4})',
            teks
        )
        if match:
            letter_number = match.group(1).strip()

        # ============================================================
        # 4. EKSTRAK TANGGAL
        # Prioritas: tanggal yang ada di dekat "Endra Febri Styawan"
        # ============================================================
        date_value = None

        # Cari pola "23 September 2026" di halaman Indonesia (halaman 2)
        # Format: "Demikian untuk diketahui.\n\n23 September 2026\n\nEndra"
        match = re.search(
            r'(\d{1,2}\s+(?:Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember)\s+\d{4})\s*\n\s*Endra',
            teks, re.IGNORECASE
        )
        if match:
            date_value = self.parse_tanggal(match.group(1))

        # Fallback: cari tanggal Indonesia apapun
        if not date_value:
            match = re.search(
                r'(\d{1,2}\s+(?:Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember)\s+\d{4})',
                teks, re.IGNORECASE
            )
            if match:
                date_value = self.parse_tanggal(match.group(1))

        # Fallback terakhir: cari format Inggris "September 23, 2026"
        if not date_value:
            match = re.search(
                r'((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4})',
                teks
            )
            if match:
                date_value = self.parse_tanggal(match.group(1))

        return {
            'code': code,
            'company': company,
            'letter_number': letter_number,
            'date': date_value,
        }

    # ==========================================================
    # CEK DUPLIKAT
    # ==========================================================
    def check_duplicate(self, cursor, code, letter_number):
        """Cek duplikat berdasarkan code + letter_number."""
        cursor.execute(
            "SELECT id FROM ca_uma WHERE code = %s AND letter_number = %s LIMIT 1",
            (code, letter_number)
        )
        return cursor.fetchone() is not None

    # ==========================================================
    # INSERT KE ca_uma
    # ==========================================================
    def insert_data(self, cursor, data):
        """Insert data ke tabel ca_uma."""
        sql = """
            INSERT INTO ca_uma (code, company, letter_number, date)
            VALUES (%s, %s, %s, %s)
        """
        cursor.execute(sql, (
            data['code'],
            data['company'],
            data['letter_number'],
            data['date']
        ))

    # ==========================================================
    # PINDAH FILE
    # ==========================================================
    def move_file(self, src, dest_folder):
        os.makedirs(dest_folder, exist_ok=True)
        dest = os.path.join(dest_folder, os.path.basename(src))

        if os.path.exists(dest):
            name, ext = os.path.splitext(os.path.basename(src))
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest = os.path.join(dest_folder, f"{name}_{timestamp}{ext}")

        shutil.move(src, dest)
        return dest

    # ==========================================================
    # MAIN RUN
    # ==========================================================
    def run(self):
        total = 0
        sukses = 0
        error = 0
        duplikat = 0
        error_details = []

        # ---------- Folder output ----------
        parent = os.path.dirname(self.folder_path)
        success_folder = os.path.join(parent, 'success_processed')
        error_folder = os.path.join(parent, 'error_processed')
        os.makedirs(success_folder, exist_ok=True)
        os.makedirs(error_folder, exist_ok=True)

        # ---------- Koneksi DB ----------
        try:
            conn = mysql.connector.connect(**DB_CONFIG)
            cursor = conn.cursor(dictionary=True)
        except Error as e:
            self.finished.emit(0, 0, 0, [f"Gagal koneksi DB: {e}"])
            return

        # ---------- Ambil file PDF ----------
        pdf_files = sorted([
            f for f in os.listdir(self.folder_path)
            if f.lower().endswith('.pdf')
        ])

        for idx, filename in enumerate(pdf_files, start=1):
            if not self.is_running:
                break

            total += 1
            path = os.path.join(self.folder_path, filename)
            self.progress_updated.emit(idx, filename)

            try:
                teks = self.baca_pdf_teks(path)
                data = self.extract_data_uma(teks)

                # ---------- Validasi ----------
                missing = []
                if not data['code']:
                    missing.append("code")
                if not data['company']:
                    missing.append("company")
                if not data['letter_number']:
                    missing.append("letter_number")
                if not data['date']:
                    missing.append("date")

                if missing:
                    error += 1
                    ket = f"Data tidak lengkap: {', '.join(missing)}"
                    error_details.append(f"{filename} → {ket}")
                    self.row_added.emit(idx, filename, data, "ERROR", ket)
                    self.move_file(path, error_folder)
                    self.statistics_updated.emit(total, sukses, error, duplikat)
                    continue

                # ---------- Cek duplikat ----------
                if self.check_duplicate(cursor, data['code'], data['letter_number']):
                    duplikat += 1
                    ket = f"Duplikat: {data['code']} - {data['letter_number']}"
                    self.row_added.emit(idx, filename, data, "DUPLIKAT", ket)
                    self.move_file(path, success_folder)
                    self.statistics_updated.emit(total, sukses, error, duplikat)
                    continue

                # ---------- Insert ----------
                self.insert_data(cursor, data)
                conn.commit()

                sukses += 1
                ket = f"{data['code']} - {data['company'][:40]}"
                self.row_added.emit(idx, filename, data, "BERHASIL", ket)
                self.move_file(path, success_folder)

            except Exception as e:
                error += 1
                ket = str(e)[:100]
                error_details.append(f"{filename} → {ket}")
                self.row_added.emit(idx, filename, {}, "ERROR", ket)
                try:
                    self.move_file(path, error_folder)
                except Exception:
                    pass

            self.statistics_updated.emit(total, sukses, error, duplikat)

        cursor.close()
        conn.close()
        self.finished.emit(total, sukses, error, error_details)
        

class BatchInsertWindow(BaseWindow):
    def __init__(self):
        super() .__init__()
        current_dir = os.path.dirname(os.path.abspath(__file__))
        ui_path = resource_path("batch_insert.ui")
        uic.loadUi(ui_path, self)
        self.setWindowTitle("Batch Insert UMA")

        # Auto-connect semua menu action ke handler generik
        self.wire_menu_actions()
        #hendler button
        self.btn_import.clicked.connect(self.browse_folder)
        self.pushButton.clicked.connect(self.start_process)

        self.folder_path = ""
        self.worker = None

        self.reset_statistics()
        self.check_database()
        self.setup_table()

    # ==========================================================
    # SETUP TABLE
    # ==========================================================
    def setup_table(self):
        table = self.get_table()
        if table:
            headers = ["No", "Nama File", "Kode", "Perusahaan",
                       "No. Surat", "Tanggal", "Status", "Keterangan"]
            table.setColumnCount(len(headers))
            table.setHorizontalHeaderLabels(headers)

            table.setColumnWidth(0, 40)    # No
            table.setColumnWidth(1, 200)   # Nama File
            table.setColumnWidth(2, 70)    # Kode
            table.setColumnWidth(3, 220)   # Perusahaan
            table.setColumnWidth(4, 220)   # No. Surat
            table.setColumnWidth(5, 100)   # Tanggal
            table.setColumnWidth(6, 90)    # Status
            table.setColumnWidth(7, 200)   # Keterangan

            table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
            table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)

    def get_table(self):
        names = ['tableWidget', 'tableWidget_result', 'tbl_result', 'tbl_hasil']
        for name in names:
            widget = self.findChild(QtWidgets.QTableWidget, name)
            if widget:
                return widget
        return None

    def get_process_button(self):
        if hasattr(self, "pushButton"):
            return self.pushButton
        return None

    def get_folder_input(self):
        if hasattr(self, "txt_path"):
            return self.txt_path
        return None

    # ==========================================================
    # DATABASE CHECK
    # ==========================================================
    def check_database(self):
        try:
            conn = mysql.connector.connect(**DB_CONFIG)
            if conn.is_connected():
                print("✅ Koneksi database berhasil (Batch UMA)")
                conn.close()
                return True
        except Error as e:
            print(f"❌ Gagal koneksi: {e}")
            QMessageBox.warning(self, "Database", f"Gagal koneksi ke database:\n\n{e}")
            return False
        return False

    # ==========================================================
    # BROWSE FOLDER
    # ==========================================================
    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Pilih Folder PDF UMA")
        if folder:
            self.folder_path = folder
            folder_input = self.get_folder_input()
            if folder_input:
                folder_input.setText(folder)
            self.check_paths()

    def check_paths(self):
        valid = self.folder_path and os.path.exists(self.folder_path)
        btn = self.get_process_button()
        if btn:
            btn.setEnabled(valid)

    # ==========================================================
    # STATISTIK
    # ==========================================================
    def reset_statistics(self):
        self.total_files = 0
        self.success_count = 0
        self.error_count = 0
        self.duplicate_count = 0
        self.update_statistics()
        self.clear_table()

    def update_statistics(self):
        mapping = {
            'label_total': f'Total: {self.total_files}',
            'lbl_total': f'Total: {self.total_files}',
            'label_berhasil': f'Berhasil: {self.success_count}',
            'lbl_berhasil': f'Berhasil: {self.success_count}',
            'label_error': f'Error: {self.error_count}',
            'lbl_error': f'Error: {self.error_count}',
            'label_duplikat': f'Duplikat: {self.duplicate_count}',
            'lbl_duplikat': f'Duplikat: {self.duplicate_count}'
        }
        for name, text in mapping.items():
            widget = self.findChild(QtWidgets.QLabel, name)
            if widget:
                widget.setText(text)
        QtWidgets.QApplication.processEvents()

    def clear_table(self):
        table = self.get_table()
        if table:
            table.setRowCount(0)

    # ==========================================================
    # ADD ROW
    # ==========================================================
    def add_table_row(self, no, filename, data, status, keterangan):
        table = self.get_table()
        if not table:
            return

        row = table.rowCount()
        table.insertRow(row)

        values = [
            str(no),
            filename,
            data.get('code', ''),
            (data.get('company') or '')[:60],
            data.get('letter_number', ''),
            str(data.get('date') or ''),
            status,
            keterangan
        ]

        for col, value in enumerate(values):
            item = QTableWidgetItem(str(value))
            if status == "BERHASIL":
                item.setBackground(Qt.green)
            elif status == "DUPLIKAT":
                item.setBackground(Qt.yellow)
            elif status == "ERROR":
                item.setBackground(Qt.red)
            table.setItem(row, col, item)

        table.scrollToBottom()

    # ==========================================================
    # PROCESS
    # ==========================================================
    def start_process(self):
        if not self.folder_path:
            folder_input = self.get_folder_input()
            if folder_input:
                self.folder_path = folder_input.text().strip()

        if not self.folder_path:
            QMessageBox.warning(self, "Peringatan", "Silakan pilih folder PDF terlebih dahulu.")
            return

        if not os.path.exists(self.folder_path):
            QMessageBox.critical(self, "Error", "Folder PDF tidak ditemukan.")
            return

        self.reset_statistics()
        self.clear_table()

        btn = self.get_process_button()
        if btn:
            btn.setEnabled(False)
            btn.setText("Processing...")

        self.worker = UmaProcessWorker(self.folder_path)
        self.worker.progress_updated.connect(self.on_progress_updated)
        self.worker.statistics_updated.connect(self.on_statistics_updated)
        self.worker.row_added.connect(self.add_table_row)
        self.worker.finished.connect(self.on_process_finished)

        self.worker.start()

    def on_progress_updated(self, idx, filename):
        self.statusBar().showMessage(f"Memproses file {idx}: {filename}")

    def on_statistics_updated(self, total, success, error, duplicate):
        self.total_files = total
        self.success_count = success
        self.error_count = error
        self.duplicate_count = duplicate
        self.update_statistics()

    def on_process_finished(self, total, success, error, error_details):
        btn = self.get_process_button()
        if btn:
            btn.setEnabled(True)
            btn.setText("Process Files")

        self.statusBar().showMessage("Selesai!")
        self.show_summary(total, success, error, error_details)

    def show_summary(self, total, success, error, error_details):
        parent = os.path.dirname(self.folder_path)
        success_folder = os.path.join(parent, 'success_processed')
        error_folder = os.path.join(parent, 'error_processed')

        text = f"""
BATCH UMA SELESAI

Total File : {total}
Berhasil   : {success}
Error      : {error}
Duplikat   : {self.duplicate_count}

Success Folder: {success_folder}
Error Folder: {error_folder}
        """

        if error_details:
            text += "\n\nDETAIL ERROR:\n" + "\n".join(f"• {e}" for e in error_details[:10])
            if len(error_details) > 10:
                text += f"\n• ... dan {len(error_details) - 10} error lainnya"

        QMessageBox.information(self, "Batch UMA", text)





#menu teoretis
class DownloaderTeoretisWindow(BaseWindow):
    def __init__(self):
        super(DownloaderTeoretisWindow, self).__init__()
        ui_path = resource_path("downloader_teoretis.ui")
        uic.loadUi(ui_path, self)
        self.setWindowTitle("Downloader Teoretis")

        # Auto-connect semua menu action ke handler generik
        self.wire_menu_actions()

        # Set default date to current date
        self.date_edit.setDate(QDate.currentDate())
        self.btn_run_2.clicked.connect(self.btn_run_2_clicked)

    def wait_for_download_complete(self, folder, existing_files=None, timeout=60):
        """Tunggu download selesai. Return path file baru atau None."""
        if existing_files is None:
            existing_files = set()

        start_time = time.time()
        while time.time() - start_time < timeout:
            downloading = [
                f for f in os.listdir(folder)
                if f.lower().endswith(('.crdownload', '.part'))
            ]
            current_pdfs = set(
                f for f in os.listdir(folder)
                if f.lower().endswith(".pdf")
            )
            new_files = current_pdfs - existing_files

            if not downloading and new_files:
                newest = max(
                    new_files,
                    key=lambda f: os.path.getctime(os.path.join(folder, f))
                )
                print(f"Download selesai: {newest}")
                return os.path.join(folder, newest)
            time.sleep(1)

        print(f"Timeout: Download tidak selesai dalam {timeout} detik.")
        return None

    def setup_chrome_options(self, download_path):
        """Setup Chrome options for automatic downloading"""
        chrome_options = uc.ChromeOptions()
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
        
        return chrome_options
    
    def rename_latest_pdf(self, folder, kode_saham, downloaded_file=None):
        """Rename file PDF yang baru didownload."""
        if downloaded_file and os.path.exists(downloaded_file):
            latest_file = downloaded_file
        else:
            pdf_files = [
                os.path.join(folder, f)
                for f in os.listdir(folder)
                if f.lower().endswith(".pdf")
            ]
            if not pdf_files:
                print("Tidak ada file PDF ditemukan.")
                return None
            latest_file = max(pdf_files, key=os.path.getctime)

        new_filename = f"Harga Teoretis_{kode_saham}.pdf"
        safe_filename = "".join(
            c for c in new_filename
            if c.isalnum() or c in (" ", "-", "_", ".")
        )
        new_path = os.path.join(folder, safe_filename)

        counter = 1
        while os.path.exists(new_path):
            name, ext = os.path.splitext(safe_filename)
            new_path = os.path.join(folder, f"{name}_{counter}{ext}")
            counter += 1

        try:
            os.rename(latest_file, new_path)
            print(f"Saved: {os.path.basename(new_path)}")
            return new_path
        except Exception as e:
            print(f"Gagal rename: {e}")
            return latest_file
        
    def btn_run_2_clicked(self):
        # KONFIGURASI
        keywords = ["Harga Teoretis"]
        download_path = os.path.abspath("D:/IDX_Data/Teoretis/download_teoretis")
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

        # === INIT DRIVER VIA UCD ===
        try:
            print("Membuka Chrome via undetected-chromedriver...")
            driver = uc.Chrome(
                options=chrome_options,
                version_main=152,       # ← sesuaikan versi Chrome Anda
                use_subprocess=True,
            )
            print("✓ Chrome berhasil dibuka")
        except Exception as e:
            QMessageBox.critical(
                self, "Chrome Error",
                f"Gagal membuka Chrome:\n\n{type(e).__name__}: {e}\n\n"
                f"Sesuaikan version_main dengan versi Chrome Anda\n"
                f"(Cek: chrome://version/)"
            )
            return
        
        try:
            # BUKA WEBSITE IDX
            url = ("https://www.idx.co.id/id/perusahaan-tercatat/keterbukaan-informasi/")
            driver.get(url)
            
            print("Membuka halaman IDX...")
            time.sleep(30)

            # INPUT KEYWORD
            for keyword in keywords:
                print(
                    f"\nMencari: {keyword} | "
                    f"Tanggal: {target_date}"
                )

                try:
                    keyword_input = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, "//input[@placeholder='Kata kunci...']")))
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
                    button = WebDriverWait(driver, 3).until(EC.element_to_be_clickable((By.XPATH, selector)))
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
                        renamed_file = self.rename_latest_pdf(download_path, kode_saham, downloaded_file)

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

    

class ExportTeoretisWindow(BaseWindow):
    def __init__(self):
        super(ExportTeoretisWindow, self).__init__()
        ui_path = resource_path("export.ui")
        uic.loadUi(ui_path, self)
        self.setWindowTitle("Export Data")

        # Auto-connect semua menu action ke handler generik
        self.wire_menu_actions()

#menu ETF
class InsertETFWindow(BaseWindow):
    def __init__(self):
        super(InsertETFWindow, self).__init__()
        # Dapatkan path direktori file ini
        ui_path = resource_path("insert_etf.ui")
        uic.loadUi(ui_path, self)
        self.setWindowTitle("Insert ETF")

        # Auto-connect semua menu action ke handler generik
        self.wire_menu_actions()
        #default tanggal
        self.tanggal_mulai.setDate(QDate.currentDate())
        #hendler button
        self.pushButton.clicked.connect(self.pushButton_clicked)
        self.btn_clear.clicked.connect(self.btn_clear_clicked)
        
    def pushButton_clicked(self):
        # Mengambil data dari UI (nama variabel di UI tidak perlu diubah)
        isi_nama_kik = self.nama_kik.text()
        isi_underlying_aset = self.underlying.text()
        isi_kode_kik = self.kode_kik.text()
        isi_jumlah_unit_yang_dicatat = self.jml_unit.text()
        isi_jumlah_maksimum_unit_penyertaan = self.jml_maksimum.text()
        isi_harga_perdana = self.harga_perdana.text()
        isi_nilai_awal = self.nilai_awal.text()
        isi_manajemen_investasi = self.manajemen_investasi.text()
        isi_bank_kustodian = self.bank_kustodian.text()
        isi_dealer_participan = self.dealer.text()
        isi_tanggal_mulai = self.tanggal_mulai.date().toString("yyyy-MM-dd")

        print (isi_nama_kik)
        print (isi_underlying_aset)
        print (isi_kode_kik)
        print (isi_jumlah_unit_yang_dicatat)
        print (isi_jumlah_maksimum_unit_penyertaan)
        print (isi_harga_perdana)
        print (isi_nilai_awal)
        print (isi_manajemen_investasi)
        print (isi_bank_kustodian)
        print (isi_dealer_participan)
        print (isi_tanggal_mulai)

        if not isi_nama_kik or not isi_kode_kik or not isi_jumlah_unit_yang_dicatat or not isi_jumlah_maksimum_unit_penyertaan or not isi_harga_perdana or not isi_nilai_awal or not isi_manajemen_investasi or not isi_bank_kustodian or not isi_dealer_participan or not isi_tanggal_mulai:
        
            QMessageBox.warning(self, "Peringatan", "data harus di isi dengan lengkap.")
            return
        
        pesan = "Apakah data sudah benar?\n\n"
        result = QMessageBox.question(self, 'Konfirmasi', pesan,
                                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if result == QMessageBox.Yes:
            print('Yes clicked.')
        else:
            print('No clicked.')
        self.show()
        koneksi = None  # Inisialisasi di luar try agar bisa diakses di finally
        try:
            # =======================================================
            # KONEKSI KE DATABASE MYSQL
            # =======================================================
            koneksi = mysql.connector.connect(**DB_CONFIG)
            cursor = koneksi.cursor()

            # QUERY INSERT DISESUAIKAN DENGAN FIELD DATABASE MYSQL
            perintahSQL = """
                INSERT INTO ca_etf (
                    name_kik, 
                    under_aset, 
                    kik_code, 
                    num_list_units, 
                    max_num_units, 
                    int_Prc, 
                    int_val, 
                    invest_management, 
                    cust_bank, 
                    part_dealers, 
                    trading_date
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            # Data yang akan dimasukkan (urutan harus sama dengan kolom di atas)
            values = (
                isi_nama_kik,
                isi_underlying_aset,
                isi_kode_kik,
                isi_jumlah_unit_yang_dicatat,
                isi_jumlah_maksimum_unit_penyertaan,
                isi_harga_perdana,
                isi_nilai_awal,
                isi_manajemen_investasi,
                isi_bank_kustodian,
                isi_dealer_participan,
                isi_tanggal_mulai
            )
            
            cursor.execute(perintahSQL, values)
            koneksi.commit()
            
            QMessageBox.information(self, "Sukses", "Data Berhasil Disimpan")
            
        except mysql.connector.Error as e:
            QMessageBox.critical(self, "Error Database", f"Gagal menyimpan data:\n\n{e}")
            print("Gagal menyimpan data :", e)

        finally:
            if koneksi and koneksi.is_connected():
                koneksi.close()

    def btn_clear_clicked(self):
        self.nama_kik.clear()
        self.underlying.clear()
        self.kode_kik.clear()
        self.jml_unit.clear()
        self.jml_maksimum.clear()
        self.harga_perdana.clear()
        self.nilai_awal.clear()
        self.manajemen_investasi.clear()
        self.bank_kustodian.clear()
        self.dealer.clear()
        self.tanggal_mulai.clear()

    

class EditETFWindow(BaseWindow):
    def __init__(self, db_path="cpca.db"):
        super(EditETFWindow, self).__init__()
        
        try:
            
            ui_path = resource_path("edit_etf.ui")
            uic.loadUi(ui_path, self)
            self.setWindowTitle("Edit ETF")

            # Auto-connect semua menu action ke handler generik
            self.wire_menu_actions()
            #handler button
            self.btn_clear.clicked.connect(self.clear_form)
            self.pushButton.clicked.connect(self.save_change_clicked)
            self.check_id.clicked.connect(self.check_id_clicked)
            
            self.current_etf_id = None
            # ... dst ...
            
            self.set_form_locked(True)
            
        except Exception as e:
            err = traceback.format_exc()
            logger.critical(f"Gagal init EditETFWindow:\n{err}")
            QtWidgets.QMessageBox.critical(
                self, "Error Init",
                f"Gagal memuat Edit ETF:\n\n{type(e).__name__}: {e}\n\n"
                f"Cek log: {GLOBAL_LOG_FILE}"
            )

        #self.check_id.clicked.connect(self.check_id_clicked)
        #self.save_change.clicked.connect(self.save_change_clicked)
        #self.clear.clicked.connect(self.clear_form)

        #self.set_form_locked()

        # Path database
        self.db_path = db_path
        
        # State: ID yang sedang diedit (None = mode insert baru)
        self.current_etf_id = None

        

    # ============================================================
    # DATABASE HELPER
    # ============================================================
    def get_connection(self):
        """Buat koneksi ke database MySQL server remote"""
        return mysql.connector.connect(**DB_CONFIG)

    def fetch_etf_by_id(self, etf_id):
        """Ambil data dari ca_etf berdasarkan ID."""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM ca_etf WHERE id = %s", (etf_id,))
            row = cursor.fetchone()
            cursor.close()
            return row
        except Exception as e:
            # TANGKAP SEMUA ERROR (bukan hanya mysql.connector.Error)
            import traceback
            err = traceback.format_exc()
            print("=== ERROR fetch_etf_by_id ===")
            print(err)
            QtWidgets.QMessageBox.critical(
                self, "Database Error",
                f"Gagal membaca data:\n\n{type(e).__name__}: {e}\n\n{err[:500]}"
            )
            return None
        finally:
            if conn:
                try:
                    if conn.is_connected():
                        conn.close()
                except Exception:
                    pass


    def update_etf(self, etf_id, data: dict) -> bool:
        """Update data di ca_etf berdasarkan ID."""
        if not data:
            return False

        set_clause = ", ".join([f"{k} = %s" for k in data.keys()])
        values = list(data.values()) + [etf_id]
        query = f"UPDATE ca_etf SET {set_clause}, revised_date = NOW() WHERE id = %s"

        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(query, values)
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            import traceback
            err = traceback.format_exc()
            print("=== ERROR update_etf ===")
            print(err)
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            QtWidgets.QMessageBox.critical(
                self, "Database Error",
                f"Gagal update data:\n\n{type(e).__name__}: {e}\n\n{err[:500]}"
            )
            return False
        finally:
            if conn:
                try:
                    if conn.is_connected():
                        conn.close()
                except Exception:
                    pass

    # ============================================================
    # FORM LOCK / POPULATE / CLEAR
    # ============================================================
    def set_form_locked(self, locked=True):
        """Kunci/buka field input."""
        fields = [
            "nama_kik", "underlying", "kode_kik",
            "jml_unit", "jml_maksimum", "harga_perdana",
            "nilai_awal", "manajemen_investasi", "bank_kustodian",
            "dealer", "tanggal_mulai",
        ]
        for name in fields:
            w = getattr(self, name, None)
            if w is not None:
                w.setEnabled(not locked)

        id_widget = getattr(self, "id", None)
        if id_widget is not None:
            id_widget.setEnabled(self.current_etf_id is None)

        if hasattr(self, "check_id"):
            self.check_id.setEnabled(self.current_etf_id is None)
        
        # Tombol Save (nama widget di .ui = 'pushButton')
        if hasattr(self, "pushButton"):
            self.pushButton.setEnabled(not locked)

    def populate_form(self, data: dict):
        """Isi form dari dict hasil database."""
        mapping = {
            "nama_kik": "name_kik",
            "underlying": "under_aset",
            "kode_kik": "kik_code",
            "jml_unit": "num_list_units",
            "jml_maksimum": "max_num_units",
            "harga_perdana": "int_Prc",
            "nilai_awal": "int_val",
            "manajemen_investasi": "invest_management",
            "bank_kustodian": "cust_bank",
            "dealer": "part_dealers",
        }

        for widget_name, db_col in mapping.items():
            w = getattr(self, widget_name, None)
            if w is not None:
                value = data.get(db_col, "")
                if hasattr(w, "setText"):
                    w.setText(str(value) if value is not None else "")

        # Tanggal
        if hasattr(self, "tanggal_mulai") and data.get("trading_date"):
            try:
                from PyQt5.QtCore import QDate
                tgl = data["trading_date"]
                if hasattr(tgl, "year"):
                    self.tanggal_mulai.setDate(QDate(tgl.year, tgl.month, tgl.day))
                else:
                    self.tanggal_mulai.setDate(QDate.fromString(str(tgl), "yyyy-MM-dd"))
            except Exception as e:
                print(f"Gagal set tanggal: {e}")

    def collect_form_data(self) -> dict:
        """Ambil nilai dari form -> dict."""
        data = {}
        mapping = {
            "nama_kik": "name_kik",
            "underlying": "under_aset",
            "kode_kik": "kik_code",
            "jml_unit": "num_list_units",
            "jml_maksimum": "max_num_units",
            "harga_perdana": "int_Prc",
            "nilai_awal": "int_val",
            "manajemen_investasi": "invest_management",
            "bank_kustodian": "cust_bank",
            "dealer": "part_dealers",
        }

        for widget_name, db_col in mapping.items():
            w = getattr(self, widget_name, None)
            if w is not None and hasattr(w, "text"):
                data[db_col] = w.text().strip()

        if hasattr(self, "tanggal_mulai"):
            data["trading_date"] = self.tanggal_mulai.date().toString("yyyy-MM-dd")

        return data

    def clear_form(self):
        """Kosongkan semua field input."""
        # Kosongkan semua field teks (kecuali ID)
        field_names = [
            "nama_kik", "underlying", "kode_kik",
            "jml_unit", "jml_maksimum", "harga_perdana",
            "nilai_awal", "manajemen_investasi", "bank_kustodian",
            "dealer",
        ]
        for name in field_names:
            w = getattr(self, name, None)
            if w is not None and hasattr(w, "clear"):
                w.clear()

        # Reset tanggal ke hari ini
        if hasattr(self, "tanggal_mulai"):
            from PyQt5.QtCore import QDate
            self.tanggal_mulai.setDate(QDate.currentDate())

        # Reset state
        self.current_etf_id = None
        self.set_form_locked(True)

        # Kosongkan field ID (nama widget di .ui = 'id')
        id_widget = getattr(self, "id", None)
        if id_widget is not None:
            id_widget.clear()

        # Aktifkan kembali tombol Check ID
        if hasattr(self, "check_id"):
            self.check_id.setEnabled(True)

        # Aktifkan kembali field ID dan tombol Check ID
        id_widget = getattr(self, "id", None)
        if id_widget is not None:
            id_widget.setEnabled(True)

        if hasattr(self, "check_id"):
            self.check_id.setEnabled(True)
    # ============================================================
    # HANDLERS
    # ============================================================
    def check_id_clicked(self):
        try:
            id_widget = getattr(self, "id", None)
            if id_widget is None:
                QtWidgets.QMessageBox.warning(
                    self, "Warning", "Widget ID tidak ditemukan di edit_etf.ui."
                )
                return

            etf_id_text = id_widget.text().strip()
            if not etf_id_text:
                QtWidgets.QMessageBox.warning(self, "Warning", "ID ETF tidak boleh kosong!")
                return

            try:
                etf_id = int(etf_id_text)
            except ValueError:
                QtWidgets.QMessageBox.warning(self, "Warning", "ID harus berupa angka!")
                return

            data = self.fetch_etf_by_id(etf_id)
            if data is None:
                self.set_form_locked(True)
                self.current_etf_id = None
                return

            self.current_etf_id = etf_id
            self.populate_form(data)
            self.set_form_locked(False)
            QtWidgets.QMessageBox.information(
                self, "Ditemukan",
                f"Data ETF ID {etf_id} berhasil dimuat. Silakan edit."
            )
        except Exception as e:
            import traceback
            err = traceback.format_exc()
            print("=== ERROR check_id_clicked ===")
            print(err)
            QtWidgets.QMessageBox.critical(
                self, "Error",
                f"Terjadi kesalahan:\n\n{type(e).__name__}: {e}\n\n{err[:500]}"
            )

    def save_change_clicked(self):
        try:
            if self.current_etf_id is None:
                QtWidgets.QMessageBox.warning(
                    self, "Warning", "Tidak ada data yang sedang diedit."
                )
                return

            if not self.validate_input():
                return

            reply = QtWidgets.QMessageBox.question(
                self, "Konfirmasi",
                f"Simpan perubahan untuk ETF ID {self.current_etf_id}?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )
            if reply != QtWidgets.QMessageBox.Yes:
                return

            data = self.collect_form_data()
            success = self.update_etf(self.current_etf_id, data)

            if success:
                QtWidgets.QMessageBox.information(
                    self, "Sukses",
                    f"Data ETF ID {self.current_etf_id} berhasil diperbarui."
                )
                self.set_form_locked(True)
            else:
                QtWidgets.QMessageBox.warning(
                    self, "Gagal",
                    "Tidak ada perubahan yang disimpan atau terjadi kesalahan."
                )
        except Exception as e:
            import traceback
            err = traceback.format_exc()
            print("=== ERROR save_change_clicked ===")
            print(err)
            QtWidgets.QMessageBox.critical(
                self, "Error",
                f"Terjadi kesalahan:\n\n{type(e).__name__}: {e}\n\n{err[:500]}"
            )

    def btn_clear_clicked(self):
        """Handler tombol Clear."""
        self.clear_form()

    def validate_input(self) -> bool:
        if hasattr(self, "nama_kik"):
            if not self.nama_kik.text().strip():
                QtWidgets.QMessageBox.warning(
                    self, "Validasi", "Nama KIK tidak boleh kosong!"
                )
                return False
        return True

    def closeEvent(self, event):
        """Bersihkan referensi saat window ditutup."""
        self.form_export = None
        self.form_downloader = None
        self.form_batch_insert = None
        self.form_edit = None
        self.form_edit_etf = None
        event.accept()


class ProcessWorker(QThread):
    """Thread untuk memproses file di background agar UI tidak freeze"""
    
    progress_updated = pyqtSignal(int, str)  # idx, filename
    statistics_updated = pyqtSignal(int, int, int, int)  # total, success, error, duplicate
    row_added = pyqtSignal(int, str, dict, str, str)  # no, filename, data, status, keterangan
    finished = pyqtSignal(int, int, int, list)  # total, success, error, error_details
    
    def __init__(self, folder_path):
        super().__init__()
        self.folder_path = folder_path
        self.is_running = True
    
    def run(self):
        """Proses semua file PDF"""
        
        # Cari file PDF
        pdf_files = [f for f in os.listdir(self.folder_path) if f.lower().endswith('.pdf')]
        pdf_files.sort()
        
        if not pdf_files:
            self.finished.emit(0, 0, 0, [])
            return
        
        total = len(pdf_files)
        success = 0
        error = 0
        duplicate = 0
        error_details = []
        
        # Buat folder hasil
        parent = os.path.dirname(self.folder_path)
        success_folder = os.path.join(parent, 'success_processed')
        error_folder = os.path.join(parent, 'error_processed')
        os.makedirs(success_folder, exist_ok=True)
        os.makedirs(error_folder, exist_ok=True)
        
        for idx, filename in enumerate(pdf_files, 1):
            if not self.is_running:
                break
            
            pdf_path = os.path.join(self.folder_path, filename)
            
            data = {
                'nama_kik': '',
                'underlying_aset': '',
                'kode_kik': '',
                'jumlah_unit': '',
                'jumlah_max': '',
                'harga_perdana': '',
                'nilai_awal': '',
                'manajemen_investasi': '',
                'bank_kustodian': '',
                'dealer_participant': '',
                'tanggal_mulai': ''
            }
            
            try:
                # Step 1: Extract PDF
                text = self.extract_pdf_text(pdf_path)
                if not text.strip():
                    raise ValueError("PDF tidak memiliki teks.")
                
                # Step 2: Parse Data
                data = self.parse_pdf_data(text)
                
                # Step 3: Validasi
                valid, missing = self.validate_data(data)
                if not valid:
                    raise ValueError(f"Field kosong: {', '.join(missing)}")
                
                # Step 4: Cek Duplikat
                if self.check_duplicate(data['kode_kik']):
                    duplicate += 1
                    error += 1
                    keterangan = f"Kode {data['kode_kik']} sudah ada"
                    error_details.append(f"{filename}: {keterangan}")
                    self.row_added.emit(idx, filename, data, "DUPLIKAT", keterangan)
                    self.move_file(pdf_path, error_folder)
                    self.statistics_updated.emit(total, success, error, duplicate)
                    continue
                
                # Step 5: Insert Database
                self.insert_to_database(data)
                
                # Step 6: Move Success
                self.move_file(pdf_path, success_folder)
                success += 1
                self.row_added.emit(idx, filename, data, "BERHASIL", "Data berhasil diinsert")
                
            except Exception as e:
                error += 1
                error_msg = str(e)
                error_details.append(f"{filename}: {error_msg}")
                self.row_added.emit(idx, filename, data, "ERROR", error_msg[:100])
                
                if os.path.exists(pdf_path):
                    try:
                        self.move_file(pdf_path, error_folder)
                    except Exception:
                        pass
            
            # Update progress
            self.progress_updated.emit(idx, filename)
            self.statistics_updated.emit(total, success, error, duplicate)
        
        self.finished.emit(total, success, error, error_details)
    
    # ==========================================================
    # FUNGSI PARSING PDF (SAMA DENGAN SEBELUMNYA)
    # ==========================================================
    
    def extract_pdf_text(self, pdf_path):
        """Ekstrak teks dari PDF"""
        text = ""
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        except Exception as e:
            raise Exception(f"Gagal baca PDF: {e}")
        return text
    
    def clean_number(self, value):
        """Bersihkan format angka dan ubah ke format koma (20.000.000 -> 20,000,000)"""
        if not value:
            return ""
        
        value = str(value).strip()
        
        # Hapus Rp
        value = re.sub(r'Rp\.?', '', value, flags=re.IGNORECASE)
        
        # Hapus spasi
        value = value.replace(" ", "")
        
        # Hapus titik dan koma lama untuk dibersihkan
        value = value.replace(".", "")
        value = value.replace(",", "")
        
        # Hanya ambil angka
        value = re.sub(r'[^0-9]', '', value)
        
        if not value:
            return ""
        
        # Konversi ke integer dan format dengan koma
        try:
            number = int(value)
            return f"{number:,}"  # Hasil: "20,000,000"
        except ValueError:
            return value
    
    def clean_text(self, value):
        """Bersihkan teks"""
        if not value:
            return ""
        return str(value).strip()
    
    def convert_date(self, tanggal_str):
        """Konversi tanggal ke YYYY-MM-DD"""
        if not tanggal_str:
            return "1970-01-01"
        
        tanggal_str = str(tanggal_str).strip()
        
        bulan_map = {
            'januari': '01', 'februari': '02', 'maret': '03',
            'april': '04', 'mei': '05', 'juni': '06',
            'juli': '07', 'agustus': '08', 'september': '09',
            'oktober': '10', 'november': '11', 'desember': '12',
            'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04',
            'may': '05', 'jun': '06', 'jul': '07', 'aug': '08',
            'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'
        }
        
        # Format: DD Month YYYY
        match = re.search(r'(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})', tanggal_str)
        if match:
            day, month, year = match.groups()
            month_num = bulan_map.get(month.lower())
            if month_num:
                return f"{year}-{month_num}-{day.zfill(2)}"
        
        # Format: DD/MM/YYYY atau DD-MM-YYYY
        match = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})', tanggal_str)
        if match:
            day, month, year = match.groups()
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        
        # Format: YYYY-MM-DD
        if re.match(r'^\d{4}-\d{2}-\d{2}$', tanggal_str):
            return tanggal_str
        
        return "1970-01-01"
    
    def parse_pdf_data(self, text):
        """Parsing data dari teks PDF"""
        data = {
            'nama_kik': '',
            'underlying_aset': '',
            'kode_kik': '',
            'jumlah_unit': '',
            'jumlah_max': '',
            'harga_perdana': '',
            'nilai_awal': '',
            'manajemen_investasi': '',
            'bank_kustodian': '',
            'dealer_participant': '',
            'tanggal_mulai': ''
        }
        
        text = text.replace('\xa0', ' ')
        
        # Pola regex untuk ekstrak data
        patterns = {
            'nama_kik': [
                r'Nama KIK\s*[:]?\s*([^\n]+?)(?=\s*Underlying|\s*Kode|$)',
                r'Name of Collective Investment Contract.*?[:]?\s*([^\n]+?)(?=\s*Underlying|\s*KIK|\s*$)'
            ],
            'underlying_aset': [
                r'Underlying Aset\s*[:]?\s*([^\n]*?)(?=\s*Kode|\s*KIK|\s*Jumlah|\n\n|$)',
                r'Underlying Asset\s*[:]?\s*([^\n]*?)(?=\s*KIK|\s*Code|\s*Number|\n\n|$)'
            ],
            'kode_kik': [
                r'Kode KIK\s*[:]?\s*([A-Z0-9]+)',
                r'KIK Code\s*[:]?\s*([A-Z0-9]+)'
            ],
            'jumlah_unit': [
                r'Jumlah Unit Yang dicatatkan\s*[:]?\s*([\d\.]+)',
                r'Number of Listed Units\s*[:]?\s*([\d\.]+)'
            ],
            'jumlah_max': [
                r'Jumlah Maksimum Unit Penyerataan\s*[:]?\s*([\d\.]+)',
                r'Maximum Number of Units\s*[:]?\s*([\d\.]+)'
            ],
            'harga_perdana': [
                r'Harga Perdana\s*[:]?\s*([\d\.]+)',
                r'Initial Price\s*[:]?\s*([\d\.]+)'
            ],
            'nilai_awal': [
                r'Nilai Awal\s*[:]?\s*([\d\.]+)',
                r'Initial Value\s*[:]?\s*([\d\.]+)'
            ],
            'manajemen_investasi': [
                r'Manajemen Investasi\s*[:]?\s*([^\n]+)',
                r'Investment Management\s*[:]?\s*([^\n]+)'
            ],
            'bank_kustodian': [
                r'Bank Kustodian\s*[:]?\s*([^\n]+)',
                r'Custodian Bank\s*[:]?\s*([^\n]+)'
            ],
            'dealer_participant': [
                r'Dealer Participant\s*[:]?\s*([^\n]+)',
                r'Participating Dealers?\s*[:]?\s*([^\n]+)'
            ],
            'tanggal_mulai': [
                r'Tanggal Mulai Perdagangan\s*[:]?\s*([^\n]+)',
                r'Listing and Initial Trading Date\s*[:]?\s*([^\n]+)',
                r'Initial Listing and Trading Date\s*[:]?\s*([^\n]+)'
            ]
        }
        
        for key, pattern_list in patterns.items():
            for pattern in pattern_list:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    value = match.group(1).strip()
                    # 🔥 CEK APAKAH VALUE KOSONG ATAU TIDAK 🔥
                    if key == 'underlying_aset':
                    # Jika value kosong atau berisi whitespace, tetap kosong
                        if not value or value == '':
                            data[key] = ''
                        else:
                            # Bersihkan value
                            data[key] = self.clean_text(value)
                        break
                    elif key in ['jumlah_unit', 'jumlah_max', 'harga_perdana', 'nilai_awal']:
                        value = self.clean_number(value)
                    elif key == 'tanggal_mulai':
                        value = self.convert_date(value)
                    else:
                        value = self.clean_text(value)
                    data[key] = value
                    break
        
        return data
    
    def validate_data(self, data):
        """Validasi data wajib"""
        required = {
            'nama_kik': 'Nama KIK',
            'kode_kik': 'Kode KIK',
            'jumlah_unit': 'Jumlah Unit',
            'manajemen_investasi': 'Manajemen Investasi',
            'bank_kustodian': 'Bank Kustodian'
        }
        
        missing = []
        for field, label in required.items():
            if not data.get(field, ''):
                missing.append(label)
        
        return len(missing) == 0, missing
    
    def check_duplicate(self, kode_kik):
        """Cek duplikat berdasarkan kode KIK"""
        conn = None
        try:
            conn = mysql.connector.connect(**DB_CONFIG)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM ca_etf WHERE kik_code = %s", (kode_kik,))
            result = cursor.fetchone()
            return result[0] > 0
        except Error as e:
            print(f"Error cek duplikat: {e}")
            return False
        finally:
            if conn and conn.is_connected():
                conn.close()
    
    def insert_to_database(self, data):
        """Insert data ke database"""
        conn = None
        try:
            conn = mysql.connector.connect(**DB_CONFIG)
            cursor = conn.cursor()
            
            # 1. Query: 11 Kolom, 11 Tanda %s
            query = """
                INSERT INTO ca_etf (
                    name_kik, 
                    under_aset, 
                    kik_code, 
                    num_list_units, 
                    max_num_units, 
                    int_Prc, 
                    int_val, 
                    invest_management, 
                    cust_bank, 
                    part_dealers, 
                    trading_date
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            # 2. Values: 11 Data (Sesuai urutan kolom di atas)
            values = (
                data.get('nama_kik', ''),            # -> name_kik
                data.get('underlying_aset', ''),     # -> under_aset
                data.get('kode_kik', ''),            # -> kik_code
                data.get('jumlah_unit', ''),         # -> num_list_units
                data.get('jumlah_max', ''),          # -> max_num_units
                data.get('harga_perdana', ''),       # -> int_Prc
                data.get('nilai_awal', ''),          # -> int_val
                data.get('manajemen_investasi', ''), # -> invest_management
                data.get('bank_kustodian', ''),      # -> cust_bank
                data.get('dealer_participant', ''),  # -> part_dealers
                data.get('tanggal_mulai', '1970-01-01') # -> trading_date
            )
            
            cursor.execute(query, values)
            conn.commit()
            return cursor.lastrowid
            
        except Error as e:
            if conn:
                conn.rollback()
            raise Exception(f"Error insert: {e}")
        finally:
            if conn and conn.is_connected():
                conn.close()
    
    def move_file(self, src, dest_folder):
        """Pindahkan file ke folder tujuan"""
        os.makedirs(dest_folder, exist_ok=True)
        dest = os.path.join(dest_folder, os.path.basename(src))
        
        if os.path.exists(dest):
            name, ext = os.path.splitext(os.path.basename(src))
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest = os.path.join(dest_folder, f"{name}_{timestamp}{ext}")
        
        shutil.move(src, dest)
        return dest


class BatchETFWindow(BaseWindow):
    def __init__(self):
        super(BatchETFWindow, self).__init__()
        
        # Dapatkan path direktori file ini
        current_dir = os.path.dirname(os.path.abspath(__file__))
        ui_path = resource_path("batch_etf.ui")
        uic.loadUi(ui_path, self)
        self.setWindowTitle("Batch Insert ETF")

        # Auto-connect semua menu action ke handler generik
        self.wire_menu_actions()

        self.folder_path = ""
        self.worker = None

        # ======================================================
        # SET DEFAULT
        # ======================================================
        self.reset_statistics()  
        self.check_database()
        self.setup_table()

        #mengoneksikan button import dan proses
        self.btn_import.clicked.connect(self.browse_folder)
        self.btn_proses.clicked.connect(self.start_process)
    
    def setup_table(self):
        """Setup table widget"""
        table = self.get_table()
        if table:
            # Set header
            headers = ["No", "Nama File", "Kode", "Nama KIK", "Tanggal", "Status", "Keterangan"]
            table.setColumnCount(len(headers))
            table.setHorizontalHeaderLabels(headers)
            
            # Set column widths
            table.setColumnWidth(0, 40)   # No
            table.setColumnWidth(1, 180)  # Nama File
            table.setColumnWidth(2, 80)   # Kode
            table.setColumnWidth(3, 250)  # Nama KIK
            table.setColumnWidth(4, 100)  # Tanggal
            table.setColumnWidth(5, 80)   # Status
            table.setColumnWidth(6, 200)  # Keterangan
            
            # Set selection mode
            table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
            table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
    
    def get_table(self):
        """Dapatkan table widget"""
        names = ['tableWidget', 'tableWidget_result', 'tbl_result', 'tbl_hasil']
        for name in names:
            widget = self.findChild(QtWidgets.QTableWidget, name)
            if widget:
                return widget
        return None
    
    def get_process_button(self):
        """Dapatkan tombol proses"""
        if hasattr(self, "btn_proses"):
            return self.btn_proses
        return None
    
    def get_folder_input(self):
        """Dapatkan input folder"""
        if hasattr(self, "txt_path"):
            return self.txt_path
        return None

    def check_database(self):
        """Cek koneksi database"""
        try:
            conn = mysql.connector.connect(**DB_CONFIG)
            if conn.is_connected():
                print("✅ Koneksi database berhasil")
                conn.close()
                return True
        except Error as e:
            print(f"❌ Gagal koneksi: {e}")
            QMessageBox.warning(self, "Database", f"Gagal koneksi ke database:\n\n{e}")
            return False
        return False

    def browse_folder(self):
        """Pilih folder PDF"""
        folder = QFileDialog.getExistingDirectory(self, "Pilih Folder PDF ETF")
        if folder:
            self.folder_path = folder
            folder_input = self.get_folder_input()
            if folder_input:
                folder_input.setText(folder)
            self.check_paths()

    def check_paths(self):
        """Cek path valid"""
        valid = self.folder_path and os.path.exists(self.folder_path)
        btn = self.get_process_button()
        if btn:
            btn.setEnabled(valid)

    def reset_statistics(self):
        """Reset statistik"""
        self.total_files = 0
        self.success_count = 0
        self.error_count = 0
        self.duplicate_count = 0
        self.update_statistics()
        self.clear_table()

    def update_statistics(self):
        """Update label statistik"""
        mapping = {
            'label_total': f'Total: {self.total_files}',
            'lbl_total': f'Total: {self.total_files}',
            'label_berhasil': f'Berhasil: {self.success_count}',
            'lbl_berhasil': f'Berhasil: {self.success_count}',
            'label_error': f'Error: {self.error_count}',
            'lbl_error': f'Error: {self.error_count}',
            'label_duplikat': f'Duplikat: {self.duplicate_count}',
            'lbl_duplikat': f'Duplikat: {self.duplicate_count}'
        }
        
        for name, text in mapping.items():
            widget = self.findChild(QtWidgets.QLabel, name)
            if widget:
                widget.setText(text)
        
        QtWidgets.QApplication.processEvents()
    
    def clear_table(self):
        """Clear table"""
        table = self.get_table()
        if table:
            table.setRowCount(0)

    def add_table_row(self, no, filename, data, status, keterangan):
        """Tambah row ke tabel"""
        table = self.get_table()
        if not table:
            return
        
        row = table.rowCount()
        table.insertRow(row)
        
        values = [
            str(no),
            filename,
            data.get('kode_kik', ''),
            data.get('nama_kik', '')[:50],
            data.get('tanggal_mulai', ''),
            status,
            keterangan
        ]
        
        for col, value in enumerate(values):
            item = QTableWidgetItem(str(value))
            # Warna berdasarkan status
            if status == "BERHASIL":
                item.setBackground(Qt.green)
            elif status == "DUPLIKAT":
                item.setBackground(Qt.yellow)
            elif status == "ERROR":
                item.setBackground(Qt.red)
            table.setItem(row, col, item)
        
        table.scrollToBottom()

    # ==========================================================
    # PROCESS FUNCTIONS
    # ==========================================================
    
    def start_process(self):
        """Mulai proses di thread terpisah"""
        
        # Cek folder
        if not self.folder_path:
            folder_input = self.get_folder_input()
            if folder_input:
                self.folder_path = folder_input.text().strip()
        
        if not self.folder_path:
            QMessageBox.warning(self, "Peringatan", "Silakan pilih folder PDF terlebih dahulu.")
            return
        
        if not os.path.exists(self.folder_path):
            QMessageBox.critical(self, "Error", "Folder PDF tidak ditemukan.")
            return
        
        # Reset UI
        self.reset_statistics()
        self.clear_table()
        
        # Disable tombol
        btn = self.get_process_button()
        if btn:
            btn.setEnabled(False)
            btn.setText("Processing...")
        
        # Buat worker thread
        self.worker = ProcessWorker(self.folder_path)
        self.worker.progress_updated.connect(self.on_progress_updated)
        self.worker.statistics_updated.connect(self.on_statistics_updated)
        self.worker.row_added.connect(self.add_table_row)
        self.worker.finished.connect(self.on_process_finished)
        
        # Start thread
        self.worker.start()
    
    def on_progress_updated(self, idx, filename):
        """Update progress"""
        self.statusBar().showMessage(f"Memproses file {idx}: {filename}")
    
    def on_statistics_updated(self, total, success, error, duplicate):
        """Update statistik"""
        self.total_files = total
        self.success_count = success
        self.error_count = error
        self.duplicate_count = duplicate
        self.update_statistics()
    
    def on_process_finished(self, total, success, error, error_details):
        """Selesai proses"""
        # Enable tombol
        btn = self.get_process_button()
        if btn:
            btn.setEnabled(True)
            btn.setText("Process Files")
        
        self.statusBar().showMessage("Selesai!")
        
        # Tampilkan summary
        self.show_summary(total, success, error, error_details)
    
    def show_summary(self, total, success, error, error_details):
        """Tampilkan ringkasan hasil"""
        parent = os.path.dirname(self.folder_path)
        success_folder = os.path.join(parent, 'success_processed')
        error_folder = os.path.join(parent, 'error_processed')
        
        text = f"""
BATCH INSERT ETF SELESAI

Total File : {total}
Berhasil   : {success}
Error      : {error}
Duplikat   : {self.duplicate_count}

Success Folder: {success_folder}
Error Folder: {error_folder}
        """
        
        if error_details:
            text += "\n\nDETAIL ERROR:\n" + "\n".join(f"• {e}" for e in error_details[:10])
            if len(error_details) > 10:
                text += f"\n• ... dan {len(error_details) - 10} error lainnya"
        
        QMessageBox.information(self, "Batch Insert ETF", text)

    
class ExportETFWindow(BaseWindow):
    def __init__(self):
        super(ExportETFWindow, self).__init__()
        
        # Dapatkan path direktori file ini
        current_dir = os.path.dirname(os.path.abspath(__file__))
        ui_path = resource_path("export_etf.ui")
        uic.loadUi(ui_path, self)
        self.setWindowTitle("Export ETF Data")

        # Auto-connect semua menu action ke handler generik
        self.wire_menu_actions()
        #hendler button
        self.btn_export.clicked.connect(self.export_ke_xml)

    # =========================================================
    # METHOD BARU: UNTUK EXPORT DATABASE KE XML
    # =========================================================
    def export_ke_xml(self):
        # 1. Tentukan folder tujuan secara otomatis
        folder_tujuan = r"D:/IDX_Data/ETF/xml_etf"
        
        # Buat foldernya jika belum ada
        if not os.path.exists(folder_tujuan):
            try:
                os.makedirs(folder_tujuan)
            except Exception as e:
                QMessageBox.critical(self, "Error Folder", f"Gagal membuat folder:\n{e}")
                return

        # 2. Ambil tanggal dari UI
        try:
            start_date = self.dateEdit.date().toString("yyyy-MM-dd")
            end_date = self.dateEdit_2.date().toString("yyyy-MM-dd")
        except AttributeError:
            QMessageBox.warning(self, "Peringatan", "Pastikan komponen tanggal (dateEdit & dateEdit_2) sudah ada di UI.")
            return

        # Validasi: Pastikan Start Date tidak lebih besar dari End Date
        if start_date > end_date:
            QMessageBox.warning(self, "Peringatan", "Start Date tidak boleh lebih besar dari End Date!")
            return

        # 3. Tentukan nama file berdasarkan rentang tanggal
        nama_file = f"data_etf_{end_date}.xml"
        file_path = os.path.join(folder_tujuan, nama_file)

        try:
            # 4. Koneksi ke Database
            conn = mysql.connector.connect(**DB_CONFIG)
            cursor = conn.cursor(dictionary=True) 
            
            # 5. Query dengan Filter Tanggal (Menggunakan revised_date)
            query = """
                SELECT * FROM ca_etf 
                WHERE revised_date BETWEEN %s AND %s
                ORDER BY revised_date ASC
            """
            params = (f"{start_date} 00:00:00", f"{end_date} 23:59:59")
            
            cursor.execute(query, params)
            records = cursor.fetchall()
            
            # Cek jika tidak ada data
            if not records:
                QMessageBox.information(self, "Info", f"Tidak ada data {start_date} dan {end_date}.")
                cursor.close()
                conn.close()
                return

            # =========================================================
            # 6. BUAT STRUKTUR XML
            # =========================================================
            
            # A. Root Element: <table name="ca_etf">
            root = ET.Element("table", name="ca_etf")
            
            # B. Bagian <fields> (Definisi Kolom)
            # Kita hardcode sesuai struktur tabel ca_etf
            fields_element = ET.SubElement(root, "fields")
            
            # Daftar kolom: (nama, tipe, atribut_tambahan)
            daftar_kolom = [
                ("id", "int", {"primary_key": "yes"}),
                ("name_kik", "varchar(50)", {}),           
                ("under_aset", "varchar(50)", {}),         
                ("kik_code", "varchar(50)", {}),           
                ("num_list_units", "varchar(50)", {}),     
                ("max_num_units", "varchar(50)", {}),      
                ("int_Prc", "varchar(10)", {}),            
                ("int_val", "varchar(50)", {}),            
                ("invest_management", "varchar(50)", {}),  
                ("cust_bank", "varchar(50)", {}),          
                ("part_dealers", "varchar(50)", {}),       
                ("trading_date", "date", {}),              
                ("created_date", "datetime", {}),          
                ("revised_date", "datetime", {}),          # <-- Tetap
            ]
            
            for nama, tipe, atribut in daftar_kolom:
                field_attrs = {"name": nama, "type": tipe}
                field_attrs.update(atribut) # Tambahkan atribut seperti primary_key
                ET.SubElement(fields_element, "field", field_attrs)
            
            # C. Bagian <records> (Isi Data)
            records_element = ET.SubElement(root, "records")
            
            for row in records:
                # Setiap baris dibungkus dengan <record>
                record_element = ET.SubElement(records_element, "record")
                
                for key, value in row.items():
                    child = ET.SubElement(record_element, str(key))
                    # Format datetime agar lebih rapi
                    if isinstance(value, datetime):
                        child.text = value.strftime("%Y-%m-%d %H:%M:%S")
                    else:
                        child.text = str(value) if value is not None else ""
            
            # =========================================================
            
            # 7. Simpan ke File
            tree = ET.ElementTree(root)
            ET.indent(tree, space="    ") 
            # Gunakan encoding utf-8 dan xml_declaration=True seperti di gambar
            tree.write(file_path, encoding="utf-8", xml_declaration=True)
            
            # 8. Tutup koneksi
            cursor.close()
            conn.close()
            
            # 9. Tampilkan pesan sukses
            QMessageBox.information(self, "Sukses", f"Berhasil mengekspor {len(records)} data ke:\n{file_path}")
            
        except mysql.connector.Error as err:
            QMessageBox.critical(self, "Error Database", f"Gagal mengambil data: {err}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Terjadi kesalahan: {e}")


#Suspend
class InsertSuspendWindow(BaseWindow):
    def __init__(self):
        super(InsertSuspendWindow, self).__init__()
        
        # Dapatkan path direktori file ini
        current_dir = os.path.dirname(os.path.abspath(__file__))
        ui_path = resource_path("insert_suspend.ui")
        uic.loadUi(ui_path, self)
        self.setWindowTitle("Insert Suspend")

        # Auto-connect semua menu action ke handler generik
        self.wire_menu_actions()

        self.date.setDate(QDate.currentDate())
        #tombol hendler add & clear
        self.pushButton.clicked.connect(self.pushButton_clicked)
        self.btn_clear.clicked.connect(self.btn_clear_clicked)

    def pushButton_clicked(self):
        # Mengambil data dari UI (nama variabel di UI tidak perlu diubah)
        isi_code = self.code.text()
        isi_company = self.company.text()
        isi_remark = self.remark.currentText()
        isi_details = self.details.toPlainText()
        isi_date = self.date.date().toString("yyyy-MM-dd")

        print (isi_code)
        print (isi_company)
        print (isi_remark)
        print (isi_details)
        print (isi_date)

        if not isi_code or not isi_company or not isi_details or not isi_date:
                
            QMessageBox.warning(self, "Peringatan", "data harus di isi dengan lengkap.")
            return

        if self.remark.currentIndex() == 0:   # FIX: cek "Select Status"
            QMessageBox.warning(self, "Peringatan", "Silakan pilih Remark.")
            return
        
        pesan = "Apakah data sudah benar?\n\n"
        result = QMessageBox.question(self, 'Konfirmasi', pesan,
                                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if result != QMessageBox.Yes:
            return   # FIX: jangan lanjut kalau No
    
        koneksi = None  # Inisialisasi di luar try agar bisa diakses di finally
        try:
            # =======================================================
            # KONEKSI KE DATABASE MYSQL
            # =======================================================
            koneksi = mysql.connector.connect(**DB_CONFIG)
            cursor = koneksi.cursor()

            # QUERY INSERT DISESUAIKAN DENGAN FIELD DATABASE MYSQL
            perintahSQL = """
                INSERT INTO ca_suspend (
                    code,
                    company_name,
                    remark,
                    information,
                    date
                ) VALUES (%s, %s, %s, %s, %s)
            """
            
            # Data yang akan dimasukkan (urutan harus sama dengan kolom di atas)
            values = (
                isi_code,
                isi_company,
                isi_remark,
                isi_details,
                isi_date
            )
            
            cursor.execute(perintahSQL, values)
            koneksi.commit()
            
            QMessageBox.information(self, "Sukses", "Data Berhasil Disimpan")
            
        except mysql.connector.Error as e:
            QMessageBox.critical(self, "Error Database", f"Gagal menyimpan data:\n\n{e}")
            print("Gagal menyimpan data :", e)

        finally:
            if koneksi and koneksi.is_connected():
                koneksi.close()

    def btn_clear_clicked(self):
        self.code.clear()
        self.company.clear()
        self.remark.clear()
        self.details.clear()
        self.date.clear()


class EditSuspendWindow(BaseWindow):
    def __init__(self, db_path="cpca.db"):
        super(EditSuspendWindow, self).__init__()
        # Dapatkan path direktori file ini
        current_dir = os.path.dirname(os.path.abspath(__file__))
        ui_path = resource_path("edit_suspend.ui")
        uic.loadUi(ui_path, self)
        self.setWindowTitle("Edit Suspend")

        # Auto-connect semua menu action ke handler generik
        self.wire_menu_actions()
        #hendler button
        self.btn_clear.clicked.connect(self.clear_form)
        self.pushButton.clicked.connect(self.save_change_clicked)
        self.check_id.clicked.connect(self.check_id_clicked)
        
        self.current_suspend_id = None
        self.set_form_locked(True)
        # Path database
        self.db_path = db_path
        # State: ID yang sedang diedit (None = mode insert baru)
        self.current_suspend_id = None

    # ============================================================
    # DATABASE HELPER
    # ============================================================
    def get_connection(self):
        """Buat koneksi ke database MySQL server remote"""
        return mysql.connector.connect(**DB_CONFIG)

    def fetch_suspend_by_id(self, suspend_id):
        """Ambil data dari ca_suspend berdasarkan ID."""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM ca_suspend WHERE id = %s", (suspend_id,))
            row = cursor.fetchone()
            cursor.close()
            return row
        except Exception as e:
            # TANGKAP SEMUA ERROR (bukan hanya mysql.connector.Error)
            import traceback
            err = traceback.format_exc()
            print("=== ERROR fetch_suspend_by_id ===")
            print(err)
            QtWidgets.QMessageBox.critical(
                self, "Database Error",
                f"Gagal membaca data:\n\n{type(e).__name__}: {e}\n\n{err[:500]}"
            )
            return None
        finally:
            if conn:
                try:
                    if conn.is_connected():
                        conn.close()
                except Exception:
                    pass

    def update_suspend(self, suspend_id, data: dict) -> bool:
        """Update data di ca_suspend berdasarkan ID."""
        if not data:
            return False

        set_clause = ", ".join([f"{k} = %s" for k in data.keys()])
        values = list(data.values()) + [suspend_id]
        query = f"UPDATE ca_suspend SET {set_clause}, revised_date = NOW() WHERE id = %s"

        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(query, values)
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            import traceback
            err = traceback.format_exc()
            print("=== ERROR update_suspend ===")
            print(err)
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            QtWidgets.QMessageBox.critical(
                self, "Database Error",
                f"Gagal update data:\n\n{type(e).__name__}: {e}\n\n{err[:500]}"
            )
            return False
        finally:
            if conn:
                try:
                    if conn.is_connected():
                        conn.close()
                except Exception:
                    pass

    # ============================================================
    # FORM LOCK / POPULATE / CLEAR
    # ============================================================
    def set_form_locked(self, locked=True):
        """Kunci/buka field input."""
        fields = [
            "code", "company", "remark",
            "details", "date",
        ]
        for name in fields:
            w = getattr(self, name, None)
            if w is not None:
                w.setEnabled(not locked)

        id_widget = getattr(self, "id", None)
        if id_widget is not None:
            id_widget.setEnabled(self.current_suspend_id is None)

        if hasattr(self, "check_id"):
            self.check_id.setEnabled(self.current_suspend_id is None)
        
        # Tombol Save (nama widget di .ui = 'pushButton')
        if hasattr(self, "pushButton"):
            self.pushButton.setEnabled(not locked)

    def populate_form(self, data: dict):
        """Isi form dari dict hasil database."""
        # --- Debug: lihat isi data ---
        print("=== populate_form data ===")
        for k, v in data.items():
            print(f"  {k!r}: {v!r}")

        # --- 1. QLineEdit: code ---
        if hasattr(self, "code"):
            self.code.setText(str(data.get("code") or ""))

        # --- 2. QLineEdit: company ---
        # Coba beberapa kemungkinan nama kolom
        if hasattr(self, "company"):
            company_val = (
                data.get("company_name")
                or data.get("company")
                or ""
            )
            self.company.setText(str(company_val))
            print(f"  → set company = {company_val!r}")

        # --- 3. QTextEdit: details ---
        if hasattr(self, "details"):
            details_val = (
                data.get("information")
                or data.get("details")
                or ""
            )
            self.details.setPlainText(str(details_val))

        # --- 4. QComboBox: remark ---
        if hasattr(self, "remark"):
            remark_raw = data.get("remark") or ""
            print(f"  → remark dari DB = {remark_raw!r}")

            # Bersihkan: hilangkan spasi, ubah ke upper
            remark_clean = str(remark_raw).strip().upper()
            print(f"  → remark_clean = {remark_clean!r}")

            # Cari item yang cocok (case-insensitive manual)
            found_idx = -1
            for i in range(self.remark.count()):
                item_text = self.remark.itemText(i).strip().upper()
                if item_text == remark_clean:
                    found_idx = i
                    break

            if found_idx >= 0:
                self.remark.setCurrentIndex(found_idx)
                print(f"  → remark di-set ke index {found_idx} "
                    f"({self.remark.itemText(found_idx)})")
            else:
                # Fallback: kalau tidak ada yang cocok, coba cari
                # yang mengandung kata kunci
                if "SUSPEND" in remark_clean and "UNSUSPEND" not in remark_clean:
                    self.remark.setCurrentIndex(1)   # SUSPEND
                    print("  → fallback: SUSPEND")
                elif "UNSUSPEND" in remark_clean:
                    self.remark.setCurrentIndex(2)   # UNSUSPEND
                    print("  → fallback: UNSUSPEND")
                else:
                    self.remark.setCurrentIndex(0)   # Select Status
                    print(f"  → tidak ada yang cocok, set ke index 0")

        # --- 5. QDateEdit: date ---
        if hasattr(self, "date") and data.get("date"):
            try:
                tgl = data["date"]
                if hasattr(tgl, "year"):
                    # datetime.date atau datetime.datetime
                    self.date.setDate(QDate(tgl.year, tgl.month, tgl.day))
                else:
                    # string "yyyy-MM-dd"
                    self.date.setDate(QDate.fromString(str(tgl), "yyyy-MM-dd"))
                print(f"  → date di-set ke {self.date.date().toString('yyyy-MM-dd')}")
            except Exception as e:
                print(f"  ⚠ Gagal set tanggal: {e}")


    def collect_form_data(self) -> dict:
        """Ambil nilai dari form -> dict."""
        data = {}
        mapping = {
            "code": "code",
            "company": "company",
        }

        for widget_name, db_col in mapping.items():
            w = getattr(self, widget_name, None)
            if w is not None and hasattr(w, "text"):
                data[db_col] = w.text().strip()

        # QTextEdit (details)
        if hasattr(self, "details"):
            data["information"] = self.details.toPlainText().strip()

        # QComboBox (remark)
        if hasattr(self, "remark"):
            data["remark"] = self.remark.currentText().strip()

        # QDateEdit (date)
        if hasattr(self, "date"):
            data["date"] = self.date.date().toString("yyyy-MM-dd")

        return data

    def clear_form(self):
        """Kosongkan semua field input."""
        # Kosongkan semua field teks (kecuali ID)
        field_names = [
            "code", "company",
        ]
        for name in field_names:
            w = getattr(self, name, None)
            if w is not None and hasattr(w, "clear"):
                w.clear()

        # Kosongkan QTextEdit
        if hasattr(self, "details"):
            self.details.clear()

        # Reset QComboBox ke "Select Status" (index 0)
        if hasattr(self, "remark"):
            self.remark.setCurrentIndex(0)

        # Reset QDateEdit ke hari ini
        if hasattr(self, "date"):
            self.date.setDate(QDate.currentDate())


        # Reset state
        self.current_suspend_id = None
        self.set_form_locked(True)

        # Kosongkan field ID (nama widget di .ui = 'id')
        id_widget = getattr(self, "id", None)
        if id_widget is not None:
            id_widget.clear()

        # Aktifkan kembali tombol Check ID
        if hasattr(self, "check_id"):
            self.check_id.setEnabled(True)

        # Aktifkan kembali field ID dan tombol Check ID
        id_widget = getattr(self, "id", None)
        if id_widget is not None:
            id_widget.setEnabled(True)

        if hasattr(self, "check_id"):
            self.check_id.setEnabled(True)
    # ============================================================
    # HANDLERS
    # ============================================================
    def check_id_clicked(self):
        try:
            id_widget = getattr(self, "id", None)
            if id_widget is None:
                QtWidgets.QMessageBox.warning(
                    self, "Warning", "Widget ID tidak ditemukan di edit_suspend.ui."
                )
                return

            suspend_id_text = id_widget.text().strip()
            if not suspend_id_text:
                QtWidgets.QMessageBox.warning(self, "Warning", "ID Suspend tidak boleh kosong!")
                return

            try:
                suspend_id = int(suspend_id_text)
            except ValueError:
                QtWidgets.QMessageBox.warning(self, "Warning", "ID harus berupa angka!")
                return

            data = self.fetch_suspend_by_id(suspend_id)
            if data is None:
                self.set_form_locked(True)
                self.current_suspend_id = None
                return

            self.current_suspend_id = suspend_id
            self.populate_form(data)
            self.set_form_locked(False)
            
        except Exception as e:
            import traceback
            err = traceback.format_exc()
            print("=== ERROR check_id_clicked ===")
            print(err)
            QtWidgets.QMessageBox.critical(
                self, "Error",
                f"Terjadi kesalahan:\n\n{type(e).__name__}: {e}\n\n{err[:500]}"
            )

    def save_change_clicked(self):
        try:
            if self.current_suspend_id is None:
                QtWidgets.QMessageBox.warning(
                    self, "Warning", "Tidak ada data yang sedang diedit."
                )
                return

            if not self.validate_input():
                return

            reply = QtWidgets.QMessageBox.question(
                self, "Konfirmasi",
                f"Simpan perubahan untuk suspend ID {self.current_suspend_id}?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )
            if reply != QtWidgets.QMessageBox.Yes:
                return

            data = self.collect_form_data()
            success = self.update_etf(self.current_suspend_id, data)

            if success:
                QtWidgets.QMessageBox.information(
                    self, "Sukses",
                    f"Data Suspend ID {self.current_Suspend_id} berhasil diperbarui."
                )
                self.set_form_locked(True)
            else:
                QtWidgets.QMessageBox.warning(
                    self, "Gagal",
                    "Tidak ada perubahan yang disimpan atau terjadi kesalahan."
                )
        except Exception as e:
            import traceback
            err = traceback.format_exc()
            print("=== ERROR save_change_clicked ===")
            print(err)
            QtWidgets.QMessageBox.critical(
                self, "Error",
                f"Terjadi kesalahan:\n\n{type(e).__name__}: {e}\n\n{err[:500]}"
            )

    def btn_clear_clicked(self):
        """Handler tombol Clear."""
        self.clear_form()

    def validate_input(self) -> bool:
        if hasattr(self, "code"):
            if not self.code.text().strip():
                QtWidgets.QMessageBox.warning(
                    self, "Validasi", "Code tidak boleh kosong!"
                )
                return False
        return True

    def closeEvent(self, event):
        """Bersihkan referensi saat window ditutup."""
        self.tutup_semua_form()
        self.forms.clear()
        event.accept()

class DownloaderSuspendWindow(BaseWindow):
    def __init__(self):
        super(DownloaderSuspendWindow, self).__init__()
        
        # Dapatkan path direktori file ini
        current_dir = os.path.dirname(os.path.abspath(__file__))
        ui_path = resource_path("downloader_suspend.ui")
        uic.loadUi(ui_path, self)
        self.setWindowTitle("Downloader Suspend")

        # Auto-connect semua menu action ke handler generik
        self.wire_menu_actions()
        #default date
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit_2.setDate(QDate.currentDate())
        #hendler button
        self.btn_run_3.clicked.connect(self.btn_run_clicked)

    # =========================================================
    # SETUP CHROME
    # =========================================================
    def setup_chrome_options(self, download_path):
        """Setup Chrome options for automatic downloading (undetected-chromedriver)"""
        chrome_options = uc.ChromeOptions()   # ← Ganti ke uc.ChromeOptions()
        
        prefs = {
            "download.default_directory": download_path,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "plugins.always_open_pdf_externally": True,
            "profile.default_content_setting_values.popups": 0,
            "profile.default_content_setting_values.automatic_downloads": 1,
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        # Opsi dasar - TETAP DIPAKAI
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--start-maximized")
        
        # ❌ HAPUS baris user-agent!
        # UCD sudah handle fingerprint secara otomatis.
        # Menambah user-agent manual malah bisa bikin terdeteksi.
        
        return chrome_options

    def _init_chrome_driver(self, chrome_options):
        """
        Init Chrome via undetected-chromedriver.
        Versi Chrome: 152 (sesuaikan kalau Chrome Anda update)
        """
        try:
            print("=" * 60)
            print("Membuka Chrome via undetected-chromedriver...")
            print("Chrome version: 152")
            print("=" * 60)
            
            driver = uc.Chrome(
                options=chrome_options,
                version_main=152,        # ← INI KUNCINYA: paksa versi 152
                use_subprocess=True,
            )
            print("✓ Chrome berhasil dibuka")
            return driver
            
        except Exception as e:
            tb = traceback.format_exc()
            print(f"✗ Gagal: {type(e).__name__}: {e}")
            print(tb)
            
            # Cek kalau error masih sama (versi mismatch)
            err_msg = str(e)
            if "only supports Chrome version" in err_msg:
                # Ekstrak versi dari error
                match = re.search(r'only supports Chrome version (\d+)', err_msg)
                supports = match.group(1) if match else "?"
                
                match2 = re.search(r'Current browser version is (\d+)', err_msg)
                current = match2.group(1) if match2 else "?"
                
                QMessageBox.critical(
                    self, "Versi Chrome Tidak Cocok",
                    f"Versi ChromeDriver ({supports}) tidak cocok\n"
                    f"dengan Chrome Anda ({current}).\n\n"
                    f"Solusi:\n"
                    f"Ubah version_main di kode menjadi {current}\n\n"
                    f"File: menu_utama_umanew.py\n"
                    f"Cari: version_main=...\n"
                    f"Ganti jadi: version_main={current}"
                )
            else:
                QMessageBox.critical(
                    self, "Chrome Error",
                    f"{type(e).__name__}: {e}\n\n"
                    f"Cek log: ~/Desktop/cpca_error.log"
                )
            return None

    # =========================================================
    # WAIT FOR DOWNLOAD
    # =========================================================
    def wait_for_download_complete(self, download_path, existing_files=None, timeout=60):
        """
        Tunggu download selesai dengan membandingkan file baru vs existing.
        Return: path file PDF baru, atau None jika timeout.
        """
        if existing_files is None:
            existing_files = set()

        start_time = time.time()

        while time.time() - start_time < timeout:
            # Cek file .crdownload (sedang download)
            downloading = [
                f for f in os.listdir(download_path)
                if f.lower().endswith(('.crdownload', '.part'))
            ]

            # File PDF saat ini
            current_pdfs = set(
                f for f in os.listdir(download_path)
                if f.lower().endswith(".pdf")
            )

            # File baru = ada sekarang tapi tidak ada sebelumnya
            new_files = current_pdfs - existing_files

            # Jika tidak ada download berjalan & ada file baru
            if not downloading and new_files:
                newest = max(
                    new_files,
                    key=lambda f: os.path.getctime(os.path.join(download_path, f))
                )
                print(f"  Download selesai: {newest}")
                return os.path.join(download_path, newest)

            time.sleep(1)

        print(f"  Timeout: Download tidak selesai dalam {timeout} detik.")
        return None

    # =========================================================
    # RENAME FILE
    # =========================================================
    def rename_pdf(self, file_path, kode_saham, tanggal):
        """Rename file PDF ke format: Suspensi_<KODE>_<YYYY-MM-DD>.pdf"""
        if not file_path or not os.path.exists(file_path):
            return None

        folder = os.path.dirname(file_path)

        # Nama file baru
        new_filename = f"Suspensi_{kode_saham}_{tanggal}.pdf"

        # Bersihkan karakter ilegal
        safe_filename = "".join(
            c for c in new_filename
            if c.isalnum() or c in (" ", "-", "_", ".")
        ).strip()

        new_path = os.path.join(folder, safe_filename)

        # Jika sudah ada, tambah counter
        counter = 1
        while os.path.exists(new_path):
            name, ext = os.path.splitext(safe_filename)
            new_path = os.path.join(folder, f"{name}_{counter}{ext}")
            counter += 1

        try:
            os.rename(file_path, new_path)
            print(f"Renamed: {os.path.basename(new_path)}")
            return new_path
        except Exception as e:
            print(f"Gagal rename: {e}")
            return file_path


    # =========================================================
    # HELPER: BUILD FILENAME (Suspend/Unsuspend + Kode Saham)
    # =========================================================
    def _build_suspend_filename(self, row_date, announcement):
        """
        Bangun nama file dengan format: <YYYYMMDD> - <Suspend/Unsuspend> <KODE>.pdf
        Contoh: 20260915 - Suspend ALKA.pdf
        """
        import re as _re
        from datetime import datetime

        # 1) Tentukan jenis: Suspend / Unsuspend
        ann_lower = announcement.lower()
        if "unsuspend" in ann_lower or "pembukaan kembali" in ann_lower:
            jenis = "Unsuspend"
        else:
            jenis = "Suspend"

        # 2) Ekstrak kode saham dari dalam tanda kurung, mis. (PACK), (INPS)
        match = _re.search(r'\(([A-Z]{4})\)', announcement)
        kode_saham = match.group(1) if match else "UNKNOWN"

        # 3) Konversi tanggal "15 Sep 2026" → "20260915"
        try:
            dt = datetime.strptime(row_date, "%d %b %Y")
            tanggal_file = dt.strftime("%Y%m%d")
        except ValueError:
            # fallback kalau format beda
            tanggal_file = row_date

        # 4) Susun nama file
        raw_filename = f"{tanggal_file} - {jenis} {kode_saham}.pdf"

        # 5) Bersihkan karakter ilegal
        safe_filename = "".join(
            c for c in raw_filename
            if c.isalnum() or c in (" ", "-", "_", ".")
        ).strip()

        return safe_filename

    # =========================================================
    # MAIN PROCESS
    # =========================================================
    def btn_run_clicked(self):
        """Handler tombol Run - download semua PDF suspensi dalam rentang tanggal"""

        # ============ KONFIGURASI ============
        download_path = os.path.abspath("D:/IDX_Data/Suspend/downloads_suspend")
        os.makedirs(download_path, exist_ok=True)

        # ============ AMBIL TANGGAL DARI UI ============
        start_qdate = self.date_edit.date()
        end_qdate = self.date_edit_2.date()

        # Konversi ke format Indonesia
        bulan_map = {
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

        target_start = start_qdate.toString("dd MMM yyyy")
        target_end = end_qdate.toString("dd MMM yyyy")

        for en, idn in bulan_map.items():
            target_start = target_start.replace(en, idn)
            target_end = target_end.replace(en, idn)
        print(f"Target Start: {target_start}, Target End: {target_end}")

        # Validasi tanggal
        if start_qdate > end_qdate:
            QMessageBox.warning(
                self, "Peringatan",
                "Start date tidak boleh lebih besar dari End date!"
            )
            return

        print(f"=== DOWNLOADER SUSPEND ===")
        print(f"Start date: {target_start}")
        print(f"End date  : {target_end}")
        print(f"Folder    : {download_path}")

        # ============ SETUP CHROME ============
        chrome_options = self.setup_chrome_options(download_path)

        # Init driver via helper (fallback berlapis)
        driver = self._init_chrome_driver(chrome_options)

        if driver is None:
            # Error sudah ditampilkan di _init_chrome_driver
            print("Driver None — error sudah ditampilkan sebelumnya")
            return

        wait = WebDriverWait(driver, 30)
        downloads_count = 0

        try:
            # ============ BUKA HALAMAN SUSPENSI ============
            url = "https://www.idx.co.id/id/berita/suspensi/"
            driver.get(url)
            print("Membuka halaman Suspensi IDX...")
            time.sleep(5)

            # =====================================================
            # LANGKAH 1: ISI FILTER TANGGAL (START & END DATE)
            # =====================================================
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

                if not terapkan_button:
                    terapkan_button.click()
                    print("Clicked Terapkan button.")
                    time.sleep(2)

                else:
                    print("Terapkan button not found, continuing anyway...")

            except Exception as e:
                print(f"Error saat klik Terapkan: {e}")
                # Lanjutkan meskipun error

            time.sleep(2)

            # =====================================================
            # LANGKAH 1B: SET DROPDOWN "BARIS" KE "All"
            # =====================================================
            try:
                # Cari elemen <select> dropdown Baris
                # Berdasarkan HTML: id="vgt-select-rpp-..." atau class "vgt-select"
                dropdown_selectors = [
                    "//select[contains(@id, 'vgt-select-rpp')]",
                    "//select[contains(@class, 'vgt-select')]",
                    "//select[.//option[contains(text(), 'All')]]",
                    "//select[.//option[contains(text(), 'Semua')]]",
                ]

                baris_select = None
                for selector in dropdown_selectors:
                    try:
                        baris_select = wait.until(EC.presence_of_element_located((By.XPATH, selector)))
                        if baris_select:
                            break
                    except:
                        continue

                if baris_select:
                    # Pakai Select dari Selenium untuk pilih "All"
                    from selenium.webdriver.support.ui import Select
                    sel = Select(baris_select)

                    # Coba pilih berdasarkan teks "All" dulu
                    selected = False
                    for opt in sel.options:
                        opt_text = (opt.text or "").strip().lower()
                        if opt_text in ("all", "semua"):
                            sel.select_by_visible_text(opt.text.strip())
                            selected = True
                            print(f"  ✓ Dropdown Baris di-set ke: {opt.text.strip()}")
                            break

                    # Fallback: pilih opsi terakhir (biasanya "All")
                    if not selected and sel.options:
                        last_opt = sel.options[-1]
                        sel.select_by_visible_text(last_opt.text.strip())
                        print(f"  ✓ Dropdown Baris di-set ke opsi terakhir: {last_opt.text.strip()}")

                    # Trigger event change via JS untuk memastikan Vue merespon
                    driver.execute_script(
                        """
                        arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
                        """,
                        baris_select
                    )

                    time.sleep(2)  # Tunggu tabel refresh menampilkan semua baris
                else:
                    print("  ⚠ Dropdown Baris tidak ditemukan, lanjut dengan default.")

            except Exception as e:
                print(f"  ⚠ Gagal set dropdown Baris: {e}")

            time.sleep(2)

            # Find all rows in the table
            rows = driver.find_elements(By.XPATH, '//table[@id="vgt-table"]/tbody/tr')
            print(f"Total rows found in table: {len(rows)}")

            #Process each row
            downloads_found = 0
            for i, row in enumerate(rows, 1):
                try:
                    # Get date from the row
                    date_element = row.find_element(By.XPATH, './td[1]')
                    row_date = date_element.text.strip()
                    

                    # Check if date matches target (bandingkan sebagai datetime)
                    try:
                        row_dt = _dt.strptime(row_date, "%d %b %Y")
                    except ValueError:
                        # Coba format dengan bulan Indonesia
                        row_date_norm = row_date
                        for idn, en in [("Mei","May"),("Agt","Aug"),("Okt","Oct"),("Des","Dec")]:
                            row_date_norm = row_date_norm.replace(idn, en)
                        try:
                            row_dt = _dt.strptime(row_date_norm, "%d %b %Y")
                        except ValueError:
                            row_dt = None

                    try:
                        start_dt = _dt.strptime(target_start, "%d %b %Y")
                        end_dt = _dt.strptime(target_end, "%d %b %Y")
                    except ValueError:
                        start_dt = end_dt = None

                    # Bandingkan pakai datetime; fallback ke string kalau gagal parse
                    if row_dt and start_dt and end_dt:
                        date_in_range = start_dt <= row_dt <= end_dt
                    else:
                        date_in_range = target_start <= row_date <= target_end

                    if date_in_range:
                        print(f"Row {i}: Date = {row_date}  ← dalam rentang, diproses")

                        # Find the PDF link in the row
                        try:
                            download_link = row.find_element(By.XPATH, './/a[contains(@href, ".pdf")]')

                            if download_link:
                                announcement = row.find_element(By.XPATH, './/td[2]/span').text.strip()

                                # Create filename
                                filename = self._build_suspend_filename(row_date, announcement)

                                print(f"Downloading: {filename})")

                                 # ── Scroll + klik langsung via JS ──
                                driver.execute_script(
                                    "arguments[0].scrollIntoView({block:'center'});",
                                    download_link
                                )
                                time.sleep(1)
                                driver.execute_script("arguments[0].click();", download_link)

                                download_link.click()

                                downloads_found += 1
                                
                                # Wait for download to start and complete
                                time.sleep(3)
                                self.wait_for_download_complete(download_path, timeout=30)
                                
                                # Rename downloaded file
                                renamed = False
                                for attempt in range(5):
                                    time.sleep(2)

                                    # Cari PDF baru (bukan file lama)
                                    current_pdfs = [
                                        f for f in os.listdir(download_path)
                                        if f.lower().endswith(".pdf")
                                    ]
                                    # Skip file yang sudah punya format " - Suspend"/" - Unsuspend"
                                    candidates = [
                                        f for f in current_pdfs
                                        if " - Suspend " not in f and " - Unsuspend " not in f
                                    ]

                                    if candidates:
                                        latest_file = max(
                                            [os.path.join(download_path, f) for f in candidates],
                                            key=os.path.getctime
                                        )
                                        new_file_path = os.path.join(download_path, filename)

                                        counter = 1
                                        while os.path.exists(new_file_path):
                                            name, ext = os.path.splitext(filename)
                                            new_file_path = os.path.join(download_path, f"{name}_{counter}{ext}")
                                            counter += 1

                                        try:
                                            os.rename(latest_file, new_file_path)
                                            print(f"Saved as: {os.path.basename(new_file_path)}")
                                            renamed = True
                                            break
                                        except Exception as e:
                                            print(f"  Rename gagal (attempt {attempt+1}): {e}")

                                if not renamed:
                                    print(f"  ⚠ Rename gagal untuk: {filename}")
                                
                                time.sleep(2)  # Delay between downloads
                                
                        except Exception as e:
                            print(f"Error finding download link in row {i}: {e}")
                            
                except Exception as e:
                    print(f"Error processing row {i}: {e}")
                    continue

            print(f"\n=== Download Summary ===")
            print(f"Total files downloaded for {target_start}: {downloads_found}")
            print(f"Files saved in: {download_path}")
            
        except Exception as e:
            print(f"Error during execution: {e}")
            
        finally:
            # Keep browser open for a moment to ensure downloads complete
            time.sleep(2)
            try:
                for f in os.listdir(download_path):
                    if f.lower().endswith(".pdf") and " - Suspend " not in f and " - Unsuspend " not in f:
                        print(f"⚠ Sisa file belum direname: {f}")
            except Exception:
                pass
            driver.quit()

    # =========================================================
    #HELPER:SET DATE INPUT
    # =========================================================
    def _set_date_input(self, driver, element, date_str):
        """
        Isi date picker dengan date_str.
        Coba via JS dulu (paling reliable untuk date picker kompleks),
        lalu fallback ke send_keys.
        """
        try:
            # Strategi 1: Set value via JavaScript + trigger events
            driver.execute_script(
                """
                arguments[0].value = arguments[1];
                arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
                arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
                arguments[0].dispatchEvent(new Event('blur', { bubbles: true }));
                """,
                element, date_str
            )
            print(f"  Set tanggal via JS: {date_str}")
            return True
        except Exception as e:
            print(f"  Gagal set via JS: {e}")

        # Fallback: clear + send_keys
        try:
            element.click()
            time.sleep(0.5)
            element.clear()
            element.send_keys(date_str)
            time.sleep(0.5)
            # Tekan Escape untuk tutup kalender popup
            from selenium.webdriver.common.keys import Keys
            element.send_keys(Keys.ESCAPE)
            print(f"  Set tanggal via send_keys: {date_str}")
            return True
        except Exception as e:
            print(f"  Gagal set via send_keys: {e}")
            return False


# ============================================================
# WORKER THREAD UNTUK BATCH SUSPEND
# ============================================================
class SuspendProcessWorker(QThread):
    """Thread untuk memproses file PDF suspend/unsuspend di background."""

    progress_updated = pyqtSignal(int, str)              # idx, filename
    statistics_updated = pyqtSignal(int, int, int, int)  # total, sukses, error, duplikat
    row_added = pyqtSignal(int, str, dict, str, str)     # no, filename, data, status, ket
    finished = pyqtSignal(int, int, int, list)           # total, sukses, error, error_details

    def __init__(self, folder_path):
        super().__init__()
        self.folder_path = folder_path
        self.is_running = True

    def normalisasi_teks(self, teks):
        """Bersihkan teks dari karakter aneh PDF."""
        if not teks:
            return ""
        
        # Hapus karakter non-breaking space
        teks = teks.replace('\xa0', ' ')
        teks = teks.replace('\u200b', '')  # zero-width space
        teks = teks.replace('\ufeff', '')  # BOM
        
        # Hapus markdown bold/italic dari pdfplumber
        teks = teks.replace('**', '')
        teks = teks.replace('__', '')
        
        # Normalisasi whitespace
        teks = re.sub(r'[ \t]+', ' ', teks)
        teks = re.sub(r'\n\s*\n', '\n', teks)
        
        return teks
    
    # ==========================================================
    # HELPER PARSING
    # ==========================================================
    def parse_tanggal(self, teks_tanggal):
        """Parse berbagai format tanggal."""
        if not teks_tanggal:
            return None
        
        # Mapping bulan Inggris + Indonesia
        bulan_map = {
            # Indonesia
            'januari': 1, 'februari': 2, 'maret': 3, 'april': 4,
            'mei': 5, 'juni': 6, 'juli': 7, 'agustus': 8,
            'september': 9, 'oktober': 10, 'november': 11, 'desember': 12,
            # Inggris (singkat)
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4,
            'may': 5, 'jun': 6, 'jul': 7, 'aug': 8,
            'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
            # Inggris (panjang)
            'january': 1, 'february': 2, 'march': 3,
            'june': 6, 'july': 7, 'august': 8,
            'october': 10, 'december': 12,
        }
        
        teks_tanggal = str(teks_tanggal).strip()
        
        # Format: "17 September 2026" atau "September 17, 2026"
        match = re.search(r'(\d{1,2})\s+(\w+)\s+(\d{4})', teks_tanggal)
        if match:
            hari, bulan_str, tahun = match.groups()
            bulan = bulan_map.get(bulan_str.lower())
            if bulan:
                try:
                    return datetime(int(tahun), bulan, int(hari)).date()
                except ValueError:
                    pass
        
        # Format: "September 17, 2026"
        match = re.search(r'(\w+)\s+(\d{1,2}),?\s+(\d{4})', teks_tanggal)
        if match:
            bulan_str, hari, tahun = match.groups()
            bulan = bulan_map.get(bulan_str.lower())
            if bulan:
                try:
                    return datetime(int(tahun), bulan, int(hari)).date()
                except ValueError:
                    pass
        
        return None

    def baca_pdf_teks(self, path):
        """Extract semua teks dari PDF (semua halaman)."""
        teks = ""
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                teks += page.extract_text() or ""
                teks += "\n"
        return teks

    def extract_data_suspend(self, teks):
        """Parse info halaman 2 — SUSPEND. Support berbagai format."""
        teks = self.normalisasi_teks(teks)

        if not hasattr(self, '_debug_written'):
            with open('debug_suspend_text.txt', 'w', encoding='utf-8') as f:
                f.write(teks)
            self._debug_written = True
        # ============================================================
        # 1. EKSTRAK KODE EMITEN — multiple strategi
        # ============================================================
        kode = None
        
        # Strategi A: cari pattern (XXXX) dengan 3-5 huruf kapital
        matches = re.findall(r'\(([A-Z]{3,5})\)', teks)
        if matches:
            # Filter yang masuk akal (bukan "BEI", "PT", dll)
            blacklist = {'BEI', 'OJK', 'KSEI', 'KPEI', 'PT', 'TBK', 'IDX'}
            for m in matches:
                if m not in blacklist:
                    kode = m
                    break
        
        # Strategi B: fallback - cari pattern [XXXX]
        if not kode:
            match = re.search(r'\[([A-Z]{3,5})\]', teks)
            if match:
                kode = match.group(1)
        
        # ============================================================
        # 2. EKSTRAK NAMA PERUSAHAAN — multiple strategi
        # ============================================================
        company_name = None
        
        # Strategi A: "saham PT ... Tbk (KODE)"
        patterns_nama = [
            r'saham\s+(PT\s+[A-Za-z\s\.]+?)\s*\(',
            r'Perdagangan\s+Efek\s+(PT\s+[A-Za-z\s\.]+?)\s*\(',
            r'Perdagangan\s+Saham\s+(PT\s+[A-Za-z\s\.]+?)\s*\(',
            r'perdagangan\s+saham\s+(PT\s+[A-Za-z\s\.]+?)\s*\(',
            r'(PT\s+[A-Za-z\s\.]+?Tbk)\s*\(',
        ]
        
        for pattern in patterns_nama:
            match = re.search(pattern, teks, re.IGNORECASE)
            if match:
                company_name = match.group(1).strip()
                break
        
        # Strategi B: fallback - ambil dari teks "saham PT ... Tbk"
        if not company_name:
            match = re.search(r'(PT\s+[A-Za-z\s\.]+?Tbk)', teks)
            if match:
                company_name = match.group(1).strip()
        
        # ============================================================
        # 3. EKSTRAK TANGGAL SUSPEND — multiple format
        # ============================================================
        tanggal_suspend = None
        
        patterns_tanggal = [
            r'pada tanggal\s+(\d{1,2}\s+\w+\s+\d{4})',          # "pada tanggal 21 Sept 2026"
            r'tanggal\s+(\d{1,2}\s+\w+\s+\d{4})',                # "tanggal 21 Sept 2026"
            r'mulai\s+(?:Sesi\s+\w+\s+)?tanggal\s+(\d{1,2}\s+\w+\s+\d{4})',  # "mulai tanggal ..."
            r'sejak\s+(?:Sesi\s+\w+\s+)?tanggal\s+(\d{1,2}\s+\w+\s+\d{4})',  # "sejak tanggal ..."
            r'efektif\s+dari\s+.*?tanggal\s+(\d{1,2}\s+\w+\s+\d{4})',        # "efektif dari ... tanggal ..."
            r'(\d{1,2}\s+(?:Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember)\s+\d{4})',
        ]
        
        for pattern in patterns_tanggal:
            match = re.search(pattern, teks, re.IGNORECASE)
            if match:
                tanggal_suspend = match.group(1).strip()
                break
        
        # ============================================================
        # 4. BUILD REMARK
        # ============================================================
        if company_name and kode and tanggal_suspend:
            informasi = (
                f"Penghentian sementara perdagangan saham {company_name} ({kode}) "
                f"pada tanggal {tanggal_suspend} di Pasar Reguler dan Pasar Tunai"
            )
        elif company_name and kode:
            informasi = f"Penghentian sementara perdagangan saham {company_name} ({kode})"
        else:
            informasi = "Penghentian sementara perdagangan saham"
        
        # ============================================================
        # 5. FALLBACK DATE jika tanggal_suspend gagal di-parse
        # ============================================================
        date_value = self.parse_tanggal(tanggal_suspend) if tanggal_suspend else None
        
        # Fallback: cari tanggal surat (di akhir, sebelum "Endra")
        if not date_value:
            match = re.search(r'(\d{1,2}\s+\w+\s+\d{4})\s*\n\s*Endra', teks)
            if match:
                date_value = self.parse_tanggal(match.group(1))
        
        # Fallback terakhir: cari tanggal apapun di teks
        if not date_value:
            match = re.search(
                r'(\d{1,2})\s+(Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember)\s+(\d{4})',
                teks, re.IGNORECASE
            )
            if match:
                date_value = self.parse_tanggal(match.group(0))
        
        return {
            'code': kode,
            'company_name': company_name,
            'remark': 'suspend',
            'information': informasi,
            'action_type': 'suspend',
            'date': date_value
        }

    def extract_data_unsuspend(self, teks):
        """Parse info halaman 2 — UNSUSPEND. Support berbagai format."""
        teks = self.normalisasi_teks(teks)
        
        # ============================================================
        # 1. KODE EMITEN
        # ============================================================
        kode = None
        matches = re.findall(r'\(([A-Z]{3,5})\)', teks)
        if matches:
            blacklist = {'BEI', 'OJK', 'KSEI', 'KPEI', 'PT', 'TBK', 'IDX'}
            for m in matches:
                if m not in blacklist:
                    kode = m
                    break
        
        # ============================================================
        # 2. NAMA PERUSAHAAN
        # ============================================================
        company_name = None
        patterns_nama = [
            r'saham\s+(PT\s+[A-Za-z\s\.]+?)\s*\(',
            r'Perdagangan\s+(?:Efek|Saham)\s+(PT\s+[A-Za-z\s\.]+?)\s*\(',
            r'(PT\s+[A-Za-z\s\.]+?Tbk)\s*\(',
        ]
        for pattern in patterns_nama:
            match = re.search(pattern, teks, re.IGNORECASE)
            if match:
                company_name = match.group(1).strip()
                break
        
        if not company_name:
            match = re.search(r'(PT\s+[A-Za-z\s\.]+?Tbk)', teks)
            if match:
                company_name = match.group(1).strip()
        
        # ============================================================
        # 3. TANGGAL BUKA KEMBALI
        # ============================================================
        tanggal_buka = None
        patterns_tanggal = [
            r'dibuka kembali mulai\s+(?:Sesi\s+\w+\s+Periodic\s+Call\s+Auction\s+)?tanggal\s+(\d{1,2}\s+\w+\s+\d{4})',
            r'dibuka kembali mulai\s+(?:Sesi\s+\w+\s+)?tanggal\s+(\d{1,2}\s+\w+\s+\d{4})',
            r'dibuka kembali mulai tanggal\s+(\d{1,2}\s+\w+\s+\d{4})',
            r'dibuka kembali mulai\s+(\d{1,2}\s+\w+\s+\d{4})',
            r'dibuka kembali.*?tanggal\s+(\d{1,2}\s+\w+\s+\d{4})',
            r'resume\s+starting\s+from\s+.*?(\w+\s+\d{1,2},\s+\d{4})',
            r'tanggal\s+(\d{1,2}\s+\w+\s+\d{4})',
        ]
        for pattern in patterns_tanggal:
            match = re.search(pattern, teks, re.IGNORECASE | re.DOTALL)
            if match:
                tanggal_buka = match.group(1).strip()
                break
        
        # ============================================================
        # 4. REMARK
        # ============================================================
        remark_match = re.search(
            r'(suspensi atas perdagangan saham.*?dibuka kembali[^\.]*\.?)',
            teks, re.IGNORECASE | re.DOTALL
        )
        if remark_match:
            informasi = re.sub(r'\s+', ' ', remark_match.group(1)).strip()
            if not informasi.endswith('.'):
                informasi += '.'
        elif company_name and kode and tanggal_buka:
            informasi = (
                f"suspensi atas perdagangan saham {company_name} ({kode}) "
                f"di Pasar Reguler dan Pasar Tunai dibuka kembali mulai tanggal {tanggal_buka}"
            )
        else:
            informasi = f"Suspensi saham {company_name or ''} ({kode or ''}) dibuka kembali"
        
        # ============================================================
        # 5. DATE VALUE + FALLBACK
        # ============================================================
        date_value = self.parse_tanggal(tanggal_buka) if tanggal_buka else None
        
        if not date_value:
            match = re.search(r'(\d{1,2}\s+\w+\s+\d{4})\s*\n\s*Endra', teks)
            if match:
                date_value = self.parse_tanggal(match.group(1))
        
        if not date_value:
            match = re.search(
                r'(\d{1,2})\s+(Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember)\s+(\d{4})',
                teks, re.IGNORECASE
            )
            if match:
                date_value = self.parse_tanggal(match.group(0))
        
        return {
            'code': kode,
            'company_name': company_name,
            'remark': 'unsuspend',
            'information': informasi,
            'action_type': 'unsuspend',
            'date': date_value
        }

    # ==========================================================
    # CEK DUPLIKAT & INSERT
    # ==========================================================
    def check_duplicate(self, cursor, code, date_value):
        """Cek apakah (code, date) sudah ada di tabel."""
        cursor.execute(
            "SELECT id FROM ca_suspend WHERE code = %s AND date = %s LIMIT 1",
            (code, date_value)
        )
        return cursor.fetchone() is not None

    def insert_data(self, cursor, data):
        print("DEBUG data:", data)
        print("DEBUG jumlah key:", len(data))
        sql = """
            INSERT INTO ca_suspend (code, company_name, remark, information, date)
            VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(sql, (
            data['code'],
            data['company_name'],
            data['remark'],
            data.get('information', ''),
            data['date']
        ))

    # ==========================================================
    # PINDAH FILE
    # ==========================================================
    def move_file(self, src, dest_folder):
        os.makedirs(dest_folder, exist_ok=True)
        dest = os.path.join(dest_folder, os.path.basename(src))

        if os.path.exists(dest):
            name, ext = os.path.splitext(os.path.basename(src))
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest = os.path.join(dest_folder, f"{name}_{timestamp}{ext}")

        shutil.move(src, dest)
        return dest

    # ==========================================================
    # MAIN RUN
    # ==========================================================
    def run(self):
        total = 0
        sukses = 0
        error = 0
        duplikat = 0
        error_details = []

        # ---------- Folder output ----------
        parent = os.path.dirname(self.folder_path)
        success_folder = os.path.join(parent, 'success_processed')
        error_folder = os.path.join(parent, 'error_processed')
        os.makedirs(success_folder, exist_ok=True)
        os.makedirs(error_folder, exist_ok=True)

        # ---------- Koneksi DB ----------
        try:
            conn = mysql.connector.connect(**DB_CONFIG)
            cursor = conn.cursor(dictionary=True)
        except Error as e:
            self.finished.emit(0, 0, 0, [f"Gagal koneksi DB: {e}"])
            return

        # ---------- Ambil file PDF ----------
        pdf_files = sorted([
            f for f in os.listdir(self.folder_path)
            if f.lower().endswith('.pdf')
        ])

        for idx, filename in enumerate(pdf_files, start=1):
            if not self.is_running:
                break

            total += 1
            path = os.path.join(self.folder_path, filename)
            self.progress_updated.emit(idx, filename)

            try:
                teks = self.baca_pdf_teks(path)

                # ---------- Deteksi jenis ----------
                if 'unsuspend' in filename.lower() or 'unsuspen' in filename.lower():
                    data = self.extract_data_unsuspend(teks)
                    jenis = "UNSUSPEND"
                else:
                    data = self.extract_data_suspend(teks)
                    jenis = "SUSPEND"

                data['remark'] = jenis          # kolom DB 'remark' = "suspend" / "unsuspend"
                data['action_type'] = jenis     # kolom UI 'Keterangan'
                

                # ---------- Validasi ----------
                if not data['code'] or not data['company_name'] or not data['date']:
                    error += 1
                    ket = "Data tidak lengkap"
                    error_details.append(f"{filename} → {ket}")
                    self.row_added.emit(idx, filename, data, "ERROR", ket)
                    self.move_file(path, error_folder)
                    self.statistics_updated.emit(total, sukses, error, duplikat)
                    continue

                # ---------- Cek duplikat ----------
                if self.check_duplicate(cursor, data['code'], data['date']):
                    duplikat += 1
                    ket = f"Duplikat: {data['code']} pada {data['date']}"
                    self.row_added.emit(idx, filename, data, "DUPLIKAT", ket)
                    self.move_file(path, success_folder)
                    self.statistics_updated.emit(total, sukses, error, duplikat)
                    continue

                # ---------- Insert ----------
                self.insert_data(cursor, data)
                conn.commit()

                sukses += 1
                ket = data.get('information', '')[:150]
                self.row_added.emit(idx, filename, data, "BERHASIL", ket)
                self.move_file(path, success_folder)

            except Exception as e:
                error += 1
                ket = str(e)[:100]
                error_details.append(f"{filename} → {ket}")
                self.row_added.emit(idx, filename, {}, "ERROR", ket)
                try:
                    self.move_file(path, error_folder)
                except Exception:
                    pass

            self.statistics_updated.emit(total, sukses, error, duplikat)

        cursor.close()
        conn.close()
        self.finished.emit(total, sukses, error, error_details)


class BatchSuspendWindow(BaseWindow):
    def __init__(self):
        super(BatchSuspendWindow, self).__init__()
        
        # Dapatkan path direktori file ini
        current_dir = os.path.dirname(os.path.abspath(__file__))
        ui_path = resource_path("batch_suspend.ui")
        uic.loadUi(ui_path, self)
        self.setWindowTitle("Batch Suspend")

        # Auto-connect semua menu action ke handler generik
        self.wire_menu_actions()

        self.folder_path = ""
        self.worker = None

        # ======================================================
        # SET DEFAULT
        # ======================================================
        self.reset_statistics()
        self.check_database()
        self.setup_table()

        # ======================================================
        # KONEKSI TOMBOL
        # ======================================================
        self.btn_import.clicked.connect(self.browse_folder)
        self.pushButton.clicked.connect(self.start_process)

    # ==========================================================
    # SETUP TABLE
    # ==========================================================
    def setup_table(self):
        """Setup table widget."""
        table = self.get_table()
        if table:
            headers = ["No", "Nama File", "Kode", "Nama Perusahaan", "Tanggal", "Status", "Keterangan", "Informasi"]
            table.setColumnCount(len(headers))
            table.setHorizontalHeaderLabels(headers)

            table.setColumnWidth(0, 40)    # No
            table.setColumnWidth(1, 200)   # Nama File
            table.setColumnWidth(2, 70)    # Kode
            table.setColumnWidth(3, 250)   # Nama Perusahaan
            table.setColumnWidth(4, 100)   # Tanggal
            table.setColumnWidth(5, 90)    # Status
            table.setColumnWidth(6, 220)   # Keterangan
            table.setColumnWidth(7, 220)    # informasi

            table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
            table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)

    def get_table(self):
        """Cari table widget di UI."""
        names = ['tableWidget', 'tableWidget_result', 'tbl_result', 'tbl_hasil']
        for name in names:
            widget = self.findChild(QtWidgets.QTableWidget, name)
            if widget:
                return widget
        return None

    def get_process_button(self):
        if hasattr(self, "pushButton"):
            return self.pushButton
        return None

    def get_folder_input(self):
        if hasattr(self, "txt_path"):
            return self.txt_path
        return None

    # ==========================================================
    # DATABASE CHECK
    # ==========================================================
    def check_database(self):
        try:
            conn = mysql.connector.connect(**DB_CONFIG)
            if conn.is_connected():
                print("✅ Koneksi database berhasil (Batch Suspend)")
                conn.close()
                return True
        except Error as e:
            print(f"❌ Gagal koneksi: {e}")
            QMessageBox.warning(self, "Database", f"Gagal koneksi ke database:\n\n{e}")
            return False
        return False

    # ==========================================================
    # BROWSE FOLDER
    # ==========================================================
    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Pilih Folder PDF Suspend/Unsuspend")
        if folder:
            self.folder_path = folder
            folder_input = self.get_folder_input()
            if folder_input:
                folder_input.setText(folder)
            self.check_paths()

    def check_paths(self):
        valid = self.folder_path and os.path.exists(self.folder_path)
        btn = self.get_process_button()
        if btn:
            btn.setEnabled(valid)

    # ==========================================================
    # STATISTIK
    # ==========================================================
    def reset_statistics(self):
        self.total_files = 0
        self.success_count = 0
        self.error_count = 0
        self.duplicate_count = 0
        self.update_statistics()
        self.clear_table()

    def update_statistics(self):
        mapping = {
            'label_total': f'Total: {self.total_files}',
            'lbl_total': f'Total: {self.total_files}',
            'label_berhasil': f'Berhasil: {self.success_count}',
            'lbl_berhasil': f'Berhasil: {self.success_count}',
            'label_error': f'Error: {self.error_count}',
            'lbl_error': f'Error: {self.error_count}',
            'label_duplikat': f'Duplikat: {self.duplicate_count}',
            'lbl_duplikat': f'Duplikat: {self.duplicate_count}'
        }
        for name, text in mapping.items():
            widget = self.findChild(QtWidgets.QLabel, name)
            if widget:
                widget.setText(text)
        QtWidgets.QApplication.processEvents()

    def clear_table(self):
        table = self.get_table()
        if table:
            table.setRowCount(0)

    # ==========================================================
    # ADD ROW
    # ==========================================================
    def add_table_row(self, no, filename, data, status, keterangan):
        table = self.get_table()
        if not table:
            return

        row = table.rowCount()
        table.insertRow(row)

        # Tentukan jenis aksi: suspend / unsuspend
        action_type = data.get('action_type', '')
        if not action_type:
            # fallback: deteksi dari keterangan atau default
            action_type = 'suspend'  # default, bisa disesuaikan


        values = [
            str(no),
            filename,
            data.get('code', ''),
            (data.get('company_name') or '')[:50],
            str(data.get('date') or ''),
            status,
            action_type,
            keterangan
        ]

        for col, value in enumerate(values):
            item = QTableWidgetItem(str(value))
            if status == "BERHASIL":
                item.setBackground(Qt.green)
            elif status == "DUPLIKAT":
                item.setBackground(Qt.yellow)
            elif status == "ERROR":
                item.setBackground(Qt.red)
            table.setItem(row, col, item)

        table.scrollToBottom()

    # ==========================================================
    # PROCESS
    # ==========================================================
    def start_process(self):
        """Mulai proses di thread terpisah."""

        # Cek folder
        if not self.folder_path:
            folder_input = self.get_folder_input()
            if folder_input:
                self.folder_path = folder_input.text().strip()

        if not self.folder_path:
            QMessageBox.warning(self, "Peringatan", "Silakan pilih folder PDF terlebih dahulu.")
            return

        if not os.path.exists(self.folder_path):
            QMessageBox.critical(self, "Error", "Folder PDF tidak ditemukan.")
            return

        # Reset UI
        self.reset_statistics()
        self.clear_table()

        # Disable tombol
        btn = self.get_process_button()
        if btn:
            btn.setEnabled(False)
            btn.setText("Processing...")

        # Worker thread
        self.worker = SuspendProcessWorker(self.folder_path)
        self.worker.progress_updated.connect(self.on_progress_updated)
        self.worker.statistics_updated.connect(self.on_statistics_updated)
        self.worker.row_added.connect(self.add_table_row)
        self.worker.finished.connect(self.on_process_finished)

        self.worker.start()

    def on_progress_updated(self, idx, filename):
        self.statusBar().showMessage(f"Memproses file {idx}: {filename}")

    def on_statistics_updated(self, total, success, error, duplicate):
        self.total_files = total
        self.success_count = success
        self.error_count = error
        self.duplicate_count = duplicate
        self.update_statistics()

    def on_process_finished(self, total, success, error, error_details):
        btn = self.get_process_button()
        if btn:
            btn.setEnabled(True)
            btn.setText("Process Files")

        self.statusBar().showMessage("Selesai!")
        self.show_summary(total, success, error, error_details)

    def show_summary(self, total, success, error, error_details):
        parent = os.path.dirname(self.folder_path)
        success_folder = os.path.join(parent, 'success_processed')
        error_folder = os.path.join(parent, 'error_processed')

        text = f"""
BATCH SUSPEND SELESAI

Total File : {total}
Berhasil   : {success}
Error      : {error}
Duplikat   : {self.duplicate_count}

Success Folder: {success_folder}
Error Folder: {error_folder}
        """

        if error_details:
            text += "\n\nDETAIL ERROR:\n" + "\n".join(f"• {e}" for e in error_details[:10])
            if len(error_details) > 10:
                text += f"\n• ... dan {len(error_details) - 10} error lainnya"

        QMessageBox.information(self, "Batch Suspend", text)
    

class ExportSuspendWindow(BaseWindow):
    def __init__(self):
        super(ExportSuspendWindow, self).__init__()
        
        # Dapatkan path direktori file ini
        current_dir = os.path.dirname(os.path.abspath(__file__))
        ui_path = resource_path("export_suspend.ui")
        uic.loadUi(ui_path, self)
        self.setWindowTitle("Export Suspend")

        # Auto-connect semua menu action ke handler generik
        self.wire_menu_actions()


def excepthook_qt(exctype, value, tb):
    """Qt-specific exception hook — tampilkan dialog + log."""
    error_msg = "".join(traceback.format_exception(exctype, value, tb))
    logger.critical(f"UNCAUGHT (Qt):\n{error_msg}")
    ErrorReporter._write_crash_file(
        exctype.__name__, str(value), error_msg, "Qt event loop"
    )

    try:
        msg = QtWidgets.QMessageBox()
        msg.setIcon(QtWidgets.QMessageBox.Critical)
        msg.setWindowTitle("❌ Aplikasi Error")
        msg.setText(f"Terjadi kesalahan: {exctype.__name__}")
        msg.setInformativeText(str(value)[:300])
        msg.setDetailedText(
            f"{error_msg}\n\n"
            f"Log file   : {GLOBAL_LOG_FILE}\n"
            f"Crash file : {ErrorReporter.CRASH_LOG}"
        )
        msg.exec_()
    except Exception:
        print(error_msg, file=sys.stderr)


def main():
    """Main function dengan error handling lengkap."""
    try:
        logger.info("Membuat QApplication...")
        app = QtWidgets.QApplication(sys.argv)
        app.setApplicationName("CPCA Scanner")

        # Install Qt exception hook — supaya error di event loop tertangkap
        def qt_excepthook(exctype, value, tb):
            error_msg = "".join(traceback.format_exception(exctype, value, tb))
            logger.critical(f"UNCAUGHT (Qt event loop):\n{error_msg}")
            try:
                msg = QtWidgets.QMessageBox()
                msg.setIcon(QtWidgets.QMessageBox.Critical)
                msg.setWindowTitle("❌ Aplikasi Error")
                msg.setText(f"Terjadi kesalahan: {exctype.__name__}")
                msg.setInformativeText(str(value)[:300])
                msg.setDetailedText(f"{error_msg}\n\nLog: {LOG_FILE}")
                msg.exec_()
            except Exception:
                print(error_msg, file=sys.stderr)

        sys.excepthook = qt_excepthook

        logger.info("Membuat Ui_MainWindow...")
        window = Ui_MainWindow()
        window.show()

        logger.info("Masuk ke event loop...")
        return app.exec_()

    except Exception as e:
        err = traceback.format_exc()
        logger.critical(f"FATAL saat startup:\n{err}")
        print(err, file=sys.stderr)

        # Tahan console agar user bisa baca
        try:
            input("\n\n>>> Tekan ENTER untuk keluar...")
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:
        traceback.print_exc()
        input("\n\n>>> Tekan ENTER untuk keluar...")
        sys.exit(1)