"""Canonical local development and UAT data bootstrap."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from pydantic import JsonValue, SecretStr, TypeAdapter
from sqlalchemy import insert, update
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel, col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.authorization.policy import Role
from app.core.tenancy import TenantStatus, tenant_scope
from app.models.audit import AuditAction, AuditLog, AuditTriggerType, RiskLevel
from app.models.complaint import (
    ComplaintCategory,
    ComplaintStatus,
    ComplaintTicket,
    ComplaintUrgency,
    ExpectedResolution,
)
from app.models.knowledge_document import KnowledgeDocument
from app.models.memory import AgentConfig, RoutingRule, UserProfile
from app.models.order import Order, OrderStatus
from app.models.outbox import OutboxEvent
from app.models.refund import RefundApplication, RefundReason, RefundStatus
from app.models.tenant import Tenant
from app.models.user import User
from app.outbox import enqueue_task
from app.task_runtime.context import build_task_context


class LocalBootstrapError(RuntimeError):
    """Raised when the local-only bootstrap contract is not satisfied."""


@dataclass(frozen=True, slots=True)
class LocalBootstrapConfig:
    """Validated local identity and tenant inputs for the bootstrap."""

    enabled: bool
    environment: str
    tenant_id: str
    tenant_name: str
    customer_username: str
    customer_password: SecretStr
    customer_email: str
    admin_username: str
    admin_password: SecretStr
    admin_email: str

    def validate_for_execution(self) -> None:
        """Reject unsafe or incomplete local bootstrap execution."""
        if self.environment.strip().lower() == "production":
            raise LocalBootstrapError("Local bootstrap is forbidden in production")
        if not self.enabled:
            raise LocalBootstrapError("LOCAL_BOOTSTRAP_ENABLED must be true")
        required_values = {
            "LOCAL_BOOTSTRAP_TENANT_ID": self.tenant_id,
            "LOCAL_BOOTSTRAP_TENANT_NAME": self.tenant_name,
            "LOCAL_BOOTSTRAP_CUSTOMER_USERNAME": self.customer_username,
            "LOCAL_BOOTSTRAP_CUSTOMER_EMAIL": self.customer_email,
            "LOCAL_BOOTSTRAP_ADMIN_USERNAME": self.admin_username,
            "LOCAL_BOOTSTRAP_ADMIN_EMAIL": self.admin_email,
        }
        missing = [name for name, value in required_values.items() if not value.strip()]
        if missing:
            raise LocalBootstrapError(f"Required local bootstrap value is empty: {missing[0]}")
        if self.customer_username == self.admin_username:
            raise LocalBootstrapError("Customer and admin usernames must be distinct")
        for password in (self.customer_password, self.admin_password):
            if len(password.get_secret_value()) < 12:
                raise LocalBootstrapError(
                    "Local bootstrap passwords must contain at least 12 characters"
                )


@dataclass(frozen=True, slots=True)
class LocalBootstrapReport:
    """Non-secret counts emitted after a successful bootstrap."""

    tenant_id: str
    users: int
    memberships: int
    orders: int
    refund_applications: int
    approval_records: int
    complaint_tickets: int
    agent_configs: int
    routing_rules: int
    outbox_events: int
    task_receipts: int
    knowledge_documents: int
    knowledge_chunks: int
    product_points: int


@dataclass(frozen=True, slots=True)
class _OrderSpec:
    order_sn: str
    status: OrderStatus
    total_amount: Decimal
    items: list[dict[str, JsonValue]]
    tracking_number: str | None
    shipping_address: str
    delivered_at: datetime | None = None


_ORDERS: tuple[_OrderSpec, ...] = (
    _OrderSpec(
        order_sn="UAT-NO-2026092201",
        status=OrderStatus.DELIVERED,
        total_amount=Decimal("899.00"),
        items=[
            {
                "sku": "AUDIO-004",
                "name": "无线降噪耳机",
                "category": "数码",
                "qty": 1,
                "price": 899.0,
            }
        ],
        tracking_number="UAT-SF-72001001",
        shipping_address="星海市云港区松涛路88号（合成地址）",
        delivered_at=datetime(2026, 9, 18, 9, 30, tzinfo=UTC),
    ),
    _OrderSpec(
        order_sn="UAT-NO-2026092202",
        status=OrderStatus.PENDING,
        total_amount=Decimal("129.00"),
        items=[
            {
                "sku": "SPORT-002",
                "name": "速干运动衫",
                "category": "运动户外",
                "qty": 1,
                "price": 129.0,
            }
        ],
        tracking_number=None,
        shipping_address="星海市云港区松涛路88号（合成地址）",
    ),
    _OrderSpec(
        order_sn="UAT-NO-2026092203",
        status=OrderStatus.SHIPPED,
        total_amount=Decimal("1899.00"),
        items=[
            {
                "sku": "FURN-005",
                "name": "北欧风实木餐桌",
                "category": "家具",
                "qty": 1,
                "price": 1899.0,
            }
        ],
        tracking_number="UAT-JD-72003001",
        shipping_address="星海市云港区松涛路88号（合成地址）",
    ),
    _OrderSpec(
        order_sn="UAT-NO-2026092204",
        status=OrderStatus.DELIVERED,
        total_amount=Decimal("159.00"),
        items=[
            {
                "sku": "CARE-006",
                "name": "密封声波牙刷替换刷头",
                "category": "个人卫生用品",
                "qty": 1,
                "price": 159.0,
            }
        ],
        tracking_number="UAT-ZT-72004001",
        shipping_address="星海市云港区松涛路88号（合成地址）",
        delivered_at=datetime(2026, 9, 10, 15, 20, tzinfo=UTC),
    ),
)

_AGENT_NAMES: tuple[str, ...] = (
    "policy_agent",
    "order_agent",
    "product",
    "cart",
    "logistics",
    "account",
    "payment",
    "complaint",
)

_ROUTING_RULES: tuple[tuple[str, str], ...] = (
    ("ORDER", "order_agent"),
    ("AFTER_SALES", "order_agent"),
    ("POLICY", "policy_agent"),
    ("LOGISTICS", "logistics"),
    ("ACCOUNT", "account"),
    ("PAYMENT", "payment"),
    ("PRODUCT", "product"),
    ("CART", "cart"),
    ("PROMOTION", "policy_agent"),
    ("COMPLAINT", "complaint"),
    ("OTHER", "policy_agent"),
)

_KNOWLEDGE_SOURCES: tuple[tuple[str, str], ...] = (
    ("return_policy.md", "local-uat-return-policy.md"),
    ("shipping_policy.md", "local-uat-shipping-policy.md"),
    ("products.json", "local-uat-product-faq.json"),
)
_PRODUCT_CATALOG_ADAPTER = TypeAdapter(list[dict[str, JsonValue]])


async def _upsert_user(
    session: AsyncSession,
    *,
    username: str,
    password: SecretStr,
    email: str,
    full_name: str,
    role: Role,
) -> User:
    result = await session.exec(select(User).where(User.username == username))
    user = result.one_or_none()
    if user is None:
        email_result = await session.exec(select(User).where(User.email == email))
        if email_result.one_or_none() is not None:
            raise LocalBootstrapError(
                f"Bootstrap email {email!r} belongs to a different local account"
            )
        password_hash = await asyncio.to_thread(User.hash_password, password.get_secret_value())
        user = User(
            username=username,
            password_hash=password_hash,
            email=email,
            full_name=full_name,
            is_admin=role is Role.SUPER_ADMIN,
            role=role.value,
            is_active=True,
        )
        session.add(user)
        await session.flush()
        return user

    password_matches = await asyncio.to_thread(user.verify_password, password.get_secret_value())
    if not password_matches:
        user.password_hash = await asyncio.to_thread(
            User.hash_password, password.get_secret_value()
        )
    user.email = email
    user.full_name = full_name
    user.is_admin = role is Role.SUPER_ADMIN
    user.role = role.value
    user.is_active = True
    session.add(user)
    await session.flush()
    return user


async def _upsert_order(session: AsyncSession, *, user_id: int, spec: _OrderSpec) -> Order:
    result = await session.exec(select(Order).where(Order.order_sn == spec.order_sn))
    order = result.one_or_none()
    if order is None:
        order = Order(
            order_sn=spec.order_sn,
            user_id=user_id,
            status=spec.status,
            total_amount=spec.total_amount,
            items=spec.items,
            tracking_number=spec.tracking_number,
            shipping_address=spec.shipping_address,
            delivered_at=spec.delivered_at,
        )
    else:
        order.user_id = user_id
        order.status = spec.status
        order.total_amount = spec.total_amount
        order.items = spec.items
        order.tracking_number = spec.tracking_number
        order.shipping_address = spec.shipping_address
        order.delivered_at = spec.delivered_at
    session.add(order)
    await session.flush()
    return order


async def bootstrap_business_records(
    session: AsyncSession, config: LocalBootstrapConfig
) -> tuple[User, User, list[Order]]:
    """Reconcile the tenant-owned local UAT dataset in one caller-owned transaction."""
    config.validate_for_execution()
    customer = await _upsert_user(
        session,
        username=config.customer_username,
        password=config.customer_password,
        email=config.customer_email,
        full_name="林澄宇（合成 UAT 身份）",
        role=Role.CUSTOMER,
    )
    admin = await _upsert_user(
        session,
        username=config.admin_username,
        password=config.admin_password,
        email=config.admin_email,
        full_name="北辰运营专员（合成 UAT 身份）",
        role=Role.SUPER_ADMIN,
    )
    if customer.id is None or admin.id is None:
        raise LocalBootstrapError("Bootstrap user identifiers were not assigned")

    profile_result = await session.exec(
        select(UserProfile).where(UserProfile.user_id == customer.id)
    )
    profile = profile_result.one_or_none()
    if profile is None:
        profile = UserProfile(
            user_id=customer.id,
            membership_level="星选会员",
            preferred_language="zh-CN",
            timezone="Asia/Shanghai",
            total_orders=len(_ORDERS),
            lifetime_value=3086.0,
        )
    else:
        profile.membership_level = "星选会员"
        profile.preferred_language = "zh-CN"
        profile.timezone = "Asia/Shanghai"
        profile.total_orders = len(_ORDERS)
        profile.lifetime_value = 3086.0
    session.add(profile)

    orders = [await _upsert_order(session, user_id=customer.id, spec=spec) for spec in _ORDERS]
    refundable_order = orders[0]
    shipped_order = orders[2]
    if refundable_order.id is None:
        raise LocalBootstrapError("Refundable bootstrap order identifier was not assigned")

    refund_result = await session.exec(
        select(RefundApplication).where(
            RefundApplication.order_id == refundable_order.id,
            RefundApplication.user_id == customer.id,
        )
    )
    refund = refund_result.one_or_none()
    if refund is None:
        refund = RefundApplication(
            order_id=refundable_order.id,
            user_id=customer.id,
            status=RefundStatus.PENDING,
            reason_category=RefundReason.QUALITY_ISSUE,
            reason_detail="右侧耳罩出现间歇性杂音，申请人工核验后退货（合成 UAT 场景）。",
            refund_amount=Decimal("899.00"),
        )
        session.add(refund)
        await session.flush()
    if refund.id is None:
        raise LocalBootstrapError("Bootstrap refund identifier was not assigned")

    audit_result = await session.exec(
        select(AuditLog).where(AuditLog.thread_id == "uat-refund-approval-20260922")
    )
    audit = audit_result.one_or_none()
    if audit is None:
        audit = AuditLog(
            thread_id="uat-refund-approval-20260922",
            order_id=refundable_order.id,
            refund_application_id=refund.id,
            user_id=customer.id,
            trigger_reason="Medium-value refund requires operator review in the local UAT dataset.",
            risk_level=RiskLevel.MEDIUM,
            action=AuditAction.PENDING,
            audit_level="manual",
            trigger_type=AuditTriggerType.RISK,
            context_snapshot={
                "dataset": "local_uat",
                "order_sn": refundable_order.order_sn,
                "synthetic": True,
            },
            decision_metadata={"bootstrap": True},
        )
        session.add(audit)

    complaint_result = await session.exec(
        select(ComplaintTicket).where(
            ComplaintTicket.thread_id == "uat-logistics-complaint-20260922"
        )
    )
    complaint = complaint_result.one_or_none()
    if complaint is None:
        complaint = ComplaintTicket(
            user_id=customer.id,
            thread_id="uat-logistics-complaint-20260922",
            category=ComplaintCategory.LOGISTICS.value,
            order_sn=shipped_order.order_sn,
            description="大件订单运输节点超过一天未更新，请协助核查（合成 UAT 场景）。",
            expected_resolution=ExpectedResolution.APOLOGY.value,
            status=ComplaintStatus.OPEN.value,
            urgency=ComplaintUrgency.MEDIUM.value,
            assigned_to=admin.id,
        )
        session.add(complaint)

    for agent_name in _AGENT_NAMES:
        config_result = await session.exec(
            select(AgentConfig).where(AgentConfig.agent_name == agent_name)
        )
        if config_result.one_or_none() is None:
            session.add(
                AgentConfig(
                    agent_name=agent_name,
                    system_prompt=None,
                    confidence_threshold=0.7,
                    max_retries=3,
                    enabled=True,
                )
            )

    for intent_category, target_agent in _ROUTING_RULES:
        rule_result = await session.exec(
            select(RoutingRule).where(
                RoutingRule.intent_category == intent_category,
                RoutingRule.target_agent == target_agent,
            )
        )
        if rule_result.one_or_none() is None:
            session.add(
                RoutingRule(
                    intent_category=intent_category,
                    target_agent=target_agent,
                    priority=10,
                )
            )

    await session.flush()
    if audit.id is None:
        raise LocalBootstrapError("Bootstrap approval identifier was not assigned")
    notification_context = build_task_context(
        task_name="refund.notify_admin",
        tenant_id=config.tenant_id,
        user_id=admin.id,
        correlation_id="local-bootstrap:refund-review",
        operation_id=f"audit:{audit.id}:notify",
    )
    existing_event = await session.exec(
        select(OutboxEvent).where(
            OutboxEvent.tenant_id == config.tenant_id,
            OutboxEvent.idempotency_key == notification_context.idempotency_key,
        )
    )
    if existing_event.one_or_none() is None:
        await enqueue_task(
            session=session,
            task_name="refund.notify_admin",
            task_context=notification_context,
            payload={"audit_log_id": audit.id},
            event_type="local_bootstrap.refund_review_notification",
            aggregate_type="audit_log",
            aggregate_id=str(audit.id),
        )
    return customer, admin, orders


async def _ensure_tenant(config: LocalBootstrapConfig, admin_database_url: str) -> None:
    engine = create_async_engine(admin_database_url, pool_pre_ping=True)
    try:
        async with engine.begin() as connection:
            tenant_id = await connection.scalar(
                select(Tenant.id).where(Tenant.id == config.tenant_id)
            )
            if tenant_id is None:
                await connection.execute(
                    insert(Tenant).values(
                        id=config.tenant_id,
                        slug=config.tenant_id,
                        display_name=config.tenant_name,
                        status=TenantStatus.ACTIVE,
                    )
                )
            else:
                await connection.execute(
                    update(Tenant)
                    .where(col(Tenant.id) == config.tenant_id)
                    .values(
                        display_name=config.tenant_name,
                        status=TenantStatus.ACTIVE,
                    )
                )
    finally:
        await engine.dispose()


async def _upsert_knowledge_metadata(
    session: AsyncSession,
    *,
    config: LocalBootstrapConfig,
    data_dir: Path,
) -> list[KnowledgeDocument]:
    from app.storage.knowledge import get_knowledge_object_store

    object_store = get_knowledge_object_store()
    documents: list[KnowledgeDocument] = []
    for source_name, object_name in _KNOWLEDGE_SOURCES:
        source_path = data_dir / source_name
        if not source_path.is_file():
            raise LocalBootstrapError(f"Repository knowledge source is missing: {source_path}")
        content = await asyncio.to_thread(source_path.read_bytes)
        object_key = await object_store.put_bytes(
            tenant_id=config.tenant_id,
            object_name=object_name,
            content=content,
        )
        filename = f"local-uat/{source_name}"
        result = await session.exec(
            select(KnowledgeDocument).where(KnowledgeDocument.filename == filename)
        )
        document = result.one_or_none()
        content_type = "application/json" if source_path.suffix == ".json" else "text/markdown"
        if document is None:
            document = KnowledgeDocument(
                filename=filename,
                storage_path=object_key,
                content_type=content_type,
                doc_size_bytes=len(content),
                sync_status="pending",
                sync_message="Local UAT bootstrap ingestion pending",
            )
        else:
            document.storage_path = object_key
            document.content_type = content_type
            document.doc_size_bytes = len(content)
            document.sync_status = "pending"
            document.sync_message = "Local UAT bootstrap reconciliation pending"
        session.add(document)
        documents.append(document)
    await session.flush()
    return documents


async def _index_knowledge_documents(documents: list[KnowledgeDocument]) -> int:
    from app.core.utils import utc_now
    from app.tasks.knowledge_tasks import InvalidDenseEmbeddingError, ingest_knowledge_document

    total_chunks = 0
    for document in documents:
        if document.id is None:
            raise LocalBootstrapError("Knowledge document identifier was not assigned")
        try:
            for attempt in range(3):
                try:
                    result = await ingest_knowledge_document(
                        document.id, document.storage_path, document.filename
                    )
                    break
                except InvalidDenseEmbeddingError:
                    if attempt == 2:
                        raise
                    await asyncio.sleep(2**attempt)
        except Exception:
            document.sync_status = "failed"
            document.sync_message = "Local UAT bootstrap ingestion failed"
            raise
        document.sync_status = "done"
        document.sync_message = "Local UAT bootstrap ingestion completed"
        document.last_synced_at = utc_now()
        total_chunks += int(result["chunks"])
    return total_chunks


async def _index_product_catalog(data_dir: Path) -> int:
    from qdrant_client import models

    from app.core.config import settings
    from app.retrieval.client import QdrantKnowledgeClient
    from app.retrieval.embeddings import create_embedding_model

    source_path = data_dir / "products.json"
    if not source_path.is_file():
        raise LocalBootstrapError(f"Repository product source is missing: {source_path}")
    source_json = await asyncio.to_thread(source_path.read_text, encoding="utf-8")
    products = _PRODUCT_CATALOG_ADAPTER.validate_json(source_json)
    texts: list[str] = []
    for product in products:
        required = ("name", "description", "category", "sku")
        if any(not isinstance(product.get(field), str) for field in required):
            raise LocalBootstrapError("Product catalog contains an invalid required text field")
        texts.append(
            "\n".join(
                (
                    f"Product: {product['name']}",
                    f"Description: {product['description']}",
                    f"Category: {product['category']}",
                    f"SKU: {product['sku']}",
                )
            )
        )

    for attempt in range(3):
        vectors = await create_embedding_model().aembed_documents(texts)
        if all(vector and any(value != 0.0 for value in vector) for vector in vectors):
            break
        if attempt == 2:
            raise LocalBootstrapError(
                "Product catalog embedding returned an unusable all-zero dense vector"
            )
        await asyncio.sleep(2**attempt)

    client = QdrantKnowledgeClient(
        url=settings.QDRANT_URL,
        collection_name="product_catalog",
        api_key=settings.QDRANT_API_KEY.get_secret_value() or None,
    )
    try:
        await client.ensure_collection()
        points = [
            models.PointStruct(
                id=index,
                vector={"dense": vectors[index]},
                payload=product,
            )
            for index, product in enumerate(products)
        ]
        await client.upsert_chunks(points)
    finally:
        await client.aclose()
    return len(products)


async def _tenant_count(session: AsyncSession, model: type[SQLModel]) -> int:
    result = await session.exec(select(func.count()).select_from(model))
    return int(result.one())


async def bootstrap_local_data(
    config: LocalBootstrapConfig, *, data_dir: Path
) -> LocalBootstrapReport:
    """Create or reconcile the complete persisted local/UAT dataset."""
    from qdrant_client import AsyncQdrantClient, models

    from app.core.config import settings
    from app.core.database import async_session_maker
    from app.core.tenancy import namespaced_collection
    from app.models.task_receipt import TaskExecutionReceipt

    config.validate_for_execution()
    await _ensure_tenant(config, settings.MIGRATION_DATABASE_URL)

    with tenant_scope(config.tenant_id):
        async with async_session_maker() as session, session.begin():
            await bootstrap_business_records(session, config)
            documents = await _upsert_knowledge_metadata(session, config=config, data_dir=data_dir)

        await _index_knowledge_documents(documents)
        await _index_product_catalog(data_dir)

        async with async_session_maker() as session, session.begin():
            for document in documents:
                session.add(document)

        qdrant = AsyncQdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY.get_secret_value() or None,
            timeout=settings.QDRANT_TIMEOUT,
        )
        try:
            tenant_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="tenant_id",
                        match=models.MatchValue(value=config.tenant_id),
                    )
                ]
            )
            knowledge_count, product_count = await asyncio.gather(
                qdrant.count(
                    collection_name=namespaced_collection(settings.QDRANT_COLLECTION_NAME),
                    count_filter=tenant_filter,
                    exact=True,
                ),
                qdrant.count(
                    collection_name=namespaced_collection("product_catalog"),
                    count_filter=tenant_filter,
                    exact=True,
                ),
            )
        finally:
            await qdrant.close()

        async with async_session_maker() as session:
            return LocalBootstrapReport(
                tenant_id=config.tenant_id,
                users=await _tenant_count(session, User),
                memberships=await _tenant_count(session, User),
                orders=await _tenant_count(session, Order),
                refund_applications=await _tenant_count(session, RefundApplication),
                approval_records=await _tenant_count(session, AuditLog),
                complaint_tickets=await _tenant_count(session, ComplaintTicket),
                agent_configs=await _tenant_count(session, AgentConfig),
                routing_rules=await _tenant_count(session, RoutingRule),
                outbox_events=await _tenant_count(session, OutboxEvent),
                task_receipts=await _tenant_count(session, TaskExecutionReceipt),
                knowledge_documents=await _tenant_count(session, KnowledgeDocument),
                knowledge_chunks=int(knowledge_count.count),
                product_points=int(product_count.count),
            )
