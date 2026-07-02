import pytest

from scripts.qa_agents import agent_007_invariants, agent_008_e2e_journey, agent_010_infra_sentry


@pytest.mark.parametrize(
    ("module", "filename"),
    [
        (agent_007_invariants, "agent_007.json"),
        (agent_008_e2e_journey, "agent_008.json"),
        (agent_010_infra_sentry, "agent_010.json"),
    ],
)
def test_report_path_uses_env_dir_when_writable(monkeypatch, tmp_path, module, filename):
    report_dir = tmp_path / "reports"
    monkeypatch.setenv("AGENT_REPORT_DIR", str(report_dir))
    path = module._report_path(filename)
    assert path == report_dir / filename
    assert report_dir.is_dir()


@pytest.mark.parametrize(
    ("module", "filename"),
    [
        (agent_007_invariants, "agent_007.json"),
        (agent_008_e2e_journey, "agent_008.json"),
        (agent_010_infra_sentry, "agent_010.json"),
    ],
)
def test_report_path_falls_back_when_env_dir_is_not_writable(monkeypatch, module, filename):
    monkeypatch.setenv("AGENT_REPORT_DIR", "/proc/1")
    path = module._report_path(filename)
    assert path.name == filename
    assert path.parent.name == "test_reports"
