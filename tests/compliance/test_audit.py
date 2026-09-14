"""Audit metadata minimization and PostgreSQL immutability tests."""

from app.compliance.audit import sanitize_audit_metadata


def test_audit_metadata_redacts_credentials_and_export_content() -> None:
    metadata = sanitize_audit_metadata(
        {
            "password": "secret-password",
            "jwt_token": "signed-token",
            "Cookie": "session-cookie",
            "csrf_secret": "csrf-value",
            "export_content": "private,csv,data",
            "record_count": 3,
            "operation_hash": "safe-hash",
        }
    )

    assert metadata["record_count"] == 3
    assert metadata["operation_hash"] == "safe-hash"
    assert all(
        value == "[REDACTED]"
        for key, value in metadata.items()
        if key not in {"record_count", "operation_hash"}
    )
