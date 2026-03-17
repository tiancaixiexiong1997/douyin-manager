from app.services.crawler_service import CrawlerService


def test_parse_video_item_prefers_static_cover_over_dynamic_cover() -> None:
    item = {
        "aweme_id": "123",
        "desc": "test video",
        "video": {
            "cover": {"url_list": ["https://example.com/cover.jpg"]},
            "origin_cover": {"url_list": ["https://example.com/origin-cover.jpg"]},
            "dynamic_cover": {"url_list": ["https://example.com/dynamic-cover.webp"]},
            "play_addr": {
                "url_list": ["https://example.com/playwm/video.mp4"],
            },
            "duration": 12000,
        },
        "statistics": {},
    }

    parsed = CrawlerService._parse_video_item(item)

    assert parsed is not None
    assert parsed["cover_url"] == "https://example.com/origin-cover.jpg"


def test_parse_video_item_falls_back_to_dynamic_cover_when_needed() -> None:
    item = {
        "aweme_id": "123",
        "desc": "test video",
        "video": {
            "dynamic_cover": {"url_list": ["https://example.com/dynamic-cover.webp"]},
            "play_addr": {
                "url_list": ["https://example.com/playwm/video.mp4"],
            },
            "duration": 12000,
        },
        "statistics": {},
    }

    parsed = CrawlerService._parse_video_item(item)

    assert parsed is not None
    assert parsed["cover_url"] == "https://example.com/dynamic-cover.webp"
