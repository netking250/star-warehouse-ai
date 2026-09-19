"""意图分类器测试

测试场景:
- Function Calling成功
- Function Calling无结果时降级到规则匹配
- 规则匹配（直接调用 _classify_with_rules）
- 三级意图验证（合法和非法）
- LLM异常直接抛出
"""

import pytest

from app.intent.classifier import IntentClassifier
from app.intent.models import IntentAction, IntentCategory, IntentResult


@pytest.fixture
def classifier(deterministic_llm):
    """创建带Deterministic LLM的分类器"""
    return IntentClassifier(llm=deterministic_llm)


# ========== Layer 1: Function Calling Tests ==========


@pytest.mark.asyncio
async def test_function_calling_success(classifier, deterministic_llm):
    """测试Function Calling成功场景"""
    deterministic_llm.tool_calls = [
        {
            "name": "classify_intent",
            "args": {
                "primary_intent": "ORDER",
                "secondary_intent": "QUERY",
                "tertiary_intent": "ORDER_TRACKING_DETAIL",
                "confidence": 0.95,
                "slots": {"order_sn": "SN20240001"},
            },
        }
    ]

    result = await classifier.classify("我想查订单SN20240001")

    assert result.primary_intent == IntentCategory.ORDER
    assert result.secondary_intent == IntentAction.QUERY


@pytest.mark.asyncio
async def test_function_calling_no_tool_calls(classifier, deterministic_llm):
    """测试Function Calling无工具调用时降级到规则匹配"""
    deterministic_llm.tool_calls = []

    result = await classifier.classify("我想退货")

    assert result.primary_intent == IntentCategory.AFTER_SALES
    assert result.secondary_intent == IntentAction.APPLY


@pytest.mark.asyncio
async def test_function_calling_exception_graceful_fallback(classifier, deterministic_llm):
    """测试Function Calling异常时降级到规则匹配"""
    deterministic_llm.exception = ValueError("Function calling failed")

    result = await classifier.classify("运费怎么算")

    assert result.primary_intent == IntentCategory.POLICY
    assert result.secondary_intent == IntentAction.CONSULT


# ========== Layer 2: Rule Matching Tests ==========


def test_rule_matching_order_query(classifier):
    """测试规则匹配 - 订单查询"""
    result = classifier._classify_with_rules("我的订单SN12345到哪了")

    assert result.primary_intent == IntentCategory.ORDER
    assert result.secondary_intent == IntentAction.QUERY
    assert "matched_pattern" in result.slots


def test_rule_matching_after_sales_apply(classifier):
    """测试规则匹配 - 售后申请"""
    result = classifier._classify_with_rules("我想申请退货")

    assert result.primary_intent == IntentCategory.AFTER_SALES
    assert result.secondary_intent == IntentAction.APPLY


def test_rule_matching_policy_consult(classifier):
    """测试规则匹配 - 政策咨询"""
    result = classifier._classify_with_rules("运费怎么算")

    assert result.primary_intent == IntentCategory.POLICY
    assert result.secondary_intent == IntentAction.CONSULT


def test_rule_matching_aurora_policy_consultation(classifier):
    result = classifier._classify_with_rules("What is the Aurora Chair return window?")

    assert result.primary_intent == IntentCategory.POLICY
    assert result.secondary_intent == IntentAction.CONSULT


def test_rule_matching_product_return_eligibility_is_policy_not_refund_apply(classifier):
    result = classifier._classify_with_rules("\u6211\u7684 Aurora Chair \u80fd\u9000\u5417\uff1f")

    assert result.primary_intent == IntentCategory.POLICY
    assert result.secondary_intent == IntentAction.CONSULT


def test_rule_matching_product_return_period_duration_is_policy(classifier):
    result = classifier._classify_with_rules("Aurora Chair 的退货期多久？")

    assert result.primary_intent == IntentCategory.POLICY
    assert result.secondary_intent == IntentAction.CONSULT


