from sqlmodel import select

from app.memory.extractor import FactExtractor
from app.models.memory import UserFact
from app.models.user import User
from app.task_runtime.context import build_task_context
from app.task_runtime.envelope import TaskEnvelope
from app.tasks.memory_tasks import build_extract_facts_payload, extract_and_save_facts


def _envelope(*, user_id: int, thread_id: str, history: list[dict], question: str, answer: str):
    context = build_task_context(
        task_name="memory.extract_and_save_facts",
        tenant_id="default",
        user_id=user_id,
        correlation_id=f"memory-{thread_id}",
        thread_id=thread_id,
    )
    payload = build_extract_facts_payload(
        history=history,
        question=question,
        answer=answer,
    )
    return TaskEnvelope(task_context=context, payload=payload.model_dump(mode="json")).to_message()


def test_extract_and_save_facts_deduplicates_existing_facts(db_sync_session, deterministic_llm):
    user = User(
        username="memory_user_1",
        password_hash=User.hash_password("testpass"),
        email="memory1@test.com",
        full_name="Test User",
    )
    db_sync_session.add(user)
    db_sync_session.commit()
    db_sync_session.refresh(user)
    assert user.id is not None

    thread_id = "t1"

    existing = UserFact(
        user_id=user.id,
        fact_type="preference",
        content="likes fast shipping",
        confidence=0.9,
        source_thread_id=thread_id,
    )
    db_sync_session.add(existing)
    db_sync_session.commit()

    deterministic_llm.responses = [
        (
            "",
            '[{"fact_type":"preference","content":"likes fast shipping","confidence":0.9},'
            '{"fact_type":"general","content":"is a vip","confidence":0.8}]',
        )
    ]

    result = extract_and_save_facts.run(
        envelope=_envelope(
            user_id=user.id,
            thread_id=thread_id,
            history=[{"role": "user", "content": "hi"}],
            question="send it fast",
            answer="sure, expedited shipping available",
        ),
        session=db_sync_session,
        extractor=FactExtractor(llm=deterministic_llm),
    )

    assert result["status"] == "success"
    assert result["facts_extracted"] == 1

    facts = db_sync_session.exec(
        select(UserFact).where(
            UserFact.user_id == user.id,
            UserFact.source_thread_id == thread_id,
        )
    ).all()
    assert len(facts) == 2
    contents = {f.content for f in facts}
    assert contents == {"likes fast shipping", "is a vip"}


def test_extract_and_save_facts_saves_all_when_no_existing_facts(
    db_sync_session, deterministic_llm
):
    user = User(
        username="memory_user_2",
        password_hash=User.hash_password("testpass"),
        email="memory2@test.com",
        full_name="Test User",
    )
    db_sync_session.add(user)
    db_sync_session.commit()
    db_sync_session.refresh(user)
    assert user.id is not None

    thread_id = "t2"

    deterministic_llm.responses = [
        (
            "",
            '[{"fact_type":"preference","content":"likes red","confidence":0.9}]',
        )
    ]

    result = extract_and_save_facts.run(
        envelope=_envelope(
            user_id=user.id,
            thread_id=thread_id,
            history=[],
            question="what color",
            answer="red",
        ),
        session=db_sync_session,
        extractor=FactExtractor(llm=deterministic_llm),
    )

    assert result["status"] == "success"
    assert result["facts_extracted"] == 1

    facts = db_sync_session.exec(
        select(UserFact).where(
            UserFact.user_id == user.id,
            UserFact.source_thread_id == thread_id,
        )
    ).all()
    assert len(facts) == 1
    assert facts[0].content == "likes red"
