# Known Limitations

This is the canonical final limitation list for the T14-T21 integration branch. A limitation stays
open until new real evidence exists; wording alone does not close it.

- **OpenAI SDK cold-start timing:** a historical full-suite timing assertion remains sensitive to
  first-process OpenAI SDK import cost.
- **Celery fresh-process import timing:** a historical timing assertion remains sensitive to a
  fresh Celery process/import path.
- **Vulnerability baseline:** T18 scan findings remain visible; the repository does not claim zero
  dependency or image vulnerabilities.
- **Hosted protected-PR proof:** the final hosted PR checks have not yet run.
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

Optional live OpenAI/DashScope evaluation is also outside deterministic T21 acceptance. The offline
suite verifies objective workflow contracts only and makes no claim about live-model linguistic
quality.
