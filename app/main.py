# app/main.py
import asyncio
import contextlib
import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from opentelemetry import trace
from prometheus_client import make_asgi_app
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.v1.admin import router as admin_router
from app.api.v1.auth import router as auth_router
from app.api.v1.chat import router as chat_router
from app.api.v1.conversation import router as conversation_router
from app.api.v1.status import router as status_router
from app.api.v1.web_vitals import router as web_vitals_router
from app.api.v1.websocket import router as websocket_router
from app.authorization.route_inventory import assert_routes_classified
from app.core.branding import APP_VERSION, HEALTH_VERSION, PRODUCT_NAME_EN
from app.core.config import settings
from app.core.limiter import limiter
from app.core.logging import (
    normalize_correlation_id,
    reset_correlation_id,
    set_correlation_id,
)
from app.core.structured_logging import configure_logging
from app.core.tenancy import (
    TenantAccessError,
    TenantContextMissingError,
    clear_current_tenant,
    reset_current_tenant,
)
from app.core.tracing import is_langsmith_tracing_enabled
from app.observability.http import observe_http_request
from app.observability.metrics import (
    record_dependency_check_duration,
    set_dependency_health,
)
from app.observability.otel_setup import instrument_fastapi, setup_otel_tracing
from app.websocket.manager import get_manager
from app.websocket.redis_bridge import RedisBroadcastBridge

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    assert_routes_classified(app)
    _setup_logging()
    _setup_langsmith_tracing()
    logger.info("Starting %s v%s", PRODUCT_NAME_EN, APP_VERSION)

    if "*" in settings.CORS_ORIGINS:
        raise RuntimeError(
            "CORS allow_origins=['*'] combined with allow_credentials=True is not allowed. "
            "Please restrict CORS_ORIGINS to specific domains."
        )

    from app.adapters import build_adapters
    from app.agents.account import AccountAgent
    from app.agents.cart import CartAgent
    from app.agents.complaint import ComplaintAgent
    from app.agents.evaluator import ConfidenceEvaluator
    from app.agents.logistics import LogisticsAgent
    from app.agents.order import OrderAgent
    from app.agents.payment import PaymentAgent
    from app.agents.policy import PolicyAgent
    from app.agents.product import ProductAgent
    from app.agents.router import IntentRouterAgent
    from app.agents.supervisor import SupervisorAgent
    from app.core.cache import CacheManager
    from app.core.database import async_engine
    from app.core.redis import create_redis_client
    from app.graph.checkpointer import OptimizedRedisCheckpoint
    from app.graph.workflow import compile_app_graph
    from app.intent.service import IntentRecognitionService
    from app.memory.structured_manager import StructuredMemoryManager
    from app.memory.vector_manager import VectorMemoryManager
    from app.model_gateway.factory import create_model_client, get_model_gateway
    from app.retrieval import create_retriever
    from app.services.order_service import OrderService
    from app.tools import (
        AccountTool,
        CartTool,
        ComplaintTool,
        LogisticsTool,
        PaymentTool,
        ProductTool,
    )
    from app.tools.registry import ToolRegistry

    try:
        redis_client = create_redis_client()
        checkpointer = OptimizedRedisCheckpoint(redis_client=redis_client)
        await checkpointer.setup()
        app.state.checkpointer = checkpointer

        model_gateway = get_model_gateway()
        llm = create_model_client("default_chat", gateway=model_gateway)
        intent_llm = create_model_client("intent", gateway=model_gateway)
        eval_llm = create_model_client("evaluation", gateway=model_gateway)
        cache_manager = CacheManager(redis_client)
        intent_service = IntentRecognitionService(
            llm=intent_llm, redis_client=redis_client, cache_manager=cache_manager
        )
        structured_manager = StructuredMemoryManager(cache_manager=cache_manager)
        router_agent = IntentRouterAgent(
            intent_service=intent_service, llm=llm, structured_manager=structured_manager
        )
        retriever = create_retriever(
            llm=llm, redis_client=redis_client, cache_manager=cache_manager
        )
        adapters = build_adapters(redis_client, rewriter=retriever.rewriter)

        app.state.manager = get_manager()

        bridge = RedisBroadcastBridge(settings.REDIS_URL)

        async def _redis_listener() -> None:
            try:
                async for payload in bridge.subscribe("admins"):
                    if payload.get("room") == "admins":
                        await get_manager().broadcast_to_admins(payload.get("data", {}))
            except asyncio.CancelledError:
                raise
            except (ConnectionError, OSError, RuntimeError):
                logger.exception("Redis broadcast listener error")

        listener_task = asyncio.create_task(_redis_listener())

        tool_registry = ToolRegistry()
        tool_registry.register(LogisticsTool(logistics_port=adapters.logistics))
        tool_registry.register(AccountTool(identity_port=adapters.identity))
        tool_registry.register(
            PaymentTool(
                payment_port=adapters.payment,
                invoice_port=adapters.invoice,
                order_port=adapters.order,
                refund_port=adapters.refund,
            )
        )
        tool_registry.register(ProductTool(product_port=adapters.product))
        tool_registry.register(CartTool(cart_port=adapters.cart))
        tool_registry.register(ComplaintTool())
        app.state.tool_registry = tool_registry
        policy_agent = PolicyAgent(retriever=retriever, llm=llm)
        order_agent = OrderAgent(order_service=OrderService(order_port=adapters.order), llm=llm)
        logistics_agent = LogisticsAgent(tool_registry=tool_registry, llm=llm)
        account_agent = AccountAgent(tool_registry=tool_registry, llm=llm)
        payment_agent = PaymentAgent(tool_registry=tool_registry, llm=llm)
        product_agent = ProductAgent(tool_registry=tool_registry, llm=llm)
        cart_agent = CartAgent(tool_registry=tool_registry, llm=llm)
        complaint_agent = ComplaintAgent(llm=llm)
        supervisor_agent = SupervisorAgent(llm=llm)
        evaluator = ConfidenceEvaluator(llm=eval_llm)
        vector_manager = VectorMemoryManager(cache_manager=cache_manager)

        # Fail fast on Qdrant connectivity and ensure manual uvicorn startup has
        # all collections even when the Docker seed command was not used.
        await retriever.qdrant_client.ensure_collection()
        await vector_manager.ensure_collection()
        from app.retrieval.client import QdrantKnowledgeClient

        product_collection = QdrantKnowledgeClient(
            url=settings.QDRANT_URL,
            collection_name="product_catalog",
            api_key=settings.QDRANT_API_KEY.get_secret_value() or None,
        )
        try:
            await product_collection.ensure_collection()
        finally:
            await product_collection.aclose()

        app.state.intent_service = intent_service
        app.state.llm = llm
        app.state.model_gateway = model_gateway
        app.state.vector_manager = vector_manager
        app.state.redis_client = redis_client
        app.state.cache_manager = cache_manager
        app.state.adapters = adapters

        from app.services.alert_service import AlertService

        app.state.alert_service = AlertService(redis=redis_client)
        logger.info("AlertService initialized")

        app.state.app_graph = await compile_app_graph(
            router_agent=router_agent,
            policy_agent=policy_agent,
            order_agent=order_agent,
            logistics_agent=logistics_agent,
            account_agent=account_agent,
            payment_agent=payment_agent,
            evaluator=evaluator,
            checkpointer=checkpointer,
            supervisor_agent=supervisor_agent,
            product_agent=product_agent,
            cart_agent=cart_agent,
            complaint_agent=complaint_agent,
            llm=llm,
            structured_manager=structured_manager,
            vector_manager=vector_manager,
        )
        logger.info(" Infrastructure is ready.")

        yield
    finally:
        logger.info("Shutting down...")
        with contextlib.suppress(NameError):
            if listener_task is not None:
                listener_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await listener_task
        with contextlib.suppress(NameError):
            if bridge is not None:
                await bridge.close()
        with contextlib.suppress(NameError):
            if redis_client is not None:
                await redis_client.close()
        with contextlib.suppress(NameError):
            if retriever is not None:
                await retriever.qdrant_client.aclose()
        with contextlib.suppress(NameError):
            if vector_manager is not None:
                await vector_manager.aclose()
        with contextlib.suppress(NameError):
            if model_gateway is not None:
                await model_gateway.aclose()
        with contextlib.suppress(NameError):
            if adapters is not None:
                await adapters.aclose()
        await async_engine.dispose()


