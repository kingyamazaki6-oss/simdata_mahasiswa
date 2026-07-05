import os
import json

from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, FadeTransition
from kivy.properties import ListProperty

from kivymd.app import MDApp

# Widget custom (didaftarkan ke Factory saat modul ini diimport)
import widgets.bottom_nav  # noqa: F401

from screens.splash_screen import SplashScreen
from screens.login_screen import LoginScreen
from screens.dashboard_screen import DashboardScreen
from screens.input_screen import InputScreen
from screens.data_screen import DataScreen
from screens.filter_screen import FilterScreen
from screens.profile_screen import ProfileScreen
from screens.detail_screen import DetailScreen
from screens.edit_screen import EditScreen

from database import Database


class SIMDATAMahasiswa(MDApp):

    # ==========================================================
    # WARNA TEMA (berubah otomatis saat Mode Gelap di-toggle)
    # Dipakai di semua file .kv lewat referensi `app.bg_screen`,
    # `app.bg_card`, `app.text_primary`, dst supaya SELURUH
    # aplikasi ikut berubah, bukan cuma satu layar.
    # ==========================================================
    bg_screen = ListProperty([0.96, 0.97, 0.99, 1])
    bg_card = ListProperty([1, 1, 1, 1])
    text_primary = ListProperty([0.1, 0.1, 0.12, 1])
    text_secondary = ListProperty([0.55, 0.55, 0.55, 1])
    line_color = ListProperty([0.88, 0.89, 0.91, 1])

    def build(self):

        self.title = "SIMDATA MAHASISWA"

        self.theme_cls.primary_palette = "Blue"

        # SATU-SATUNYA Database() untuk seluruh aplikasi (lihat catatan sebelumnya)
        self.db = Database()

        # Riwayat navigasi, dipakai supaya tombol "back" (arrow-left)
        # selalu kembali ke layar SEBELUMNYA, bukan selalu ke dashboard.
        self.nav_history = []

        # Muat preferensi tersimpan (mode gelap, dsb)
        pengaturan = self.load_settings()
        self.theme_cls.theme_style = "Dark" if pengaturan.get("dark_mode") else "Light"

        self._update_theme_colors()
        self.theme_cls.bind(theme_style=lambda *a: self._update_theme_colors())

        Builder.load_file("kv/components.kv")
        Builder.load_file("kv/splash.kv")
        Builder.load_file("kv/login.kv")
        Builder.load_file("kv/dashboard.kv")
        Builder.load_file("kv/input.kv")
        Builder.load_file("kv/data.kv")
        Builder.load_file("kv/filter.kv")
        Builder.load_file("kv/profile.kv")
        Builder.load_file("kv/detail.kv")
        Builder.load_file("kv/edit.kv")

        sm = ScreenManager(
            transition=FadeTransition(duration=0.35)
        )

        sm.add_widget(
            SplashScreen(name="splash")
        )

        sm.add_widget(
            LoginScreen(name="login")
        )

        sm.add_widget(
            DashboardScreen(name="dashboard")
        )

        sm.add_widget(
            InputScreen(name="input")
        )

        sm.add_widget(
            DataScreen(name="data")
        )

        sm.add_widget(
            FilterScreen(name="filter")
        )

        sm.add_widget(
            ProfileScreen(name="profile")
        )

        sm.add_widget(
            DetailScreen(name="detail")
        )

        sm.add_widget(
            EditScreen(name="edit")
        )

        return sm

    # ==========================================================
    # NAVIGASI (dengan riwayat, agar tombol back akurat)
    # ==========================================================

    def go_to(self, nama_layar):
        """Pindah ke layar baru sambil menyimpan layar saat ini ke riwayat."""

        current = self.root.current

        if current and current != nama_layar:
            self.nav_history.append(current)

        self.root.current = nama_layar

    def go_back(self, default="dashboard"):
        """Kembali ke layar sebelumnya berdasarkan riwayat navigasi."""

        if self.nav_history:
            sebelumnya = self.nav_history.pop()
        else:
            sebelumnya = default

        self.root.current = sebelumnya

    def reset_history(self):
        self.nav_history = []

    # ==========================================================
    # MODE GELAP (Dark Mode)
    # ==========================================================

    def set_dark_mode(self, aktif):
        self.theme_cls.theme_style = "Dark" if aktif else "Light"

        pengaturan = self.load_settings()
        pengaturan["dark_mode"] = bool(aktif)
        self.save_settings(pengaturan)

    def _update_theme_colors(self):
        if self.theme_cls.theme_style == "Dark":
            self.bg_screen = [0.07, 0.08, 0.10, 1]
            self.bg_card = [0.15, 0.16, 0.18, 1]
            self.text_primary = [0.92, 0.93, 0.95, 1]
            self.text_secondary = [0.68, 0.69, 0.72, 1]
            self.line_color = [0.26, 0.27, 0.30, 1]
        else:
            self.bg_screen = [0.96, 0.97, 0.99, 1]
            self.bg_card = [1, 1, 1, 1]
            self.text_primary = [0.1, 0.1, 0.12, 1]
            self.text_secondary = [0.55, 0.55, 0.55, 1]
            self.line_color = [0.88, 0.89, 0.91, 1]

    # ==========================================================
    # PENGATURAN SEDERHANA (disimpan sebagai file JSON kecil)
    # Menggunakan user_data_dir supaya tetap berfungsi saat
    # dibundel jadi APK Android (bukan menulis ke folder read-only).
    # ==========================================================

    def _settings_path(self):
        return os.path.join(self.user_data_dir, "settings.json")

    def load_settings(self):
        path = self._settings_path()

        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    return json.load(f)
            except Exception:
                return {}

        return {}

    def save_settings(self, data):
        path = self._settings_path()

        try:
            with open(path, "w") as f:
                json.dump(data, f)
        except Exception as e:
            print("Gagal menyimpan pengaturan:", e)


if __name__ == "__main__":
    SIMDATAMahasiswa().run()