@pytest.mark.parametrize(
    "query",
    [
        "What is the Aurora Chair return window?",
        "\u6781\u5149\u6905\u4e70\u56de\u6765\u591a\u4e45\u4ee5\u5185\u80fd\u9000\uff1f",
        "If the Aurora Chair has a verified defect, who pays return shipping?",
        "\u4e0d\u662f\u8d28\u91cf\u95ee\u9898\uff0c\u6211\u9000\u8d27\u7684\u8bdd\u8fd0\u8d39\u8c01\u51fa\uff1f",
        "\u4e0d\u662f\u8d28\u91cf\u95ee\u9898\uff0c\u6211\u53ea\u662f\u60f3\u9000\u8d27\uff0c\u8fd0\u8d39\u8c01\u51fa\uff1f",
        "Nova Desk \u4fdd\u4fee\u591a\u4e45\uff1f",
        "How long is the Nova Desk warranty?",
        "East Harbor \u7684\u8ba2\u5355\u901a\u5e38\u591a\u4e45\u51fa\u5e93\uff1f",
        "When does East Harbor normally dispatch?",
        "\u8fd9\u4e2a\u6905\u5b50\u4e70\u4e86\u5341\u5929\uff0c\u4e0d\u559c\u6b22\u4e86\uff0c\u8fd8\u80fd\u9000\u5417\uff1f",
        "\u684c\u5b50\u7528\u4e86\u4e24\u5e74\u591a\u574f\u4e86\uff0c\u8fd8\u5728\u4fdd\u4fee\u5417\uff1f",
        "Aurora Chair \u4e0b\u5468\u4e94\u4f1a\u4e0d\u4f1a\u964d\u4ef7\uff1f",
    ],
)
def test_rule_matching_known_policy_questions_as_read_only_consultation(classifier, query):
    result = classifier._classify_with_rules(query)

    assert result.primary_intent == IntentCategory.POLICY
    assert result.secondary_intent == IntentAction.CONSULT


def test_rule_matching_transaction_controls_keep_stateful_actions(classifier):
    order = classifier._classify_with_rules("查一下订单 SN649201")
    logistics = classifier._classify_with_rules("订单 SN649201 的物流到哪了？")
    refund = classifier._classify_with_rules("我要退订单 SN649201")
    complaint = classifier._classify_with_rules("我要投诉，请帮我提交投诉")

    assert (order.primary_intent, order.secondary_intent) == (
        IntentCategory.ORDER,
        IntentAction.QUERY,
    )
    assert (logistics.primary_intent, logistics.secondary_intent) == (
        IntentCategory.LOGISTICS,
        IntentAction.QUERY,
    )
    assert (refund.primary_intent, refund.secondary_intent) == (
        IntentCategory.AFTER_SALES,
        IntentAction.APPLY,
    )
    assert (complaint.primary_intent, complaint.secondary_intent) == (
        IntentCategory.COMPLAINT,
        IntentAction.APPLY,
    )

    order_refund_status = classifier._classify_with_rules(
        "What is the refund status for order SN649201?"
    )
    assert order_refund_status.primary_intent != IntentCategory.POLICY


def test_rule_matching_logistics_request_with_order_number_extracts_order_sn(classifier):
    result = classifier._classify_with_rules(
        "\u67e5\u4e00\u4e0b\u8ba2\u5355 SN649201 \u7684\u7269\u6d41\u3002"
    )

    assert (result.primary_intent, result.secondary_intent) == (
        IntentCategory.LOGISTICS,
        IntentAction.QUERY,
    )
    assert result.slots["order_sn"] == "SN649201"


def test_rule_matching_refund_request_with_order_number_is_authoritative(classifier):
    result = classifier._classify_with_rules(
        "\u8ba2\u5355 SN649201 \u6211\u4e0d\u60f3\u8981\u4e86\uff0c\u5e2e\u6211\u7533\u8bf7\u9000\u8d27\u3002"
    )

    assert (result.primary_intent, result.secondary_intent) == (
        IntentCategory.AFTER_SALES,
        IntentAction.APPLY,
    )
    assert result.tertiary_intent == "REFUND"
    assert result.slots["order_sn"] == "SN649201"
    assert result.slots["action_type"] == "REFUND"


def test_rule_matching_return_shipping_fee_consult(classifier):
    result = classifier._classify_with_rules("退货运费由谁承担？")

    assert result.primary_intent == IntentCategory.POLICY
    assert result.secondary_intent == IntentAction.CONSULT


def test_rule_matching_cart_add(classifier):
    """测试规则匹配 - 添加购物车"""
    result = classifier._classify_with_rules("把这个加入购物车")

    assert result.primary_intent == IntentCategory.CART
    assert result.secondary_intent == IntentAction.ADD


