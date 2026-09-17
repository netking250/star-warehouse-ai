"""Tests for the provider-free T21 workflow evaluation."""

import json

import pytest

from app.evaluation.offline import load_offline_dataset, run_offline_evaluation


def test_offline_dataset_loads_supported_synthetic_scenarios() -> None:
    scenarios = load_offline_dataset("data/offline_workflow_eval_v1.jsonl")

    assert len(scenarios) == 12
    assert {scenario.dataset_version for scenario in scenarios} == {"t21-workflow-v1"}
    assert len({scenario.scenario_id for scenario in scenarios}) == len(scenarios)


@pytest.mark.asyncio
async def test_offline_evaluation_passes_all_objective_contracts() -> None:
    report = await run_offline_evaluation("data/offline_workflow_eval_v1.jsonl")

    assert report.real_provider is False
    assert report.evaluation_type == "deterministic_workflow"
    assert report.scenarios.model_dump() == {
        "total": 12,
        "passed": 12,
        "failed": 0,
        "pass_rate": 1.0,
    }
    assert report.metrics["routing_correctness"].model_dump() == {
        "passed": 4,
        "total": 4,
        "rate": 1.0,
    }
    assert report.metrics["tool_routing_correctness"].model_dump() == {
        "passed": 3,
        "total": 3,
        "rate": 1.0,
    }
    assert report.metrics["approval_policy_correctness"].model_dump() == {
        "passed": 1,
        "total": 1,
        "rate": 1.0,
    }
    assert report.metrics["tenant_isolation_pass_rate"].model_dump() == {
        "passed": 1,
        "total": 1,
        "rate": 1.0,
    }
    assert report.metrics["fallback_policy_correctness"].model_dump() == {
        "passed": 2,
        "total": 2,
        "rate": 1.0,
    }
    assert report.metrics["terminal_uniqueness"].model_dump() == {
        "passed": 3,
        "total": 3,
        "rate": 1.0,
    }


@pytest.mark.asyncio
async def test_offline_evaluation_returns_failure_for_objective_regression(tmp_path) -> None:
    source = load_offline_dataset("data/offline_workflow_eval_v1.jsonl")
    records = [scenario.model_dump(mode="json") for scenario in source]
    records[0]["expected_route"] = "order_agent"
    dataset = tmp_path / "regressed.jsonl"
    dataset.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n",
        encoding="utf-8",
    )

    report = await run_offline_evaluation(dataset)

    assert report.scenarios.failed == 1
    assert report.scenarios.pass_rate < 1.0
