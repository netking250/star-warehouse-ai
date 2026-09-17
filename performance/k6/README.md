# T20 bounded HTTP load harness

This is the repository's single concurrent HTTP load harness. It complements, rather than replaces,
the deterministic pytest regressions in `tests/performance/`.

Profiles are intentionally small:

| Profile | Shape | Operations | Opt-in |
| --- | --- | --- | --- |
| `SMOKE` | 1 VU for 10 seconds | `/health`; authenticated read when credentials are supplied | default |
| `BASELINE` | ramp to 5 VUs, hold 20 seconds, ramp down | login once, `/health`, `/api/v1/me` | `T20_HEAVY_OPT_IN=YES` |
| `SOAK_SHORT` | 3 VUs for 2 minutes | login once, `/health`, `/api/v1/me` | `T20_HEAVY_OPT_IN=YES` |

Run through `scripts/t20-run-load.sh`. The wrapper requires an explicit environment and target,
rejects production-like names, and writes raw local summaries only under ignored `reports/t20/`.
Use `127.0.0.1` with a native k6 binary; when the wrapper falls back to Docker, address a host
port-forward as `host.docker.internal` (the wrapper installs the bounded host-gateway mapping).
Latency values are disposable-environment measurements, not contractual production SLOs. Compare
three `BASELINE` runs from the same environment; investigate a repeatable large shift before
changing resource, pool, timeout, worker, or replica settings.

Async/Outbox and Mock-provider/conversation load use the accepted integration seams and focused
tests because no safe public endpoint exists for injecting those fixtures. They are not a second
request-load framework. Real OpenAI or DashScope traffic is forbidden in T20.
