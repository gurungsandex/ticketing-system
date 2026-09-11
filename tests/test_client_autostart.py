"""Auto-start registration and the single-instance guard.

These cover the desktop client's login-persistence contract without needing a
GUI: the modules under test are deliberately free of Qt imports so they can be
exercised headlessly in CI.
"""
import os
import sys
from pathlib import Path

import pytest

CLIENT_APP = Path(__file__).resolve().parent.parent / "client_app"

# The client and the backend both have a top-level ``config`` module, so
# client_app must go on sys.path only for the duration of a client test and the
# previously-imported backend modules must be put back afterwards. Without this
# the backend suite would silently start importing client_app/config.py.
_SHADOWED = ("config", "settings", "autostart", "single_instance")


@pytest.fixture()
def client_home(tmp_path, monkeypatch):
    """Import the client modules in isolation, with per-user storage pointed at
    a throwaway directory so tests never touch the real profile."""
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

    saved_modules = {name: sys.modules.get(name) for name in _SHADOWED}
    saved_path = list(sys.path)
    for name in _SHADOWED:
        sys.modules.pop(name, None)
    sys.path.insert(0, str(CLIENT_APP))
    try:
        yield tmp_path
    finally:
        sys.path[:] = saved_path
        for name in _SHADOWED:
            sys.modules.pop(name, None)
            if saved_modules[name] is not None:
                sys.modules[name] = saved_modules[name]


# ── Launch command construction ───────────────────────

def test_run_key_command_quotes_every_path(client_home, monkeypatch):
    """A client installed under 'C:\\Program Files\\...' must still start.

    The unquoted form was a real defect: Windows parsed the space as an
    argument separator and the Run entry silently did nothing.
    """
    import autostart

    monkeypatch.setattr(autostart.sys, "frozen", True, raising=False)
    monkeypatch.setattr(
        autostart.sys, "executable", r"C:\Program Files\Helpdesk\HelpdeskClient.exe"
    )
    cmd = autostart._run_key_command()
    assert cmd.startswith('"') and cmd.endswith('"')
    assert "Program Files" in cmd


def test_run_key_command_is_stable_across_calls(client_home):
    """Registration compares against this string to decide whether to rewrite.
    If it were not byte-stable the registry would churn on every launch."""
    import autostart

    assert autostart._run_key_command() == autostart._run_key_command()


def test_dev_mode_launch_includes_interpreter(client_home, monkeypatch):
    import autostart

    monkeypatch.setattr(autostart.sys, "frozen", False, raising=False)
    argv = autostart.launch_argv()
    assert len(argv) == 2, "a non-frozen run needs interpreter + script"


# ── Opt-out is honoured by self-healing ───────────────

def test_disable_then_relaunch_does_not_reregister(client_home, monkeypatch):
    """The core auto-start defect: 'Disable auto-start' from the tray was
    undone by the self-healing registration on the next launch."""
    import autostart

    calls = []
    monkeypatch.setattr(autostart, "_win_register", lambda: calls.append("win"))
    monkeypatch.setattr(autostart, "_mac_register", lambda: calls.append("mac"))

    autostart.disable()
    assert autostart.is_opted_out() is True

    autostart.register_if_wanted()  # simulates the next launch
    assert calls == [], "opted-out client must not be re-registered at launch"


def test_enable_clears_opt_out(client_home, monkeypatch):
    import autostart

    monkeypatch.setattr(autostart, "_win_register", lambda: True)
    monkeypatch.setattr(autostart, "_mac_register", lambda: True)

    autostart.disable()
    assert autostart.is_opted_out() is True
    autostart.enable()
    assert autostart.is_opted_out() is False


def test_register_if_wanted_runs_when_not_opted_out(client_home, monkeypatch):
    import autostart

    calls = []
    monkeypatch.setattr(autostart, "_win_register", lambda: calls.append("win") or True)
    monkeypatch.setattr(autostart, "_mac_register", lambda: calls.append("mac") or True)
    monkeypatch.setattr(autostart.sys, "platform", "win32")

    autostart.register_if_wanted()
    assert calls == ["win"]


def test_opt_out_survives_module_reload(client_home):
    """The flag must be persisted, not in-memory — a launch is a fresh process."""
    import autostart

    autostart.disable()
    sys.modules.pop("autostart", None)
    sys.modules.pop("settings", None)
    import autostart as autostart_reloaded

    assert autostart_reloaded.is_opted_out() is True


