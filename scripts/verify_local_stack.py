"""Verify a running local stack without exposing bootstrap credentials."""

from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Awaitable
from pathlib import Path
from typing import cast

import httpx
from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory
from qdrant_client import AsyncQdrantClient, models
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.adapters.context import AdapterContext
from app.adapters.local import LocalLogisticsAdapter, LocalOrderAdapter
from app.bootstrap.local_data import LocalBootstrapConfig
from app.core.config import settings
from app.core.database import async_session_maker
from app.core.redis import create_redis_client
from app.core.tenancy import namespaced_collection, tenant_scope
from app.models.audit import AuditLog
from app.models.complaint import ComplaintTicket
from app.models.knowledge_document import KnowledgeDocument
from app.models.memory import AgentConfig, RoutingRule
from app.models.order import Order
from app.models.outbox import OutboxEvent, OutboxStatus
from app.models.refund import RefundApplication
from app.models.task_receipt import TaskExecutionReceipt, TaskReceiptStatus
from app.models.user import User
from app.retrieval.client import QdrantKnowledgeClient
from app.retrieval.embeddings import create_embedding_model


def _bootstrap_config() -> LocalBootstrapConfig:
    return LocalBootstrapConfig(
        enabled=settings.LOCAL_BOOTSTRAP_ENABLED,
        environment=settings.ENVIRONMENT,
        tenant_id=settings.LOCAL_BOOTSTRAP_TENANT_ID,
        tenant_name=settings.LOCAL_BOOTSTRAP_TENANT_NAME,
        customer_username=settings.LOCAL_BOOTSTRAP_CUSTOMER_USERNAME,
        customer_password=settings.LOCAL_BOOTSTRAP_CUSTOMER_PASSWORD,
        customer_email=settings.LOCAL_BOOTSTRAP_CUSTOMER_EMAIL,
        admin_username=settings.LOCAL_BOOTSTRAP_ADMIN_USERNAME,
        admin_password=settings.LOCAL_BOOTSTRAP_ADMIN_PASSWORD,
        admin_email=settings.LOCAL_BOOTSTRAP_ADMIN_EMAIL,
    )


async def _count(session: AsyncSession, model: type[SQLModel]) -> int:
    return int((await session.exec(select(func.count()).select_from(model))).one())


async def _wait_for_async_receipt(tenant_id: str, timeout_seconds: float) -> dict[str, str]:
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    while asyncio.get_running_loop().time() < deadline:
        with tenant_scope(tenant_id):
            async with async_session_maker() as session:
                event = (
                    await session.exec(
                        select(OutboxEvent).where(
                            OutboxEvent.event_type == "local_bootstrap.refund_review_notification"
                        )
                    )
                ).one_or_none()
                receipt = (
                    await session.exec(
                        select(TaskExecutionReceipt).where(
                            TaskExecutionReceipt.handler == "refund.notify_admin"
                        )
                    )
                ).one_or_none()
        if (
            event is not None
            and event.status == OutboxStatus.PUBLISHED
            and receipt is not None
            and receipt.status == TaskReceiptStatus.COMPLETED
        ):
            return {"event": str(event.status), "receipt": str(receipt.status)}
        await asyncio.sleep(0.5)
    raise RuntimeError("Timed out waiting for the local bootstrap outbox receipt")


