"""Canonical storage contracts and adapters."""

from app.storage.knowledge import (
    KnowledgeObjectAccessError,
    KnowledgeObjectNotFoundError,
    KnowledgeObjectStore,
    LocalKnowledgeObjectStore,
    get_knowledge_object_store,
)

__all__ = [
    "KnowledgeObjectAccessError",
    "KnowledgeObjectNotFoundError",
    "KnowledgeObjectStore",
    "LocalKnowledgeObjectStore",
    "get_knowledge_object_store",
]
