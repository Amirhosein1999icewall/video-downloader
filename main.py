import os
import sys
import threading
import requests

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton,
    QFileDialog, QProgressBar, QMessageBox, QTextEdit,
    QVBoxLayout, QHBoxLayout, QFrame
)


class DownloadWorker(QThread):
    progress = Signal(int)
    status = Signal(str)
    finished_ok = Signal(str)
    finished_fail = Signal(str)

    def __init__(self, url: str, save_path: str):
        super().__init__()
        self.url = url
        self.save_path = save_path
        self._cancel_event = threading.Event()

    def cancel(self):
        self._cancel_event.set()

    def run(self):
        temp_path = self.save_path + ".part"

        try:
            self.status.emit("در حال اتصال به سرور...")
            os.makedirs(os.path.dirname(self.save_path) or ".", exist_ok=True)

            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

            with requests.get(self.url, stream=True, timeout=30) as r:
                r.raise_for_status()

                total = r.headers.get("content-length")
                total = int(total) if total and total.isdigit() else 0

                downloaded = 0
                chunk_size = 1024 * 64

                self.status.emit("دانلود شروع شد...")
                with open(temp_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=chunk_size):
                        if self._cancel_event.is_set():
                            try:
                                f.close()
                            except Exception:
                                pass
                            try:
                                os.remove(temp_path)
                            except Exception:
                                pass
                            self.finished_fail.emit("دانلود لغو شد.")
                            return

                        if not chunk:
                            continue

                        f.write(chunk)
                        downloaded += len(chunk)

                        if total > 0:
                            percent = int(downloaded * 100 / total)
                            self.progress.emit(max(0, min(100, percent)))

            if total == 0:
                self.progress.emit(100)

            os.replace(temp_path, self.save_path)
            self.finished_ok.emit(self.save_path)

        except Exception as e:
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception:
                pass
            self.finished_fail.emit(f"خطا: {e}")


class DownloaderApp(QWidget):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.save_path = ""
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Simple Downloader")
        self.setMinimumSize(720, 420)

        self.setStyleSheet("""
            QWidget {
                background: #f4f6f9;
                color: #1f2937;
                font-size: 14px;
            }
            QFrame#Card {
                background: white;
                border-radius: 14px;
                border: 1px solid #e5e7eb;
            }
            QLabel#Title {
                font-size: 22px;
                font-weight: bold;
                color: #111827;
            }
            QLabel#Subtitle {
                color: #6b7280;
                font-size: 13px;
            }
            QLineEdit {
                background: white;
                border: 1px solid #d1d5db;
                border-radius: 10px;
                padding: 10px 12px;
            }
            QLineEdit:focus {
                border: 1px solid #2563eb;
            }
            QPushButton {
                border: none;
                border-radius: 10px;
                padding: 10px 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                opacity: 0.9;
            }
            QPushButton#Primary {
                background: #2563eb;
                color: white;
            }
            QPushButton#Danger {
                background: #ef4444;
                color: white;
            }
            QPushButton#Secondary {
                background: #e5e7eb;
                color: #111827;
            }
            QProgressBar {
                border: 1px solid #d1d5db;
                border-radius: 10px;
                text-align: center;
                background: white;
                height: 24px;
            }
            QProgressBar::chunk {
                border-radius: 10px;
                background: #10b981;
            }
            QTextEdit {
                background: white;
                border: 1px solid #d1d5db;
                border-radius: 10px;
                padding: 8px;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(14)

        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(14)

        title = QLabel("Simple Downloader")
        title.setObjectName("Title")
        subtitle = QLabel("لینک مستقیم را وارد کن، مسیر را انتخاب کن، دانلود را شروع کن یا هر لحظه لغو کن.")
        subtitle.setObjectName("Subtitle")
        subtitle.setWordWrap(True)

        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("لینک مستقیم فایل را وارد کنید...")

        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)
        self.path_edit.setPlaceholderText("مسیر ذخیره فایل")

        self.browse_btn = QPushButton("انتخاب مسیر")
        self.browse_btn.setObjectName("Secondary")
        self.browse_btn.clicked.connect(self.pick_path)

        path_row = QHBoxLayout()
        path_row.addWidget(self.path_edit, 1)
        path_row.addWidget(self.browse_btn)

        self.status_label = QLabel("آماده برای دانلود")
        self.status_label.setStyleSheet("color: #374151; font-weight: 600;")

        self.progress = QProgressBar()
        self.progress.setValue(0)

        btn_row = QHBoxLayout()
        self.start_btn = QPushButton("دانلود")
        self.start_btn.setObjectName("Primary")
        self.start_btn.clicked.connect(self.start_download)

        self.cancel_btn = QPushButton("لغو")
        self.cancel_btn.setObjectName("Danger")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel_download)

        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(self.cancel_btn)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(120)

        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)
        card_layout.addWidget(QLabel("لینک فایل"))
        card_layout.addWidget(self.url_edit)
        card_layout.addWidget(QLabel("مسیر ذخیره"))
        card_layout.addLayout(path_row)
        card_layout.addWidget(self.status_label)
        card_layout.addWidget(self.progress)
        card_layout.addLayout(btn_row)
        card_layout.addWidget(QLabel("لاگ"))
        card_layout.addWidget(self.log)

        main_layout.addWidget(card)

    def add_log(self, text: str):
        self.log.append(text)

    def guess_filename(self, url: str) -> str:
        name = url.split("/")[-1].split("?")[0]
        return name if name else "downloaded_file"

    def pick_path(self):
        url = self.url_edit.text().strip()
        default_name = self.guess_filename(url) if url else "downloaded_file"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "انتخاب محل ذخیره",
            default_name,
            "All Files (*.*)"
        )
        if file_path:
            self.save_path = file_path
            self.path_edit.setText(file_path)
            self.add_log(f"مسیر ذخیره انتخاب شد: {file_path}")

    def start_download(self):
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, "در حال اجرا", "دانلود قبلاً شروع شده است.")
            return

        url = self.url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, "خطا", "لطفاً لینک مستقیم فایل را وارد کنید.")
            return
        if not self.save_path:
            QMessageBox.warning(self, "خطا", "لطفاً مسیر ذخیره را انتخاب کنید.")
            return

        self.progress.setValue(0)
        self.status_label.setText("در حال شروع...")
        self.add_log(f"شروع دانلود: {url}")

        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)

        self.worker = DownloadWorker(url, self.save_path)
        self.worker.progress.connect(self.progress.setValue)
        self.worker.status.connect(self.on_status)
        self.worker.finished_ok.connect(self.on_success)
        self.worker.finished_fail.connect(self.on_fail)
        self.worker.start()

    def cancel_download(self):
        if self.worker and self.worker.isRunning():
            self.add_log("درخواست لغو ارسال شد...")
            self.status_label.setText("در حال لغو...")
            self.worker.cancel()

    def on_status(self, text: str):
        self.status_label.setText(text)
        self.add_log(text)

    def on_success(self, path: str):
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.status_label.setText("دانلود کامل شد ✅")
        self.add_log(f"تمام شد: {path}")
        self.progress.setValue(100)
        QMessageBox.information(self, "موفق", f"فایل با موفقیت دانلود شد:\n{path}")

    def on_fail(self, msg: str):
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.status_label.setText("دانلود متوقف شد")
        self.add_log(msg)
        QMessageBox.warning(self, "نتیجه", msg)
        self.progress.setValue(0)


def main():
    app = QApplication(sys.argv)
    win = DownloaderApp()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
