"""Explicit deny-by-default inventory for every production HTTP and WebSocket route."""

from dataclasses import dataclass
from enum import StrEnum

from fastapi import FastAPI
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute, APIWebSocketRoute
from starlette.routing import BaseRoute, Mount, Route

from app.authorization.policy import AuthorizationPolicy, Scope


class RouteClassification(StrEnum):
    """Security classification for a registered transport endpoint."""

    PUBLIC = "PUBLIC"
    AUTHENTICATED = "AUTHENTICATED"
    TENANT_SCOPE_REQUIRED = "TENANT_SCOPE_REQUIRED"
    SYSTEM_INTERNAL = "SYSTEM_INTERNAL"


@dataclass(frozen=True, slots=True)
class RoutePolicy:
    """Explicit route classification and optional tenant capability policy."""

    classification: RouteClassification
    authorization: AuthorizationPolicy | None = None


@dataclass(frozen=True, slots=True)
class RouteInventoryEntry:
    """One registered route and its explicit policy."""

    kind: str
    method: str
    path: str
    policy: RoutePolicy


def _tenant_scope(scope: Scope) -> RoutePolicy:
    return RoutePolicy(
        classification=RouteClassification.TENANT_SCOPE_REQUIRED,
        authorization=AuthorizationPolicy(scopes=frozenset({scope})),
    )


PUBLIC = RoutePolicy(RouteClassification.PUBLIC)
AUTHENTICATED = RoutePolicy(RouteClassification.AUTHENTICATED)
SYSTEM_INTERNAL = RoutePolicy(RouteClassification.SYSTEM_INTERNAL)