async def _verify_database(config: LocalBootstrapConfig) -> dict[str, object]:
    with tenant_scope(config.tenant_id):
        async with async_session_maker() as session:
            customer = (
                await session.exec(select(User).where(User.username == config.customer_username))
            ).one()
            admin = (
                await session.exec(select(User).where(User.username == config.admin_username))
            ).one()
            if customer.id is None or admin.id is None:
                raise RuntimeError("Bootstrap user identifiers are missing")
            adapter_context = AdapterContext(
                tenant_id=config.tenant_id,
                user_id=customer.id,
                correlation_id="local-stack-verification",
            )
            order_adapter = LocalOrderAdapter(session)
            order = await order_adapter.get_order("UAT-NO-2026092203", adapter_context)
            if order is None:
                raise RuntimeError("Customer-owned bootstrap order was not readable")
            tracking = await LocalLogisticsAdapter(order_adapter).get_tracking(
                order.order_sn, adapter_context
            )
            if tracking is None or tracking.tracking_number != "UAT-JD-72003001":
                raise RuntimeError("Persisted logistics projection did not match the UAT order")
            admin_context = AdapterContext(
                tenant_id=config.tenant_id,
                user_id=admin.id,
                correlation_id="local-stack-verification",
            )
            if await order_adapter.get_order(order.order_sn, admin_context) is not None:
                raise RuntimeError("Admin identity bypassed user-owned order isolation")
            connection = await session.connection()
            database_name, current_user, session_user = (
                await connection.execute(
                    text("SELECT current_database(), current_user, session_user")
                )
            ).one()
            counts = {
                "users": await _count(session, User),
                "memberships": await _count(session, User),
                "orders": await _count(session, Order),
                "refund_applications": await _count(session, RefundApplication),
                "approval_records": await _count(session, AuditLog),
                "complaint_tickets": await _count(session, ComplaintTicket),
                "agent_configs": await _count(session, AgentConfig),
                "routing_rules": await _count(session, RoutingRule),
                "knowledge_documents": await _count(session, KnowledgeDocument),
                "outbox_events": await _count(session, OutboxEvent),
                "task_receipts": await _count(session, TaskExecutionReceipt),
            }

    with tenant_scope("local-bootstrap-isolation-probe"):
        async with async_session_maker() as session:
            if await _count(session, User) != 0 or await _count(session, Order) != 0:
                raise RuntimeError("Cross-tenant rows were visible through the runtime role")

    alembic = AlembicConfig(str(Path("alembic.ini")))
    heads = ScriptDirectory.from_config(alembic).get_heads()
    if len(heads) != 1:
        raise RuntimeError(f"Expected one Alembic head, found {len(heads)}")
    migration_engine = create_async_engine(settings.MIGRATION_DATABASE_URL, pool_pre_ping=True)
    try:
        async with migration_engine.connect() as connection:
            current_revision = await connection.scalar(
                text("SELECT version_num FROM alembic_version")
            )
    finally:
        await migration_engine.dispose()
    if current_revision != heads[0]:
        raise RuntimeError("The database is not at the single expected Alembic head")
    return {
        "database": database_name,
        "current_user": current_user,
        "session_user": session_user,
        "alembic_current": current_revision,
        "alembic_head": heads[0],
        "counts": counts,
        "customer_order": order.order_sn,
        "tracking_number": tracking.tracking_number,
        "cross_tenant_visible": False,
        "cross_user_order_visible": False,
    }


async def _verify_qdrant(config: LocalBootstrapConfig) -> dict[str, object]:
    tenant_filter = models.Filter(
        must=[
            models.FieldCondition(key="tenant_id", match=models.MatchValue(value=config.tenant_id))
        ]
    )
    client = AsyncQdrantClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY.get_secret_value() or None,
        timeout=settings.QDRANT_TIMEOUT,
        trust_env=False,
    )
    collection_name = namespaced_collection(settings.QDRANT_COLLECTION_NAME)
    product_collection_name = namespaced_collection("product_catalog")
    knowledge_client = QdrantKnowledgeClient(
        settings.QDRANT_URL,
        collection_name=settings.QDRANT_COLLECTION_NAME,
        api_key=settings.QDRANT_API_KEY.get_secret_value() or None,
        client=client,
    )
    try:
        point_count = await client.count(
            collection_name=collection_name,
            count_filter=tenant_filter,
            exact=True,
        )
        points, _ = await client.scroll(
            collection_name=collection_name,
            scroll_filter=tenant_filter,
            limit=100,
            with_payload=True,
            with_vectors=["dense"],
        )
        product_count = await client.count(
            collection_name=product_collection_name,
            count_filter=tenant_filter,
            exact=True,
        )
        product_points, _ = await client.scroll(
            collection_name=product_collection_name,
            scroll_filter=tenant_filter,
            limit=100,
            with_payload=True,
            with_vectors=["dense"],
        )
        if point_count.count <= 0 or not points:
            raise RuntimeError("Tenant knowledge points are missing from Qdrant")
        if product_count.count <= 0 or not product_points:
            raise RuntimeError("Tenant product points are missing from Qdrant")
        if any((point.payload or {}).get("tenant_id") != config.tenant_id for point in points):
            raise RuntimeError("Qdrant knowledge points contain invalid tenant metadata")
        if any(
            (point.payload or {}).get("tenant_id") != config.tenant_id for point in product_points
        ):
            raise RuntimeError("Qdrant product points contain invalid tenant metadata")
        for point in (*points, *product_points):
            vectors = point.vector
            dense = vectors.get("dense") if isinstance(vectors, dict) else None
            if not isinstance(dense, list) or not any(value != 0.0 for value in dense):
                raise RuntimeError("Qdrant contains an unusable all-zero dense vector")
        with tenant_scope(config.tenant_id):
            vector = await create_embedding_model().aembed_query("质量问题商品的退货运费由谁承担")
            retrieved = await knowledge_client.query_dense(vector, limit=5)
    finally:
        await knowledge_client.aclose()
    sources = [str((point.payload or {}).get("source", "")) for point in retrieved]
    if not any("return_policy" in source for source in sources):
        raise RuntimeError("Known return-policy retrieval did not return its repository source")
    return {
        "collection": collection_name,
        "point_count": int(point_count.count),
        "product_collection": product_collection_name,
        "product_point_count": int(product_count.count),
        "dense_vectors_nonzero": True,
        "tenant_metadata": True,
        "known_retrieval_source": next(source for source in sources if "return_policy" in source),
    }


