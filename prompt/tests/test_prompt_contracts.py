from prompt.templates import (
    build_chat_reply_prompt_spec,
    build_memory_decision_prompt_spec,
    build_tool_final_reply_prompt_spec,
)


def test_chat_prompt_spec_renders_plain_text_contract() -> None:
    """普通聊天 prompt 应明确要求纯文本输出。"""
    spec = build_chat_reply_prompt_spec(
        mode="advice",
        safety_level="medium",
        llm_provider="xai_router",
        message="我现在总想给前任发消息",
        recent_messages=[{"role": "user", "content": "刚分手两天"}],
        memory_hits=[{"content": "用户容易冲动联系前任", "score": 0.92, "chunk_id": "m-1"}],
        knowledge_hits=["分手初期建议先降温，不要立即高频联系。"],
        knowledge_evidences=[
            {
                "evidence_id": "K1",
                "chunk_id": "c-1",
                "parent_id": "p-1",
                "title": "分手期沟通策略",
                "source": "builtin",
                "heading_path": "分手 / 降温",
                "snippet": "分手初期建议先降温，不要立即高频联系。",
                "rank": 1,
                "locator": "分手.md | 分手 / 降温",
            }
        ],
        retrieval_query="分手后总想联系前任怎么办",
        evidence_status="grounded",
    )

    system_prompt = spec.render_system_prompt()
    user_prompt = spec.render_user_prompt()

    assert spec.prompt_version == "chat.reply.v1"
    assert spec.output_schema_name == "PlainTextReply"
    assert spec.output_contract_version == "chat_reply_text.v2"
    assert "<role>" in system_prompt
    assert "<task>" in system_prompt
    assert "<constraints>" in system_prompt
    assert "<examples>" in system_prompt
    assert "<output_contract>" in system_prompt
    assert "<fallback_policy>" in system_prompt
    assert "<context>" in user_prompt
    assert "<evidence>" in user_prompt
    assert "只输出一段可直接发送给用户的纯文本回复" in system_prompt
    assert "不要输出 JSON" in system_prompt
    assert "输出必须匹配 ChatReplyModel" not in system_prompt
    assert "K1" in user_prompt


def test_tool_final_prompt_spec_renders_structured_field_guide() -> None:
    """工具终结 prompt 应保留 structured field guide，但不再要求模型手写 JSON。"""
    spec = build_tool_final_reply_prompt_spec(
        mode="advice",
        safety_level="low",
        llm_provider="openai_remote_mcp",
        message="帮我看看今天北京天气怎么样",
        recent_messages=[{"role": "user", "content": "我要出门"}],
        memory_hits=[],
        knowledge_hits=["天气问答要优先给结论，再补充穿衣建议。"],
        knowledge_evidences=[],
        retrieval_query="北京今天天气",
        evidence_status="weak_grounding",
    )

    system_prompt = spec.render_system_prompt()
    user_prompt = spec.render_user_prompt()

    assert spec.prompt_version == "chat.reply.tool_final.v1"
    assert spec.output_schema_name == "ChatReplyModel"
    assert spec.output_contract_version == "chat_reply_structured.v2"
    assert "<field_guide>" in system_prompt
    assert "reply_text" in system_prompt
    assert "used_evidence_ids" in system_prompt
    assert "本阶段禁止继续调用工具" in system_prompt
    assert "请严格输出一个 JSON 对象" not in system_prompt
    assert "修复为合法 JSON" not in system_prompt
    assert "<tool_phase>" in user_prompt


def test_memory_prompt_spec_has_semantic_contract_metadata() -> None:
    """memory prompt 应保留字段语义，但不再使用旧 JSON contract 文案。"""
    spec = build_memory_decision_prompt_spec(
        user_message="我其实很害怕吵架，一冲突我就会沉默。",
        assistant_reply="你更像是在冲突里会先退回去保护自己。",
    )

    system_prompt = spec.render_system_prompt()

    assert spec.prompt_version == "memory.extraction.v2"
    assert spec.output_schema_name == "MemoryExtractionResult"
    assert spec.output_contract_version == "memory_extraction.v2"
    assert "<examples>" in system_prompt
    assert "<fallback_policy>" in system_prompt
    assert "should_store" in system_prompt
    assert "memory_type" in system_prompt
    assert "canonical_key" in system_prompt
    assert "do_not_record_everything" in spec.render_user_prompt()
    assert "输出 JSON" not in system_prompt
    assert "修复为合法 JSON" not in system_prompt