def test_rule_matching_default_other(classifier):
    """测试规则匹配 - 无匹配时默认OTHER"""
    result = classifier._classify_with_rules("xyzabc123")

    assert result.primary_intent == IntentCategory.OTHER
    assert result.secondary_intent == IntentAction.CONSULT
    assert result.confidence == 0.3


def test_rule_matching_logistics_query(classifier):
    """测试规则匹配 - 物流查询"""
    result = classifier._classify_with_rules("快递到哪了")

    assert result.primary_intent == IntentCategory.LOGISTICS
    assert result.secondary_intent == IntentAction.QUERY


def test_rule_matching_greeting(classifier):
    """测试规则匹配 - 问候语"""
    result = classifier._classify_with_rules("你好")

    assert result.primary_intent == IntentCategory.OTHER
    assert result.secondary_intent == IntentAction.CONSULT


def test_explicit_complaint_rule_is_state_changing(classifier):
    query = (
        "\u6211\u8981\u6295\u8bc9\u8fd9\u6b21\u552e\u540e\u670d\u52a1\uff0c"
        "\u8bf7\u5e2e\u6211\u63d0\u4ea4\u6295\u8bc9\u3002"
    )

    result = classifier._classify_with_rules(query)

    assert result.primary_intent == IntentCategory.COMPLAINT
    assert result.secondary_intent == IntentAction.APPLY
    assert result.confidence == 1.0


@pytest.mark.parametrize(
    "query",
    [
        "\u6211\u8981\u6295\u8bc9\uff0c\u8bf7\u5e2e\u6211\u521b\u5efa\u6295\u8bc9\u5de5\u5355\u3002",
        "\u5ba2\u670d\u6001\u5ea6\u5f88\u5dee\uff0c\u6211\u8981\u6b63\u5f0f\u6295\u8bc9\u3002",
        "I want to file a complaint ticket.",
    ],
)
def test_explicit_complaint_variants_are_authoritative(classifier, query):
    result = classifier._classify_with_rules(query)

    assert result.primary_intent == IntentCategory.COMPLAINT
    assert result.secondary_intent == IntentAction.APPLY
    assert result.confidence == 1.0


@pytest.mark.parametrize(
    "query",
    [
        "\u8fd9\u4e2a\u4ea7\u54c1\u6709\u7f3a\u9677\u600e\u4e48\u529e",
        "\u6211\u53ea\u662f\u60f3\u77e5\u9053\u9000\u8d27\u89c4\u5219",
        "\u7269\u6d41\u5f88\u6162\u600e\u4e48\u529e",
    ],
)
def test_consultation_does_not_become_state_changing_complaint(classifier, query):
    result = classifier._classify_with_rules(query)

    assert not (
        result.primary_intent == IntentCategory.COMPLAINT
        and result.secondary_intent == IntentAction.APPLY
    )


@pytest.mark.asyncio
async def test_explicit_complaint_rule_survives_llm_other_result(classifier, deterministic_llm):
    deterministic_llm.tool_calls = [
        {
            "name": "classify_intent",
            "args": {
                "primary_intent": "OTHER",
                "secondary_intent": "CONSULT",
                "confidence": 0.99,
                "slots": {},
            },
        }
    ]

    result = await classifier.classify(
        "\u6211\u8981\u6295\u8bc9\u8fd9\u6b21\u552e\u540e\u670d\u52a1\uff0c"
        "\u8bf7\u5e2e\u6211\u63d0\u4ea4\u6295\u8bc9\u3002"
    )

    assert result.primary_intent == IntentCategory.COMPLAINT
    assert result.secondary_intent == IntentAction.APPLY


# ========== Tertiary Intent Validation Tests ==========


@pytest.mark.asyncio
async def test_valid_tertiary_intent(classifier, deterministic_llm):
    """测试合法的三级意图"""
    deterministic_llm.tool_calls = [
        {
            "name": "classify_intent",
            "args": {
                "primary_intent": "AFTER_SALES",
                "secondary_intent": "APPLY",
                "tertiary_intent": "REFUND",
                "confidence": 0.90,
                "slots": {},
            },
        }
    ]

    result = await classifier.classify("我要退款")

    assert result.tertiary_intent == "REFUND"


@pytest.mark.asyncio
async def test_invalid_tertiary_intent_filtered(classifier, deterministic_llm):
    """测试非法的三级意图被过滤"""
    deterministic_llm.tool_calls = [
        {
            "name": "classify_intent",
            "args": {
                "primary_intent": "AFTER_SALES",
                "secondary_intent": "APPLY",
                "tertiary_intent": "INVALID_TERTIARY",
                "confidence": 0.90,
                "slots": {},
            },
        }
    ]

    result = await classifier.classify("我要退款")

    assert result.tertiary_intent is None


