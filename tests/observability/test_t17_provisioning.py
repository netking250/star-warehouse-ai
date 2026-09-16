"""Focused validation for T17 dashboards and local observability provisioning."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import cast

import yaml

PROJECT_ROOT = Path(__file__).parents[2]
DASHBOARDS_DIR = PROJECT_ROOT / "grafana" / "dashboards" / "t17"
DATASOURCES_DIR = PROJECT_ROOT / "grafana" / "provisioning" / "datasources"
ALERT_RULES_FILE = PROJECT_ROOT / "grafana" / "provisioning" / "alerting" / "t17-operational.yml"
ALERTMANAGER_FILE = PROJECT_ROOT / "alertmanager" / "alertmanager.yml"
OTEL_FILE = PROJECT_ROOT / "otel" / "otel-collector-config.yml"

T17_METRICS = {
    "http_requests_total",
    "http_errors_total",
    "http_request_duration_seconds",
    "http_requests_in_flight",
    "celery_task_events_total",
    "celery_tasks_in_flight",
    "celery_task_duration_seconds",
    "outbox_events_pending",
    "outbox_event_oldest_age_seconds",
    "outbox_delivery_attempts_total",
    "outbox_publish_failure_total",
    "model_logical_requests_total",
    "model_logical_request_duration_seconds",
    "model_provider_attempts_total",
    "model_fallbacks_total",
    "model_circuit_state",
    "conversation_terminals_total",
    "conversation_run_duration_seconds",
    "app_dependency_health",
    "db_query_duration_seconds",
    "db_connections_in_use",
    "db_connection_errors_total",
}
type YamlScalar = str | int | float | bool | None
type YamlValue = YamlScalar | list[YamlValue] | dict[str, YamlValue]
type YamlMapping = dict[str, YamlValue]
FORBIDDEN_TELEMETRY_IDENTIFIERS = re.compile(
    r"(?:request_id|correlation_id|conversation_id|run_id|user_id|email|prompt|messages)",
    re.IGNORECASE,
)


def _load_yaml(path: Path) -> YamlMapping:
    with path.open(encoding="utf-8") as handle:
        value = cast(YamlValue, yaml.safe_load(handle))
    assert isinstance(value, dict), f"{path} must contain a mapping"
    return value


def _walk(value: object) -> Iterator[dict[str, object]]:
    if isinstance(value, dict):
        mapping = cast(dict[str, object], value)
        yield mapping
        for child in mapping.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _dashboard_datasource_uids(dashboard: dict[str, object]) -> set[str]:
    uids: set[str] = set()
    for item in _walk(dashboard):
        datasource = item.get("datasource")
        if isinstance(datasource, dict):
            datasource_mapping = cast(dict[str, object], datasource)
            uid = datasource_mapping.get("uid")
            if isinstance(uid, str):
                uids.add(uid)
    return uids


def test_t17_dashboards_are_valid_and_reference_provisioned_datasources() -> None:
    """The three operational dashboards must be loadable without manual setup."""
    dashboard_paths = sorted(DASHBOARDS_DIR.glob("*.json"))
    assert len(dashboard_paths) == 3
    dashboards = [json.loads(path.read_text(encoding="utf-8")) for path in dashboard_paths]
    assert {dashboard["title"] for dashboard in dashboards} == {
        "Platform / API Health",
        "Async / Outbox / Worker",
        "AI / Conversation Runtime",
    }
    assert len({dashboard["uid"] for dashboard in dashboards}) == len(dashboards)
    assert all(dashboard.get("panels") for dashboard in dashboards)

    valid_uids: set[str] = set()
    for path in DATASOURCES_DIR.glob("*.yml"):
        datasources = _load_yaml(path).get("datasources", [])
        assert isinstance(datasources, list)
        for datasource in datasources:
            if isinstance(datasource, dict) and isinstance(datasource.get("uid"), str):
                valid_uids.add(datasource["uid"])
    assert {"mimir", "loki", "tempo", "prometheus", "alertmanager"} <= valid_uids

    for dashboard in dashboards:
        assert _dashboard_datasource_uids(dashboard) <= valid_uids
        expressions = [
            target["expr"]
            for panel in dashboard["panels"]
            for target in panel.get("targets", [])
            if isinstance(target, dict) and isinstance(target.get("expr"), str)
        ]
        assert expressions
        assert all(
            any(metric in expression for metric in T17_METRICS) for expression in expressions
        )
        assert not any(
            FORBIDDEN_TELEMETRY_IDENTIFIERS.search(expression) for expression in expressions
        )


def test_t17_alert_rules_are_actionable_and_use_real_metrics() -> None:
    """T17 alert rules have operator context and only query bounded signal families."""
    data = _load_yaml(ALERT_RULES_FILE)
    groups = data.get("groups")
    assert isinstance(groups, list) and len(groups) == 1
    group = groups[0]
    assert isinstance(group, dict)
    rules = group.get("rules")
    assert isinstance(rules, list) and len(rules) == 11

    for rule in rules:
        assert isinstance(rule, dict)
        annotations = rule.get("annotations")
        labels = rule.get("labels")
        assert isinstance(annotations, dict)
        assert {"summary", "impact", "subsystem", "runbook_url"} <= annotations.keys()
        assert isinstance(labels, dict)
        assert {"severity", "team", "service"} <= labels.keys()
        data_items = rule.get("data", [])
        assert isinstance(data_items, list)
        expressions: list[str] = []
        for datum in data_items:
            if isinstance(datum, dict):
                model = datum.get("model", {})
                if isinstance(model, dict):
                    expression = model.get("expr", "")
                    if isinstance(expression, str):
                        expressions.append(expression)
        assert expressions and all(isinstance(expression, str) for expression in expressions)
        assert all(
            any(metric in expression for metric in T17_METRICS) for expression in expressions
        )
        assert not any(
            FORBIDDEN_TELEMETRY_IDENTIFIERS.search(expression) for expression in expressions
        )


def test_local_signal_routing_is_explicit_and_secret_free() -> None:
    """Local alerting and tracing configs keep signal ownership and credentials bounded."""
    alertmanager = _load_yaml(ALERTMANAGER_FILE)
    receivers = alertmanager.get("receivers", [])
    assert isinstance(receivers, list)
    assert any(
        receiver.get("name") == "local-noop" and _has_loopback_webhook(receiver)
        for receiver in receivers
        if isinstance(receiver, dict)
    )
    alertmanager_text = ALERTMANAGER_FILE.read_text(encoding="utf-8").lower()
    assert not any(host in alertmanager_text for host in ("slack.com", "pagerduty.com", "smtp"))

    otel = _load_yaml(OTEL_FILE)
    processors = otel.get("processors", {})
    assert isinstance(processors, dict)
    assert {"memory_limiter", "resource", "batch"} <= processors.keys()
    service = otel.get("service", {})
    assert isinstance(service, dict)
    pipelines = service.get("pipelines", {})
    assert isinstance(pipelines, dict) and "traces" in pipelines
    assert "logs" not in pipelines


def _has_loopback_webhook(receiver: dict[str, YamlValue]) -> bool:
    """Return whether a receiver has a local loopback webhook URL."""
    webhooks = receiver.get("webhook_configs", [])
    if not isinstance(webhooks, list) or not webhooks or not isinstance(webhooks[0], dict):
        return False
    url = webhooks[0].get("url", "")
    return isinstance(url, str) and url.startswith("http://127.0.0.1:")
