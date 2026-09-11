"""
Login autostart registration, shared by startup self-healing and the tray menu.

This lived in two places -- main.py (self-heal on every launch) and the tray
"Enable auto-start" action -- which had drifted apart and disagreed about the
command to write and about KeepAlive. A single implementation is the point of
this module: both callers now produce byte-identical entries, which is also
what keeps upgrades from leaving a second, stale entry behind.

Design notes
------------
Windows: one HKCU\\...\\Run value under a fixed name. Writing the same name is
by definition idempotent, so an upgrade overwrites rather than accumulating.
The command is QUOTED -- an unquoted "C:\\Program Files\\..." path is read by
the shell as "C:\\Program" plus arguments and the client silently stops
starting at login.

macOS: one LaunchAgent plist at a fixed path, RunAtLoad so it starts at login.
KeepAlive is {SuccessfulExit: false} rather than plain true: the client must
come back after a crash, but a user who deliberately picks Quit in the tray
should stay quit. Plain `true` relaunches even a clean exit, so Quit appears
broken.

Scope: this is a per-user registration (HKCU / ~/Library/LaunchAgents) and
needs no administrator rights. Registering for ALL users on a machine requires
a machine-wide logon task or LaunchDaemon and is a deployment decision -- see
docs/TROUBLESHOOTING.md.
"""
import os
import sys
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "ITTicketingClient"
PLIST_LABEL = "com.ticketing.helpdesk.client"


def is_macos() -> bool:
    return sys.platform == "darwin"


# ── What to launch ────────────────────────────────────

def program_arguments() -> list:
    """argv for the client, as a list. Frozen builds are a single executable;
    a source checkout needs the interpreter in front of the script."""
    if getattr(sys, "frozen", False):
        return [os.path.abspath(sys.executable)]
    return [os.path.abspath(sys.executable), os.path.abspath(sys.argv[0])]


def command_string() -> str:
    """The same thing as a single quoted command line, for the registry."""
    return " ".join(f'"{part}"' for part in program_arguments())


def plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{PLIST_LABEL}.plist"


def plist_contents() -> str:
    args = "".join(f"<string>{a}</string>" for a in program_arguments())
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>{PLIST_LABEL}</string>
    <key>ProgramArguments</key>
    <array>{args}</array>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key>
    <dict><key>SuccessfulExit</key><false/></dict>
    <key>ProcessType</key><string>Interactive</string>
</dict>
</plist>
"""


# ── Query / enable / disable ──────────────────────────

def is_enabled() -> bool:
    if is_macos():
        return plist_path().exists()
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as k:
            try:
                winreg.QueryValueEx(k, VALUE_NAME)
                return True
            except FileNotFoundError:
                return False
    except Exception:
        return False


def enable() -> bool:
    """Register autostart. Idempotent; safe to call on every launch."""
    if is_macos():
        try:
            p = plist_path()
            p.parent.mkdir(parents=True, exist_ok=True)
            desired = plist_contents()
            # Only rewrite when the content actually differs, so an upgrade
            # doesn't churn the file (and launchd's watch) on every start.
            if not p.exists() or p.read_text(encoding="utf-8") != desired:
                p.write_text(desired, encoding="utf-8")
            return True
        except Exception:
            return False
    try:
        import winreg
        desired = command_string()
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE
        ) as k:
            try:
                current, _ = winreg.QueryValueEx(k, VALUE_NAME)
            except FileNotFoundError:
                current = None
            if current != desired:
                winreg.SetValueEx(k, VALUE_NAME, 0, winreg.REG_SZ, desired)
        return True
    except Exception:
        return False


def disable() -> bool:
    """Remove the autostart entry. Used by the tray toggle and by uninstall."""
    if is_macos():
        try:
            p = plist_path()
            if p.exists():
                p.unlink()
            return True
        except Exception:
            return False
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as k:
            try:
                winreg.DeleteValue(k, VALUE_NAME)
            except FileNotFoundError:
                pass
        return True
    except Exception:
        return False
