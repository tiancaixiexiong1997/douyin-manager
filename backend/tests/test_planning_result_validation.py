import app.api.endpoints.planning as planning_endpoint


def test_has_meaningful_plan_result_rejects_empty_payload() -> None:
    assert planning_endpoint._has_meaningful_plan_result({}, {}, []) is False


def test_has_meaningful_plan_result_accepts_structured_plan_content() -> None:
    assert planning_endpoint._has_meaningful_plan_result(
        {"core_identity": "同城探店账号"},
        {},
        [],
    ) is True


def test_has_meaningful_plan_result_accepts_calendar_only_result() -> None:
    assert planning_endpoint._has_meaningful_plan_result(
        {},
        {},
        [{"day": 1, "title_direction": "先拍一条验证题"}],
    ) is True