def _setup_langsmith_tracing() -> None:
    """Configure LangSmith tracing based on application settings.

    If LANGSMITH_API_KEY is configured, automatically set the environment
    variables required for LangChain/LangSmith automatic tracing. This ensures
    all LLM calls (via LangChain) are traced without requiring code changes
    at each call site.
    """
    if not is_langsmith_tracing_enabled():
        os.environ["LANGCHAIN_TRACING_V2"] = "false"
        return

    # Set required environment variables for LangChain automatic tracing
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_API_KEY", settings.LANGSMITH_API_KEY.get_secret_value())
    os.environ.setdefault("LANGCHAIN_PROJECT", settings.LANGSMITH_PROJECT)

    logger.info(
        "LangSmith tracing enabled",
        extra={"event": "langsmith_tracing_enabled", "project": settings.LANGSMITH_PROJECT},
    )


def _setup_logging() -> None:
    configure_logging(log_format=settings.LOG_FORMAT)


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=APP_VERSION,
    description="星仓原生 AI 智能客服平台 · Star Warehouse native AI customer service",
    docs_url="/docs" if settings.ENABLE_OPENAPI_DOCS else None,
    redoc_url="/redoc" if settings.ENABLE_OPENAPI_DOCS else None,
    openapi_url="/openapi.json" if settings.ENABLE_OPENAPI_DOCS else None,
    lifespan=lifespan,
)
app.state.limiter = limiter


