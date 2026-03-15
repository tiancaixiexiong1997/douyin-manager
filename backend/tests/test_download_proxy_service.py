from fastapi import HTTPException
import pytest

import app.services.download_proxy_service as download_proxy_module
from app.services.download_proxy_service import (
    build_proxy_download_response,
    build_safe_filename,
)


def test_build_safe_filename_sanitizes_and_preserves_mp4_suffix() -> None:
    assert build_safe_filename('a/b:c*?"<>|name') == "a_b_c______name.mp4"
    assert build_safe_filename("clean-name.MP4") == "clean-name.MP4"
    assert build_safe_filename("") == "video.mp4"


@pytest.mark.asyncio
async def test_build_proxy_download_response_rejects_untrusted_domain() -> None:
    class DummyDB:
        pass

    with pytest.raises(HTTPException) as exc_info:
        await build_proxy_download_response(
            url="https://evil.example/video.mp4",
            filename="video",
            video_id=None,
            db=DummyDB(),  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 400


def test_proxy_timeout_and_chunk_size_normalization(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(download_proxy_module.settings, "DOWNLOAD_PROXY_CONNECT_TIMEOUT_SECONDS", 1)
    monkeypatch.setattr(download_proxy_module.settings, "DOWNLOAD_PROXY_READ_TIMEOUT_SECONDS", 5)
    monkeypatch.setattr(download_proxy_module.settings, "DOWNLOAD_PROXY_CHUNK_SIZE_BYTES", 1024)
    monkeypatch.setattr(download_proxy_module.settings, "DOWNLOAD_PROXY_MAX_NETWORK_RETRIES", 99)

    timeout = download_proxy_module._build_http_timeout()
    assert timeout.connect == 3
    assert timeout.read == 10
    assert download_proxy_module._chunk_size_bytes() == 64 * 1024
    assert download_proxy_module._max_network_retries() == 3
