# Known Limitations

This register describes accepted main `f852a8f2ce0f82fa6157d8bd72b0d1a1f8a1da40`.
See [Final Acceptance](FINAL_ACCEPTANCE.md) for the evidence baseline and the
[execution log](EXECUTION_LOG.md) for historical task results.

- **No live production operation:** There is no production deployment, live AWS
  environment, public VM, public DNS or production certificate, real customer
  data, production SLA/availability evidence, or long-duration production soak.
  Trusted GHCR publication delivers an artifact, not a live service.
- **Recovery boundary:** Disposable logical PostgreSQL backup and fresh-target
  restore were verified; full production point-in-time recovery was not exercised.
  RPO is the latest completed logical backup. The local compatibility object
  store does not prove production S3 behavior or recovery. Kubernetes `emptyDir`
  is not durable production storage.
- **Container and dependency debt:** The final trusted image scan found zero
  CRITICAL findings under the repository's current blocking policy, 81 HIGH
  findings, and 37 HIGH findings with known fixes. The final frontend dependency
  scan recorded 9 HIGH findings. CVE-2026-63374 was absent. Green policy does
  not mean zero vulnerabilities.
- **Frontend retry:** Main's Frontend job succeeded with 63/63 unit tests and
  hosted Playwright success. The test `customer journey remains functional across
  premium login, chat, feedback, theme, and mobile states` passed on one retry;
  13 other tests passed normally. Its first attempt observed transient 502 Bad
  Gateway responses in the browser console. The suite is not 14/14 stable on
  first attempt.
- **Bounded real-provider evidence:** P-UAT-03's 30/30 first-attempt result
  applies only to its frozen synthetic Bailian corpus. A separate real-provider
  smoke after V1.2 did not prove an exact tracking-number answer. Neither result
  establishes universal model quality.
- **Historical timing debt:** Earlier full-suite runs exposed OpenAI SDK
  cold-start, Celery fresh-process import, and a nondeterministic chat-stream
  timeout assertion. The accepted main backend suite passed 1,920 tests with
  zero failures and errors; these earlier observations remain historical debt,
  not a current failing main gate.
- **Performance scope:** T20 load measurements were bounded disposable runs,
  including a two-minute run. They do not establish production capacity, HA,
  latency SLA, or sustained traffic behavior.

No external security certification, fully secure claim, or enterprise
production-scale operating history is implied.
