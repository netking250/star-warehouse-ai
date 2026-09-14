import json
import os
import tempfile

import pytest

from app.task_runtime.context import build_task_context
from app.task_runtime.envelope import TaskEnvelope
from app.tasks.knowledge_tasks import load_documents, sync_knowledge_document


class TestLoadDocuments:
    def test_load_md_file(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write("# Hello")
            path = f.name
        try:
            docs = load_documents(path)
            assert len(docs) == 1
            assert "# Hello" in docs[0].page_content
        finally:
            os.unlink(path)

    def test_load_json_file(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            json.dump({"key": "value"}, f)
            path = f.name
        try:
            docs = load_documents(path)
            assert len(docs) == 1
            assert '"key": "value"' in docs[0].page_content
        finally:
            os.unlink(path)

    def test_load_unsupported_file_raises(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xyz", delete=False) as f:
            path = f.name
        try:
            with pytest.raises(ValueError, match="Unsupported file type"):
                load_documents(path)
        finally:
            os.unlink(path)


class TestSyncKnowledgeDocument:
    def test_sync_knowledge_document_not_found(self):
        context = build_task_context(
            task_name="tests.knowledge.sync",
            tenant_id="default",
            user_id=1,
            correlation_id="knowledge-sync-not-found",
        )
        envelope = TaskEnvelope(
            task_context=context,
            payload={"document_id": 99999},
        )
        with pytest.raises(ValueError, match="Knowledge document 99999 not found"):
            sync_knowledge_document.run(envelope.to_message())