@pytest.mark.asyncio
async def test_none_tertiary_intent_allowed(classifier, deterministic_llm):
    """测试None三级意图是合法的"""
    deterministic_llm.tool_calls = [
        {
            "name": "classify_intent",
            "args": {
                "primary_intent": "ORDER",
                "secondary_intent": "QUERY",
                "tertiary_intent": None,
                "confidence": 0.85,
                "slots": {"order_sn": "SN123"},
            },
        }
    ]

    result = await classifier.classify("查订单")

    assert result.tertiary_intent is None


# ========== Intent Validation Tests ==========


def test_validate_intent_result_valid(classifier):
    """测试验证有效的意图结果"""
    result = IntentResult(
        primary_intent=IntentCategory.ORDER,
        secondary_intent=IntentAction.QUERY,
        tertiary_intent="ORDER_TRACKING_DETAIL",
        confidence=0.85,
        slots={},
        raw_query="测试",
    )

    is_valid, error_msg = classifier.validate_intent_result(result)

    assert is_valid is True
    assert error_msg == ""


def test_validate_intent_result_invalid_primary(classifier):
    """测试验证无效的一级意图"""
    result = IntentResult.model_construct(
        primary_intent="INVALID",
        secondary_intent=IntentAction.QUERY,
        confidence=0.85,
        slots={},
        raw_query="测试",
    )

    is_valid, error_msg = classifier.validate_intent_result(result)

    assert is_valid is False
    assert "无效的一级意图" in error_msg


def test_validate_intent_result_invalid_tertiary(classifier):
    """测试验证无效的三级意图"""
    result = IntentResult(
        primary_intent=IntentCategory.AFTER_SALES,
        secondary_intent=IntentAction.APPLY,
        tertiary_intent="INVALID_TERTIARY",
        confidence=0.85,
        slots={},
        raw_query="测试",
    )

    is_valid, error_msg = classifier.validate_intent_result(result)

    assert is_valid is False
    assert "无效的三级意图" in error_msg


def test_validate_intent_result_invalid_confidence(classifier):
    """测试验证无效的置信度"""
    result = IntentResult(
        primary_intent=IntentCategory.ORDER,
        secondary_intent=IntentAction.QUERY,
        confidence=1.5,
        slots={},
        raw_query="测试",
    )

    is_valid, error_msg = classifier.validate_intent_result(result)

    assert is_valid is False
    assert "置信度超出范围" in error_msg


# ========== Context Tests ==========


@pytest.mark.asyncio
async def test_classification_with_context(classifier, deterministic_llm):
    """测试带上下文的分类"""
    deterministic_llm.tool_calls = [
        {
            "name": "classify_intent",
            "args": {
                "primary_intent": "ORDER",
                "secondary_intent": "QUERY",
                "tertiary_intent": "ORDER_TRACKING_DETAIL",
                "confidence": 0.90,
                "slots": {"order_sn": "SN20240001"},
            },
        }
    ]

    context = {
        "session_id": "sess_123",
        "history": "用户之前查询过订单",
        "user_info": {"vip": True},
    }

    result = await classifier.classify("那个订单到哪了", context=context)

    assert result.primary_intent == IntentCategory.ORDER


# ========== Edge Case Tests ==========


def test_empty_query(classifier):
    """测试空输入直接走规则匹配"""
    result = classifier._classify_with_rules("")

    assert result.primary_intent == IntentCategory.OTHER


@pytest.mark.asyncio
async def test_very_long_query(classifier, deterministic_llm):
    """测试超长输入"""
    deterministic_llm.tool_calls = [
        {
            "name": "classify_intent",
            "args": {
                "primary_intent": "COMPLAINT",
                "secondary_intent": "CONSULT",
                "tertiary_intent": None,
                "confidence": 0.80,
                "slots": {"complaint_content": "很长的内容"},
            },
        }
    ]

    long_query = "我要投诉" + "!" * 1000

    result = await classifier.classify(long_query)

    assert result is not None


def test_special_characters_query(classifier):
    """测试特殊字符输入直接走规则匹配"""
    result = classifier._classify_with_rules("订单!@#$%^&*()")

    assert result is not None
    assert isinstance(result, IntentResult)


