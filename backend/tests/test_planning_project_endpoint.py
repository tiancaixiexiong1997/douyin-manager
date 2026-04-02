from types import SimpleNamespace

from app.api.endpoints import planning_project


def test_build_project_client_data_includes_store_profile_fields() -> None:
    project = SimpleNamespace(
        client_name="测试门店",
        industry="餐饮",
        target_audience="同城上班族",
        unique_advantage="上桌快",
        ip_requirements="先做决策型内容",
        style_preference="直接一点",
        business_goal="到店",
        reference_blogger_ids=["b1"],
        store_profile={
            "city": "柳州",
            "business_district": "城中区",
            "store_type": "夜宵烧烤",
            "avg_ticket": "人均30",
            "core_products_or_services": ["烧烤", "炒螺"],
            "top_reasons_to_choose": ["上桌快", "不踩雷"],
            "customer_common_questions": ["几个人怎么点"],
            "common_hesitations": ["怕排队"],
            "primary_consumption_scenes": ["下班夜宵"],
            "on_camera_roles": ["老板"],
            "shootable_scenes": ["后厨", "前厅"],
            "peak_hours": ["22:00-00:00"],
            "batch_shoot_windows": ["下午备菜"],
            "store_constraints": ["高峰期难拍"],
            "special_requirements": "不要苦情创业",
            "forbidden_directions": ["纯氛围感"],
        },
    )

    payload = planning_project._build_project_client_data(project)

    assert payload["city"] == "柳州"
    assert payload["store_type"] == "夜宵烧烤"
    assert payload["core_products_or_services"] == ["烧烤", "炒螺"]
    assert payload["special_requirements"] == "不要苦情创业"


def test_normalize_account_plan_payload_syncs_legacy_fields_from_store_growth_plan() -> None:
    payload = {
        "store_growth_plan": {
            "store_positioning": {
                "market_position": "本地人会反复来的社区店",
                "primary_scene": "下班顺路吃",
                "target_audience_detail": "附近住户和上班族",
                "core_store_value": "价格稳、选择省脑子",
                "differentiation": "老板会直接给建议",
                "avoid_positioning": ["假高端"],
            },
            "decision_triggers": {
                "stop_scroll_triggers": ["别再乱点了"],
                "visit_decision_factors": ["方便", "稳", "不踩雷"],
                "common_hesitations": ["怕不值"],
                "trust_builders": ["真实顾客反馈", "现场服务过程"],
            },
            "content_model": {
                "primary_formats": [{"name": "决策建议型", "fit_reason": "直接解决选择困难", "ratio": "35%"}],
                "content_pillars": [
                    {"name": "点单判断", "description": "帮用户少踩雷", "scene_source": "门店"},
                    {"name": "服务现场", "description": "证明体验", "scene_source": "前厅"},
                    {"name": "产品证明", "description": "证明值不值", "scene_source": "出品"},
                ],
                "traffic_hooks": ["第一次来最容易点错的是这个"],
                "interaction_triggers": ["你一般最纠结哪一步"],
            },
            "on_camera_strategy": {
                "recommended_roles": [{"role": "老板", "responsibility": "做判断", "expression_style": "直给"}],
                "light_persona": "讲话很直接的老板",
                "persona_boundaries": ["不要装专家"],
            },
            "conversion_path": {
                "traffic_to_trust": "先给建议，再给现场证明",
                "trust_to_visit": "最后轻带到店理由",
                "soft_cta_templates": ["要不要下一条我直接教你怎么选"],
                "hard_sell_boundaries": ["开头别报店名"],
            },
            "execution_rules": {
                "posting_frequency": "每周5条",
                "best_posting_times": ["12:00", "19:00"],
                "batch_shoot_scenes": ["营业前准备"],
                "must_capture_elements": ["服务动作"],
                "quality_checklist": ["有停留点"],
            },
        }
    }

    normalized = planning_project._normalize_account_plan_payload(payload)

    assert normalized["account_positioning"]["core_identity"] == "本地人会反复来的社区店"
    assert normalized["content_strategy"]["hook_template"] == "第一次来最容易点错的是这个"
