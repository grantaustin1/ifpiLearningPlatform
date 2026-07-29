from pathlib import Path


def test_emergentintegrations_not_pinned_in_requirements():
    requirements = (Path(__file__).resolve().parents[1] / "requirements.txt").read_text(
        encoding="utf-8"
    )

    # Prevent reinstall-time failures by disallowing emergentintegrations in requirements.
    for line in requirements.splitlines():
        requirement = line.split("#", 1)[0].strip()
        if requirement.lower().startswith("emergentintegrations"):
            assert False, (
                "emergentintegrations should not be listed in requirements.txt, "
                f"found: {line!r}"
            )
