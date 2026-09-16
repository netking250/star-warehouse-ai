# Deployment Architecture

## Runtime shape

One OCI image preserves the modular monolith while Kubernetes runs distinct process roles:

```text
Internet / DNS / TLS
        |
     Ingress
        |
  ClusterIP API Service -> API Deployment
                              |
                PostgreSQL / Redis / Qdrant
                              |
                transactional outbox rows
                              |
                    Outbox Relay -> RabbitMQ -> Celery Workers
                                                   ^
                                                   |
                                            single Celery Beat

All roles -> configured T17 OpenTelemetry Collector; logs -> stdout/stderr
```

The API and tenant workers may scale independently. The maintenance worker remains a worker role
with the explicit maintenance database capability and queue. Celery Beat is hard-limited to one
replica because the current application has no scheduler leader election. The outbox relay's
database lease logic is concurrent-safe, but the baseline remains one replica until operational
evidence justifies more. No domain microservice, service mesh, Kafka, or second deployment system
is introduced.

## Release flow

```text
trusted main or version tag
  -> T18 build + OCI revision metadata
  -> secret/dependency/image scans + CycloneDX SBOM
  -> exact scanned image archive
  -> trusted GHCR publication + provenance attestation
  -> immutable repository@sha256 digest
  -> Helm values / deployment script
  -> revision-scoped Alembic Job + non-mutating workload init gate
  -> bounded Kubernetes rollout and smoke evidence
```

Pull requests never publish. The cluster never checks out Git or builds source. Helm history and
Kubernetes rollout state are the deployment history; there is no custom history database.

## Demo topology

The public-demo target is a small operator-managed VM running k3s and its default Traefik ingress.
`values-demo.yaml` enables single-replica PostgreSQL, Redis Stack, RabbitMQ, and Qdrant StatefulSets
with PVCs. Only the application ingress is public. This topology is cost-conscious and runnable,
but it is neither HA nor a backup strategy and must not be presented as production capacity.

Flannel, the common default k3s CNI, does not enforce Kubernetes NetworkPolicy. The chart therefore
does not enable a pretend deny-all policy that the canonical demo cannot validate. A production
cluster should select and verify a policy-capable CNI, then restrict ingress to the ingress
controller and egress to DNS, PostgreSQL, Redis, RabbitMQ, Qdrant, the OTel Collector, and explicitly
configured external providers.

## AWS production reference

AWS is a reference architecture, not infrastructure provisioned by T19:

| Concern | Reference mapping | Qualification |
| --- | --- | --- |
| DNS | Route 53 | Public alias to the selected load balancer |
| Compute | EKS managed node groups or approved autoscaling nodes | Chart deploys the same API/worker/scheduler/relay roles |
| Ingress | AWS Load Balancer Controller with ALB/ACM, or ingress-nginx behind an AWS load balancer | Preserve HTTPS, SSE, WebSocket, upload size, and bounded idle timeouts |
| PostgreSQL | RDS PostgreSQL or Aurora PostgreSQL-compatible | Multi-AZ/PITR are production-reference targets; T20 owns proof |
| Redis | ElastiCache Valkey/Redis-compatible service | Cache/session/lock/result-backend endpoint, not Celery broker |
| RabbitMQ | Amazon MQ for RabbitMQ | AWS has no need to substitute Kafka for the accepted broker |
| Qdrant | Qdrant Cloud or a separately operated Qdrant deployment on EKS/EBS | No first-party AWS managed Qdrant equivalent is claimed |
| Object storage | S3 behind the accepted future tenant-scoped object-store Port | Current application upload storage remains a documented local compatibility path |
| Secrets | Secrets Manager, synchronized by External Secrets using IRSA | No static AWS keys in chart or repository |
| Registry | ECR may mirror the trusted GHCR digest, or GHCR may be consumed directly | Digest identity must remain stable across mirroring |
| Observability | Existing T17 OpenTelemetry/Prometheus/Loki/Tempo contract, self-hosted or connected to approved AWS-compatible backends | Do not create a second instrumentation architecture |

The chart's `values-production.yaml` demonstrates externally managed endpoints, multiple API and
tenant-worker replicas, a single scheduler and relay, TLS ingress, and an API PDB. Values are
starter configuration, not measured sizing. It deliberately contains no AWS credentials,
Terraform/CDK stack, production hostname, certificate, or live resource identifier.

## Security boundaries

- Runtime and migration database identities are distinct. Normal request/tenant work uses the
  NO BYPASSRLS runtime role; maintenance/relay uses the explicit maintenance role; only the
  revision-scoped migration Job receives migration administration credentials.
- Secrets are referenced, not rendered. ConfigMap rollout checksums contain only non-secret data.
- Application pods are non-root, unprivileged, capability-free, read-only-root, and have no API
  token. The chart installs no Kubernetes RBAC permissions.
- Production public origin, secure cookie, CSRF, WebSocket Origin, `wss`, and OIDC redirect
  contracts are preserved at ingress. Browser bearer storage and WebSocket query tokens remain
  forbidden.
- Infrastructure services and observability endpoints have no public Service or Ingress.

## Known boundary

The accepted object-storage target is not yet an active application adapter. T19 does not add fake
S3 environment variables or claim local upload durability. Production multi-replica knowledge
uploads require a future explicit application-contract change and evidence. This does not alter
the Helm deployment of provider-free health/session smoke or the AWS reference mapping.
