"""The self-update endpoint is remote code execution by design.

These tests pin the guards that keep it from being reachable by accident.
"""
import pytest


def test_apply_is_refused_when_self_update_disabled(client, admin_headers):
    """Default posture: even a valid super_admin session cannot replace the
    server's code unless an operator deliberately enabled it."""
    r = client.post("/update/apply", headers=admin_headers)
    assert r.status_code == 403
    assert "disabled" in r.json()["detail"].lower()


def test_apply_requires_super_admin(client, make_tech):
    _, tech_headers = make_tech()
    assert client.post("/update/apply", headers=tech_headers).status_code == 403


def test_apply_requires_authentication(client):
    assert client.post("/update/apply").status_code in (401, 403)


def test_check_requires_super_admin(client, make_tech):
    _, tech_headers = make_tech()
    assert client.get("/update/check", headers=tech_headers).status_code == 403


def test_check_reports_disabled_state(client, admin_headers):
    body = client.get("/update/check", headers=admin_headers).json()
    assert body["self_update_enabled"] is False
    # Nothing is ever offered as available while the feature is off.
    assert body["update_available"] is False


def test_apply_refused_without_repo_configured(client, admin_headers, monkeypatch):
    """Enabling the feature is not enough — the source repo must be pinned."""
    import config
    from routers import update as update_router

    monkeypatch.setattr(config, "SELF_UPDATE_ENABLED", True)
    monkeypatch.setattr(update_router.config, "SELF_UPDATE_ENABLED", True)
    monkeypatch.setattr(update_router, "GITHUB_REPO", "")

    r = client.post("/update/apply", headers=admin_headers)
    assert r.status_code == 400
    assert "GITHUB_REPO" in r.json()["detail"]


def test_apply_refused_when_remote_does_not_match(client, admin_headers, monkeypatch):
    """The core supply-chain guard: a tampered or unexpected 'origin' must not
    be pulled from, even when everything else is configured correctly."""
    from routers import update as update_router

    monkeypatch.setattr(update_router.config, "SELF_UPDATE_ENABLED", True)
    monkeypatch.setattr(update_router, "GITHUB_REPO", "trusted-org/ticketing-system")
    monkeypatch.setattr(update_router, "_is_git_repo", lambda: True)
    monkeypatch.setattr(update_router, "_remote_url",
                        lambda: "https://github.com/attacker/evil")

    r = client.post("/update/apply", headers=admin_headers)
    assert r.status_code == 400
    assert "origin" in r.json()["detail"].lower()


def test_apply_refused_over_local_modifications(client, admin_headers, monkeypatch):
    from routers import update as update_router

    monkeypatch.setattr(update_router.config, "SELF_UPDATE_ENABLED", True)
    monkeypatch.setattr(update_router, "GITHUB_REPO", "trusted-org/ticketing-system")
    monkeypatch.setattr(update_router, "_is_git_repo", lambda: True)
    monkeypatch.setattr(update_router, "_remote_matches_configured_repo", lambda: True)
    monkeypatch.setattr(update_router, "_working_tree_is_clean", lambda: False)

    r = client.post("/update/apply", headers=admin_headers)
    assert r.status_code == 409


@pytest.mark.parametrize(
    "remote,repo,expected",
    [
        ("https://github.com/acme/app.git", "acme/app", True),
        ("https://github.com/acme/app", "acme/app", True),
        ("git@github.com:acme/app.git", "acme/app", True),
        ("ssh://git@github.com/acme/app.git", "acme/app", True),
        ("https://github.com/ACME/App.git", "acme/app", True),      # case-insensitive
        ("https://github.com/attacker/app.git", "acme/app", False),  # wrong owner
        ("https://github.com/acme/other.git", "acme/app", False),    # wrong repo
        ("https://evil.example/acme/app.git", "acme/app", False),    # wrong host
        ("https://github.com.evil.example/acme/app", "acme/app", False),  # lookalike host
        ("git@evil.example:acme/app.git", "acme/app", False),        # wrong ssh host
        ("http://github.com/acme/app.git", "acme/app", False),       # plain http
        ("/srv/local/clone", "acme/app", False),                     # local path
        ("", "acme/app", False),                                     # no remote
    ],
)
def test_remote_matching(monkeypatch, remote, repo, expected):
    from routers import update as update_router

    monkeypatch.setattr(update_router, "GITHUB_REPO", repo)
    monkeypatch.setattr(update_router, "_remote_url", lambda: remote)
    assert update_router._remote_matches_configured_repo() is expected


@pytest.mark.parametrize("bad", ["", "not-a-repo", "a/b/c", "owner/", "/repo", "o r/repo"])
def test_invalid_repo_values_are_rejected(monkeypatch, bad):
    from routers import update as update_router

    monkeypatch.setattr(update_router, "GITHUB_REPO", bad)
    assert update_router._repo_configured() is False


def test_pull_is_fast_forward_only(monkeypatch):
    """A merge or rebase on a production host can run merge drivers and resolve
    conflicts unattended. Refusing is the safer failure."""
    from routers import update as update_router

    captured = {}

    class _Result:
        returncode = 0
        stdout = "Already up to date."
        stderr = ""

    def fake_git(*args, **kwargs):
        captured["args"] = args
        return _Result()

    monkeypatch.setattr(update_router, "_git", fake_git)
    update_router._do_git_pull()
    assert "--ff-only" in captured["args"]
    assert "--rebase" not in captured["args"]
