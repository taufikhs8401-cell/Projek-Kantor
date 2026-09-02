import sqlite3

#table ETF insert
perintahSQL = "CREATE TABLE insert_etf ("
perintahSQL += "id INTEGER PRIMARY KEY AUTOINCREMENT,"
perintahSQL += "nama_kik TEXT NOT NULL,"
perintahSQL += "underlying_aset TEXT NOT NULL,"
perintahSQL += "kode_kik TEXT NOT NULL,"
perintahSQL += "jumlah_unit_yang_dicatat TEXT NOT NULL,"
perintahSQL += "jumlah_maksimum_unit_penyertaan TEXT NOT NULL,"
perintahSQL += "harga_perdana TEXT NOT NULL,"
perintahSQL += "nilai_awal TEXT NOT NULL,"
perintahSQL += "manajemen_investasi TEXT NOT NULL,"
perintahSQL += "bank_kustodian TEXT NOT NULL,"
perintahSQL += "dealer_participan TEXT NOT NULL,"
perintahSQL += "tanggal_mulai DATE);"

try:
    koneksi = sqlite3.connect('IQPlus_downloader.db')
    koneksi.execute(perintahSQL)

    print("semua table berhasil dibuat")

except sqlite3.Error as e:
    print("Gagal memuat table :", e)

finally:
    koneksi.close()