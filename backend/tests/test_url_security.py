from app.services.url_security import is_allowed_media_url


def test_allow_known_domain_and_subdomain() -> None:
    assert is_allowed_media_url("https://www.douyin.com/video/123") is True
    assert is_allowed_media_url("https://cdn.douyinvod.com/path/video.mp4") is True


def test_reject_fake_suffix_or_substring() -> None:
    assert is_allowed_media_url("https://douyin.com.evil.example/video.mp4") is False
    assert is_allowed_media_url("https://evil-douyin.com/video.mp4") is False


def test_reject_non_http_scheme_and_invalid_url() -> None:
    assert is_allowed_media_url("javascript:alert(1)") is False
    assert is_allowed_media_url("not-a-url") is False