def _rate_limit_handler(request: Request, exc: Exception) -> Response:
    if not isinstance(exc, RateLimitExceeded):
        raise TypeError(f"Unexpected exception type: {type(exc).__name__}")
    return _rate_limit_exceeded_handler(request, exc)


app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)


def _tenant_access_handler(request: Request, exc: Exception) -> JSONResponse:
    """Map fail-closed tenant resolution errors without exposing tenant data."""
    if not isinstance(exc, TenantAccessError):
        raise TypeError(f"Unexpected exception type: {type(exc).__name__}")
    status_code = 400 if isinstance(exc, TenantContextMissingError) else 403
    return JSONResponse(status_code=status_code, content={"detail": exc.code})


app.add_exception_handler(TenantAccessError, _tenant_access_handler)


@app.middleware("http")
async def tenant_context_middleware(request: Request, call_next):
    """Start every request unbound and prevent tenant-context leakage."""
    token = clear_current_tenant()
    try:
        return await call_next(request)
    finally:
        reset_current_tenant(token)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    cid = normalize_correlation_id(request.headers.get("x-correlation-id"))
    token = set_correlation_id(cid)
    try:
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = cid
        return response
    finally:
        reset_correlation_id(token)


# 1. 配置跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Accept", "Authorization", "Content-Type", "X-Correlation-ID", "X-CSRF-Token"],
)


# 2. OpenTelemetry trace-id response middleware (after CORS)
@app.middleware("http")
async def trace_id_middleware(request: Request, call_next):
    response = await call_next(request)
    span = trace.get_current_span()
    span_context = span.get_span_context()
    if span_context.is_valid:
        trace_id = format(span_context.trace_id, "032x")
        response.headers["X-Trace-ID"] = trace_id
    return response


@app.middleware("http")
async def http_observability_middleware(request: Request, call_next):
    """Record normalized application HTTP RED metrics around the request pipeline."""
    return await observe_http_request(request, call_next)


# 3. Rate limiting middleware
app.add_middleware(SlowAPIMiddleware)

# 3. 注册路由
app.include_router(auth_router, prefix=settings.API_V1_STR, tags=["Auth"])  # v4.0 新增
app.include_router(chat_router, prefix=settings.API_V1_STR, tags=["Chat"])
app.include_router(conversation_router, prefix=settings.API_V1_STR, tags=["Conversation Runtime"])
app.include_router(status_router, prefix=settings.API_V1_STR, tags=["Status"])
app.include_router(web_vitals_router, prefix=settings.API_V1_STR, tags=["Metrics"])
app.include_router(admin_router, prefix=settings.API_V1_STR, tags=["Admin"])
app.include_router(websocket_router, prefix=settings.API_V1_STR, tags=["WebSocket"])

app.mount("/metrics", make_asgi_app())

# 3. 静态文件托管
frontend_dist_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")


def _frontend_unavailable() -> JSONResponse:
    """Return an explicit response when the optional frontend build is absent."""
    return JSONResponse(
        status_code=503,
        content={
            "detail": ("Frontend assets are unavailable; build the frontend before serving the UI.")
        },
    )


def _frontend_file(path: str) -> Response:
    """Serve a frontend file or fail explicitly when the build is unavailable."""
    if os.path.isfile(path):
        return FileResponse(path)
    return _frontend_unavailable()


if os.path.exists(frontend_dist_path):
    app.mount(
        "/customer",
        StaticFiles(directory=os.path.join(frontend_dist_path, "customer")),
        name="customer_assets",
    )
    app.mount(
        "/shared",
        StaticFiles(directory=os.path.join(frontend_dist_path, "shared")),
        name="shared_assets",
    )
    app.mount(
        "/assets",
        StaticFiles(directory=os.path.join(frontend_dist_path, "assets")),
        name="root_assets",
    )


