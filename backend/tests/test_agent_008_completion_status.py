from scripts.qa_agents.agent_008_e2e_journey import _is_completion_status_ok


def test_completion_status_ok_for_success_codes():
    assert _is_completion_status_ok(200, False)
    assert _is_completion_status_ok(201, False)


def test_completion_status_ok_for_422_when_already_completed():
    assert _is_completion_status_ok(422, True)


def test_completion_status_not_ok_for_422_without_completed_state():
    assert not _is_completion_status_ok(422, False)
