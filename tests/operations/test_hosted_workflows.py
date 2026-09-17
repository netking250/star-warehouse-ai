"""Regression guards for the hosted T21 pull-request workflows."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REVISION_LABEL = "org.opencontainers.image.revision"


def _workflow(name: str) -> str:
    return (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")


def test_docker_revision_templates_do_not_escape_quotes_inside_single_quotes() -> None:
    """Pass valid Go templates to Docker while preserving the revision assertion."""
    for workflow_name in ("ci.yml", "supply-chain.yml"):
        workflow = _workflow(workflow_name)
        assert f'\\"{REVISION_LABEL}\\"' not in workflow
        assert f'{{{{ index .Config.Labels "{REVISION_LABEL}" }}}}' in workflow


def test_specialized_pytest_workflows_bootstrap_database_capability_roles() -> None:
    """Create migration-owned capability roles before pytest's global DB fixture runs."""
    for workflow_name in ("eval.yml", "performance.yml"):
        workflow = _workflow(workflow_name)
        assert "uv run alembic upgrade head" in workflow
        assert workflow.index("uv run alembic upgrade head") < workflow.index("uv run pytest")
