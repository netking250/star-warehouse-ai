"""Low-maintenance static guard for the centralized Celery publication seam."""

from pathlib import Path


def test_application_celery_publication_uses_task_runtime_dispatch() -> None:
    """Request code must not add direct Celery publication outside the seam."""
    app_root = Path(__file__).resolve().parents[2] / "app"
    violations: list[str] = []
    for path in app_root.rglob("*.py"):
        relative = path.relative_to(app_root).as_posix()
        if relative == "task_runtime/dispatch.py":
            continue
        source = path.read_text(encoding="utf-8")
        if ".delay(" in source or ".apply_async(" in source:
            violations.append(relative)

    assert violations == [], f"Direct Celery publication found in: {violations}"
