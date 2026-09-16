# app/core/config.py
from typing import Literal

from pydantic import (
    Field,
    PostgresDsn,
    RedisDsn,
    SecretStr,
    computed_field,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.branding import PRODUCT_NAME_ZH, SERVICE_SLUG, normalize_product_name
from app.model_gateway.config import ModelRouteSettings, default_model_routes


class ConfidenceSettings(BaseSettings):
    """置信度评估配置（v4.1）"""

    model_config = SettingsConfigDict(
        env_prefix="CONFIDENCE_",
        extra="ignore",
    )

    # ========== 阈值配置 ==========
    THRESHOLD: float = Field(default=0.7, ge=0.0, le=1.0)
    HIGH_THRESHOLD: float = Field(default=0.8, ge=0.0, le=1.0)
    MEDIUM_THRESHOLD: float = Field(default=0.5, ge=0.0, le=1.0)
    LOW_THRESHOLD: float = Field(default=0.3, ge=0.0, le=1.0)

    # ========== 信号权重配置 ==========
    RAG_WEIGHT: float = Field(default=0.3, ge=0.0, le=1.0)
    LLM_WEIGHT: float = Field(default=0.5, ge=0.0, le=1.0)
    EMOTION_WEIGHT: float = Field(default=0.2, ge=0.0, le=1.0)

    # ========== 超时配置 ==========
    CALCULATION_TIMEOUT_SECONDS: float = Field(default=3.0, ge=1.0, le=10.0)

    # ========== 情感检测配置 ==========
    EMOTION_HISTORY_ROUNDS: int = Field(default=3, ge=1, le=10)

    # ========== LLM 解析配置 ==========
    LLM_PARSE_MAX_RETRIES: int = Field(default=3, ge=1, le=10)
    LLM_PARSE_RETRY_DELAY: float = Field(default=0.5, ge=0.1, le=5.0)

    # ========== 成本优化配置 ==========
    EVALUATION_MODEL: str = "qwen-turbo"
    ENABLE_CACHE: bool = True
    CACHE_TTL_SECONDS: int = 3600
    SKIP_LLM_ON_CLEAR_RAG: bool = True
    CLEAR_RAG_THRESHOLD_HIGH: float = 0.9
    CLEAR_RAG_THRESHOLD_LOW: float = 0.3

    @property
    def default_weights(self) -> dict[str, float]:
        return {
            "rag": self.RAG_WEIGHT,
            "llm": self.LLM_WEIGHT,
            "emotion": self.EMOTION_WEIGHT,
        }

    def get_audit_level(self, confidence: float) -> str:
        if confidence >= self.HIGH_THRESHOLD:
            return "none"
        elif confidence >= self.MEDIUM_THRESHOLD:
            return "auto"
        else:
            return "manual"


class Settings(BaseSettings):
    PROJECT_NAME: str = PRODUCT_NAME_ZH
    SERVICE_NAME: str = SERVICE_SLUG
    ALERT_DEDUP_PREFIX: str = SERVICE_SLUG
    API_V1_STR: str
    ENVIRONMENT: str = "development"
    LOCAL_BOOTSTRAP_TENANT_ID: str = "default"

    # Database
    POSTGRES_SERVER: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: SecretStr
    POSTGRES_DB: str
    POSTGRES_PORT: int
    POSTGRES_RUNTIME_USER: str | None = None
    POSTGRES_RUNTIME_PASSWORD: SecretStr | None = None
    POSTGRES_MAINTENANCE_USER: str | None = None
    POSTGRES_MAINTENANCE_PASSWORD: SecretStr | None = None
    DB_CAPABILITY: Literal["runtime", "maintenance"] = "runtime"

    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_RECYCLE: int = 1800
    DB_POOL_TIMEOUT: int = 15
    DB_CONNECT_TIMEOUT: int = 10
    DB_STATEMENT_TIMEOUT: int = 5000

    @computed_field
    @property
    def DATABASE_URL(self) -> str:
        username, password = self._application_database_credentials()
        return self._database_url(
            scheme="postgresql+asyncpg",
            username=username,
            password=password,
        )

    @computed_field
    @property
    def SYNC_DATABASE_URL(self) -> str:
        username, password = self._application_database_credentials()
        return self._database_url(
            scheme="postgresql",
            username=username,
            password=password,
        )

    @computed_field
    @property
    def MIGRATION_DATABASE_URL(self) -> str:
        """Return the administrative URL reserved for Alembic and role provisioning."""
        return self._database_url(
            scheme="postgresql+asyncpg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
        )

    def _application_database_credentials(self) -> tuple[str, SecretStr]:
        if self.DB_CAPABILITY == "maintenance":
            if self.POSTGRES_MAINTENANCE_USER is not None and (
                self.POSTGRES_MAINTENANCE_PASSWORD is not None
            ):
                return self.POSTGRES_MAINTENANCE_USER, self.POSTGRES_MAINTENANCE_PASSWORD
        elif self.POSTGRES_RUNTIME_USER is not None and self.POSTGRES_RUNTIME_PASSWORD is not None:
            return self.POSTGRES_RUNTIME_USER, self.POSTGRES_RUNTIME_PASSWORD
        if self.POSTGRES_DB.startswith("test_"):
            return self.POSTGRES_USER, self.POSTGRES_PASSWORD
        raise ValueError(
            f"Dedicated PostgreSQL credentials are required for {self.DB_CAPABILITY!r} capability"
        )

    def _database_url(self, *, scheme: str, username: str, password: SecretStr) -> str:
        return str(
            PostgresDsn.build(
                scheme=scheme,
                username=username,
                password=password.get_secret_value(),
                host=self.POSTGRES_SERVER,
                port=self.POSTGRES_PORT,
                path=self.POSTGRES_DB,
            )
        )

    # Redis
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_DB: int = Field(default=0, ge=0)
    REDIS_PASSWORD: SecretStr

    # Redis connection pool settings
    REDIS_MAX_CONNECTIONS: int = 50
    REDIS_SOCKET_TIMEOUT: float = 5.0
    REDIS_SOCKET_CONNECT_TIMEOUT: float = 5.0
    REDIS_HEALTH_CHECK_INTERVAL: int = 30
    REDIS_RETRY_ON_TIMEOUT: bool = True
    REDIS_SOCKET_KEEPALIVE: bool = True
    REDIS_CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = 5
    REDIS_CIRCUIT_BREAKER_RECOVERY_TIMEOUT: int = 30
    REDIS_CIRCUIT_BREAKER_HALF_OPEN_MAX_CALLS: int = 3

    # Cache TTL settings (seconds)
    CACHE_TTL_INTENT: int = 3600  # 1 hour
    INTENT_CACHE_VERSION: str = "v3.1"
    CACHE_TTL_PROFILE: int = 300  # 5 minutes
    CACHE_TTL_RETRIEVAL: int = 600  # 10 minutes
    CACHE_TTL_DB_CONFIG: int = 300  # 5 minutes

    # Shadow testing
    SHADOW_TESTING_ENABLED: bool = False
    SHADOW_SAMPLE_RATE: float = 0.1  # 10% of traffic

    @computed_field
    @property
    def REDIS_URL(self) -> str:
        return str(
            RedisDsn.build(
                scheme="redis",
                host=self.REDIS_HOST,
                port=self.REDIS_PORT,
                password=self.REDIS_PASSWORD.get_secret_value(),
                path=str(self.REDIS_DB),
            )
        )

    # Legacy embedding endpoint plus Dynamic Model Gateway provider configuration
    OPENAI_BASE_URL: str
    OPENAI_API_KEY: SecretStr
    DASHSCOPE_API_KEY: SecretStr
    LLM_MODEL: str = "qwen-plus"
    MODEL_OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    MODEL_DASHSCOPE_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-api/v1"
    MODEL_GATEWAY_DEFAULT_TIMEOUT_SECONDS: float = Field(default=30.0, gt=0, le=300)
    MODEL_ROUTES: dict[str, ModelRouteSettings] = Field(default_factory=default_model_routes)
    # T14 model failure policy. These are trusted server-side bounds; request payloads cannot
    # override retry, fallback, circuit, or degradation behavior.
    MODEL_FAILURE_MAX_ATTEMPTS_PER_CANDIDATE: int = Field(default=2, ge=1, le=10)
    MODEL_FAILURE_MAX_TOTAL_ATTEMPTS: int = Field(default=4, ge=1, le=20)
    MODEL_FAILURE_TOTAL_DEADLINE_SECONDS: float = Field(default=60.0, gt=0, le=600)
    MODEL_FAILURE_BASE_BACKOFF_SECONDS: float = Field(default=0.25, ge=0, le=60)
    MODEL_FAILURE_MAX_BACKOFF_SECONDS: float = Field(default=5.0, ge=0, le=120)
    MODEL_FAILURE_JITTER_RATIO: float = Field(default=0.2, ge=0, le=1)
    MODEL_FAILURE_RETRY_AFTER_MAX_SECONDS: float = Field(default=5.0, ge=0, le=120)
    MODEL_FAILURE_CIRCUIT_FAILURE_THRESHOLD: int = Field(default=5, ge=1, le=100)
    MODEL_FAILURE_CIRCUIT_OPEN_SECONDS: float = Field(default=30.0, gt=0, le=3600)
    MODEL_FAILURE_CIRCUIT_HALF_OPEN_PROBE_SECONDS: float = Field(default=5.0, gt=0, le=300)
    MODEL_FAILURE_DEGRADATION_MODE: Literal["fail", "safe_static_response"] = "fail"
    MODEL_FAILURE_SAFE_STATIC_RESPONSE: str = (
        "The AI service is temporarily unavailable. Please try again later."
    )
    MODEL_FAILURE_RETRY_INVALID_RESPONSE: bool = False
    RUN_REAL_LLM_TESTS: bool = False
    REAL_LLM_TEST_ROUTE: str = "default_chat"
    EMBEDDING_MODEL: str = "text-embedding-v3"
    EMBEDDING_DIM: int = 1024

    # Qdrant
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: SecretStr
    QDRANT_COLLECTION_NAME: str = "knowledge_chunks"
    QDRANT_TIMEOUT: int = 10
    QDRANT_RETRIES: int = 3

    # Reranker / Rewriter
    RERANK_MODEL: str = "qwen3-rerank"
    RERANK_BASE_URL: str
    REWRITE_MODEL: str = "qwen-turbo"
    RERANK_TIMEOUT: float = 10.0
    REWRITE_TIMEOUT: float = 5.0
    REWRITE_CACHE_TTL_SECONDS: int = 3600

    # LangSmith / LangChain tracing
    LANGCHAIN_TRACING_V2: bool = False
    LANGSMITH_API_KEY: SecretStr = SecretStr("")
    LANGSMITH_PROJECT: str = SERVICE_SLUG
    LANGSMITH_OTEL_ENABLED: bool = False
    LANGSMITH_CELERY_TRACING: bool = True

    # OpenTelemetry resource/export settings. The endpoint is optional and the service name may
    # be overridden per deployment boundary (API, worker, scheduler, or outbox).
    OTEL_SERVICE_NAME: str = ""

    # Retriever
    RETRIEVER_DENSE_TOPK: int = 15
    RETRIEVER_SPARSE_TOPK: int = 15
    RETRIEVER_RRF_K: int = 60
    RETRIEVER_FINAL_TOPK: int = 5
    RETRIEVER_MULTI_QUERY: bool = False
    RETRIEVER_MULTI_QUERY_N: int = 3

    # fastembed
    FASTEMBED_CACHE_PATH: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",  # 关键：支持 CONFIDENCE__THRESHOLD=0.7
        extra="ignore",
    )

    # === 安全配置 ===
    # 建议生产环境使用: openssl rand -hex 32 生成
    SECRET_KEY: SecretStr
    ALGORITHM: str
    # Token 有效期（分钟），默认 1 天
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    JWT_ISSUER: str = "star-warehouse-ai"
    JWT_AUDIENCE: str = "star-warehouse-api"
    BROWSER_AUTH_COOKIE_NAME: str = "star_warehouse_session"
    BROWSER_AUTH_COOKIE_SECURE: bool = True
    BROWSER_AUTH_COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"
    BROWSER_POST_LOGIN_REDIRECT_PATH: str = "/app"
    OIDC_ENABLED: bool = False
    OIDC_PROVIDER_NAME: str = "oidc"
    OIDC_ISSUER: str = ""
    OIDC_CLIENT_ID: str = ""
    OIDC_CLIENT_SECRET: SecretStr = SecretStr("")
    OIDC_REDIRECT_URI: str = "http://localhost:8000/api/v1/oidc/callback"
    OIDC_ALLOWED_ALGORITHMS: list[str] = Field(default_factory=lambda: ["RS256"])
    OIDC_LINK_VERIFIED_EMAIL: bool = False
    OIDC_STATE_TTL_SECONDS: int = Field(default=300, ge=60, le=900)
    OIDC_METADATA_CACHE_SECONDS: int = Field(default=3600, ge=60, le=86400)
    OIDC_CLOCK_SKEW_SECONDS: int = Field(default=30, ge=0, le=300)
    OIDC_TIMEOUT_SECONDS: float = 5.0
    OIDC_ALLOW_INSECURE_HTTP: bool = False

    # Business-system adapters
    BUSINESS_ADAPTER_MODE: Literal["local", "sandbox", "production"] = "local"
    BUSINESS_API_BASE_URL: str = ""
    BUSINESS_API_TOKEN: SecretStr = SecretStr("")
    BUSINESS_API_ALLOW_INSECURE_HTTP: bool = False
    BUSINESS_API_TIMEOUT_SECONDS: float = Field(default=5.0, gt=0)
    BUSINESS_API_MAX_RETRIES: int = Field(default=2, ge=0, le=10)
    BUSINESS_API_CIRCUIT_FAILURE_THRESHOLD: int = Field(default=5, ge=1)
    BUSINESS_API_CIRCUIT_RECOVERY_SECONDS: float = Field(default=30.0, gt=0)

    # CORS 配置
    CORS_ORIGINS: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    # OpenAPI docs 配置（生产环境默认关闭）
    ENABLE_OPENAPI_DOCS: bool = False

    # Celery 配置
    CELERY_BROKER_URL: SecretStr
    CELERY_RESULT_BACKEND: str

    # Transactional outbox relay
    OUTBOX_BATCH_SIZE: int = 50
    OUTBOX_POLL_INTERVAL_SECONDS: float = 1.0
    OUTBOX_LEASE_SECONDS: int = 60
    OUTBOX_RETRY_BASE_SECONDS: int = 5
    OUTBOX_RETRY_MAX_SECONDS: int = 300

    # 风控阈值配置
    HIGH_RISK_REFUND_AMOUNT: float = 2000.0  # 高风险退款金额阈值
    MEDIUM_RISK_REFUND_AMOUNT: float = 500.0  # 中风险退款金额阈值

    # WebSocket 配置
    WEBSOCKET_HEARTBEAT_INTERVAL: int = 30  # 心跳间隔（秒）
    WEBSOCKET_RECONNECT_TIMEOUT: int = 60  # 重连超时（秒）

    # 轮询配置
    STATUS_POLLING_INTERVAL: int = 3  # 状态轮询间隔（秒）

    # Refund rules
    REFUND_DEADLINE_DAYS: int = 7
    NON_REFUNDABLE_CATEGORIES: list[str] = Field(
        default_factory=lambda: ["内衣", "食品", "定制商品"]
    )

    # Graph routing limits
    MAX_ROUTER_ITERATIONS: int = 5
    MAX_EVALUATOR_RETRIES: int = 3
    CONFIDENCE_RETRY_THRESHOLD: float = 0.3

    # Emotion signal word lists
    NEGATIVE_WORDS: list[str] = Field(
        default_factory=lambda: [
            "生气",
            "愤怒",
            "不满",
            "投诉",
            "差评",
            "退款",
            "骗子",
            "垃圾",
            "太差",
            "失望",
            "欺骗",
            "坑",
            "忽悠",
            "恶劣",
            "糟糕",
            "气愤",
            "恼火",
            "心烦",
        ]
    )
    URGENT_WORDS: list[str] = Field(
        default_factory=lambda: [
            "马上",
            "立刻",
            "现在",
            "急",
            "紧急",
            "hurry",
            "urgent",
            "asap",
            "立即",
            "赶紧",
            "赶快",
            "快点",
            "等着",
            "急用",
        ]
    )
    POSITIVE_WORDS: list[str] = Field(
        default_factory=lambda: [
            "谢谢",
            "感谢",
            "满意",
            "好评",
            "不错",
            "好用",
            "推荐",
            "喜欢",
            "完美",
            "优秀",
            "棒",
            "赞",
            "给力",
            "靠谱",
        ]
    )

    # Intent classification threshold
    FUNCTION_CALLING_THRESHOLD: float = 0.7

    MEMORY_RETENTION_DAYS: int = 90
    RETENTION_EXECUTION_ENABLED: bool = True
    RETENTION_BATCH_LIMIT: int = Field(default=100, ge=1, le=1000)
    RETENTION_TENANT_BATCH_LIMIT: int = Field(default=100, ge=1, le=1000)
    MEMORY_CONTEXT_TOKEN_BUDGET: int = 2048
    HISTORY_CONTEXT_TOKEN_BUDGET: int = 1024
    COMPACTION_THRESHOLD: float = 0.75
    OBSERVATION_MASKING_MAX_CHARS: int = 500
    VECTOR_MEMORY_SCORE_THRESHOLD: float = 0.5
    AGENT_CONFIG_CACHE_TTL: int = 60
    CHAT_STREAM_TIMEOUT_SECONDS: float = 45.0
    CHECKPOINT_SCHEMA_VERSION: str = "v3.1"

    # Email 配置（用于告警和通知）
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: SecretStr = SecretStr("")
    SMTP_FROM_EMAIL: str = ""
    ALERT_ADMIN_EMAILS: list[str] = Field(default_factory=list)

    # 自动告警阈值配置
    ALERT_CSAT_THRESHOLD: float = 0.7
    ALERT_COMPLAINT_WINDOW_HOURS: int = 24
    ALERT_COMPLAINT_MAX: int = 10

    # Dashboard alert thresholds (configurable)
    ALERT_TRANSFER_RATE_THRESHOLD: float = 0.3
    ALERT_CONFIDENCE_THRESHOLD: float = 0.6
    ALERT_LATENCY_MS_THRESHOLD: float = 5000.0
    SERVICE_HEALTH_URL: str = "http://localhost:8000/health"

    LOG_FORMAT: str = "json"

    KNOWLEDGE_UPLOAD_DIR: str = "uploads/knowledge"
    OTEL_EXPORTER_OTLP_ENDPOINT: str = ""
    PROMETHEUS_ENABLED: bool = False
    PROMETHEUS_URL: str = "http://localhost:9090"
    TEMPO_URL: str = "http://localhost:3200"
    GRAFANA_URL: str = "http://localhost:3000"

    # 置信度评估配置（嵌套模型）
    CONFIDENCE: ConfidenceSettings = Field(default_factory=ConfidenceSettings)

    @field_validator("PROJECT_NAME", mode="before")
    @classmethod
    def normalize_legacy_project_name(cls, value: object) -> object:
        """Normalize known v4 product names during the v5 compatibility window."""
        return normalize_product_name(value) if isinstance(value, str) else value

    @field_validator("BROWSER_AUTH_COOKIE_NAME")
    @classmethod
    def validate_browser_auth_cookie_name(cls, value: str) -> str:
        """Reject cookie names that cannot be represented safely in HTTP headers."""
        if not value or not value.replace("_", "").replace("-", "").isalnum():
            raise ValueError(
                "BROWSER_AUTH_COOKIE_NAME must contain only letters, digits, '_' or '-'"
            )
        return value

    @field_validator("BROWSER_POST_LOGIN_REDIRECT_PATH")
    @classmethod
    def validate_browser_post_login_redirect_path(cls, value: str) -> str:
        """Keep the OIDC completion redirect on this application origin."""
        if not value.startswith("/") or value.startswith("//") or "?" in value or "#" in value:
            raise ValueError("BROWSER_POST_LOGIN_REDIRECT_PATH must be an absolute local path")
        return value

    @model_validator(mode="after")
    def validate_browser_cookie_security(self) -> "Settings":
        """Fail closed for insecure production or SameSite=None cookie settings."""
        if self.ENVIRONMENT.lower() == "production" and not self.BROWSER_AUTH_COOKIE_SECURE:
            raise ValueError("Production browser authentication cookies must be Secure")
        if self.BROWSER_AUTH_COOKIE_SAMESITE == "none" and not self.BROWSER_AUTH_COOKIE_SECURE:
            raise ValueError("SameSite=None browser authentication cookies must be Secure")
        return self


def _create_settings() -> Settings:
    """Create settings from environment at runtime.

    This factory avoids top-level instantiation errors during static analysis.
    ty does not understand pydantic-settings' env-file defaulting, so we
    suppress the missing-argument diagnostic locally.
    """
    return Settings()  # ty: ignore[missing-argument]


settings: Settings = _create_settings()
