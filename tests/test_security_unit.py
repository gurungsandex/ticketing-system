"""Unit tests for the rate limiter and file magic-byte detection."""
import security


def test_rate_limiter_blocks_over_limit():
    limiter = security.RateLimiter()
    key = "unit-test"
    # 3 allowed within the window, 4th blocked.
    assert limiter.check(key, limit=3, window_seconds=60) is True
    assert limiter.check(key, limit=3, window_seconds=60) is True
    assert limiter.check(key, limit=3, window_seconds=60) is True
    assert limiter.check(key, limit=3, window_seconds=60) is False


def test_rate_limiter_isolates_keys():
    limiter = security.RateLimiter()
    assert limiter.check("a", 1, 60) is True
    assert limiter.check("a", 1, 60) is False
    assert limiter.check("b", 1, 60) is True


def test_detect_content_type():
    assert security.detect_content_type(b"%PDF-1.7 ...") == "application/pdf"
    assert security.detect_content_type(b"\x89PNG\r\n\x1a\n rest") == "image/png"
    assert security.detect_content_type(b"\xff\xd8\xff\xe0 jpeg") == "image/jpeg"
    assert security.detect_content_type(b"GIF89a....") == "image/gif"
    assert security.detect_content_type(b"not a known type") is None


# ── client_ip / X-Forwarded-For trust ─────────────────
#
# X-Forwarded-For is caller-supplied. If it is trusted blindly, an attacker
# rotates the header and bypasses the login rate limit entirely, so these
# tests pin the trust rules rather than just the happy path.

class _FakeClient:
    def __init__(self, host):
        self.host = host


class _FakeRequest:
    def __init__(self, peer, headers=None):
        self.client = _FakeClient(peer) if peer else None
        self.headers = headers or {}


def _with_trusted(monkeypatch, ips):
    # Patch the config module object that `security` actually holds a reference
    # to. conftest evicts "config" from sys.modules between tests, so a bare
    # `import config` here can resolve to a DIFFERENT module object than the one
    # security.py imported, and the patch would silently have no effect.
    monkeypatch.setattr(security.config, "TRUSTED_PROXY_IPS", set(ips))


def test_client_ip_ignores_forwarded_header_when_no_proxy_configured(monkeypatch):
    """Default deployment: the header is forgeable, so it must be ignored."""
    _with_trusted(monkeypatch, [])
    req = _FakeRequest("203.0.113.9", {"x-forwarded-for": "1.2.3.4"})
    assert security.client_ip(req) == "203.0.113.9"


def test_client_ip_ignores_forwarded_header_from_untrusted_peer(monkeypatch):
    """A direct caller spoofing the header must not pick its own identity."""
    _with_trusted(monkeypatch, ["10.0.0.1"])
    req = _FakeRequest("203.0.113.9", {"x-forwarded-for": "1.2.3.4"})
    assert security.client_ip(req) == "203.0.113.9"


def test_client_ip_honours_forwarded_header_from_trusted_proxy(monkeypatch):
    _with_trusted(monkeypatch, ["10.0.0.1"])
    req = _FakeRequest("10.0.0.1", {"x-forwarded-for": "198.51.100.7"})
    assert security.client_ip(req) == "198.51.100.7"


def test_client_ip_takes_rightmost_untrusted_hop(monkeypatch):
    """nginx APPENDS the real peer, so a client-seeded value sits on the left.
    Reading left-to-right would trust exactly the forged part."""
    _with_trusted(monkeypatch, ["10.0.0.1"])
    req = _FakeRequest("10.0.0.1", {"x-forwarded-for": "9.9.9.9, 198.51.100.7"})
    assert security.client_ip(req) == "198.51.100.7"


def test_client_ip_skips_chained_trusted_proxies(monkeypatch):
    _with_trusted(monkeypatch, ["10.0.0.1", "10.0.0.2"])
    req = _FakeRequest("10.0.0.1", {"x-forwarded-for": "198.51.100.7, 10.0.0.2"})
    assert security.client_ip(req) == "198.51.100.7"


def test_client_ip_falls_back_to_peer_when_all_hops_trusted(monkeypatch):
    _with_trusted(monkeypatch, ["10.0.0.1", "10.0.0.2"])
    req = _FakeRequest("10.0.0.1", {"x-forwarded-for": "10.0.0.2"})
    assert security.client_ip(req) == "10.0.0.1"


def test_client_ip_handles_missing_peer(monkeypatch):
    _with_trusted(monkeypatch, [])
    assert security.client_ip(_FakeRequest(None)) == "unknown"
