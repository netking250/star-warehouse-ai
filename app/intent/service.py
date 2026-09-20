"""意图识别服务层"""

from __future__ import annotations

import json
import logging
import re

import redis.asyncio as aioredis
from langchain_core.language_models.chat_models import BaseChatModel

from app.core.cache import CacheManager
from app.core.tenancy import namespaced_key
from app.intent.clarification import ClarificationEngine, ClarificationResponse
from app.intent.classifier import IntentClassifier
from app.intent.models import ClarificationState, IntentAction, IntentCategory, IntentResult
from app.intent.multi_intent import MultiIntentProcessor
from app.intent.safety import SafetyCheckResult, SafetyConfig, SafetyFilter
from app.intent.slot_validator import SlotValidator
from app.intent.topic_switch import TopicSwitchDetector

logger = logging.getLogger(__name__)

_CONTEXTUAL_POLICY_FOLLOW_UP = re.compile(
    r"(?:"
    r"(?:已经|我(?:买|用)了?|买了|用了|是)\s*(?:\d+|[一二三四五六七八九十百两]+)\s*(?:天|个月|年)"
    r"|(?:刚才说错|说错了|更正|其实|实际).*(?:\d+|[一二三四五六七八九十百两]+)\s*(?:天|个月|年)"
    r"|(?:那|如果).*(?:周[一二三四五六日天]|星期[一二三四五六日天])"
    r"|(?:那|如果|what if|and if)?.*(?:质量问题|缺陷|瑕疵|损坏|defect|defective|damaged)"
    r")",
    re.IGNORECASE,
)
_POLICY_HISTORY_SIGNAL = re.compile(
    r"(?:退货|退换|日历日|保修|质保|出库|工作日|return|warranty|dispatch|business days|calendar days)",
    re.IGNORECASE,
)


