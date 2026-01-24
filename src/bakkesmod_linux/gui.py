from PySide6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QVBoxLayout, QHBoxLayout,
    QWidget, QSystemTrayIcon, QMenu, QLabel, QProgressBar, QFrame
)
from PySide6.QtGui import QIcon, QAction, QDesktopServices
from PySide6.QtCore import QThread, Signal, Qt, QUrl, QTimer

from bakkesmod_linux.bakkesmod import BakkesHelper, WATCHER_INTERVAL_MS
from bakkesmod_linux.utils import get_resource_path
from bakkesmod_linux.constants import BAKKESMOD_LOCATION

class ProgressReporter:
    def __init__(self, callback):
        self._callback = callback
        self._has_error = False
        self._last_message = ""

    def set_status_msg(self, message):
        print(f"[status] {message}")
        self._last_message = message
        self._callback(message, -2)

    def status(self, message):
        print(f"[progress] {message}")
        self._last_message = message
        self._callback(message, -1)

    def progress(self, message, percentage):
        if message != "":
            print(f"[progress] {message} ({percentage}%)")
        self._last_message = message
        self._callback(message, percentage)

    def done(self, message):
        if message != "":
            print(f"[done] {message}")
        self._last_message = message
        self._callback(message, 100)

    def error(self, message):
        print(f"[error] {message}")
        self._has_error = True
        self._last_message = message
        self._callback(message, 100)

class WorkerThread(QThread):
    finished = Signal(bool, str)
    progress_update = Signal(str, int)

    def __init__(self, task_fn):
        super().__init__()
        self.task_fn = task_fn

    def run(self):
        try:
            def emit_progress(message, percentage=-1):
                self.progress_update.emit(message, percentage)

            progress = ProgressReporter(emit_progress)
            self.task_fn(progress)

            success = not progress._has_error
            self.finished.emit(success, progress._last_message)
        except Exception as e:
            self.finished.emit(False, str(e))

class BakkesWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BakkesMod")
        self.setFixedSize(360, 200)

        with get_resource_path("bakkesmod.png") as file:
            self.setWindowIcon(QIcon(str(file)))

        self.injector = BakkesHelper()
        self.worker_thread = None
        self.is_busy = False

        self.setup_ui()
        self.setup_tray()
        self.setup_watcher()

        with get_resource_path("main.qss") as file:
            self.setStyleSheet(file.read_text(encoding="utf-8"))

        self.start_task(
            lambda progress: self.injector.update(progress),
            after_fn=lambda success, msg: self.on_startup_complete()
        )

    def setup_watcher(self):
        self.watcher_timer = QTimer(self)
        self.watcher_timer.timeout.connect(self.injector.check_rl_process)
        self.injector.set_process_callback(self.on_process_state_changed)
        self.watcher_timer.start(WATCHER_INTERVAL_MS)

    def check_rl_process(self):
        self.injector.check_rl_process()

        # update initial ui state
        if self.injector.rl_running:
            self.on_process_state_changed(True)
        else:
            self.on_process_state_changed(False)

    def on_startup_complete(self):
        self.show_idle_state()
        self.injector.check_rl_process()

        # update initial ui state
        self.check_rl_process()

    def on_process_state_changed(self, running: bool):
        if not running:
            self.set_status("waiting for rocket league...", "normal")
            self.inject_btn.setEnabled(False)
            self.injector.injected = False
            return

        if self.injector.injected:
            self.set_status("injected", "success")
            self.inject_btn.setEnabled(False)
        else:
            self.set_status("ready", "info")
            self.inject_btn.setEnabled(True)

    def setup_ui(self):
        central = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        header = QFrame()
        header.setObjectName("header")
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(8, 8, 8, 8)
        header_layout.setSpacing(4)

        self.update_btn = QPushButton("check for updates")
        self.update_btn.setObjectName("headerBtn")
        self.update_btn.clicked.connect(self.check_updates)

        self.folder_btn = QPushButton("open folder")
        self.folder_btn.setObjectName("headerBtn")
        self.folder_btn.clicked.connect(self.open_folder)

        header_layout.addWidget(self.update_btn)
        header_layout.addWidget(self.folder_btn)
        header_layout.addStretch()

        header.setLayout(header_layout)
        main_layout.addWidget(header)

        self.content_area = QWidget()
        self.content_layout = QVBoxLayout()
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.content_area.setLayout(self.content_layout)

        main_layout.addWidget(self.content_area, 1)

        central.setLayout(main_layout)
        self.setCentralWidget(central)

        self.setup_idle_widgets()
        self.setup_loading_widgets()

    def setup_idle_widgets(self):
        self.idle_widget = QWidget()
        idle_layout = QVBoxLayout()
        idle_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        idle_layout.setSpacing(12)

        self.inject_btn = QPushButton("inject")
        self.inject_btn.setObjectName("mainBtn")
        self.inject_btn.setFixedSize(140, 40)
        self.inject_btn.clicked.connect(self.inject_clicked)

        self.status_label = QLabel("ready")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        idle_layout.addWidget(self.inject_btn, 0, Qt.AlignmentFlag.AlignHCenter)
        idle_layout.addWidget(self.status_label, 0, Qt.AlignmentFlag.AlignHCenter)

        self.idle_widget.setLayout(idle_layout)

    def setup_loading_widgets(self):
        self.loading_widget = QWidget()
        loading_layout = QVBoxLayout()
        loading_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_layout.setSpacing(16)

        self.progress_text = QLabel("")
        self.progress_text.setObjectName("progressText")
        self.progress_text.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedWidth(260)
        self.progress_bar.setTextVisible(False)

        loading_layout.addWidget(self.progress_text, 0, Qt.AlignmentFlag.AlignHCenter)
        loading_layout.addWidget(self.progress_bar, 0, Qt.AlignmentFlag.AlignHCenter)

        self.loading_widget.setLayout(loading_layout)

    def show_idle_state(self):
        self.clear_content()
        self.content_layout.addWidget(self.idle_widget)
        self.idle_widget.show()
        self.is_busy = False
        self.toggle_header_buttons(True)

    def show_loading_state(self):
        self.clear_content()
        self.content_layout.addWidget(self.loading_widget)
        self.loading_widget.show()
        self.is_busy = True
        self.toggle_header_buttons(False)

    def clear_content(self):
        # remove all widgets from the central thing
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.hide()

    def toggle_header_buttons(self, enabled):
        self.update_btn.setEnabled(enabled)
        self.folder_btn.setEnabled(enabled)

    def setup_tray(self):
        self.tray = QSystemTrayIcon(self)

        with get_resource_path("bakkesmod.png") as icon_path:
            self.tray.setIcon(QIcon(str(icon_path)))

        self.tray.setToolTip("BakkesMod")

        menu = QMenu()
        menu.addAction(self.create_action("show", self.show_window))
        menu.addAction(self.create_action("quit", self.quit_app))

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.tray_clicked)
        self.tray.show()

    def create_action(self, text, slot):
        action = QAction(text, self)
        action.triggered.connect(slot)
        return action

    def show_window(self):
        self.show()
        self.activateWindow()

    def quit_app(self):
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.quit()
            self.worker_thread.wait()

        self.tray.hide()
        QApplication.quit()

    def tray_clicked(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.show_window()

    def closeEvent(self, event):
        event.ignore()
        self.hide()

    def check_updates(self):
        if self.is_busy:
            return

        self.start_task(
            lambda progress: self.injector.update(progress),
            after_fn=lambda success, msg: self.finish_update(success, msg)
        )

    def open_folder(self):
        if BAKKESMOD_LOCATION.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(BAKKESMOD_LOCATION)))
        else:
            self.set_status("bakkesmod folder not found", "error")

    def inject_clicked(self):
        if self.is_busy:
            return

        self.start_task(
            lambda progress: self.injector.inject(progress),
            after_fn=lambda success, msg: self.finish_injection(success, msg)
        )

    def start_task(self, task_fn, after_fn=None):
        self.show_loading_state()

        self.worker_thread = WorkerThread(task_fn)
        self.worker_thread.progress_update.connect(self.update_progress)
        self.worker_thread.finished.connect(
            lambda success, msg: self.task_finished(success, msg, after_fn)
        )
        self.worker_thread.start()

    def update_progress(self, message, percentage):
        if percentage == -2:
            self.set_status(message, "info")
            return

        self.show_loading_state()
        self.progress_text.setText(message)

        if percentage == -1:
            self.progress_bar.setRange(0, 0)
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(percentage)

    def task_finished(self, success, message, after_fn):
        if after_fn:
            after_fn(success, message)
        else:
            self.show_idle_state()

    def finish_update(self, success, message):
        self.show_idle_state()
        if success:
            self.set_status(message or "up to date", "success")
        else:
            self.set_status(message or "update failed", "error")

        self.check_rl_process()

    def finish_injection(self, success, message):
        self.injector.injected = success
        self.show_idle_state()

        if success:
            self.on_process_state_changed(self.injector.rl_running)
        else:
            self.set_status(message or "injection failed", "error")

    def set_status(self, text, state="normal"):
        self.status_label.setText(text)
        self.status_label.setProperty("state", state)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
