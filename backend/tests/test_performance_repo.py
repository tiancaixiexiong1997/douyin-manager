from types import SimpleNamespace

from app.repository.performance_repo import build_performance_summary_payload


def make_row(**overrides):
    base = {
        "id": "perf-1",
        "title": "默认标题",
        "views": 0,
        "likes": 0,
        "comments": 0,
        "shares": 0,
        "conversions": 0,
        "bounce_2s_rate": None,
        "completion_5s_rate": None,
        "completion_rate": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_build_performance_summary_payload_derives_highlights_and_insights() -> None:
    rows = [
        make_row(
            id="perf-a",
            title="爆款开头拆解",
            views=12000,
            likes=800,
            comments=120,
            shares=60,
            conversions=18,
            bounce_2s_rate=28.0,
            completion_5s_rate=52.0,
            completion_rate=31.5,
        ),
        make_row(
            id="perf-b",
            title="门店成交案例",
            views=7800,
            likes=420,
            comments=88,
            shares=42,
            conversions=24,
            bounce_2s_rate=33.0,
            completion_5s_rate=48.0,
            completion_rate=26.0,
        ),
        make_row(
            id="perf-c",
            title="避坑问题合集",
            views=5400,
            likes=180,
            comments=26,
            shares=14,
            conversions=0,
            bounce_2s_rate=41.0,
            completion_5s_rate=35.0,
            completion_rate=18.0,
        ),
    ]

    summary = build_performance_summary_payload(rows, planned_content_count=10)

    assert summary["total_items"] == 3
    assert summary["planned_content_count"] == 10
    assert summary["total_views"] == 25200
    assert round(summary["coverage_rate"], 1) == 30.0
    assert round(summary["avg_completion_5s_rate"], 1) == 45.0
    assert round(summary["avg_engagement_rate"], 1) == 6.9
    assert round(summary["avg_conversion_rate"], 2) == 0.17
    assert summary["best_view_item"].title == "爆款开头拆解"
    assert summary["best_completion_item"].title == "爆款开头拆解"
    assert summary["best_engagement_item"].title == "爆款开头拆解"
    assert summary["best_conversion_item"].title == "门店成交案例"
    assert summary["top_items"][0].title == "爆款开头拆解"
    assert len(summary["insights"]) == 3
    assert summary["insights"][0]["tone"] == "warn"
    assert any("转化" in insight["title"] for insight in summary["insights"])


def test_build_performance_summary_payload_returns_empty_state_insights() -> None:
    summary = build_performance_summary_payload([], planned_content_count=6)

    assert summary["total_items"] == 0
    assert summary["planned_content_count"] == 6
    assert summary["coverage_rate"] == 0.0
    assert summary["best_view_item"] is None
    assert summary["best_conversion_item"] is None
    assert summary["insights"][0]["tone"] == "neutral"
    assert "回流样本" in summary["insights"][0]["title"]