@app.get("/app")
@app.get("/app/{full_path:path}")
async def serve_customer_spa(full_path: str = "") -> Response:
    """Serve the customer SPA, or report that frontend assets are unavailable."""
    base_dir = os.path.realpath(os.path.join(frontend_dist_path, "customer"))
    file_path = os.path.realpath(os.path.join(base_dir, full_path))
    if file_path.startswith(base_dir) and os.path.isfile(file_path):
        return FileResponse(file_path)
    return _frontend_file(os.path.join(frontend_dist_path, "index.html"))


@app.get("/admin")
@app.get("/admin/{full_path:path}")
async def serve_admin_spa(full_path: str = "") -> Response:
    """Serve the administration SPA, or report that frontend assets are unavailable."""
    base_dir = os.path.realpath(os.path.join(frontend_dist_path, "admin"))
    file_path = os.path.realpath(os.path.join(base_dir, full_path))
    if file_path.startswith(base_dir) and os.path.isfile(file_path):
        return FileResponse(file_path)
    return _frontend_file(os.path.join(frontend_dist_path, "admin.html"))


@app.get("/favicon.svg")
async def serve_favicon() -> Response:
    """Serve the shared favicon, or report that frontend assets are unavailable."""
    return _frontend_file(os.path.join(frontend_dist_path, "favicon.svg"))


@app.get("/icons.svg")
async def serve_icons() -> Response:
    """Serve the shared icon sprite, or report that frontend assets are unavailable."""
    return _frontend_file(os.path.join(frontend_dist_path, "icons.svg"))


@app.get("/index.html")
async def serve_index_html() -> Response:
    """Serve the customer entry document, or report that frontend assets are unavailable."""
    return _frontend_file(os.path.join(frontend_dist_path, "index.html"))


@app.get("/admin.html")
async def serve_admin_html() -> Response:
    """Serve the administration entry document, or report that frontend assets are unavailable."""
    return _frontend_file(os.path.join(frontend_dist_path, "admin.html"))


@app.get("/")
async def root() -> Response:
    """Redirect to the customer SPA when built, otherwise fail explicitly."""
    if os.path.isdir(frontend_dist_path):
        return RedirectResponse(url="/app")
    return _frontend_unavailable()


@app.get("/health")
async def health_check():
    from sqlalchemy import text

    from app.core.database import async_engine
    from app.core.redis import RedisHealthCheck, create_redis_client

    health_status = {
        "status": "healthy",
        "version": HEALTH_VERSION,
        "dependencies": {},
    }

    def _record_dependency(component: str, healthy: bool, started: float) -> None:
        """Record dependency health without changing the health response contract."""
        try:
            set_dependency_health(component=component, healthy=healthy)
            record_dependency_check_duration(
                component=component,
                duration_seconds=time.perf_counter() - started,
            )
        except Exception as telemetry_error:
            logger.debug(
                "Dependency metric recording unavailable: %s",
                type(telemetry_error).__name__,
            )

    started = time.perf_counter()
    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            await conn.commit()
        health_status["dependencies"]["database"] = "connected"
        _record_dependency("database", True, started)
    except Exception as exc:
        del exc
        health_status["dependencies"]["database"] = "unavailable"
        _record_dependency("database", False, started)
        health_status["status"] = "degraded"

    started = time.perf_counter()
    try:
        redis_client = create_redis_client()
        health_check = RedisHealthCheck(redis_client)
        redis_healthy = await health_check.check()
        if redis_healthy:
            health_status["dependencies"]["redis"] = "connected"
            _record_dependency("redis", True, started)
        else:
            health_status["dependencies"]["redis"] = "unavailable"
            _record_dependency("redis", False, started)
            health_status["status"] = "degraded"
    except Exception as exc:
        del exc
        health_status["dependencies"]["redis"] = "unavailable"
        _record_dependency("redis", False, started)
        health_status["status"] = "degraded"

    started = time.perf_counter()
    try:
        from qdrant_client import AsyncQdrantClient

        from app.core.config import settings

        qdrant = AsyncQdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY.get_secret_value() if settings.QDRANT_API_KEY else None,
            timeout=settings.QDRANT_TIMEOUT,
        )
        await qdrant.get_collections()
        await qdrant.close()
        health_status["dependencies"]["qdrant"] = "connected"
        _record_dependency("qdrant", True, started)
    except Exception as exc:
        del exc
        health_status["dependencies"]["qdrant"] = "unavailable"
        _record_dependency("qdrant", False, started)
        health_status["status"] = "degraded"

    return health_status


assert_routes_classified(app)
setup_otel_tracing(service_name=settings.OTEL_SERVICE_NAME or f"{settings.SERVICE_NAME}-api")
instrument_fastapi(app)
