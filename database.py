import os
import sqlite3
from datetime import datetime, timedelta

# Path absolut ke simdata.db, berdasarkan lokasi file ini sendiri.
# Ini membuat lokasi database konsisten walau aplikasi dijalankan
# dari working directory yang berbeda (mis. lewat shortcut, IDE, dsb),
# yang sebelumnya bisa menyebabkan "unable to open database file".
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "simdata.db")

# Lokasi cadangan yang HAMPIR PASTI bisa ditulis oleh user biasa
# (tidak butuh hak admin), dipakai kalau folder aplikasi ternyata
# read-only / terkena lock antivirus / disinkron OneDrive, dsb.
# Ini adalah penyebab paling umum dari "unable to open database file"
# yang muncul hanya saat MENULIS (INSERT/UPDATE), bukan saat membaca.
FALLBACK_DIR = os.path.join(
    os.path.expanduser("~"), ".simdata_itka"
)
FALLBACK_DB_PATH = os.path.join(FALLBACK_DIR, "simdata.db")


BULAN_INDO = [
    "", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember"
]


def format_tanggal_indo(nilai):
    """
    Mengubah string tanggal tersimpan (format: YYYY-MM-DD HH:MM:SS)
    menjadi format tampilan Indonesia, contoh: "15 Mei 2025 10:30"
    """

    if not nilai:
        return "-"

    try:
        dt = datetime.strptime(nilai, "%Y-%m-%d %H:%M:%S")
        return f"{dt.day} {BULAN_INDO[dt.month]} {dt.year} {dt.strftime('%H:%M')}"
    except Exception:
        return nilai