# ── Uninstall ignores the opt-out flag ────────────────

def test_uninstall_removes_entries_regardless_of_opt_out(client_home, monkeypatch):
    import autostart

    removed = []
    monkeypatch.setattr(autostart, "_win_unregister", lambda: removed.append("win"))
    monkeypatch.setattr(autostart, "_mac_unregister", lambda: removed.append("mac"))
    monkeypatch.setattr(autostart.sys, "platform", "darwin")

    autostart.uninstall()
    assert removed == ["mac"]


# ── macOS LaunchAgent contract ────────────────────────

def test_mac_plist_has_runatload_and_keepalive(client_home):
    """RunAtLoad = start at login, KeepAlive = come back after a crash.
    One earlier code path wrote KeepAlive=false, which broke crash recovery."""
    import autostart

    body = autostart._mac_plist_body()
    assert "<key>RunAtLoad</key><true/>" in body
    assert "<key>KeepAlive</key><true/>" in body
    assert autostart.MAC_LABEL in body


def test_mac_plist_is_byte_stable(client_home):
    import autostart

    assert autostart._mac_plist_body() == autostart._mac_plist_body()


# ── Windows logon task contract ───────────────────────

def test_win_task_xml_restarts_on_failure(client_home):
    """The Run key only fires at logon; the logon task is what provides
    restart-after-crash on Windows."""
    import autostart

    xml = autostart._win_task_xml()
    assert "<RestartOnFailure>" in xml
    assert "<LogonTrigger>" in xml
    # Must not request elevation — the client runs as the logged-on user.
    assert "<RunLevel>LeastPrivilege</RunLevel>" in xml
    # IgnoreNew keeps a second logon from starting a duplicate copy.
    assert "<MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>" in xml


def test_win_task_xml_is_wellformed(client_home):
    import xml.etree.ElementTree as ET

    import autostart

    ET.fromstring(autostart._win_task_xml())  # raises if malformed


def test_win_register_leaves_only_one_mechanism(client_home, monkeypatch):
    """Upgrades must not leave both a task and a Run key behind, or the client
    would be started twice at logon."""
    import autostart

    actions = []
    monkeypatch.setattr(autostart, "_win_write_task", lambda: actions.append("task") or True)
    monkeypatch.setattr(autostart, "_win_remove_run_key", lambda: actions.append("rm_run"))
    monkeypatch.setattr(autostart, "_win_write_run_key", lambda: actions.append("run") or True)

    assert autostart._win_register() is True
    assert actions == ["task", "rm_run"], "run key must be cleared when the task wins"


def test_win_register_falls_back_to_run_key(client_home, monkeypatch):
    """Task Scheduler can be disabled by policy; login start must still work."""
    import autostart

    monkeypatch.setattr(autostart, "_win_write_task", lambda: False)
    monkeypatch.setattr(autostart, "_win_remove_run_key", lambda: None)
    monkeypatch.setattr(autostart, "_win_write_run_key", lambda: True)

    assert autostart._win_register() is True


# ── Single-instance guard ─────────────────────────────

def test_second_instance_is_refused(client_home):
    from single_instance import SingleInstance

    first = SingleInstance("test-guard")
    assert first.acquire() is True

    second = SingleInstance("test-guard")
    assert second.acquire() is False, "a second live instance must be refused"

    first.release()


def test_lock_is_reusable_after_release(client_home):
    """A crashed client must not lock itself out. Releasing the OS lock — which
    is what process death does — has to make the next acquire succeed. This is
    the failure mode the previous QSharedMemory guard had on macOS/Linux, where
    an orphaned segment survived the crash and blocked every later launch."""
    from single_instance import SingleInstance

    first = SingleInstance("test-crash")
    assert first.acquire() is True
    first.release()  # stands in for the OS releasing the lock on process death

    second = SingleInstance("test-crash")
    assert second.acquire() is True, "stale lock must not block a relaunch"
    second.release()


def test_lock_records_owner_pid(client_home):
    from single_instance import SingleInstance

    guard = SingleInstance("test-pid")
    assert guard.acquire() is True
    assert guard.owner_pid() == os.getpid()
    guard.release()
