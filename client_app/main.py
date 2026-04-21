import os
import socket
import sys

from PySide6.QtWidgets import QApplication

from client_id import get_client_id, is_first_launch
from config import APP_NAME, POLL_INTERVAL_MS, QUEUE_RETRY_MS
from notifier import Notifier
from ui.main_window import MainWindow, APP_STYLESHEET

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
    if sys.platform == "darwin":
        _register_autostart_mac()
    else:
        _register_autostart_win()


def _register_autostart_win():
    try:
        import winreg
        exe = sys.executable if getattr(sys, "frozen", False) else sys.argv[0]
        k = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE,
        )
        winreg.SetValueEx(k, "ITTicketingClient", 0, winreg.REG_SZ, exe)
        winreg.CloseKey(k)
    except Exception:
        pass


def _register_autostart_mac():
    try:
        from pathlib import Path
        exe = sys.executable if getattr(sys, "frozen", False) else os.path.abspath(sys.argv[0])
        plist_dir = Path.home() / "Library" / "LaunchAgents"
        plist_dir.mkdir(parents=True, exist_ok=True)
        plist = plist_dir / "com.ticketing.helpdesk.client.plist"
        plist.write_text(
            f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.ticketing.helpdesk.client</string>
    <key>ProgramArguments</key>
    <array><string>{exe}</string></array>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><false/>
</dict>
</plist>""",
            encoding="utf-8",
        )
    except Exception:
        pass


def main():
    first = is_first_launch()
    client_id = get_client_id()          # Creates file on first launch

    if first:
        register_autostart()

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)  # Keep alive in tray
    app.setStyleSheet(APP_STYLESHEET)

    window = MainWindow(
        client_id=client_id,
        hostname=hostname,
        ip_address=ip_address,
        sys_username=sys_username,
    )
    window.show()

    # Background notifier — polls for status changes every 30s
    notifier = Notifier(client_id, POLL_INTERVAL_MS, QUEUE_RETRY_MS)
    notifier.ticket_resolved.connect(window.show_tray_notification)
    notifier.ticket_in_progress.connect(window.show_inprogress_notification)
    notifier.queue_size_changed.connect(window.update_queue_display)
    notifier.start()

    code = app.exec()
    notifier.stop()
    sys.exit(code)


if __name__ == "__main__":
    main()