class IntentRecognitionService:
    def __init__(
        self,
        llm: BaseChatModel,
        redis_client: aioredis.Redis,
        result_cache_ttl: int = 300,
        session_cache_ttl: int = 1800,
        cache_manager: CacheManager | None = None,
    ):
        self.llm = llm
        self.redis = redis_client
        self.result_cache_ttl = result_cache_ttl
        self.session_cache_ttl = session_cache_ttl
        self.classifier = IntentClassifier(llm=llm)
        self.slot_validator = SlotValidator()
        self.clarification_engine = ClarificationEngine(slot_validator=self.slot_validator)
        self.topic_switch_detector = TopicSwitchDetector()
        self.multi_intent_processor = MultiIntentProcessor(classifier=self.classifier, llm=llm)
        self.safety_filter = SafetyFilter(llm=llm, config=SafetyConfig())
        self._cache = cache_manager or CacheManager(redis_client)

    async def recognize(
        self,
        query: str,
        session_id: str,
        conversation_history: list | None = None,
    ) -> IntentResult:
        intent_history = self._prior_intent_history(query, conversation_history)
        safety_result = await self.safety_filter.check(query)
        if not safety_result.is_safe:
            return self._create_safety_warning_result(query, safety_result)

        has_conversation_context = bool(intent_history)
        cached_result = None if has_conversation_context else await self._get_cached_result(query)
        if cached_result:
            # Ensure session state exists so clarify() can resolve missing slots
            state = await self._load_session_state(session_id)
            if state is None:
                state = ClarificationState(session_id=session_id)
            state.current_intent = cached_result
            await self._save_session_state(state)
            return cached_result

        state = await self._load_session_state(session_id)

        rule_result = self.classifier._classify_with_rules(query)
        if self._is_authoritative_current_rule(rule_result):
            result = rule_result
        else:
            multi_result = await self.multi_intent_processor.process(query, intent_history)
            if multi_result.is_multi_intent and multi_result.sub_intents:
                result = multi_result.sub_intents[0]
                merged_slots = {**multi_result.shared_slots, **(result.slots or {})}
                result.slots = merged_slots
                if len(multi_result.sub_intents) > 1:
                    result.slots["pending_intents"] = [
                        {
                            "primary_intent": si.primary_intent.value,
                            "secondary_intent": si.secondary_intent.value,
                            "slots": si.slots,
                        }
                        for si in multi_result.sub_intents[1:]
                    ]
            else:
                context = {"history": intent_history} if intent_history else None
                result = await self.classifier.classify(query, context)

        previous_result = state.current_intent if state else None
        result = self._resolve_contextual_follow_up(
            query,
            intent_history,
            result,
            previous_result,
        )
        switch_result = self.topic_switch_detector.detect(result, previous_result, query)
        if switch_result.is_switch and switch_result.should_reset_context:
            state = ClarificationState(session_id=session_id)

        validation = self.slot_validator.validate(result)
        if not validation.is_complete:
            result.needs_clarification = True
            result.missing_slots = validation.missing_p0_slots

        if state is None:
            state = ClarificationState(session_id=session_id)
        state.current_intent = result
        await self._save_session_state(state)

        if not has_conversation_context:
            await self._cache_result(query, result)
        return result

    @staticmethod
    def _prior_intent_history(query: str, conversation_history: list | None) -> list | None:
        """Return prior messages without duplicating the separately supplied query."""
        if not conversation_history:
            return None
        history = list(conversation_history)
        latest = history[-1]
        if (
            isinstance(latest, dict)
            and latest.get("role") == "user"
            and str(latest.get("content", "")).strip() == query.strip()
        ):
            history.pop()
        return history or None

    @staticmethod
    def _is_authoritative_current_rule(result: IntentResult) -> bool:
        """Return whether an unambiguous current-turn rule must outrank context."""
        slots = result.slots or {}
        return bool(
            (
                result.primary_intent == IntentCategory.POLICY
                and result.secondary_intent == IntentAction.CONSULT
            )
            or (
                result.primary_intent == IntentCategory.COMPLAINT
                and result.secondary_intent == IntentAction.APPLY
            )
            or (
                result.primary_intent == IntentCategory.LOGISTICS
                and result.secondary_intent == IntentAction.QUERY
                and slots.get("order_sn")
            )
            or (
                result.primary_intent == IntentCategory.AFTER_SALES
                and result.secondary_intent == IntentAction.APPLY
                and result.tertiary_intent == "REFUND"
                and slots.get("order_sn")
            )
        )

    @staticmethod
    def _resolve_contextual_follow_up(
        query: str,
        conversation_history: list | None,
        result: IntentResult,
        previous_result: IntentResult | None,
    ) -> IntentResult:
        """Resolve narrow policy follow-ups before topic-switch handling."""
        if not conversation_history or not _CONTEXTUAL_POLICY_FOLLOW_UP.search(query.strip()):
            return result
        previous_is_policy = bool(
            previous_result and previous_result.primary_intent == IntentCategory.POLICY
        )
        history_text = "\n".join(
            str(message.get("content", ""))
            for message in conversation_history
            if isinstance(message, dict)
        )
        if not previous_is_policy and not _POLICY_HISTORY_SIGNAL.search(history_text):
            return result
        return result.model_copy(
            update={
                "primary_intent": IntentCategory.POLICY,
                "secondary_intent": IntentAction.CONSULT,
                "confidence": max(result.confidence, 0.8),
                "missing_slots": [],
                "needs_clarification": False,
                "clarification_question": None,
            }
        )

    async def clarify(self, session_id: str, user_response: str) -> ClarificationResponse:
        state = await self._load_session_state(session_id)
        if not state or not state.current_intent:
            return ClarificationResponse(
                response="会话已过期，请重新描述您的问题。",
                state=ClarificationState(session_id=session_id),
                is_complete=True,
            )

        safety_result = await self.safety_filter.check(user_response)
        if not safety_result.is_safe:
            return ClarificationResponse(
                response="输入包含不安全内容，请重新输入。",
                state=state,
                is_complete=False,
            )

        validation = self.slot_validator.validate(state.current_intent)
        response = await self.clarification_engine.handle_user_response(
            state, user_response, validation
        )

        if response.state.current_intent and response.state.collected_slots:
            if response.state.current_intent.slots is None:
                response.state.current_intent.slots = {}
            response.state.current_intent.slots.update(response.state.collected_slots)

        await self._save_session_state(response.state)
        return response

    async def _load_session_state(self, session_id: str) -> ClarificationState | None:
        try:
            key = namespaced_key(f"intent:session:{session_id}")
            data = await self.redis.get(key)
            if data:
                return ClarificationState.model_validate_json(data)
        except (aioredis.RedisError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to load session state: {e}")
        return None

    async def _save_session_state(self, state: ClarificationState) -> None:
        try:
            key = namespaced_key(f"intent:session:{state.session_id}")
            await self.redis.setex(key, self.session_cache_ttl, state.model_dump_json())
        except aioredis.RedisError as e:
            logger.warning(f"Failed to save session state: {e}")

    async def _get_cached_result(self, query: str) -> IntentResult | None:
        try:
            cached = await self._cache.get_intent(query)
            if cached is not None:
                cached_result = IntentResult.model_validate(cached)
                rule_result = self.classifier._classify_with_rules(query)
                if (
                    (
                        rule_result.primary_intent == IntentCategory.COMPLAINT
                        and rule_result.secondary_intent == IntentAction.APPLY
                    )
                    or (
                        rule_result.primary_intent == IntentCategory.POLICY
                        and rule_result.secondary_intent == IntentAction.CONSULT
                    )
                    or (
                        rule_result.primary_intent == IntentCategory.LOGISTICS
                        and rule_result.secondary_intent == IntentAction.QUERY
                        and bool((rule_result.slots or {}).get("order_sn"))
                    )
                    or (
                        rule_result.primary_intent == IntentCategory.AFTER_SALES
                        and rule_result.secondary_intent == IntentAction.APPLY
                        and rule_result.tertiary_intent == "REFUND"
                        and bool((rule_result.slots or {}).get("order_sn"))
                    )
                ):
                    # Deterministic high-signal routes must not be replaced by
                    # a stale classification from Redis. This protects both
                    # read-only policy routes and explicit business actions.
                    return rule_result
                return cached_result
        except Exception as e:
            logger.warning("Failed to get cached intent result: %s", e)
        return None

    async def _cache_result(self, query: str, result: IntentResult) -> None:
        try:
            await self._cache.set_intent(query, result.model_dump())
        except Exception as e:
            logger.warning("Failed to cache intent result: %s", e)

    def _create_safety_warning_result(
        self, query: str, safety_result: SafetyCheckResult
    ) -> IntentResult:
        return IntentResult(
            primary_intent=IntentCategory.OTHER,
            secondary_intent=IntentAction.CONSULT,
            confidence=0.0,
            needs_clarification=True,
            clarification_question=f"输入包含不安全内容（{safety_result.reason}），请重新输入。",
            raw_query=query,
        )
