"""Tenant-aware source-object storage for knowledge ingestion."""

from __future__ import annotations

import asyncio
import os
import uuid
from pathlib import Path, PurePosixPath
from typing import Protocol

from app.core.config import settings
from app.core.tenancy import validate_tenant_id


class KnowledgeObjectNotFoundError(RuntimeError):
    """Raised when a referenced knowledge source object does not exist."""


class KnowledgeObjectAccessError(RuntimeError):
    """Raised when an object key is outside the active tenant namespace."""


class KnowledgeObjectStore(Protocol):
    """Store tenant-owned source bytes behind stable logical object keys."""

    async def put_bytes(self, *, tenant_id: str, object_name: str, content: bytes) -> str:
        """Persist bytes and return a stable tenant-scoped object key."""
        ...

    async def read_bytes(self, *, tenant_id: str, object_key: str) -> bytes:
        """Read bytes after validating tenant ownership of the object key."""
        ...

    async def delete(self, *, tenant_id: str, object_key: str) -> bool:
        """Delete an owned object and report whether it existed."""
        ...


class LocalKnowledgeObjectStore:
    """Local/demo adapter backed by one configured filesystem root."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).resolve()

    async def put_bytes(self, *, tenant_id: str, object_name: str, content: bytes) -> str:
        """Atomically persist bytes below the tenant prefix."""
        object_key = self.object_key(tenant_id=tenant_id, object_name=object_name)
        path = self._path_for_key(tenant_id=tenant_id, object_key=object_key)
        await asyncio.to_thread(self._write_atomic, path, content)
        return object_key

    async def read_bytes(self, *, tenant_id: str, object_key: str) -> bytes:
        """Read one tenant-owned source object."""
        path = self._path_for_key(tenant_id=tenant_id, object_key=object_key)
        try:
            return await asyncio.to_thread(path.read_bytes)
        except FileNotFoundError as exc:
            raise KnowledgeObjectNotFoundError(
                f"Knowledge source object is missing: {object_key}"
            ) from exc

    async def delete(self, *, tenant_id: str, object_key: str) -> bool:
        """Delete one tenant-owned source object idempotently."""
        path = self._path_for_key(tenant_id=tenant_id, object_key=object_key)
        return await asyncio.to_thread(self._unlink_if_present, path)

    @staticmethod
    def object_key(*, tenant_id: str, object_name: str) -> str:
        """Build the canonical logical key without exposing a local root."""
        normalized_tenant = validate_tenant_id(tenant_id)
        if (
            not object_name
            or "/" in object_name
            or "\\" in object_name
            or PurePosixPath(object_name).name != object_name
        ):
            raise ValueError("object_name must be a single safe path segment")
        return f"tenant/{normalized_tenant}/{object_name}"

    def _path_for_key(self, *, tenant_id: str, object_key: str) -> Path:
        normalized_tenant = validate_tenant_id(tenant_id)
        key = PurePosixPath(object_key)
        expected_parts = ("tenant", normalized_tenant)
        if (
            key.is_absolute()
            or len(key.parts) != 3
            or key.parts[:2] != expected_parts
            or key.name in {"", ".", ".."}
            or "\\" in key.name
        ):
            raise KnowledgeObjectAccessError(
                "Knowledge object key is outside the active tenant namespace"
            )
        path = self._root.joinpath(*key.parts).resolve()
        tenant_root = self._root.joinpath(*expected_parts).resolve()
        if tenant_root not in path.parents:
            raise KnowledgeObjectAccessError(
                "Knowledge object escaped the active tenant storage root"
            )
        return path

    @staticmethod
    def _write_atomic(path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            with temporary.open("wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _unlink_if_present(path: Path) -> bool:
        try:
            path.unlink()
        except FileNotFoundError:
            return False
        return True


def get_knowledge_object_store() -> KnowledgeObjectStore:
    """Return the configured knowledge source-object adapter."""
    return LocalKnowledgeObjectStore(settings.KNOWLEDGE_UPLOAD_DIR)
