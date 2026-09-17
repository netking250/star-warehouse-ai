"""Deterministic offline evaluation for accepted workflow contracts.

This runner measures objective application behavior without a public model provider, network
access, database, Redis, RabbitMQ, or Qdrant. It deliberately does not score linguistic quality.
"""

from __future__ import annotations

import argparse
import ast
import asyncio
import sys
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.authorization.policy import (
    AuthenticatedPrincipal,
    AuthorizationContext,
    AuthorizationPolicy,
    Role,
    Scope,
    authorize,
)
from app.compliance.approval import FEEDBACK_EXPORT
from app.conversation.state_machine import (
    IllegalRunTransitionError,
    RunStatus,
    transition_run_status,
)
from app.core.tenancy import (
    TenantContext,
    TenantContextMissingError,
    TenantNamespace,
    TenantStatus,
    clear_current_tenant,
    get_current_tenant_context,
    reset_current_tenant,
)
from app.evaluation.metrics import rag_precision
from app.intent.models import IntentAction, IntentCategory
from app.model_gateway.contracts import (
    ModelCandidate,
    ModelCapability,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ModelRoute,
    ModelStreamEvent,
)
from app.model_gateway.errors import ModelErrorCategory, ModelGatewayError
from app.model_gateway.failure_policy import (
    DegradationMode,
    InMemoryCircuitStore,
    ModelFailurePolicy,
    ModelFailurePolicyConfig,
)
from app.model_gateway.gateway import ModelGateway


class OfflineScenarioKind(StrEnum):
    """Supported deterministic workflow scenario types."""

    ROUTING = "routing"
    RAG_EVIDENCE = "rag_evidence"
    APPROVAL = "approval"
    CANCELLATION = "cancellation"
    PROVIDER_FALLBACK = "provider_fallback"
    PROVIDER_DEGRADATION = "provider_degradation"
    AUTHORIZATION_DENIAL = "authorization_denial"
    TENANT_ISOLATION = "tenant_isolation"
    INVALID_TRANSITION = "invalid_transition"
    TERMINAL_UNIQUENESS = "terminal_uniqueness"


class OfflineMetric(StrEnum):
    """Objective metric groups emitted by the offline evaluation."""

    WORKFLOW = "workflow_success_rate"
    ROUTING = "routing_correctness"
    TOOL_ROUTING = "tool_routing_correctness"
    APPROVAL = "approval_policy_correctness"
    AUTHORIZATION = "authorization_correctness"
    TENANT_ISOLATION = "tenant_isolation_pass_rate"
    FALLBACK = "fallback_policy_correctness"
    TERMINAL_UNIQUENESS = "terminal_uniqueness"


