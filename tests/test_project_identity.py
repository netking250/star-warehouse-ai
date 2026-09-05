"""Tests for repository identity guardrails."""

from scripts.check_project_identity import check_identity, check_markdown_links


def test_project_identity_has_no_unapproved_legacy_names() -> None:
    """Canonical metadata and display copy should stay synchronized."""
    assert check_identity() == []


def test_documentation_local_links_resolve() -> None:
    """Documentation navigation should not contain broken local links."""
    assert check_markdown_links() == []
