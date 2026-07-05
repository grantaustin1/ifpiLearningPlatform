from pathlib import Path


def test_optional_emergent_dependency_not_pinned_in_ci_requirements():
    requirements = (Path(__file__).resolve().parents[1] / "requirements.txt").read_text(
        encoding="utf-8"
    )

    assert "emergentintegrations" not in requirements
