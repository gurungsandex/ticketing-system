import os
import socket
import sys

from PySide6.QtCore import QSharedMemory
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

import autostart
from client_id import get_client_id
from config import APP_NAME, POLL_INTERVAL_MS, QUEUE_RETRY_MS
from notifier import Notifier
from ui.main_window import APP_STYLESHEET, MainWindow

# ── Collect system info silently before UI opens ──────
hostname = socket.gethostname()
try:
    ip_address = socket.gethostbyname(hostname)
except Exception:
    ip_address = "127.0.0.1"

try:
    sys_username = os.getlogin()
except Exception:
    sys_username = os.environ.get("USERNAME", os.environ.get("USER", "Unknown"))


def register_autostart():
    """Idempotently (re-)register login autostart. Runs on EVERY launch so a
    client that later lost its entry (profile reset, path change, AV cleanup,
    or an upgrade that moved the executable) re-heals itself instead of
    silently never starting again. Implementation lives in autostart.py so the
    tray toggle writes byte-identical entries."""
    autostart.enable()


def main():
    client_id = get_client_id()

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)  # Keep alive in tray
    app.setStyleSheet(APP_STYLESHEET)

    # ── Single-instance guard ────────────────────────────
    # Prevents duplicate copies (double-clicks, autostart + manual launch) from
    # running at once, which previously caused flicker and duplicate tray icons.
    shared = QSharedMemory("it-ticketing-client-singleton")
    if shared.attach():
        # Another instance already holds the segment — surface it and exit.
        print("Client already running.")
        sys.exit(0)
    if not shared.create(1):
        # Could not create (rare) — continue anyway rather than blocking the user.
        pass
    app._singleton_guard = shared  # keep a reference so it isn't GC'd

    # Re-register autostart on every launch (self-healing).
    register_autostart()

    tray_available = QSystemTrayIcon.isSystemTrayAvailable()

    window = MainWindow(
        client_id=client_id,
        hostname=hostname,
        ip_address=ip_address,
        sys_username=sys_username,
        tray_available=tray_available,
    )
    window.show()

    # Background notifier — polls for status changes + connection health.
    notifier = Notifier(client_id, POLL_INTERVAL_MS, QUEUE_RETRY_MS)
    notifier.ticket_resolved.connect(window.show_tray_notification)
    notifier.ticket_in_progress.connect(window.show_inprogress_notification)
    notifier.queue_size_changed.connect(window.update_queue_display)
    notifier.connection_changed.connect(window.update_connection_status)
    notifier.update_available.connect(window.show_update_available)
    notifier.start()

    code = app.exec()
    notifier.stop()
    sys.exit(code)


if __name__ == "__main__":
    main()
