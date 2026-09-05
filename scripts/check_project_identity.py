#!/usr/bin/env python3
"""Validate Star Warehouse AI identity and local documentation links."""

from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.branding import APP_VERSION, PRODUCT_NAME_EN, PRODUCT_NAME_ZH, SERVICE_SLUG

LEGACY_PATTERNS = (
    "E-commerce Smart Agent",
    "E-commerce-Smart-Agent",
    "ecommerce-smart-agent",
    "ecommerce-agent",
    "ecommerce_agent",
)
LEGACY_ALLOWLIST = {
    "app/core/branding.py",
    "docs/how-to-guides/migrate-to-v5.md",
    "grafana/dashboards/agent_performance.json",
    "grafana/dashboards/cost.json",
    "grafana/dashboards/security.json",
    "grafana/dashboards/star_warehouse_ai.json",
    "scripts/check_project_identity.py",
    "tests/core/test_branding.py",
}
IGNORED_PARTS = {".git", ".venv", "node_modules", "output", "dist"}
MARKDOWN_TARGET = re.compile(r"!?(?:\[[^\]]*\])\(([^)]+)\)")
HTML_TARGET = re.compile(r"(?:src|href)=[\"']([^\"']+)[\"']")


def iter_text_files() -> list[Path]:
    """Return repository text files relevant to identity validation."""
    suffixes = {
        ".conf",
        ".html",
        ".json",
        ".md",
        ".py",
        ".sh",
        ".toml",
        ".ts",
        ".tsx",
        ".yml",
        ".yaml",
    }
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in IGNORED_PARTS for part in path.parts):
            continue
        if path.suffix in suffixes or path.name == "Dockerfile":
            files.append(path)
    return files


def check_identity() -> list[str]:
    """Check canonical metadata and reject unapproved legacy identifiers."""
    errors: list[str] = []
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    frontend = json.loads((ROOT / "frontend/package.json").read_text(encoding="utf-8"))

    expected = {
        "pyproject name": (project["name"], SERVICE_SLUG),
        "pyproject version": (project["version"], APP_VERSION),
        "frontend name": (frontend["name"], f"{SERVICE_SLUG}-frontend"),
        "frontend version": (frontend["version"], APP_VERSION),
    }
    for label, (actual, wanted) in expected.items():
        if actual != wanted:
            errors.append(f"{label}: expected {wanted!r}, found {actual!r}")

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for required in (PRODUCT_NAME_ZH, PRODUCT_NAME_EN, APP_VERSION):
        if required not in readme:
            errors.append(f"README.md is missing canonical value {required!r}")

    for path in iter_text_files():
        relative = path.relative_to(ROOT).as_posix()
        if relative in LEGACY_ALLOWLIST:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for legacy in LEGACY_PATTERNS:
            if legacy in text:
                errors.append(f"{relative}: contains retired identifier {legacy!r}")
    return errors


def check_markdown_links() -> list[str]:
    """Check repository-local links and images in Markdown documents."""
    errors: list[str] = []
    for document in ROOT.rglob("*.md"):
        if any(part in IGNORED_PARTS for part in document.parts):
            continue
        text = document.read_text(encoding="utf-8")
        targets = MARKDOWN_TARGET.findall(text) + HTML_TARGET.findall(text)
        for raw_target in targets:
            target = raw_target.strip().strip("<>").split(maxsplit=1)[0]
            if not target or target.startswith(("#", "http://", "https://", "mailto:")):
                continue
            local_target = target.split("#", maxsplit=1)[0]
            if not local_target:
                continue
            resolved = (document.parent / local_target).resolve()
            if not resolved.is_relative_to(ROOT) or not resolved.exists():
                relative = document.relative_to(ROOT).as_posix()
                errors.append(f"{relative}: missing local target {target!r}")
    return errors


def main() -> int:
    """Run all project identity checks."""
    errors = check_identity() + check_markdown_links()
    if errors:
        print("Project identity validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Project identity is consistent: {PRODUCT_NAME_EN} v{APP_VERSION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