async def _login_and_verify(
    *,
    api_base_url: str,
    username: str,
    password: str,
    tenant_id: str,
    admin: bool,
    browser_origin: str,
) -> dict[str, object]:
    async with httpx.AsyncClient(base_url=api_base_url, timeout=30, trust_env=False) as client:
        login = await client.post(
            f"{settings.API_V1_STR}/browser/login",
            json={"username": username, "password": password, "tenant_id": tenant_id},
            headers={"Origin": browser_origin},
        )
        login.raise_for_status()
        login_body = login.json()
        me = await client.get(f"{settings.API_V1_STR}/me")
        me.raise_for_status()
        if bool(me.json()["is_admin"]) is not admin:
            raise RuntimeError("Authenticated account role did not match bootstrap configuration")

        checked: list[str] = ["session_restore"]
        admin_knowledge = await client.get(f"{settings.API_V1_STR}/admin/knowledge")
        if admin:
            admin_knowledge.raise_for_status()
            if not admin_knowledge.json():
                raise RuntimeError("Admin knowledge API returned an empty bootstrap dataset")
            for label, path in (
                ("operations", "/admin/tasks-all"),
                ("ai_config", "/admin/agents/config"),
                ("security", "/admin/authorization/memberships"),
            ):
                response = await client.get(f"{settings.API_V1_STR}{path}")
                response.raise_for_status()
                checked.append(label)
            checked.append("knowledge")
        elif admin_knowledge.status_code != 403:
            raise RuntimeError("Customer account could access an admin-only endpoint")
        else:
            checked.append("admin_forbidden")

        csrf = await client.get(f"{settings.API_V1_STR}/browser/csrf")
        csrf.raise_for_status()
        logout = await client.post(
            f"{settings.API_V1_STR}/logout",
            headers={
                "Origin": browser_origin,
                "X-CSRF-Token": csrf.json()["csrf_token"],
            },
        )
        logout.raise_for_status()
        return {
            "username": login_body["username"],
            "tenant_id": login_body["tenant_id"],
            "roles": login_body["roles"],
            "checks": checked,
            "logout": logout.status_code == 204,
        }


async def verify_local_stack(
    api_base_url: str, receipt_timeout: float, browser_origin: str
) -> dict[str, object]:
    """Return a non-secret verification report or raise on a failed contract."""
    config = _bootstrap_config()
    config.validate_for_execution()
    redis = create_redis_client()
    try:
        redis_healthy = bool(await cast(Awaitable[bool], redis.ping()))
    finally:
        await redis.aclose()
    if not redis_healthy:
        raise RuntimeError("Redis health verification failed")

    async with httpx.AsyncClient(base_url=api_base_url, timeout=30, trust_env=False) as client:
        health = await client.get("/health")
        health.raise_for_status()
        customer_app = await client.get("/app")
        customer_app.raise_for_status()
        admin_app = await client.get("/admin")
        admin_app.raise_for_status()

    database, qdrant, async_flow = await asyncio.gather(
        _verify_database(config),
        _verify_qdrant(config),
        _wait_for_async_receipt(config.tenant_id, receipt_timeout),
    )
    customer = await _login_and_verify(
        api_base_url=api_base_url,
        username=config.customer_username,
        password=config.customer_password.get_secret_value(),
        tenant_id=config.tenant_id,
        admin=False,
        browser_origin=browser_origin,
    )
    admin = await _login_and_verify(
        api_base_url=api_base_url,
        username=config.admin_username,
        password=config.admin_password.get_secret_value(),
        tenant_id=config.tenant_id,
        admin=True,
        browser_origin=browser_origin,
    )
    return {
        "api_health": health.json(),
        "customer_app": customer_app.status_code,
        "admin_app": admin_app.status_code,
        "postgresql": database,
        "qdrant": qdrant,
        "redis": {"healthy": redis_healthy, "role": "ephemeral runtime state"},
        "rabbitmq_celery": async_flow,
        "customer_auth": customer,
        "admin_auth": admin,
    }


async def main(api_base_url: str, receipt_timeout: float, browser_origin: str) -> None:
    report = await verify_local_stack(api_base_url, receipt_timeout, browser_origin)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify the canonical local stack.")
    parser.add_argument("--api-base-url", default="http://app:8000")
    parser.add_argument("--receipt-timeout", type=float, default=90.0)
    parser.add_argument("--browser-origin", default="http://localhost:8000")
    arguments = parser.parse_args()
    asyncio.run(main(arguments.api_base_url, arguments.receipt_timeout, arguments.browser_origin))
