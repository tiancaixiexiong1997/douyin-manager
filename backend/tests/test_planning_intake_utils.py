from app.services import planning_intake_utils
from app.services.prompt_templates import PLANNING_INTAKE_PROMPT_TEMPLATE


def test_planning_intake_prompt_mentions_store_fields() -> None:
    assert "core_products_or_services" in PLANNING_INTAKE_PROMPT_TEMPLATE
    assert "common_hesitations" in PLANNING_INTAKE_PROMPT_TEMPLATE
    assert "门店打法与内容方向" in PLANNING_INTAKE_PROMPT_TEMPLATE


def test_build_execution_preview_highlights_store_basics() -> None:
    preview = planning_intake_utils.build_execution_preview(
        {
            "client_name": "柳州小馆",
            "industry": "餐饮美食",
            "target_audience": "附近上班族",
            "ip_requirements": "先做决策型内容，再做现场证明。",
            "city": "柳州",
            "business_district": "城中区",
            "store_type": "柳州菜馆",
            "avg_ticket": "人均30",
            "core_products_or_services": "炒螺、鸭脚煲",
            "top_reasons_to_choose": "上桌快、不踩雷",
            "common_hesitations": "怕排队",
            "primary_consumption_scenes": "下班吃饭、朋友聚餐",
            "on_camera_roles": "老板",
            "shootable_scenes": "后厨、前厅",
            "business_goal": "提升到店",
        }
    )

    assert "### 1) 门店基础盘" in preview
    assert "柳州 城中区" in preview
    assert "柳州菜馆" in preview
    assert "先做决策型内容，再做现场证明。" in preview