HTTP_ROUTE_POLICIES: dict[tuple[str, str], RoutePolicy] = {
    ("POST", "/api/v1/login"): PUBLIC,
    ("POST", "/api/v1/browser/login"): PUBLIC,
    ("GET", "/api/v1/oidc/login"): PUBLIC,
    ("GET", "/api/v1/oidc/callback"): PUBLIC,
    ("POST", "/api/v1/register"): PUBLIC,
    ("POST", "/api/v1/metrics/web-vitals"): PUBLIC,
    ("GET", "/api/v1/me"): AUTHENTICATED,
    ("GET", "/api/v1/browser/csrf"): AUTHENTICATED,
    ("POST", "/api/v1/logout"): AUTHENTICATED,
    ("POST", "/api/v1/chat"): _tenant_scope(Scope.CHAT_USE),
    ("GET", "/api/v1/conversations/{conversation_id}/runs/{run_id}"): _tenant_scope(Scope.CHAT_USE),
    ("GET", "/api/v1/conversations/{conversation_id}/runs/{run_id}/events"): _tenant_scope(
        Scope.CHAT_USE
    ),
    ("POST", "/api/v1/conversations/{conversation_id}/runs/{run_id}/cancel"): _tenant_scope(
        Scope.CHAT_USE
    ),
    ("POST", "/api/v1/feedback"): _tenant_scope(Scope.FEEDBACK_WRITE),
    ("GET", "/api/v1/status/{thread_id}"): _tenant_scope(Scope.CHAT_USE),
    ("GET", "/api/v1/admin/agents/config"): _tenant_scope(Scope.OPERATIONS_READ),
    ("POST", "/api/v1/admin/agents/config/{agent_name}"): _tenant_scope(Scope.OPERATIONS_MANAGE),
    ("POST", "/api/v1/admin/agents/config/{agent_name}/rollback"): _tenant_scope(
        Scope.OPERATIONS_MANAGE
    ),
    ("GET", "/api/v1/admin/agents/config/{agent_name}/audit-log"): _tenant_scope(Scope.AUDIT_READ),
    ("GET", "/api/v1/admin/agents/config/{agent_name}/versions"): _tenant_scope(
        Scope.OPERATIONS_READ
    ),
    ("POST", "/api/v1/admin/agents/config/{agent_name}/versions/{version_id}/rollback"): (
        _tenant_scope(Scope.OPERATIONS_MANAGE)
    ),
    ("GET", "/api/v1/admin/agents/config/{agent_name}/versions/{version_id}/metrics"): (
        _tenant_scope(Scope.OPERATIONS_READ)
    ),
    ("GET", "/api/v1/admin/agents/config/{agent_name}/reports"): _tenant_scope(
        Scope.OPERATIONS_READ
    ),
    ("POST", "/api/v1/admin/agents/config/{agent_name}/reports/generate"): _tenant_scope(
        Scope.OPERATIONS_MANAGE
    ),
    ("POST", "/api/v1/admin/agents/config/{agent_name}/evaluate-few-shot"): _tenant_scope(
        Scope.EVALUATION_MANAGE
    ),
    ("POST", "/api/v1/admin/agents/routing-rules"): _tenant_scope(Scope.OPERATIONS_MANAGE),
    ("PUT", "/api/v1/admin/agents/routing-rules/{rule_id}"): _tenant_scope(Scope.OPERATIONS_MANAGE),
    ("DELETE", "/api/v1/admin/agents/routing-rules/{rule_id}"): _tenant_scope(
        Scope.OPERATIONS_MANAGE
    ),
    ("POST", "/api/v1/admin/agents/multi-intent-decisions/{decision_id}/label"): (
        _tenant_scope(Scope.EVALUATION_MANAGE)
    ),
    ("GET", "/api/v1/admin/alerts/rules"): _tenant_scope(Scope.OPERATIONS_READ),
    ("GET", "/api/v1/admin/authorization/memberships"): _tenant_scope(Scope.IDENTITY_READ),
    ("GET", "/api/v1/admin/authorization/memberships/{user_id}"): _tenant_scope(
        Scope.IDENTITY_READ
    ),
    ("PATCH", "/api/v1/admin/authorization/memberships/{user_id}/role"): _tenant_scope(
        Scope.IDENTITY_MANAGE
    ),
    ("PATCH", "/api/v1/admin/authorization/memberships/{user_id}/status"): _tenant_scope(
        Scope.IDENTITY_MANAGE
    ),
    ("POST", "/api/v1/admin/alerts/rules"): _tenant_scope(Scope.OPERATIONS_MANAGE),
    ("GET", "/api/v1/admin/alerts/rules/{rule_id}"): _tenant_scope(Scope.OPERATIONS_READ),
    ("PUT", "/api/v1/admin/alerts/rules/{rule_id}"): _tenant_scope(Scope.OPERATIONS_MANAGE),
    ("DELETE", "/api/v1/admin/alerts/rules/{rule_id}"): _tenant_scope(Scope.OPERATIONS_MANAGE),
    ("GET", "/api/v1/admin/alerts/events"): _tenant_scope(Scope.OPERATIONS_READ),
    ("GET", "/api/v1/admin/alerts/events/active"): _tenant_scope(Scope.OPERATIONS_READ),
    ("POST", "/api/v1/admin/alerts/events/{event_id}/acknowledge"): _tenant_scope(
        Scope.OPERATIONS_MANAGE
    ),
    ("POST", "/api/v1/admin/alerts/events/{event_id}/resolve"): _tenant_scope(
        Scope.OPERATIONS_MANAGE
    ),
    ("GET", "/api/v1/admin/alerts/events/{event_id}/notifications"): _tenant_scope(
        Scope.OPERATIONS_READ
    ),
    ("POST", "/api/v1/admin/alerts/rules/ensure-defaults"): _tenant_scope(Scope.OPERATIONS_MANAGE),
    ("POST", "/api/v1/admin/alerts/trigger"): _tenant_scope(Scope.OPERATIONS_MANAGE),
    ("GET", "/api/v1/admin/complaints"): _tenant_scope(Scope.REVIEWS_READ),
    ("GET", "/api/v1/admin/complaints/{ticket_id}"): _tenant_scope(Scope.REVIEWS_READ),
    ("PATCH", "/api/v1/admin/complaints/{ticket_id}/assign"): _tenant_scope(Scope.REVIEWS_APPROVE),
    ("PATCH", "/api/v1/admin/complaints/{ticket_id}/status"): _tenant_scope(Scope.REVIEWS_APPROVE),
    ("PATCH", "/api/v1/admin/complaints/{ticket_id}/resolve"): _tenant_scope(Scope.REVIEWS_APPROVE),
    ("POST", "/api/v1/admin/experiments"): _tenant_scope(Scope.EVALUATION_MANAGE),
    ("GET", "/api/v1/admin/experiments"): _tenant_scope(Scope.EVALUATION_READ),
    ("GET", "/api/v1/admin/experiments/{experiment_id}"): _tenant_scope(Scope.EVALUATION_READ),
    ("POST", "/api/v1/admin/experiments/{experiment_id}/start"): _tenant_scope(
        Scope.EVALUATION_MANAGE
    ),
    ("POST", "/api/v1/admin/experiments/{experiment_id}/pause"): _tenant_scope(
        Scope.EVALUATION_MANAGE
    ),
    ("POST", "/api/v1/admin/experiments/{experiment_id}/archive"): _tenant_scope(
        Scope.EVALUATION_MANAGE
    ),
    ("GET", "/api/v1/admin/experiments/{experiment_id}/results"): _tenant_scope(
        Scope.EVALUATION_READ
    ),
    ("GET", "/api/v1/admin/feedback"): _tenant_scope(Scope.OPERATIONS_READ),
    ("POST", "/api/v1/admin/feedback/export-requests"): _tenant_scope(Scope.EXPORTS_REQUEST),
    ("GET", "/api/v1/admin/feedback/export"): _tenant_scope(Scope.EXPORTS_REQUEST),
    ("GET", "/api/v1/admin/feedback/csat"): _tenant_scope(Scope.OPERATIONS_READ),
    ("GET", "/api/v1/admin/feedback/stats"): _tenant_scope(Scope.OPERATIONS_READ),
    ("POST", "/api/v1/admin/feedback/quality-score/run"): _tenant_scope(Scope.EVALUATION_MANAGE),
    ("GET", "/api/v1/admin/analytics/csat"): _tenant_scope(Scope.OPERATIONS_READ),
    ("GET", "/api/v1/admin/analytics/complaint-root-causes"): _tenant_scope(Scope.OPERATIONS_READ),
    ("GET", "/api/v1/admin/analytics/agent-comparison"): _tenant_scope(Scope.OPERATIONS_READ),
    ("GET", "/api/v1/admin/analytics/traces"): _tenant_scope(Scope.OPERATIONS_READ),
    ("GET", "/api/v1/admin/analytics/dashboard"): _tenant_scope(Scope.OPERATIONS_READ),
    ("GET", "/api/v1/admin/metrics/dashboard/summary"): _tenant_scope(Scope.OPERATIONS_READ),
    ("GET", "/api/v1/admin/metrics/dashboard/intent-accuracy"): _tenant_scope(
        Scope.OPERATIONS_READ
    ),
    ("GET", "/api/v1/admin/metrics/dashboard/transfer-reasons"): _tenant_scope(
        Scope.OPERATIONS_READ
    ),
    ("GET", "/api/v1/admin/metrics/dashboard/token-usage"): _tenant_scope(Scope.OPERATIONS_READ),
    ("GET", "/api/v1/admin/metrics/dashboard/latency-trend"): _tenant_scope(Scope.OPERATIONS_READ),
    ("GET", "/api/v1/admin/metrics/dashboard/rag-precision"): _tenant_scope(Scope.OPERATIONS_READ),
    ("GET", "/api/v1/admin/metrics/dashboard/hallucination-rate"): _tenant_scope(
        Scope.OPERATIONS_READ
    ),
    ("GET", "/api/v1/admin/metrics/dashboard/alerts"): _tenant_scope(Scope.OPERATIONS_READ),
    ("GET", "/api/v1/admin/evaluation/shadow/results"): _tenant_scope(Scope.EVALUATION_READ),
    ("GET", "/api/v1/admin/evaluation/shadow/alerts"): _tenant_scope(Scope.EVALUATION_READ),
    ("GET", "/api/v1/admin/evaluation/adversarial/runs"): _tenant_scope(Scope.EVALUATION_READ),
    ("POST", "/api/v1/admin/evaluation/adversarial/trigger"): _tenant_scope(
        Scope.EVALUATION_MANAGE
    ),
    ("GET", "/api/v1/admin/token-usage/"): _tenant_scope(Scope.OPERATIONS_READ),
    ("GET", "/api/v1/admin/token-usage/by-user/"): _tenant_scope(Scope.OPERATIONS_READ),
    ("GET", "/api/v1/admin/token-usage/by-agent/"): _tenant_scope(Scope.OPERATIONS_READ),
    ("GET", "/api/v1/admin/token-usage/high-cost/"): _tenant_scope(Scope.OPERATIONS_READ),
    ("GET", "/api/v1/admin/token-usage/anomalies/"): _tenant_scope(Scope.OPERATIONS_READ),
    ("GET", "/api/v1/admin/token-usage/suggestions/"): _tenant_scope(Scope.OPERATIONS_READ),
    ("GET", "/api/v1/admin/review-queue/"): _tenant_scope(Scope.REVIEWS_READ),
    ("GET", "/api/v1/admin/review-queue/{ticket_id}"): _tenant_scope(Scope.REVIEWS_READ),
    ("POST", "/api/v1/admin/review-queue/{ticket_id}/assign"): _tenant_scope(Scope.REVIEWS_APPROVE),
    ("POST", "/api/v1/admin/review-queue/{ticket_id}/resolve"): _tenant_scope(
        Scope.REVIEWS_APPROVE
    ),
    ("POST", "/api/v1/admin/review-queue/{ticket_id}/escalate"): _tenant_scope(
        Scope.REVIEWS_APPROVE
    ),
    ("GET", "/api/v1/admin/review-queue/metrics/sla"): _tenant_scope(Scope.REVIEWS_READ),
    ("GET", "/api/v1/admin/review-queue/metrics/reviewer/{reviewer_id}"): _tenant_scope(
        Scope.REVIEWS_READ
    ),
    ("GET", "/api/v1/admin/tasks"): _tenant_scope(Scope.REVIEWS_READ),
    ("GET", "/api/v1/admin/confidence-tasks"): _tenant_scope(Scope.REVIEWS_READ),
    ("GET", "/api/v1/admin/tasks-all"): _tenant_scope(Scope.REVIEWS_READ),
    ("POST", "/api/v1/admin/resume/{audit_log_id}"): _tenant_scope(Scope.REFUNDS_APPROVE),
    ("GET", "/api/v1/admin/evaluation/dataset"): _tenant_scope(Scope.EVALUATION_READ),
    ("POST", "/api/v1/admin/evaluation/run"): _tenant_scope(Scope.EVALUATION_MANAGE),
    ("POST", "/api/v1/admin/continuous-improvement/audit"): _tenant_scope(Scope.EVALUATION_MANAGE),
    ("POST", "/api/v1/admin/shadow-test/run"): _tenant_scope(Scope.EVALUATION_MANAGE),
    ("GET", "/api/v1/admin/metrics/sessions"): _tenant_scope(Scope.OPERATIONS_READ),
    ("GET", "/api/v1/admin/metrics/transfers"): _tenant_scope(Scope.OPERATIONS_READ),
    ("GET", "/api/v1/admin/metrics/confidence"): _tenant_scope(Scope.OPERATIONS_READ),
    ("GET", "/api/v1/admin/metrics/latency"): _tenant_scope(Scope.OPERATIONS_READ),
    ("GET", "/api/v1/admin/conversations"): _tenant_scope(Scope.CONVERSATIONS_READ),
    ("GET", "/api/v1/admin/conversations/{thread_id}"): _tenant_scope(Scope.CONVERSATIONS_READ),
    ("GET", "/api/v1/admin/knowledge"): _tenant_scope(Scope.KNOWLEDGE_READ),
    ("POST", "/api/v1/admin/knowledge"): _tenant_scope(Scope.KNOWLEDGE_WRITE),
    ("DELETE", "/api/v1/admin/knowledge/{doc_id}"): _tenant_scope(Scope.KNOWLEDGE_WRITE),
    ("POST", "/api/v1/admin/knowledge/{doc_id}/sync"): _tenant_scope(Scope.KNOWLEDGE_WRITE),
    ("GET", "/api/v1/admin/knowledge/sync/{task_id}"): _tenant_scope(Scope.KNOWLEDGE_READ),
    ("GET", "/api/v1/admin/compliance/approvals"): _tenant_scope(Scope.COMPLIANCE_READ),
    ("POST", "/api/v1/admin/compliance/approvals/{approval_id}/decision"): _tenant_scope(
        Scope.EXPORTS_APPROVE
    ),
    ("POST", "/api/v1/admin/compliance/retention/{dataset}/dry-run"): _tenant_scope(
        Scope.COMPLIANCE_READ
    ),
    ("POST", "/api/v1/admin/compliance/retention/{dataset}/execute"): _tenant_scope(
        Scope.COMPLIANCE_MANAGE
    ),
    ("GET", "/app/{full_path:path}"): PUBLIC,
    ("GET", "/app"): PUBLIC,
    ("GET", "/admin/{full_path:path}"): PUBLIC,
    ("GET", "/admin"): PUBLIC,
    ("GET", "/favicon.svg"): PUBLIC,
    ("GET", "/icons.svg"): PUBLIC,
    ("GET", "/index.html"): PUBLIC,
    ("GET", "/admin.html"): PUBLIC,
    ("GET", "/"): PUBLIC,
    ("GET", "/health"): PUBLIC,
}