class OfflineScenario(BaseModel):
    """One synthetic, objective workflow evaluation case."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = Field(ge=1, le=1)
    dataset_version: str = Field(min_length=1)
    scenario_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]+$")
    description: str = Field(min_length=1)
    kind: OfflineScenarioKind
    metrics: tuple[OfflineMetric, ...]
    intent: IntentCategory | None = None
    secondary_intent: IntentAction | None = None
    expected_route: str | None = None
    expected_tools: tuple[str, ...] = ()
    query: str | None = None
    evidence_chunks: tuple[str, ...] = ()
    evidence_sources: tuple[str, ...] = ()
    expected_min_rag_precision: float | None = Field(default=None, ge=0.0, le=1.0)
    current_status: RunStatus | None = None
    target_status: RunStatus | None = None
    expected_status: RunStatus | None = None
    required_scope: Scope | None = None
    granted_scopes: tuple[str, ...] = ()
    expected_authorization_reason: str | None = None
    tenant_a: str | None = None
    tenant_b: str | None = None
    primary_failures: int = Field(default=0, ge=0, le=4)
    expected_provider: str | None = None
    expected_degraded: bool | None = None
    expected_approval_required: bool | None = None
    expected_separation_of_duties: bool | None = None

    @model_validator(mode="after")
    def validate_kind_contract(self) -> Self:
        """Reject incomplete scenario records before executing application code."""
        if not self.metrics or OfflineMetric.WORKFLOW not in self.metrics:
            raise ValueError("Every scenario must contribute to workflow_success_rate")
        if self.kind in {
            OfflineScenarioKind.ROUTING,
            OfflineScenarioKind.RAG_EVIDENCE,
        } and (self.intent is None or self.expected_route is None):
            raise ValueError("Routing scenarios require intent and expected_route")
        if self.kind is OfflineScenarioKind.RAG_EVIDENCE:
            if (
                self.query is None
                or not self.evidence_chunks
                or self.expected_min_rag_precision is None
            ):
                raise ValueError("RAG scenarios require query, evidence, and a minimum precision")
            if len(self.evidence_sources) != len(self.evidence_chunks):
                raise ValueError("Every synthetic evidence chunk requires one source identifier")
        if self.kind in {
            OfflineScenarioKind.CANCELLATION,
            OfflineScenarioKind.INVALID_TRANSITION,
            OfflineScenarioKind.TERMINAL_UNIQUENESS,
        } and (self.current_status is None or self.target_status is None):
            raise ValueError("State scenarios require current_status and target_status")
        if self.kind is OfflineScenarioKind.AUTHORIZATION_DENIAL and (
            self.required_scope is None or self.expected_authorization_reason is None
        ):
            raise ValueError("Authorization scenarios require scope and expected reason")
        if self.kind is OfflineScenarioKind.TENANT_ISOLATION and (
            self.tenant_a is None or self.tenant_b is None or self.tenant_a == self.tenant_b
        ):
            raise ValueError("Tenant isolation requires two distinct tenants")
        if self.kind in {
            OfflineScenarioKind.PROVIDER_FALLBACK,
            OfflineScenarioKind.PROVIDER_DEGRADATION,
        } and (self.primary_failures < 1 or self.expected_provider is None):
            raise ValueError("Provider scenarios require failures and an expected provider")
        if self.kind is OfflineScenarioKind.APPROVAL and (
            self.expected_approval_required is None or self.expected_separation_of_duties is None
        ):
            raise ValueError("Approval scenarios require explicit expected controls")
        return self


@dataclass(frozen=True, slots=True)
class ScenarioResult:
    """Result of one deterministic scenario."""

    scenario_id: str
    description: str
    metrics: tuple[OfflineMetric, ...]
    passed: bool
    checks: tuple[str, ...]
    failures: tuple[str, ...]


class ScenarioSummary(BaseModel):
    """Aggregate pass counts for the complete dataset."""

    total: int
    passed: int
    failed: int
    pass_rate: float


class MetricSummary(BaseModel):
    """Aggregate pass counts for one objective metric group."""

    passed: int
    total: int
    rate: float


class ScenarioReport(BaseModel):
    """JSON-facing result for one scenario."""

    scenario_id: str
    description: str
    passed: bool
    checks: tuple[str, ...]
    failures: tuple[str, ...]


class OfflineEvaluationReport(BaseModel):
    """Typed machine-readable result for one deterministic evaluation run."""

    schema_version: int
    dataset_version: str
    evaluation_type: str
    real_provider: bool
    scenarios: ScenarioSummary
    metrics: dict[str, MetricSummary]
    results: tuple[ScenarioReport, ...]
    boundary: str


class _ScriptedAdapter:
    """Provider-neutral deterministic adapter used only by offline evaluation."""

    capabilities = frozenset({ModelCapability.CHAT})

    def __init__(self, name: str, responses: Sequence[ModelResponse | ModelGatewayError]) -> None:
        self.name = name
        self._responses = tuple(responses)
        self.invoke_count = 0

    async def invoke(self, candidate: ModelCandidate, request: ModelRequest) -> ModelResponse:
        del candidate, request
        index = min(self.invoke_count, len(self._responses) - 1)
        self.invoke_count += 1
        result = self._responses[index]
        if isinstance(result, ModelGatewayError):
            raise result
        return result

    async def stream(
        self, candidate: ModelCandidate, request: ModelRequest
    ) -> AsyncIterator[ModelStreamEvent]:
        del candidate, request
        if False:
            yield ModelStreamEvent(
                event_type="completed",
                provider=self.name,
                model=f"{self.name}-offline",
            )


def load_offline_dataset(path: str | Path) -> tuple[OfflineScenario, ...]:
    """Load and validate a versioned JSONL offline dataset."""
    dataset_path = Path(path)
    if not dataset_path.is_file():
        raise FileNotFoundError(f"Offline evaluation dataset not found: {dataset_path}")
    scenarios: list[OfflineScenario] = []
    for line_number, line in enumerate(dataset_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            scenarios.append(OfflineScenario.model_validate_json(line))
        except ValueError as error:
            raise ValueError(f"Invalid offline scenario on line {line_number}: {error}") from error
    if not scenarios:
        raise ValueError("Offline evaluation dataset must contain at least one scenario")
    versions = {scenario.dataset_version for scenario in scenarios}
    if len(versions) != 1:
        raise ValueError("Offline evaluation dataset must use one dataset_version")
    identifiers = [scenario.scenario_id for scenario in scenarios]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("Offline evaluation scenario_id values must be unique")
    return tuple(scenarios)


def _record_check(
    checks: list[str], failures: list[str], name: str, condition: bool, detail: str
) -> None:
    if condition:
        checks.append(name)
    else:
        failures.append(f"{name}: {detail}")


def _static_route(intent: IntentCategory, secondary: IntentAction | None) -> str:
    if intent is IntentCategory.AFTER_SALES and secondary is IntentAction.CONSULT:
        return "policy_agent"
    return _load_route_map().get(intent, "supervisor")


def _assignment_value(path: Path, variable_name: str) -> ast.expr:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == variable_name
            and node.value is not None
        ):
            return node.value
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == variable_name for target in node.targets
        ):
            return node.value
    raise ValueError(f"Could not find {variable_name} in {path}")


def _load_route_map() -> dict[IntentCategory, str]:
    root = Path(__file__).resolve().parents[2]
    value = _assignment_value(root / "app" / "agents" / "router.py", "_INTENT_MAPPINGS")
    if not isinstance(value, ast.Dict):
        raise ValueError("Router intent map must remain a dictionary literal")
    mapping: dict[IntentCategory, str] = {}
    for key, item in zip(value.keys, value.values, strict=True):
        if not isinstance(key, ast.Attribute) or not isinstance(item, ast.Constant):
            raise ValueError("Router intent map contains a non-literal entry")
        mapping[IntentCategory[key.attr]] = str(item.value)
    return mapping


def _load_tool_scopes() -> dict[str, tuple[str, ...]]:
    root = Path(__file__).resolve().parents[2]
    value = _assignment_value(root / "app" / "graph" / "workflow.py", "_AGENT_TOOL_SCOPES")
    raw = ast.literal_eval(value)
    if not isinstance(raw, dict):
        raise ValueError("Agent tool scopes must remain a dictionary literal")
    scopes: dict[str, tuple[str, ...]] = {}
    for agent, tools in raw.items():
        if not isinstance(agent, str) or not isinstance(tools, list):
            raise ValueError("Agent tool scopes contain a non-literal entry")
        if not all(isinstance(tool, str) for tool in tools):
            raise ValueError("Agent tool names must be strings")
        scopes[agent] = tuple(tools)
    return scopes


def _run_routing(scenario: OfflineScenario) -> ScenarioResult:
    assert scenario.intent is not None
    assert scenario.expected_route is not None
    route = _static_route(scenario.intent, scenario.secondary_intent)
    tools = _load_tool_scopes().get(route, ())
    checks: list[str] = []
    failures: list[str] = []
    _record_check(
        checks,
        failures,
        "expected_route",
        route == scenario.expected_route,
        f"expected {scenario.expected_route}, observed {route}",
    )
    missing_tools = sorted(set(scenario.expected_tools) - set(tools))
    _record_check(
        checks,
        failures,
        "expected_tool_scope",
        not missing_tools,
        f"missing tools {missing_tools}",
    )
    return ScenarioResult(
        scenario.scenario_id,
        scenario.description,
        scenario.metrics,
        not failures,
        tuple(checks),
        tuple(failures),
    )


async def _run_rag_evidence(scenario: OfflineScenario) -> ScenarioResult:
    result = _run_routing(scenario)
    assert scenario.query is not None
    assert scenario.expected_min_rag_precision is not None
    precision = await rag_precision(scenario.query, list(scenario.evidence_chunks), llm_judge=False)
    checks = list(result.checks)
    failures = list(result.failures)
    _record_check(
        checks,
        failures,
        "rag_precision_threshold",
        precision >= scenario.expected_min_rag_precision,
        f"minimum {scenario.expected_min_rag_precision}, observed {precision}",
    )
    _record_check(
        checks,
        failures,
        "evidence_sources_present",
        all(source.strip() for source in scenario.evidence_sources),
        "one or more source identifiers are blank",
    )
    return ScenarioResult(
        scenario.scenario_id,
        scenario.description,
        scenario.metrics,
        not failures,
        tuple(checks),
        tuple(failures),
    )


def _run_approval(scenario: OfflineScenario) -> ScenarioResult:
    checks: list[str] = []
    failures: list[str] = []
    _record_check(
        checks,
        failures,
        "approval_required",
        FEEDBACK_EXPORT.approval_required is scenario.expected_approval_required,
        "feedback export approval policy changed",
    )
    _record_check(
        checks,
        failures,
        "separation_of_duties",
        FEEDBACK_EXPORT.separation_of_duties is scenario.expected_separation_of_duties,
        "feedback export separation-of-duties policy changed",
    )
    _record_check(
        checks,
        failures,
        "approval_scope",
        FEEDBACK_EXPORT.approval_scope is Scope.EXPORTS_APPROVE,
        "approval scope is not exports.approve",
    )
    return ScenarioResult(
        scenario.scenario_id,
        scenario.description,
        scenario.metrics,
        not failures,
        tuple(checks),
        tuple(failures),
    )


def _run_cancellation(scenario: OfflineScenario) -> ScenarioResult:
    assert scenario.current_status is not None
    assert scenario.target_status is not None
    checks: list[str] = []
    failures: list[str] = []
    observed = transition_run_status(scenario.current_status, scenario.target_status)
    expected = scenario.expected_status or scenario.target_status
    _record_check(
        checks,
        failures,
        "cancel_transition",
        observed is expected,
        f"expected {expected}, observed {observed}",
    )
    repeated = transition_run_status(observed, observed)
    _record_check(
        checks,
        failures,
        "cancel_idempotency",
        repeated is observed,
        "repeated terminal cancellation was not idempotent",
    )
    try:
        transition_run_status(observed, RunStatus.COMPLETED)
    except IllegalRunTransitionError:
        checks.append("cancel_terminal_uniqueness")
    else:
        failures.append("cancel_terminal_uniqueness: cancelled run accepted completion")
    return ScenarioResult(
        scenario.scenario_id,
        scenario.description,
        scenario.metrics,
        not failures,
        tuple(checks),
        tuple(failures),
    )


def _provider_gateway(
    adapters: Sequence[_ScriptedAdapter],
) -> tuple[ModelGateway, tuple[ModelCandidate, ...]]:
    candidates = tuple(
        ModelCandidate(
            provider=adapter.name,
            model=f"{adapter.name}-offline",
            capabilities=adapter.capabilities,
            timeout_seconds=1.0,
        )
        for adapter in adapters
    )
    gateway = ModelGateway(
        adapters=adapters,
        routes=(ModelRoute(name="offline-eval", candidates=candidates),),
    )
    return gateway, candidates


def _provider_request() -> ModelRequest:
    return ModelRequest(
        route="offline-eval",
        messages=(ModelMessage(role="user", content="synthetic provider policy check"),),
    )


def _provider_policy(
    *, attempts_per_candidate: int, total_attempts: int, degradation: bool
) -> ModelFailurePolicy:
    config = ModelFailurePolicyConfig(
        max_attempts_per_candidate=attempts_per_candidate,
        max_total_attempts=total_attempts,
        total_deadline_seconds=2.0,
        base_backoff_seconds=0.0,
        max_backoff_seconds=0.0,
        jitter_ratio=0.0,
        circuit_failure_threshold=20,
        degradation_mode=(
            DegradationMode.SAFE_STATIC_RESPONSE if degradation else DegradationMode.FAIL
        ),
        safe_static_response="Synthetic safe degradation response.",
    )
    return ModelFailurePolicy(config=config, circuit_store=InMemoryCircuitStore(config))


async def _run_provider_fallback(scenario: OfflineScenario) -> ScenarioResult:
    failures = [
        ModelGatewayError(ModelErrorCategory.TIMEOUT, "synthetic timeout")
        for _ in range(scenario.primary_failures)
    ]
    primary = _ScriptedAdapter("openai", failures)
    alternate = _ScriptedAdapter(
        "dashscope",
        (
            ModelResponse(
                content="synthetic fallback answer",
                finish_reason="stop",
                provider="dashscope",
                model="dashscope-offline",
            ),
        ),
    )
    gateway, candidates = _provider_gateway((primary, alternate))
    policy = _provider_policy(
        attempts_per_candidate=scenario.primary_failures,
        total_attempts=scenario.primary_failures + 1,
        degradation=False,
    )
    response = await policy.invoke(gateway, _provider_request(), candidates=candidates)
    checks: list[str] = []
    result_failures: list[str] = []
    _record_check(
        checks,
        result_failures,
        "fallback_provider",
        response.provider == scenario.expected_provider,
        f"expected {scenario.expected_provider}, observed {response.provider}",
    )
    _record_check(
        checks,
        result_failures,
        "bounded_primary_attempts",
        primary.invoke_count == scenario.primary_failures,
        f"expected {scenario.primary_failures}, observed {primary.invoke_count}",
    )
    _record_check(
        checks,
        result_failures,
        "single_fallback_attempt",
        alternate.invoke_count == 1,
        f"expected 1, observed {alternate.invoke_count}",
    )
    return ScenarioResult(
        scenario.scenario_id,
        scenario.description,
        scenario.metrics,
        not result_failures,
        tuple(checks),
        tuple(result_failures),
    )


async def _run_provider_degradation(scenario: OfflineScenario) -> ScenarioResult:
    adapter = _ScriptedAdapter(
        "openai",
        tuple(
            ModelGatewayError(ModelErrorCategory.PROVIDER_UNAVAILABLE, "synthetic unavailable")
            for _ in range(scenario.primary_failures)
        ),
    )
    gateway, candidates = _provider_gateway((adapter,))
    policy = _provider_policy(
        attempts_per_candidate=scenario.primary_failures,
        total_attempts=scenario.primary_failures,
        degradation=True,
    )
    response = await policy.invoke(gateway, _provider_request(), candidates=candidates)
    checks: list[str] = []
    failures: list[str] = []
    _record_check(
        checks,
        failures,
        "degraded_provider",
        response.provider == scenario.expected_provider,
        f"expected {scenario.expected_provider}, observed {response.provider}",
    )
    _record_check(
        checks,
        failures,
        "explicit_degradation_marker",
        response.degraded is scenario.expected_degraded,
        f"expected degraded={scenario.expected_degraded}, observed {response.degraded}",
    )
    _record_check(
        checks,
        failures,
        "bounded_failure_attempts",
        adapter.invoke_count == scenario.primary_failures,
        f"expected {scenario.primary_failures}, observed {adapter.invoke_count}",
    )
    return ScenarioResult(
        scenario.scenario_id,
        scenario.description,
        scenario.metrics,
        not failures,
        tuple(checks),
        tuple(failures),
    )


def _run_authorization_denial(scenario: OfflineScenario) -> ScenarioResult:
    assert scenario.required_scope is not None
    assert scenario.expected_authorization_reason is not None
    tenant = TenantContext("tenant-eval", "tenant-eval", "Synthetic tenant", TenantStatus.ACTIVE)
    principal = AuthenticatedPrincipal(
        tenant_id=tenant.tenant_id,
        user_id=101,
        session_id="offline-session",
        correlation_id="offline-correlation",
        token_id="offline-token",
    )
    context = AuthorizationContext(
        principal=principal,
        tenant=tenant,
        roles=frozenset({Role.CUSTOMER}),
        scopes=frozenset(scenario.granted_scopes),
    )
    decision = authorize(
        context,
        AuthorizationPolicy(scopes=frozenset({scenario.required_scope})),
    )
    checks: list[str] = []
    failures: list[str] = []
    _record_check(checks, failures, "authorization_denied", not decision.allowed, "request allowed")
    _record_check(
        checks,
        failures,
        "authorization_reason",
        decision.reason.value == scenario.expected_authorization_reason,
        f"expected {scenario.expected_authorization_reason}, observed {decision.reason.value}",
    )
    return ScenarioResult(
        scenario.scenario_id,
        scenario.description,
        scenario.metrics,
        not failures,
        tuple(checks),
        tuple(failures),
    )


def _run_tenant_isolation(scenario: OfflineScenario) -> ScenarioResult:
    assert scenario.tenant_a is not None
    assert scenario.tenant_b is not None
    namespace_a = TenantNamespace.for_tenant(scenario.tenant_a)
    namespace_b = TenantNamespace.for_tenant(scenario.tenant_b)
    key_a = namespace_a.redis_key("conversation:synthetic")
    key_b = namespace_b.redis_key("conversation:synthetic")
    checks: list[str] = []
    failures: list[str] = []
    _record_check(checks, failures, "redis_namespace_isolated", key_a != key_b, "keys collided")
    _record_check(
        checks,
        failures,
        "storage_namespace_isolated",
        namespace_a.storage_prefix() != namespace_b.storage_prefix(),
        "storage prefixes collided",
    )
    token = clear_current_tenant()
    try:
        try:
            get_current_tenant_context()
        except TenantContextMissingError:
            checks.append("missing_tenant_fails_closed")
        else:
            failures.append("missing_tenant_fails_closed: missing tenant was accepted")
    finally:
        reset_current_tenant(token)
    return ScenarioResult(
        scenario.scenario_id,
        scenario.description,
        scenario.metrics,
        not failures,
        tuple(checks),
        tuple(failures),
    )


def _run_rejected_transition(scenario: OfflineScenario) -> ScenarioResult:
    assert scenario.current_status is not None
    assert scenario.target_status is not None
    checks: list[str] = []
    failures: list[str] = []
    try:
        transition_run_status(scenario.current_status, scenario.target_status)
    except IllegalRunTransitionError as error:
        _record_check(
            checks,
            failures,
            "transition_rejected",
            error.code == "ILLEGAL_RUN_TRANSITION",
            f"unexpected error code {error.code}",
        )
    else:
        failures.append("transition_rejected: unsafe transition was accepted")
    return ScenarioResult(
        scenario.scenario_id,
        scenario.description,
        scenario.metrics,
        not failures,
        tuple(checks),
        tuple(failures),
    )


async def run_scenario(scenario: OfflineScenario) -> ScenarioResult:
    """Execute one scenario against the relevant application seam."""
    if scenario.kind is OfflineScenarioKind.ROUTING:
        return _run_routing(scenario)
    if scenario.kind is OfflineScenarioKind.RAG_EVIDENCE:
        return await _run_rag_evidence(scenario)
    if scenario.kind is OfflineScenarioKind.APPROVAL:
        return _run_approval(scenario)
    if scenario.kind is OfflineScenarioKind.CANCELLATION:
        return _run_cancellation(scenario)
    if scenario.kind is OfflineScenarioKind.PROVIDER_FALLBACK:
        return await _run_provider_fallback(scenario)
    if scenario.kind is OfflineScenarioKind.PROVIDER_DEGRADATION:
        return await _run_provider_degradation(scenario)
    if scenario.kind is OfflineScenarioKind.AUTHORIZATION_DENIAL:
        return _run_authorization_denial(scenario)
    if scenario.kind is OfflineScenarioKind.TENANT_ISOLATION:
        return _run_tenant_isolation(scenario)
    return _run_rejected_transition(scenario)


def _metric_summary(
    scenarios: Sequence[OfflineScenario], results: Sequence[ScenarioResult]
) -> dict[str, MetricSummary]:
    summaries: dict[str, MetricSummary] = {}
    by_id = {result.scenario_id: result for result in results}
    for metric in OfflineMetric:
        metric_scenarios = [scenario for scenario in scenarios if metric in scenario.metrics]
        passed = sum(1 for scenario in metric_scenarios if by_id[scenario.scenario_id].passed)
        total = len(metric_scenarios)
        summaries[metric.value] = MetricSummary(
            passed=passed,
            total=total,
            rate=round(passed / total, 6) if total else 0.0,
        )
    return summaries


async def run_offline_evaluation(path: str | Path) -> OfflineEvaluationReport:
    """Run the full deterministic dataset and return a JSON-compatible report."""
    scenarios = load_offline_dataset(path)
    results = tuple([await run_scenario(scenario) for scenario in scenarios])
    passed = sum(1 for result in results if result.passed)
    return OfflineEvaluationReport(
        schema_version=1,
        dataset_version=scenarios[0].dataset_version,
        evaluation_type="deterministic_workflow",
        real_provider=False,
        scenarios=ScenarioSummary(
            total=len(results),
            passed=passed,
            failed=len(results) - passed,
            pass_rate=round(passed / len(results), 6),
        ),
        metrics=_metric_summary(scenarios, results),
        results=tuple(
            ScenarioReport(
                scenario_id=result.scenario_id,
                description=result.description,
                passed=result.passed,
                checks=result.checks,
                failures=result.failures,
            )
            for result in results
        ),
        boundary=(
            "Objective deterministic workflow contracts only; live-model linguistic quality "
            "requires an explicitly configured optional evaluation."
        ),
    )


def _print_summary(report: OfflineEvaluationReport) -> None:
    print(
        "Offline deterministic evaluation: "
        f"{report.scenarios.passed}/{report.scenarios.total} scenarios passed "
        f"({report.scenarios.pass_rate:.1%})"
    )
    for name, value in report.metrics.items():
        print(f"- {name}: {value.passed}/{value.total} ({value.rate:.1%})")


def main() -> int:
    """Run the CLI and return a non-zero status on objective regression."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        default="data/offline_workflow_eval_v1.jsonl",
        help="Versioned JSONL scenario dataset.",
    )
    parser.add_argument("--output", type=Path, help="Optional bounded JSON report path.")
    parser.add_argument("--json", action="store_true", help="Print the complete JSON report.")
    args = parser.parse_args()
    try:
        report = asyncio.run(run_offline_evaluation(args.dataset))
    except (FileNotFoundError, ValueError) as error:
        print(f"Offline evaluation configuration error: {error}", file=sys.stderr)
        return 2
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            report.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
        )
    if args.json:
        print(report.model_dump_json(indent=2))
    else:
        _print_summary(report)
    return 0 if report.scenarios.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