class Database:

    def __init__(self):

        # ===========================
        # KONEKSI AWAL (DENGAN FALLBACK)
        # ---------------------------
        # SEBELUMNYA baris ini langsung `sqlite3.connect(DB_PATH)` tanpa
        # penanganan error sama sekali. Kalau folder aplikasi TIDAK BISA
        # ditulis (misalnya project disimpan di folder milik user Windows
        # lain, folder OneDrive yang di-lock, folder Program Files, dsb),
        # sqlite3 langsung melempar "unable to open database file" dan
        # APLIKASI CRASH SAAT DIBUKA -- sebelum sempat masuk ke splash
        # screen sama sekali.
        #
        # Sekarang percobaan pertama dibungkus try/except: kalau folder
        # aplikasi gagal ditulis, otomatis pindah ke folder cadangan di
        # home user (~/.simdata_itka/simdata.db) yang hampir pasti bisa
        # ditulis oleh user manapun, tanpa membuat aplikasi crash.
        # ===========================
        try:
            self.db_path_aktif = DB_PATH
            self.conn = self._buka_koneksi(DB_PATH)
        except (sqlite3.OperationalError, OSError):
            print(
                "PERINGATAN: tidak bisa membuka database di folder aplikasi "
                f"({DB_PATH}). Menggunakan folder cadangan: {FALLBACK_DB_PATH}"
            )
            self.db_path_aktif = FALLBACK_DB_PATH
            self.conn = self._buka_koneksi(FALLBACK_DB_PATH)

        self.cursor = self.conn.cursor()

        # ===========================
        # TABEL MAHASISWA
        # ===========================
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS mahasiswa(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama TEXT,
            nim TEXT,
            semester TEXT,
            prodi TEXT
        )
        """)

        self.conn.commit()

        # ===========================
        # MIGRASI: tambahkan kolom tanggal_input jika belum ada
        # (agar database lama yang sudah ada tetap kompatibel)
        # ===========================
        self._migrasi_kolom_tanggal()

        # ===========================
        # TABEL ADMIN
        # ===========================
        self.create_tables()

        self.conn.commit()

    # ===========================
    # KONEKSI (dengan fallback lokasi)
    # ===========================

    def _buka_koneksi(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        return sqlite3.connect(path, timeout=10)

    def _pindah_ke_fallback(self):
        """
        Dipanggil kalau folder aplikasi tidak bisa ditulis (permission,
        antivirus, OneDrive lock, dll). Memindahkan koneksi ke folder
        di home user yang hampir pasti bisa ditulis, lalu memastikan
        tabelnya ada di lokasi baru itu.
        """

        try:
            self.conn.close()
        except Exception:
            pass

        self.conn = self._buka_koneksi(FALLBACK_DB_PATH)
        self.cursor = self.conn.cursor()
        self.db_path_aktif = FALLBACK_DB_PATH

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS mahasiswa(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama TEXT,
            nim TEXT,
            semester TEXT,
            prodi TEXT
        )
        """)
        self.conn.commit()

        self._migrasi_kolom_tanggal()
        self.create_tables()
        self.conn.commit()

    def _eksekusi_tulis(self, query, params=()):
        """
        Menjalankan query INSERT/UPDATE/DELETE dengan penanganan error.
        Kalau lokasi utama tidak bisa ditulis, otomatis coba lagi di
        folder cadangan (satu kali) sebelum benar-benar menyerah.
        """

        try:
            self.cursor.execute(query, params)
            self.conn.commit()
            return

        except sqlite3.OperationalError as e:

            if self.db_path_aktif == FALLBACK_DB_PATH:
                # Sudah di lokasi cadangan dan tetap gagal -> menyerah
                raise RuntimeError(
                    "Tidak dapat menyimpan data ke database. "
                    "Pastikan folder aplikasi tidak read-only dan "
                    "tidak sedang diblokir oleh antivirus."
                ) from e

            # Coba pindah ke folder cadangan lalu ulangi sekali
            self._pindah_ke_fallback()

            try:
                self.cursor.execute(query, params)
                self.conn.commit()
            except sqlite3.OperationalError as e2:
                raise RuntimeError(
                    "Tidak dapat menyimpan data ke database, baik di "
                    "folder aplikasi maupun folder cadangan."
                ) from e2

    # ===========================
    # MIGRASI KOLOM tanggal_input
    # ===========================

    def _migrasi_kolom_tanggal(self):
        """
        Mengecek dulu lewat PRAGMA table_info apakah kolom
        tanggal_input sudah ada, baru menjalankan ALTER TABLE
        kalau memang belum ada. Cara ini lebih aman dibanding
        langsung ALTER lalu menangkap error, karena tidak akan
        menelan error asli secara diam-diam jika migrasi gagal
        karena sebab lain.
        """

        try:
            self.cursor.execute("PRAGMA table_info(mahasiswa)")
            kolom_ada = [baris[1] for baris in self.cursor.fetchall()]

            if "tanggal_input" not in kolom_ada:
                self.cursor.execute(
                    "ALTER TABLE mahasiswa ADD COLUMN tanggal_input TEXT"
                )
                self.conn.commit()

        except sqlite3.OperationalError as e:
            print("PERINGATAN: migrasi kolom tanggal_input gagal:", e)

    def _pastikan_kolom_tanggal(self):
        """Dipanggil ulang sebelum query yang butuh kolom tanggal_input,
        sebagai jaring pengaman kalau migrasi awal ternyata belum sempat
        jalan (misalnya database dibuka lebih dulu oleh proses lain)."""
        self._migrasi_kolom_tanggal()

    # ===========================
    # SIMPAN DATA MAHASISWA
    # ===========================

    def tambah_mahasiswa(self, nama, nim, semester, prodi):

        tanggal = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self._eksekusi_tulis("""
        INSERT INTO mahasiswa
        (nama, nim, semester, prodi, tanggal_input)

        VALUES (?, ?, ?, ?, ?)
        """, (nama, nim, semester, prodi, tanggal))

    # ===========================
    # Update Data
    # ===========================

    def update_mahasiswa(self, id_mahasiswa, nama, nim, semester, prodi):

        self._eksekusi_tulis("""
            UPDATE mahasiswa
            SET
                nama = ?,
                nim = ?,
                semester = ?,
                prodi = ?
            WHERE id = ?
        """, (
            nama,
            nim,
            semester,
            prodi,
            id_mahasiswa
        ))

    # ===========================
    # AMBIL SEMUA DATA
    # ===========================

    def tampilkan_semua(self):

        try:
            self.cursor.execute("""
            SELECT
                id,
                nama,
                nim,
                semester,
                prodi,
                tanggal_input
            FROM mahasiswa
            ORDER BY nama ASC
            """)
        except sqlite3.OperationalError:
            # Jaring pengaman: migrasi kolom belum sempat jalan, coba lagi
            self._pastikan_kolom_tanggal()
            self.cursor.execute("""
            SELECT
                id,
                nama,
                nim,
                semester,
                prodi,
                tanggal_input
            FROM mahasiswa
            ORDER BY nama ASC
            """)

        return self.cursor.fetchall()

    # ===========================
    # Ambil Satu Data
    # ===========================

    def ambil_satu(self, id_mahasiswa):

        try:
            self.cursor.execute("""
                SELECT
                    id,
                    nama,
                    nim,
                    semester,
                    prodi,
                    tanggal_input
                FROM mahasiswa
                WHERE id = ?
            """, (id_mahasiswa,))
        except sqlite3.OperationalError:
            self._pastikan_kolom_tanggal()
            self.cursor.execute("""
                SELECT
                    id,
                    nama,
                    nim,
                    semester,
                    prodi,
                    tanggal_input
                FROM mahasiswa
                WHERE id = ?
            """, (id_mahasiswa,))

        return self.cursor.fetchone()

    # ===========================
    # HAPUS DATA
    # ===========================

    def hapus(self, id_data):

        self._eksekusi_tulis("""
        DELETE FROM mahasiswa
        WHERE id = ?
        """, (id_data,))

    # ===========================
    # TABEL ADMIN
    # ===========================

    def create_tables(self):

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS admin(

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            username TEXT UNIQUE,

            password TEXT

        )
        """)

        self.cursor.execute("""
        SELECT *
        FROM admin
        WHERE username='admin'
        """)

        if self.cursor.fetchone() is None:

            self.cursor.execute("""
            INSERT INTO admin(username,password)

            VALUES('admin','123')
            """)

            self.conn.commit()

    # ===========================
    # LOGIN
    # ===========================

    def login(self, username, password):

        self.cursor.execute("""
        SELECT *
        FROM admin
        WHERE username=?
        AND password=?
        """, (username, password))

        return self.cursor.fetchone()

    # ===========================
    # UBAH PASSWORD
    # ===========================

    def ubah_password(self, username, password_baru):

        self._eksekusi_tulis("""
            UPDATE admin
            SET password = ?
            WHERE username = ?
        """, (password_baru, username))

    def tampilkan_berdasarkan_prodi(self, prodi):

        query = """
        SELECT
            id,
            nama,
            nim,
            semester,
            prodi,
            tanggal_input
        FROM mahasiswa
        WHERE prodi = ?
        ORDER BY nama ASC
    """

        try:
            self.cursor.execute(query, (prodi,))
        except sqlite3.OperationalError:
            self._pastikan_kolom_tanggal()
            self.cursor.execute(query, (prodi,))

        return self.cursor.fetchall()

    # ===========================
    # STATISTIK DASHBOARD
    # ===========================

    def hitung_data_terbaru(self, hari=7):
        """
        Menghitung jumlah data yang ditambahkan dalam N hari terakhir.
        """

        batas = datetime.now() - timedelta(days=hari)

        semua = self.tampilkan_semua()

        total = 0

        for row in semua:

            tanggal = row[5] if len(row) > 5 else None

            if tanggal:
                try:
                    dt = datetime.strptime(tanggal, "%Y-%m-%d %H:%M:%S")

                    if dt >= batas:
                        total += 1

                except Exception:
                    pass

        return total

    def tampilkan_data_terbaru(self, hari=7):
        """
        Mengambil baris mahasiswa yang tanggal_input-nya masih dalam
        N hari terakhir, diurutkan dari yang paling baru ke yang lama.
        Dipakai oleh kartu 'Data Terbaru' di Dashboard.
        """

        batas = datetime.now() - timedelta(days=hari)

        semua = self.tampilkan_semua()

        hasil = []

        for row in semua:

            tanggal = row[5] if len(row) > 5 else None

            if not tanggal:
                continue

            try:
                dt = datetime.strptime(tanggal, "%Y-%m-%d %H:%M:%S")
            except Exception:
                continue

            if dt >= batas:
                hasil.append((dt, row))

        hasil.sort(key=lambda pasangan: pasangan[0], reverse=True)

        return [row for _, row in hasil]

    def hitung_per_prodi(self):
        """Mengembalikan dict {prodi: jumlah_mahasiswa}, diurutkan dari
        jumlah terbanyak. Dipakai oleh kartu 'Program Studi' di Dashboard."""

        semua = self.tampilkan_semua()

        hasil = {}

        for row in semua:
            prodi = row[4] if len(row) > 4 and row[4] else None
            if not prodi:
                continue
            hasil[prodi] = hasil.get(prodi, 0) + 1

        return dict(sorted(hasil.items(), key=lambda item: item[1], reverse=True))

    def hitung_per_semester(self):
        """Mengembalikan dict {semester: jumlah_mahasiswa}, diurutkan
        berdasarkan nama semester. Dipakai oleh kartu 'Total Semester'."""

        semua = self.tampilkan_semua()

        hasil = {}

        for row in semua:
            semester = row[3] if len(row) > 3 and row[3] else None
            if not semester:
                continue
            hasil[semester] = hasil.get(semester, 0) + 1

        return dict(sorted(hasil.items(), key=lambda item: item[0]))

    # ===========================
    # TUTUP DATABASE
    # ===========================

    def close(self):
        self.conn.close()
