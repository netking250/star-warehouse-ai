# k3s Public Demo Deployment

This guide deploys the application to an operator-managed k3s node. The repository script does not
install k3s, change the firewall or SSH, format disks, create cloud resources, or delete namespaces
and PVCs.

## Prerequisites

- A supported Linux VM for the chosen k3s release, with operator-controlled patching.
- A starting estimate of 4 vCPU, 8 GiB RAM, and 40 GiB persistent disk for the complete single-node
  demo. This is an unmeasured baseline, not a capacity claim.
- Public DNS for the chosen host pointing to the VM.
- Inbound TCP 80/443 for Traefik and tightly restricted SSH for operators. Do not publish database,
  Redis, RabbitMQ, Qdrant, or monitoring ports.
- A current kubectl compatible with the cluster, Helm 3.15 or newer, and kubeconform 0.6.7 or
  newer for static chart validation.
- A default StorageClass (normally k3s `local-path`) and a configured kubeconfig.
- k3s secrets encryption at rest enabled by operator-controlled installation/configuration.

Follow the official k3s installation documentation interactively. Review the installer and flags;
do not embed an unreviewed remote `curl | sh` command in application deployment automation. Keep
the default Traefik controller unless the cluster was intentionally built around another ingress.

## Prepare namespace, secrets, and image

```bash
kubectl create namespace star-warehouse-ai
kubectl --namespace star-warehouse-ai create secret generic star-warehouse-ai-runtime \
  --from-env-file=.env.k3s.local \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl --namespace star-warehouse-ai create secret tls star-warehouse-ai-tls \
  --cert=/operator/path/fullchain.pem \
  --key=/operator/path/privkey.pem
```

Use the key contract in [Deployment Profiles](deploy.md). Never commit `.env.k3s.local`, a
certificate private key, or rendered Secret YAML. cert-manager with Let's Encrypt may replace the
manual TLS step; set its issuer and contact email outside this repository and add only the approved
Ingress annotation through a private values file.

Retrieve the digest from the trusted GHCR workflow artifact/attestation. If GHCR is private, create
an image-pull Secret and set `image.pullSecrets`. Do not use a personal static token in values.

## Install

```bash
PUBLIC_HOST=app.example.com \
IMAGE_DIGEST=sha256:<trusted-digest> \
IMAGE_REVISION=<commit-sha> \
./scripts/deploy-k3s.sh
```

The script validates context, namespace syntax, required Secret keys, TLS Secret, and digest; then
runs `helm upgrade --install --atomic --wait --wait-for-jobs` with a bounded timeout. A migration
failure, Job timeout, pod readiness failure, or rollout failure is returned to the operator. The
script does not build an image or hide a failed command.

For an isolated disposable cluster with a locally imported image only:

```bash
PUBLIC_HOST=app.example.com \
ALLOW_MUTABLE_DEMO_IMAGE=true \
IMAGE_REPOSITORY=star-warehouse-ai \
IMAGE_TAG=local \
./scripts/deploy-k3s.sh
```

That override is not an Internet production release and still rejects `latest`.

## Smoke

After DNS and TLS resolve:

```bash
kubectl get pods,service,ingress --namespace star-warehouse-ai
curl --fail --silent --show-error https://app.example.com/health
helm status star-warehouse-ai --namespace star-warehouse-ai
```

Confirm the API is Ready, the tenant and maintenance workers are running, Beat has exactly one pod,
and the relay is running. Perform login/session smoke through HTTPS, confirm a CSRF-protected action,
and connect to the configured `wss://` endpoint without a query token. For SSE, verify response
events arrive before the 45-second application stream timeout. Provider-free infrastructure smoke
does not call a real model.

For T17, verify API/worker service identities in the Collector backend, structured container logs,
and an API metric scrape. Do not expose Grafana, Tempo, Loki, Prometheus, or the Collector publicly.

## Upgrade

Use the same command with a new trusted digest and revision. The revision-scoped migration Job runs
`alembic upgrade head`, which is idempotent at the current head. ConfigMap changes roll pods through
the checksum annotation. External Secret changes require an explicit restart:

```bash
kubectl rollout restart deployment --namespace star-warehouse-ai \
  --selector=app.kubernetes.io/instance=star-warehouse-ai
```

Inspect `helm history` and rollout status after every upgrade. Never work around a failed migration
by starting the API with an old or partially migrated schema.

## Application rollback

```bash
helm history star-warehouse-ai --namespace star-warehouse-ai
helm rollback star-warehouse-ai <compatible-revision> \
  --namespace star-warehouse-ai --wait --timeout 10m
```

Rollback changes application/chart resources only. It does not downgrade Alembic, delete PVCs, or
restore snapshots. Confirm the previous image is schema-compatible before rollback. Destructive
cleanup and disaster recovery are separate, explicit operator procedures owned by T20.

## Demo backup and restore boundary

The demo values enable the T20 PostgreSQL logical-backup CronJob. It writes custom-format dumps,
safe metadata, and SHA-256 files to a dedicated backup PVC with a seven-day test default. A file is
not considered valid until checksum/list validation and a fresh-target restore pass. See
[Backup, Restore, and Disaster Recovery](../runbooks/disaster-recovery.md). The backup PVC is still
on the single demo node and is not node-failure HA or an off-host production backup.

## Failure visibility

- Find and inspect the revision-scoped migration with
  `kubectl get jobs -n star-warehouse-ai -l app.kubernetes.io/component=migration` and
  `kubectl logs job/<job-name> -n star-warehouse-ai`.
- Inspect pod events with `kubectl describe pod ...`; do not add sleep loops or weaken readiness.
- A missing Secret key must be corrected out of band; never move it into ConfigMap.
- A failed atomic release is not healthy. Use `helm status` and `helm history`; do not automatically
  delete the namespace or persistent volumes.
