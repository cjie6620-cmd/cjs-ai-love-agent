"""QuestionAdvisor 单元测试：验证检索查询增强与建议问题生成。"""

from agents.question_advisor import QuestionAdvisor
from contracts.chat import ConversationHistoryMessage


def test_build_draft_uses_recent_user_messages() -> None:
    """验证 advisor 会利用最近多轮用户消息补齐检索查询。"""
    advisor = QuestionAdvisor()
    recent_messages = [
        ConversationHistoryMessage(id="1", role="user", content="今天心情不好"),
        ConversationHistoryMessage(id="2", role="assistant", content="我在，你愿意慢慢说。"),
        ConversationHistoryMessage(id="3", role="user", content="刚分手两天，总想给她发消息"),
    ]

    draft = advisor.build_draft(
        message="我现在忍不住想联系她",
        mode="advice",
        recent_messages=recent_messages,
    )

    assert "今天心情不好" in draft.issue_summary
    assert "刚分手两天" in draft.retrieval_query
    assert "我现在忍不住想联系她" in draft.retrieval_query


def test_finalize_returns_suggested_questions_from_topics() -> None:
    """验证 advisor 会根据命中主题生成可直接点击的追问建议。"""
    advisor = QuestionAdvisor()
    draft = advisor.build_draft(message="分手了", mode="soothing", recent_messages=[])

    payload = advisor.finalize(
        draft=draft,
        mode="soothing",
        matched_topics=["分手、复联、降温策略", "情绪安抚与支持表达"],
        reply="先别急着联系对方，先把自己稳住。",
    )

    assert payload.retrieval_query
    assert payload.matched_topics
    assert 2 <= len(payload.suggested_questions) <= 4
    assert all(item.endswith("？") for item in payload.suggested_questions)
    assert all("你可以" not in item and "需要我帮你" not in item for item in payload.suggested_questions)


def test_finalize_returns_process_and_study_followups() -> None:
    """非情感话题也应生成可直接发送的下一问。"""
    advisor = QuestionAdvisor()
    draft = advisor.build_draft(
        message="初级会计职称怎么考",
        mode="advice",
        recent_messages=[],
    )

    payload = advisor.finalize(
        draft=draft,
        mode="advice",
        matched_topics=["职业考试/初级会计职称"],
        reply="先确认报名时间和科目，再安排备考节奏。",
    )

    assert payload.suggested_questions == [
        "初级会计职称的报考流程是什么？",
        "初级会计职称主要考哪些内容或题型？",
        "初级会计职称怎么备考更高效？",
    ]


def test_finalize_returns_cost_followups() -> None:
    """费用类话题应给出谈法、底线和下一步。"""
    advisor = QuestionAdvisor()
    draft = advisor.build_draft(message="彩礼太高了", mode="advice", recent_messages=[])

    payload = advisor.finalize(
        draft=draft,
        mode="advice",
        matched_topics=[],
        reply="先把你能接受的范围和对方期待拆开来看。",
    )

    assert payload.suggested_questions == [
        "彩礼太高了怎么谈更不容易谈崩？",
        "我的底线应该怎么定？",
        "如果实在谈不拢，下一步该怎么办？",
    ]


def test_finalize_returns_troubleshooting_followups() -> None:
    """报错类话题应给出排查、原因和修复下一步。"""
    advisor = QuestionAdvisor()
    draft = advisor.build_draft(message="启动报错了", mode="advice", recent_messages=[])

    payload = advisor.finalize(
        draft=draft,
        mode="advice",
        matched_topics=[],
        reply="先确认日志和配置，再看依赖是否完整。",
    )

    assert payload.suggested_questions == [
        "启动报错了最先该排查什么？",
        "启动报错了最常见的原因有哪些？",
        "启动报错了下一步怎么修比较稳？",
    ]

