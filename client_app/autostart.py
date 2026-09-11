"""
Login auto-start registration for the desktop client.

This module is the single source of truth for auto-start. Previously the logic
lived in two places (main.py registered one form of the entry, the tray menu
wrote a different one), which meant:

  * the tray "Disable auto-start" action was silently undone on the next
    launch, because startup re-registration had no way to know the user had
    opted out;
  * Windows wrote the executable path unquoted from one path and quoted from
    the other, so a client installed under "C:\\Program Files\\..." either
    failed to start or churned the registry on every launch;
  * macOS wrote KeepAlive=false from one path and true from the other, so
    whether the client came back after a crash depended on which code had run
    last.

Design
------
Windows  : a per-user logon Scheduled Task is preferred because it supports
           automatic restart after a crash. If Task Scheduler is unavailable
           we fall back to the HKCU Run key, which starts at login on every
           supported Windows 10/11 build and needs no elevation. Exactly one
           of the two is ever active, so upgrades never leave duplicates.
macOS    : a LaunchAgent in ~/Library/LaunchAgents with RunAtLoad (start at
           login) and KeepAlive (restart after a crash).

All registration is idempotent: calling register() repeatedly converges on a
single correct entry and rewrites it only when it is missing or stale, so an
entry lost to a profile reset, a path change, or AV cleanup self-heals, while
a steady-state launch touches nothing.

An explicit user opt-out is persisted in settings.json and is honoured by
register(), so self-healing never resurrects an entry the user turned off.
"""
import os
import subprocess  # nosec B404 - used only with fixed argv, never a shell
import sys
from pathlib import Path
from typing import List, Optional

import settings

# Identity of the auto-start entry on each platform. These names are part of
# the installed footprint — changing them would orphan entries on upgrade.
WIN_RUN_VALUE = "ITTicketingClient"
WIN_TASK_NAME = "ITTicketingClient"
WIN_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
MAC_LABEL = "com.ticketing.helpdesk.client"

_OPT_OUT_KEY = "autostart_disabled"

# Hide the console window when shelling out to schtasks on Windows.
_NO_WINDOW = 0x08000000


def _run(argv: List[str], timeout: int = 15) -> subprocess.CompletedProcess:
    """Run a fixed argument vector without a shell, windowless on Windows."""
    kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = _NO_WINDOW
    return subprocess.run(  # nosec B603 - fixed argv, shell=False, no user input
        argv, capture_output=True, text=True, timeout=timeout, check=False, **kwargs
    )


# ── What to launch ────────────────────────────────────

def launch_argv() -> List[str]:
    """The argument vector that starts this client.

    A frozen PyInstaller build is a single executable; a development run needs
    the interpreter plus the script path. Returned unquoted — each consumer
    quotes for its own target format.
    """
    if getattr(sys, "frozen", False):
        return [os.path.abspath(sys.executable)]
    return [os.path.abspath(sys.executable), os.path.abspath(sys.argv[0])]


def _run_key_command() -> str:
    """The Run-key string form: every element quoted so paths with spaces
    (C:\\Program Files\\...) survive. This is the single canonical spelling —
    both registration and staleness comparison use it, so the value never
    churns between launches."""
    return " ".join(f'"{part}"' for part in launch_argv())


# ── User opt-out ──────────────────────────────────────

def is_opted_out() -> bool:
    return bool(settings.get_flag(_OPT_OUT_KEY, False))


def _set_opt_out(value: bool) -> None:
    settings.set_flag(_OPT_OUT_KEY, value)


# ══════════════════════════════════════════════════════
#  Windows
# ══════════════════════════════════════════════════════

def _win_run_key_value() -> Optional[str]:
    try:
        import winreg
    except ImportError:
        return None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, WIN_RUN_KEY, 0,
                            winreg.KEY_READ) as k:
            value, _ = winreg.QueryValueEx(k, WIN_RUN_VALUE)
            return value
    except FileNotFoundError:
        return None
    except OSError:
        return None


def _win_write_run_key() -> bool:
    try:
        import winreg
    except ImportError:
        return False
    desired = _run_key_command()
    if _win_run_key_value() == desired:
        return True  # already correct — do not churn the registry
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, WIN_RUN_KEY, 0,
                            winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, WIN_RUN_VALUE, 0, winreg.REG_SZ, desired)
        return True
    except OSError:
        return False


def _win_remove_run_key() -> None:
    try:
        import winreg
    except ImportError:
        return
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, WIN_RUN_KEY, 0,
                            winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, WIN_RUN_VALUE)
    except (FileNotFoundError, OSError):
        pass


def _win_task_exists() -> bool:
    try:
        r = _run(["schtasks", "/Query", "/TN", WIN_TASK_NAME])
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _win_task_xml() -> str:
    """Logon-triggered task definition.

    RestartOnFailure is what gives us "comes back after a crash" on Windows —
    the Run key alone only ever fires at logon. The task runs in the
    interactive session of the user who registered it, so each logged-on user
    gets their own instance and nothing runs elevated.
    """
    argv = launch_argv()
    command = argv[0]
    arguments = " ".join(f'"{a}"' for a in argv[1:])
    args_element = f"\n      <Arguments>{arguments}</Arguments>" if arguments else ""
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Starts the IT Ticketing desktop client at logon.</Description>
  </RegistrationInfo>
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
    </LogonTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings>
      <StopOnIdleEnd>false</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <RestartOnFailure>
      <Interval>PT1M</Interval>
      <Count>3</Count>
    </RestartOnFailure>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{command}</Command>{args_element}
    </Exec>
  </Actions>
