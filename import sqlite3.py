import sqlite3

koneksi = sqlite3.connect('iqplus.db')
cursor = koneksi.cursor()

# Perbaiki sintaks SQL - hapus tanda kutip yang salah
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sumber TEXT NOT NULL,
    tanggal DATE,
    judul TEXT NOT NULL,
    isi TEXT NOT NULL
)
''')  # Perhatikan: tanda kutip tiga di sini, bukan di dalam string

# Menyimpan perubahan
koneksi.commit()
print("Tabel 'users' berhasil dibuat!")

# Verifikasi tabel berhasil dibuat
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print("Daftar tabel:", tables)

# Menutup koneksi
koneksi.close()
