import io
import os
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlmodel import select

from app.core.database import async_session_maker
from app.core.security import create_access_token
from app.models.knowledge_document import KnowledgeDocument
from app.models.outbox import OutboxEvent, OutboxStatus
from app.models.user import User


@pytest.fixture(autouse=True)
def _mock_knowledge_task_dispatch(monkeypatch):
    """Keep API tests independent of a running Celery broker and worker."""
    monkeypatch.setattr(
        "app.api.v1.admin.dispatch_task",
        MagicMock(return_value=SimpleNamespace(id="knowledge-task-test")),
    )


async def create_admin_user() -> tuple[User, str]:
    unique = uuid.uuid4().hex[:8]
    username = f"admin_{unique}"
    async with async_session_maker() as session:
        user = User(
            username=username,
            password_hash=User.hash_password("adminpass"),
            email=f"{username}@_admin.com",
            full_name="Admin User",
            phone="13800138000",
            is_admin=True,
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        assert user.id is not None
        token = create_access_token(user_id=user.id or 0, is_admin=True)
        return user, token


async def create_regular_user() -> User:
    unique = uuid.uuid4().hex[:8]
    username = f"user_{unique}"
    async with async_session_maker() as session:
        user = User(
            username=username,
            password_hash=User.hash_password("userpass"),
            email=f"{username}@user.com",
            full_name="Regular User",
            phone="13900139000",
            is_admin=False,
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        assert user.id is not None
        return user


@pytest.mark.asyncio
async def test_list_knowledge_documents(client):
    _admin, token = await create_admin_user()

    async with async_session_maker() as session:
        doc = KnowledgeDocument(
            filename="test.md",
            storage_path="/tmp/test.md",
            content_type="text/markdown",
            doc_size_bytes=100,
            sync_status="done",
        )
        session.add(doc)
        await session.commit()

    response = await client.get(
        "/api/v1/admin/knowledge",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert any(d["filename"] == "test.md" for d in data)


@pytest.mark.asyncio
async def test_upload_knowledge_document(client):
    _admin, token = await create_admin_user()

    content = b"# Test knowledge document\nThis is a test."
    file = io.BytesIO(content)

    response = await client.post(
        "/api/v1/admin/knowledge",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("test.md", file, "text/markdown")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "test.md"
    assert data["sync_status"] == "pending"
    assert isinstance(data["task_id"], str)
    assert len(data["task_id"]) > 0

    async with async_session_maker() as session:
        result = await session.exec(
            select(KnowledgeDocument).where(KnowledgeDocument.id == data["id"])
        )
        doc = result.one_or_none()
        assert doc is not None
        assert doc.doc_size_bytes == len(content)
        assert tuple(Path(doc.storage_path).parts[-3:-1]) == ("tenant", "default")
        outbox_event = (
            await session.exec(
                select(OutboxEvent).where(
                    OutboxEvent.event_type == "knowledge.sync_requested",
                    OutboxEvent.aggregate_id == str(doc.id),
                )
            )
        ).one_or_none()
        assert outbox_event is not None
        assert outbox_event.status == OutboxStatus.PENDING
        assert str(outbox_event.event_id) == data["task_id"]
        if os.path.exists(doc.storage_path):
            os.remove(doc.storage_path)


@pytest.mark.asyncio
async def test_delete_knowledge_document(client, tmp_path):
    _admin, token = await create_admin_user()

    async with async_session_maker() as session:
        doc = KnowledgeDocument(
            filename="delete_me.md",
            storage_path=os.path.join(str(tmp_path), "delete_me.md"),
            content_type="text/markdown",
            doc_size_bytes=10,
            sync_status="done",
        )
        session.add(doc)
        await session.commit()
        await session.refresh(doc)
        doc_id = doc.id

    with open(doc.storage_path, "wb") as f:
        f.write(b"test")

    response = await client.delete(
        f"/api/v1/admin/knowledge/{doc_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert not os.path.exists(doc.storage_path)

    async with async_session_maker() as session:
        result = await session.exec(select(KnowledgeDocument).where(KnowledgeDocument.id == doc_id))
        assert result.one_or_none() is None


@pytest.mark.asyncio
async def test_sync_knowledge_document_endpoint(client):
    _admin, token = await create_admin_user()

    async with async_session_maker() as session:
        doc = KnowledgeDocument(
            filename="sync_me.md",
            storage_path="/tmp/sync_me.md",
            content_type="text/markdown",
            doc_size_bytes=10,
            sync_status="pending",
        )
        session.add(doc)
        await session.commit()
        await session.refresh(doc)
        doc_id = doc.id

    response = await client.post(
        f"/api/v1/admin/knowledge/{doc_id}/sync",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == doc_id
    assert data["sync_status"] == "running"
    assert isinstance(data["task_id"], str)
    assert len(data["task_id"]) > 0


@pytest.mark.asyncio
async def test_get_knowledge_sync_status(client, monkeypatch):
    _admin, token = await create_admin_user()
    task_id = "knowledge-status-test"

    from app.celery_app import celery_app

    monkeypatch.setattr(
        celery_app,
        "AsyncResult",
        MagicMock(return_value=SimpleNamespace(status="PENDING", result=None, ready=lambda: False)),
    )
    response = await client.get(
        f"/api/v1/admin/knowledge/sync/{task_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["task_id"] == task_id
    assert isinstance(data["status"], str)
    assert len(data["status"]) > 0


@pytest.mark.asyncio
async def test_knowledge_endpoints_reject_non_admin(client):
    user = await create_regular_user()
    token = create_access_token(user_id=user.id or 0, is_admin=False)

    response = await client.get(
        "/api/v1/admin/knowledge",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403

    response = await client.post(
        "/api/v1/admin/knowledge",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403

    response = await client.delete(
        "/api/v1/admin/knowledge/1",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403

    response = await client.post(
        "/api/v1/admin/knowledge/1/sync",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