</Task>"""


def _win_write_task() -> bool:
    """Register (or refresh) the logon task. /F overwrites in place, so an
    upgrade updates the existing task rather than adding a second one."""
    import tempfile
    xml_path = None
    try:
        # schtasks requires the XML file to be UTF-16 with a BOM.
        fd, xml_path = tempfile.mkstemp(suffix=".xml")
        os.close(fd)
        Path(xml_path).write_text(_win_task_xml(), encoding="utf-16")
        r = _run(["schtasks", "/Create", "/TN", WIN_TASK_NAME,
                  "/XML", xml_path, "/F"])
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False
    finally:
        if xml_path:
            try:
                os.remove(xml_path)
            except OSError:
                pass


def _win_remove_task() -> None:
    try:
        _run(["schtasks", "/Delete", "/TN", WIN_TASK_NAME, "/F"])
    except (OSError, subprocess.SubprocessError):
        pass


def _win_register() -> bool:
    """Prefer the logon task (it can restart after a crash); fall back to the
    Run key. Only one mechanism is left in place so upgrades and repeated
    launches can never produce two entries that both start the client."""
    if _win_write_task():
        _win_remove_run_key()
        return True
    return _win_write_run_key()


def _win_unregister() -> None:
    _win_remove_task()
    _win_remove_run_key()


def _win_is_registered() -> bool:
    return _win_task_exists() or _win_run_key_value() is not None


# ══════════════════════════════════════════════════════
#  macOS
# ══════════════════════════════════════════════════════

def _mac_plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{MAC_LABEL}.plist"


def _mac_plist_body() -> str:
    """RunAtLoad starts the client at login; KeepAlive brings it back if it
    exits unexpectedly. Both are required by the auto-start spec."""
    args = "".join(f"\n      <string>{a}</string>" for a in launch_argv())
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>{MAC_LABEL}</string>
    <key>ProgramArguments</key>
    <array>{args}
    </array>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>ProcessType</key><string>Interactive</string>
</dict>
</plist>
"""


def _mac_register() -> bool:
    try:
        plist = _mac_plist_path()
        plist.parent.mkdir(parents=True, exist_ok=True)
        desired = _mac_plist_body()
        # Only rewrite when missing or stale, so a steady-state launch does not
        # reload launchd for nothing.
        if plist.exists() and plist.read_text(encoding="utf-8") == desired:
            return True
        plist.write_text(desired, encoding="utf-8")
        # Re-load so the change takes effect without requiring a re-login.
        # bootout/bootstrap is the modern spelling; ignore failures because the
        # plist alone is enough from the next login onward.
        uid = os.getuid()
        _run(["launchctl", "bootout", f"gui/{uid}/{MAC_LABEL}"])
        _run(["launchctl", "bootstrap", f"gui/{uid}", str(plist)])
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def _mac_unregister() -> None:
    try:
        plist = _mac_plist_path()
        try:
            _run(["launchctl", "bootout", f"gui/{os.getuid()}/{MAC_LABEL}"])
        except (OSError, subprocess.SubprocessError):
            pass
        if plist.exists():
            plist.unlink()
    except OSError:
        pass


def _mac_is_registered() -> bool:
    return _mac_plist_path().exists()


# ══════════════════════════════════════════════════════
#  Public API
# ══════════════════════════════════════════════════════

def is_registered() -> bool:
    """True if an auto-start entry currently exists for this user."""
    if sys.platform == "darwin":
        return _mac_is_registered()
    if sys.platform == "win32":
        return _win_is_registered()
    return False


def enable() -> bool:
    """Explicitly turn auto-start on and clear any prior opt-out."""
    _set_opt_out(False)
    if sys.platform == "darwin":
        return _mac_register()
    if sys.platform == "win32":
        return _win_register()
    return False


def disable() -> None:
    """Explicitly turn auto-start off and remember the choice, so the
    self-healing call on the next launch does not put it back."""
    _set_opt_out(True)
    if sys.platform == "darwin":
        _mac_unregister()
    elif sys.platform == "win32":
        _win_unregister()


def register_if_wanted() -> None:
    """Called on every launch. Re-creates a missing or stale entry so the
    client heals itself, but stays out of the way when the user has opted out."""
    if is_opted_out():
        return
    if sys.platform == "darwin":
        _mac_register()
    elif sys.platform == "win32":
        _win_register()


def uninstall() -> None:
    """Remove every auto-start entry regardless of the opt-out flag.

    Used by the `--uninstall` entry point so removing the client leaves nothing
    behind that would try to start it again.
    """
    if sys.platform == "darwin":
        _mac_unregister()
    elif sys.platform == "win32":
        _win_unregister()
