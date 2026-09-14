from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables import RunnableConfig

from app.model_gateway.factory import create_model_client


def create_openai_llm(
    model: str | None = None,
    *,
    route: str = "default_chat",
    temperature: float = 0,
    timeout: float | None = None,
    max_retries: int | None = None,
    default_config: RunnableConfig | None = None,
) -> BaseChatModel:
    """Compatibility wrapper returning a gateway client, never a provider SDK object."""
    if max_retries not in (None, 0):
        raise ValueError("T13 adapters do not own retries; configure retry policy in T14")
    return create_model_client(
        route,
        model_override=model,
        temperature=temperature,
        timeout=timeout,
        default_config=default_config,
    )


def create_llm(
    model: str | None = None,
    *,
    route: str = "default_chat",
    temperature: float = 0,
    timeout: float | None = None,
    default_config: RunnableConfig | None = None,
) -> BaseChatModel:
    """Return the canonical gateway-backed LangChain compatibility client."""
    return create_model_client(
        route,
        model_override=model,
        temperature=temperature,
        timeout=timeout,
        default_config=default_config,
    )
