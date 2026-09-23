# Known Limitations

This is the canonical limitation list for the current accepted baseline. Historical task-specific
evidence remains in the execution ledger; a limitation stays open until new real evidence exists.

- **OpenAI SDK cold-start timing:** a historical full-suite timing assertion remains sensitive to
  first-process OpenAI SDK import cost.
- **Celery fresh-process import timing:** a historical timing assertion remains sensitive to a
  fresh Celery process/import path.
- **Historical chat-stream timing flake:**
  `tests/test_chat_api.py::test_chat_timeout_after_answer_closes_without_error` remains a
  nondeterministic historical failure observed at T21, T20, and protected `origin/main`; it is not
  demonstrated to be a T21 feature regression and is separate from the OpenAI/Celery timing debts.
- **Vulnerability baseline:** T18 scan findings remain visible; the repository does not claim zero
  dependency or image vulnerabilities.
- **Current V1.2 hosted proof:** the historical P-UAT repair has hosted regression evidence, but
  this V1.2 branch has no PR by explicit scope and therefore no branch-specific hosted run.
- **GHCR publish proof:** trusted hosted publication of the scanned image has not yet been proven.
- **Attestation proof:** hosted provenance/attestation has not yet been proven.
- **Public VM, DNS, and public CA:** T19 used a disposable deployment target; a real public VM,
  public DNS, and public certificate authority path were not exercised.
- **Object-storage runtime recovery:** the production object-storage recovery path was not
  exercised. Kubernetes `emptyDir` is explicitly not production-safe durable storage.
- **PITR:** point-in-time recovery is not implemented. RPO is the latest completed logical backup.
- **Live AWS deployment:** AWS is a qualified reference architecture, not an executed deployment.
- **Long soak:** T20's two-minute run is bounded evidence, not a long-duration soak.
- **Production capacity:** measured disposable results are not production sizing, availability, HA,
  or capacity claims.

Real-provider evaluation is opt-in rather than part of deterministic CI. The accepted Bailian
30/30 result applies only to its frozen synthetic UAT corpus; provider-free evaluation verifies
objective workflow contracts and makes no broad live-model linguistic-quality claim.
