from contextlib import nullcontext
from types import SimpleNamespace

from app.storage.knowledge import KnowledgeObjectNotFoundError
from app.task_runtime.context import build_task_context
from app.task_runtime.envelope import TaskEnvelope
from app.tasks.knowledge_tasks import sync_knowledge_document


class _FakeResult:
    def __init__(self, document: SimpleNamespace) -> None:
        self._document = document

    def one_or_none(self) -> SimpleNamespace:
        return self._document


class _FakeSession:
    def __init__(self, document: SimpleNamespace) -> None:
        self.document = document
        self.commits = 0

    def __enter__(self) -> "_FakeSession":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def exec(self, _statement: object) -> _FakeResult:
        return _FakeResult(self.document)

    def add(self, _document: object) -> None:
        return None

    def commit(self) -> None:
        self.commits += 1


def test_missing_source_on_final_attempt_sets_terminal_failure(monkeypatch) -> None:
    document = SimpleNamespace(
        id=29,
        storage_path="tenant/default/missing.txt",
        filename="missing.txt",
        sync_status="pending",
        sync_message=None,
        updated_at=None,
        last_synced_at=None,
    )
    session = _FakeSession(document)

    async def fail_ingestion(*_args: object) -> dict[str, object]:
        raise KnowledgeObjectNotFoundError("Knowledge source object is missing")

    monkeypatch.setattr("app.tasks.knowledge_tasks.sync_session_maker", lambda: session)
    monkeypatch.setattr("app.tasks.knowledge_tasks.ingest_knowledge_document", fail_ingestion)
    monkeypatch.setattr(
        "app.tasks.knowledge_tasks.task_execution_scope",
        lambda *_args, **_kwargs: nullcontext(),
    )

    context = build_task_context(
        task_name="knowledge.sync_document",
        tenant_id="default",
        user_id=1,
        correlation_id="missing-source-final-attempt",
    )
    envelope = TaskEnvelope(task_context=context, payload={"document_id": 29})

    sync_knowledge_document.push_request(id="missing-source-task", retries=3)
    try:
        result = sync_knowledge_document.run(envelope.to_message())
    finally:
        sync_knowledge_document.pop_request()

    assert result == {
        "status": "failed",
        "document_id": 29,
        "message": "同步失败，已达到最大重试次数",
    }
    assert document.sync_status == "failed"
    assert document.sync_message == "同步失败，已达到最大重试次数"
    assert session.commits == 2
