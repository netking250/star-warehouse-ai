# Deterministic Offline Workflow Evaluation

T21 extends the existing `app/evaluation` package with one versioned, synthetic workflow dataset.
It runs without OpenAI, DashScope, network access, PostgreSQL, Redis, RabbitMQ, or Qdrant.

```bash
uv run python -m app.evaluation.offline \
  --dataset data/offline_workflow_eval_v1.jsonl \
  --output reports/offline-workflow-evaluation.json
```

The command prints a concise human-readable result, writes a bounded JSON report when `--output` is
provided, and exits non-zero if an objective assertion regresses. `reports/` is ignored; generated
logs and reports are not versioned.

The 12 scenarios cover supported greeting/policy/order/product routing, synthetic RAG evidence,
sensitive-export approval, cancellation, retry/fallback, safe degradation, authorization denial,
tenant namespace isolation, invalid transitions, and duplicate terminal rejection. Metrics are
plain pass ratios for workflow success, routing, tool routing, approval, authorization, tenant
isolation, fallback policy, and terminal uniqueness. No weighted enterprise score is produced.

## Evaluation boundary

The suite calls deterministic application contracts and scripted provider-neutral adapters. It is
reproducible regression evidence for workflow structure. It does **not** evaluate semantic answer
quality, tone, groundedness under a live corpus, provider latency, or live model behavior. Those
questions require an explicitly configured optional live-model/manual evaluation and are not part
of default T21 acceptance.

The pre-existing `scripts/run_evaluation.py` pipeline remains available for configured evaluation
environments; it is not the provider-free T21 acceptance command.
