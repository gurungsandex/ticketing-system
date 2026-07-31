import os
import socket
import sys

from PySide6.QtCore import QSharedMemory
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

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

_AUTOSTART_NAME = "ITTicketingClient"
_MAC_PLIST_LABEL = "com.ticketing.helpdesk.client"


def _executable_command() -> str:
    """The command used to relaunch this client at login.

    For a frozen PyInstaller build this is the exe path; for a dev run it is the
    interpreter + script. The path is quoted so directories containing spaces
    (e.g. C:\\Program Files\\...) don't break the registry Run entry — a common
    cause of "the client stops starting after install".
    """
    if getattr(sys, "frozen", False):
        return f'"{os.path.abspath(sys.executable)}"'
    return f'"{os.path.abspath(sys.executable)}" "{os.path.abspath(sys.argv[0])}"'


def register_autostart():
    """Idempotently (re-)register login autostart. Runs on EVERY launch so a
    once-registered client that later lost its entry (profile reset, path change,
    AV cleanup) re-heals itself instead of silently never starting again."""
    if sys.platform == "darwin":
        _register_autostart_mac()
    else:
        _register_autostart_win()


def _register_autostart_win():
    try:
        import winreg
        cmd = _executable_command()
        k = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_READ | winreg.KEY_SET_VALUE,
        )
        # Only write if missing or stale, to minimise registry churn.
        try:
            current, _ = winreg.QueryValueEx(k, _AUTOSTART_NAME)
        except FileNotFoundError:
            current = None
        if current != cmd:
            winreg.SetValueEx(k, _AUTOSTART_NAME, 0, winreg.REG_SZ, cmd)
        winreg.CloseKey(k)
    except Exception:
        pass


def _register_autostart_mac():
    try:
        from pathlib import Path
        cmd = os.path.abspath(sys.executable) if getattr(sys, "frozen", False) \
            else os.path.abspath(sys.argv[0])
        plist_dir = Path.home() / "Library" / "LaunchAgents"
        plist_dir.mkdir(parents=True, exist_ok=True)
        plist = plist_dir / f"{_MAC_PLIST_LABEL}.plist"
        # KeepAlive=true so launchd relaunches the client if it ever exits
        # unexpectedly — it stays running until explicitly uninstalled.
        args = f"<string>{cmd}</string>"
        if not getattr(sys, "frozen", False):
            args = f"<string>{os.path.abspath(sys.executable)}</string>" \
                   f"<string>{os.path.abspath(sys.argv[0])}</string>"
        plist.write_text(
            f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>{_MAC_PLIST_LABEL}</string>
    <key>ProgramArguments</key>
    <array>{args}</array>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
</dict>
</plist>""",
            encoding="utf-8",
        )
    except Exception:
        pass


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
    notifier.start()

    code = app.exec()
    notifier.stop()
    sys.exit(code)


if __name__ == "__main__":
    main()
