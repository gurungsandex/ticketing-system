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