WEBSOCKET_ROUTE_POLICIES: dict[str, RoutePolicy] = {
    "/api/v1/ws/{thread_id}": _tenant_scope(Scope.CHAT_USE),
    "/api/v1/ws/admin/{admin_id}": _tenant_scope(Scope.OPERATIONS_READ),
}


_FRAMEWORK_ROUTE_POLICIES: dict[str, RoutePolicy] = {
    "/openapi.json": SYSTEM_INTERNAL,
    "/docs": SYSTEM_INTERNAL,
    "/docs/oauth2-redirect": SYSTEM_INTERNAL,
    "/redoc": SYSTEM_INTERNAL,
}

_MOUNT_POLICIES: dict[str, RoutePolicy] = {
    "/metrics": SYSTEM_INTERNAL,
    "/customer": PUBLIC,
    "/shared": PUBLIC,
    "/assets": PUBLIC,
}

_AUTHORIZATION_DEPENDENCIES = frozenset(
    {
        "get_active_auth_context",
        "get_authorized_auth_context",
        "get_authorized_user_id",
        "get_admin_user_id",
    }
)


def _has_authorization_dependency(dependant: Dependant) -> bool:
    call = dependant.call
    if (
        getattr(call, "__module__", None) == "app.core.security"
        and getattr(call, "__name__", None) in _AUTHORIZATION_DEPENDENCIES
    ):
        return True
    return any(_has_authorization_dependency(child) for child in dependant.dependencies)


