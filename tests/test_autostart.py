"""
Login autostart registration.

The registry paths need Windows, but the parts that actually caused field
failures -- how the command line is quoted, and what goes in the plist -- are
pure logic and are pinned here on every platform.
"""
import importlib.util
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parent.parent / "client_app" / "autostart.py"
_spec = importlib.util.spec_from_file_location("_autostart_under_test", _SRC)
autostart = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(autostart)


@pytest.fixture()
def frozen(monkeypatch):
    def _set(is_frozen, executable="/Applications/HelpdeskClient.app/Contents/MacOS/HelpdeskClient",
             argv0="/opt/helpdesk/main.py"):
        monkeypatch.setattr(autostart.sys, "frozen", is_frozen, raising=False)
        monkeypatch.setattr(autostart.sys, "executable", executable)
        monkeypatch.setattr(autostart.sys, "argv", [argv0])
    return _set


# ── Command construction ──────────────────────────────

def test_frozen_build_launches_the_executable_alone(frozen):
    frozen(True, executable="/Applications/Helpdesk/HelpdeskClient")
    assert autostart.program_arguments() == ["/Applications/Helpdesk/HelpdeskClient"]


def test_source_checkout_includes_the_interpreter(frozen):
    frozen(False, executable="/usr/bin/python3", argv0="/opt/helpdesk/main.py")
    args = autostart.program_arguments()
    assert args == ["/usr/bin/python3", "/opt/helpdesk/main.py"]


def test_command_string_is_quoted_for_paths_with_spaces(frozen):
    """An unquoted "C:\\Program Files\\..." Run value is parsed as "C:\\Program"
    plus arguments and the client silently stops starting at login. Uses a
    POSIX-shaped path so os.path.abspath() is a no-op on the CI platform; the
    property under test is the quoting, not the drive letter."""
    frozen(True, executable="/opt/Program Files/HelpdeskClient")
    assert autostart.command_string() == '"/opt/Program Files/HelpdeskClient"'


def test_command_string_quotes_every_part(frozen):
    frozen(False, executable="/opt/Program Files/python3",
           argv0="/opt/My Apps/helpdesk/main.py")
    cmd = autostart.command_string()
    assert cmd == '"/opt/Program Files/python3" "/opt/My Apps/helpdesk/main.py"'


# ── LaunchAgent plist ─────────────────────────────────

def test_plist_starts_at_login(frozen):
    frozen(True)
    assert "<key>RunAtLoad</key><true/>" in autostart.plist_contents()


def test_plist_restarts_after_a_crash_but_honours_a_clean_quit(frozen):
    """KeepAlive:true would relaunch even a deliberate tray Quit, making Quit
    look broken. SuccessfulExit:false restarts only on abnormal exit."""
    frozen(True)
    body = autostart.plist_contents()
    assert "<key>KeepAlive</key>" in body
    assert "<key>SuccessfulExit</key><false/>" in body
    assert "<key>KeepAlive</key><true/>" not in body


def test_plist_embeds_the_full_argument_vector(frozen):
    frozen(False, executable="/usr/bin/python3", argv0="/opt/helpdesk/main.py")
    body = autostart.plist_contents()
    assert "<string>/usr/bin/python3</string>" in body
    assert "<string>/opt/helpdesk/main.py</string>" in body


def test_plist_is_well_formed_xml(frozen):
    import plistlib
    frozen(True)
    parsed = plistlib.loads(autostart.plist_contents().encode())
    assert parsed["Label"] == "com.ticketing.helpdesk.client"
    assert parsed["RunAtLoad"] is True
    assert parsed["KeepAlive"] == {"SuccessfulExit": False}


# ── enable / disable round trip (macOS path) ──────────

@pytest.fixture()
def fake_home(tmp_path, monkeypatch):
    monkeypatch.setattr(autostart, "is_macos", lambda: True)
    monkeypatch.setattr(autostart.Path, "home", staticmethod(lambda: tmp_path))
    return tmp_path


def test_enable_creates_the_agent_and_disable_removes_it(fake_home, frozen):
    frozen(True)
    assert autostart.is_enabled() is False
    assert autostart.enable() is True
    assert autostart.is_enabled() is True
    assert autostart.disable() is True
    assert autostart.is_enabled() is False


def test_enable_is_idempotent_and_leaves_exactly_one_entry(fake_home, frozen):
    """Upgrades call this on every launch; it must not accumulate entries."""
    frozen(True)
    for _ in range(3):
        autostart.enable()
    agents = list((fake_home / "Library" / "LaunchAgents").iterdir())
    assert len(agents) == 1


def test_repeated_enable_does_not_rewrite_unchanged_file(fake_home, frozen):
    frozen(True)
    autostart.enable()
    p = autostart.plist_path()
    before = p.stat().st_mtime_ns
    autostart.enable()
    assert p.stat().st_mtime_ns == before


def test_enable_after_upgrade_replaces_a_stale_path(fake_home, frozen):
    """New install location must replace the old entry, not sit alongside it."""
    frozen(True, executable="/Applications/Old.app/Contents/MacOS/HelpdeskClient")
    autostart.enable()
    frozen(True, executable="/Applications/New.app/Contents/MacOS/HelpdeskClient")
    autostart.enable()

    agents = list((fake_home / "Library" / "LaunchAgents").iterdir())
    assert len(agents) == 1
    body = autostart.plist_path().read_text()
    assert "New.app" in body
    assert "Old.app" not in body


def test_disable_is_safe_when_nothing_registered(fake_home, frozen):
    frozen(True)
    assert autostart.disable() is True
