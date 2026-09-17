"""Static safety contracts for T20 load, failure, backup, and restore assets."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return ROOT.joinpath(relative_path).read_text(encoding="utf-8")


def test_k6_profiles_are_bounded_and_real_providers_are_absent() -> None:
    """Keep every committed request-load profile short and provider-free."""
    script = _read("performance/k6/t20.js")

    assert 'duration: "10s"' in script
    assert '{ duration: "20s", target: 5 }' in script
    assert 'duration: "2m"' in script
    assert "openai.com" not in script.lower()
    assert "dashscope" not in script.lower()
    assert "BASE_URL is required" in script
    assert 'responseType: "text"' in script


def test_load_and_failure_wrappers_reject_production_targets() -> None:
    """Require explicit disposable targets before bounded load or fault injection."""
    load_wrapper = _read("scripts/t20-run-load.sh")
    failure_wrapper = _read("scripts/t20-inject-failure.sh")

    for script in (load_wrapper, failure_wrapper):
        assert "production-like targets are forbidden" in script
        assert "TARGET_ENVIRONMENT is required" in script
    assert "host.docker.internal:host-gateway" in load_wrapper
    assert "YES_DISPOSABLE_ONLY" in failure_wrapper
    assert "NAMESPACE must be an explicit disposable t20-* namespace" in failure_wrapper
    assert "delete namespace" not in failure_wrapper


def test_restore_refuses_overwrite_and_requires_fresh_t20_database() -> None:
    """Protect the source database and reject implicit destructive restore behavior."""
    restore = _read("scripts/t20-postgres-restore.sh")

    assert "YES_DISPOSABLE_ONLY" in restore
    assert "^t20_" in restore
    assert "restore target already exists" in restore
    assert "restore target must differ from the source database" in restore
    assert "dropdb" not in restore
    assert "pg_restore --list" in restore
    assert "sha256sum --check" in restore
    assert "CREATE ROLE star_warehouse_runtime" in restore
    assert "CREATE ROLE star_warehouse_maintenance" in restore
    assert "NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS" in restore
    assert "FROM pg_policies" in restore
    assert "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE" in restore
    assert "--no-acl" not in restore
    assert restore.index("restore target already exists") < restore.index(
        "CREATE ROLE star_warehouse_runtime"
    )


def test_demo_backup_has_integrity_metadata_and_separate_persistence() -> None:
    """Require more than file existence before treating a demo backup as usable."""
    backup = _read("deploy/helm/star-warehouse-ai/files/backup-postgres.sh")
    template = _read("deploy/helm/star-warehouse-ai/templates/backup-cronjob.yaml")
    helpers = _read("deploy/helm/star-warehouse-ai/templates/_helpers.tpl")

    assert "pg_restore --list" in backup
    assert "--no-acl" not in backup
    assert "pg_isready --quiet" in backup
    assert "sha256sum" in backup
    assert 'cd "${BACKUP_DIRECTORY}"' in backup
    assert 'sha256sum "$(basename "${target}")"' in backup
    assert "alembic_revision" in backup
    assert '"backup_type": "postgresql-logical-custom"' in backup
    assert "kind: CronJob" in template
    assert "kind: Job" in template
    assert "backup-bootstrap-{{ .Release.Revision }}" in template
    assert "kind: PersistentVolumeClaim" in template
    assert "concurrencyPolicy: Forbid" in template
    assert "automountServiceAccountToken: false" in helpers


def test_manual_backup_uses_job_result_without_exec_into_completed_pod() -> None:
    """Keep the operator wrapper compatible with completed Kubernetes Jobs."""
    wrapper = _read("scripts/t20-backup-now.sh")

    assert "kubectl wait --for=condition=complete" in wrapper
    assert "kubectl logs" in wrapper
    assert "kubectl exec" not in wrapper
