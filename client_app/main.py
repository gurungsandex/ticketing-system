import argparse
import os
import socket
import sys

from PySide6.QtWidgets import QApplication, QSystemTrayIcon

import autostart
from client_id import get_client_id
from config import APP_NAME, POLL_INTERVAL_MS, QUEUE_RETRY_MS
from notifier import Notifier
from single_instance import SingleInstance
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


def _uninstall() -> int:
    """Remove every trace that would start this client again.

    Invoked as `HelpdeskClient --uninstall` by the uninstall scripts so that
    removing the application also removes its logon entry — otherwise Windows
    and launchd keep trying to start a binary that is no longer there.
    """
    autostart.uninstall()
    print("Auto-start entries removed.")
    return 0


def main():
    parser = argparse.ArgumentParser(
        prog="HelpdeskClient", add_help=True,
        description="IT Ticketing System desktop client.",
    )
    parser.add_argument(
        "--uninstall", action="store_true",
        help="Remove login auto-start entries and exit.",
    )
    # parse_known_args so a stray argument from a logon task or launchd never
    # prevents the client from starting.
    args, _unknown = parser.parse_known_args()

    if args.uninstall:
        sys.exit(_uninstall())

    client_id = get_client_id()

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)  # Keep alive in tray
    app.setStyleSheet(APP_STYLESHEET)

    # ── Single-instance guard ────────────────────────────
    # Prevents duplicate copies (double-clicks, autostart + manual launch) from
    # running at once. The lock is held by the OS and released when this
    # process dies, so a crashed client does not block the next launch.
    guard = SingleInstance()
    if not guard.acquire():
        print("Client already running.")
        sys.exit(0)
    app._singleton_guard = guard  # keep a reference so it isn't GC'd

    # Re-register autostart on every launch (self-healing), unless the user
    # has explicitly turned it off from the tray menu.
    autostart.register_if_wanted()

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
    guard.release()
    sys.exit(code)


if __name__ == "__main__":
    main()