def policy_for_http_route(method: str, path: str) -> RoutePolicy | None:
    """Return the explicit HTTP policy for a method and route template."""
    return HTTP_ROUTE_POLICIES.get((method.upper(), path)) or _FRAMEWORK_ROUTE_POLICIES.get(path)


def policy_for_websocket_route(path: str) -> RoutePolicy | None:
    """Return the explicit WebSocket policy for a route template."""
    return WEBSOCKET_ROUTE_POLICIES.get(path)


def inventory_routes(app: FastAPI) -> tuple[list[RouteInventoryEntry], list[str]]:
    """Classify registered routes and report anything not explicitly inventoried."""
    entries: list[RouteInventoryEntry] = []
    unclassified: list[str] = []
    for route in app.routes:
        if isinstance(route, APIRoute):
            methods = sorted(method for method in route.methods if method != "HEAD")
            for method in methods:
                policy = policy_for_http_route(method, route.path)
                if policy is None:
                    unclassified.append(f"HTTP {method} {route.path}")
                elif policy.classification in {
                    RouteClassification.AUTHENTICATED,
                    RouteClassification.TENANT_SCOPE_REQUIRED,
                } and not _has_authorization_dependency(route.dependant):
                    unclassified.append(
                        f"HTTP {method} {route.path} (missing authorization dependency)"
                    )
                else:
                    entries.append(RouteInventoryEntry("HTTP", method, route.path, policy))
        elif isinstance(route, APIWebSocketRoute):
            policy = policy_for_websocket_route(route.path)
            if policy is None:
                unclassified.append(f"WEBSOCKET {route.path}")
            else:
                entries.append(RouteInventoryEntry("WEBSOCKET", "WS", route.path, policy))
        elif isinstance(route, Mount):
            policy = _MOUNT_POLICIES.get(route.path)
            if policy is None:
                unclassified.append(f"MOUNT {route.path}")
            else:
                entries.append(RouteInventoryEntry("MOUNT", "MOUNT", route.path, policy))
        elif isinstance(route, Route):
            if route.methods is None:
                unclassified.append(f"HTTP <unknown> {route.path}")
                continue
            methods = sorted(method for method in route.methods if method != "HEAD")
            for method in methods:
                policy = _FRAMEWORK_ROUTE_POLICIES.get(route.path)
                if policy is None:
                    unclassified.append(f"HTTP {method} {route.path}")
                else:
                    entries.append(RouteInventoryEntry("HTTP", method, route.path, policy))
        elif isinstance(route, BaseRoute):
            unclassified.append(f"{type(route).__name__} {getattr(route, 'path', '<unknown>')}")
    return entries, unclassified


def assert_routes_classified(app: FastAPI) -> None:
    """Fail startup/tests when any registered route lacks an explicit policy."""
    _, unclassified = inventory_routes(app)
    if unclassified:
        joined = ", ".join(sorted(unclassified))
        raise RuntimeError(f"Unclassified application routes: {joined}")