def test_multiple_keywords_match(classifier):
    """测试多个关键词匹配"""
    result = classifier._classify_with_rules("订单SN123我想退货")

    assert result.confidence == 0.8


# ========== Invalid Function Calling Result Tests ==========


@pytest.mark.asyncio
async def test_invalid_function_result_falls_back_to_rules(classifier, deterministic_llm):
    """测试Function Calling返回无效结果时降级到规则匹配"""
    deterministic_llm.tool_calls = [
        {
            "name": "classify_intent",
            "args": {
                "primary_intent": "ORDER",
                "secondary_intent": "QUERY",
                "tertiary_intent": None,
                "confidence": 1.5,
                "slots": {},
            },
        }
    ]

    result = await classifier.classify("我的订单状态")

    assert result.primary_intent == IntentCategory.ORDER
    assert result.secondary_intent == IntentAction.QUERY


# ========== Regression Tests for Critical LLM/Routing Bugs ==========


@pytest.mark.asyncio
async def test_classifier_uses_auto_tool_choice_with_legacy_dashscope_settings(
    classifier, monkeypatch
):
    """Provider-neutral classifier semantics ignore legacy endpoint differences."""
    monkeypatch.setattr(
        "app.intent.classifier.settings.OPENAI_BASE_URL", "https://dashscope.aliyuncs.com/v1"
    )
    monkeypatch.setattr("app.intent.classifier.settings.LLM_MODEL", "qwen-max")

    bound_tools_calls = []

    class _FakeLLM:
        async def ainvoke(self, messages, config=None):
            return type("Resp", (), {"tool_calls": []})()

        def bind_tools(self, tools, tool_choice):
            bound_tools_calls.append(tool_choice)
            return self

    classifier._fast_llm = _FakeLLM()
    await classifier._classify_with_function_calling("测试")
    assert bound_tools_calls == ["auto"]


@pytest.mark.asyncio
async def test_classifier_uses_auto_tool_choice_with_legacy_openai_settings(
    classifier, monkeypatch
):
    """Tool selection remains provider-neutral for legacy OpenAI settings."""
    monkeypatch.setattr(
        "app.intent.classifier.settings.OPENAI_BASE_URL", "https://api.openai.com/v1"
    )
    monkeypatch.setattr("app.intent.classifier.settings.LLM_MODEL", "gpt-4o")

    bound_tools_calls = []

    class _FakeLLM:
        async def ainvoke(self, messages, config=None):
            return type("Resp", (), {"tool_calls": []})()

        def bind_tools(self, tools, tool_choice):
            bound_tools_calls.append(tool_choice)
            return self

    classifier._fast_llm = _FakeLLM()
    await classifier._classify_with_function_calling("测试")
    assert bound_tools_calls == ["auto"]


@pytest.fixture
def real_classifier(real_llm):
    return IntentClassifier(llm=real_llm)


@pytest.mark.requires_llm
@pytest.mark.asyncio
async def test_real_llm_classify_order_query(real_classifier):
    result = await real_classifier.classify("帮我查下订单SN20240001的状态")
    assert isinstance(result.primary_intent, IntentCategory)
    assert result.confidence >= 0.0
    assert result.confidence <= 1.0
    assert result.raw_query == "帮我查下订单SN20240001的状态"


@pytest.mark.requires_llm
@pytest.mark.asyncio
async def test_real_llm_classify_after_sales(real_classifier):
    result = await real_classifier.classify("我想申请退货")
    assert isinstance(result.primary_intent, IntentCategory)
    assert result.confidence >= 0.0
    assert result.confidence <= 1.0


@pytest.mark.requires_llm
@pytest.mark.asyncio
async def test_real_llm_classify_policy_consult(real_classifier):
    result = await real_classifier.classify("运费怎么算？")
    assert isinstance(result.primary_intent, IntentCategory)
    assert result.confidence >= 0.0
    assert result.confidence <= 1.0


@pytest.mark.requires_llm
@pytest.mark.asyncio
async def test_real_llm_classify_with_context(real_classifier):
    context = {
        "session_id": "sess_123",
        "history": "用户之前查询过订单",
        "user_info": {"vip": True},
    }
    result = await real_classifier.classify("那个订单到哪了", context=context)
    assert isinstance(result.primary_intent, IntentCategory)
    assert result.confidence >= 0.0
    assert result.confidence <= 1.0
