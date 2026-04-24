"""问题顾问：检索查询增强与追问建议生成。

目的：根据用户消息生成检索查询和追问建议，增强对话体验。
结果：提供问题摘要、匹配主题和4条建议问题，引导用户深入对话。
"""
# 用户消息进来
#     │
#     ▼
# ① 安全检查 (SafetyGuard)
#     │
#     ▼
# ② QuestionAdvisor.build_draft()    ← 重写问题（给检索用）
#     │
#     ├──→ MemoryManager.recall(retrieval_query)     ← 用重写后的 query 搜记忆
#     ├──→ KnowledgeRetriever.search(retrieval_query) ← 用重写后的 query 搜知识库
#     │
#     ▼
# ③ LLM 生成回复
#     │
#     ▼
# ④ QuestionAdvisor.finalize()       ← 生成追问建议（给前端用）
#     │
#     ▼
# 返回 ChatResponse { reply, advisor: { suggested_questions, ... } }

from __future__ import annotations

from dataclasses import dataclass
import re

from contracts.chat import ChatMode, ConversationHistoryMessage, QuestionAdvisorPayload


@dataclass(slots=True)
class QuestionAdvisorDraft:
    """顾问草稿，先用于检索，再在回复后补全建议问题。

    目的：封装当前领域对象的核心职责，统一相关行为和数据边界。
    结果：相关模块可以围绕该对象稳定协作，提升代码可读性和可维护性。
    """

    issue_summary: str
    retrieval_query: str


class QuestionAdvisor:
    """基于规则的轻量问题顾问，不额外引入一次模型调用。
    
    目的：封装基于规则的轻量问题顾问，不额外引入一次模型调用相关能力。
    结果：对外提供稳定、可复用的调用入口。
    """

    def build_draft(
        self,
        *,
        message: str,
        mode: ChatMode,
        recent_messages: list[ConversationHistoryMessage] | None = None,
    ) -> QuestionAdvisorDraft:
        """构建问题顾问草稿。

        目的：根据当前上下文组装目标对象、消息或输出结构。
        结果：返回结构完整的结果，供后续流程直接使用。
        """
        normalized_message = self._normalize_text(message)
        recent_user_messages = self._collect_recent_user_messages(recent_messages or [])

        issue_summary = self._build_issue_summary(
            current_message=normalized_message,
            recent_user_messages=recent_user_messages,
        )
        retrieval_query = self._build_retrieval_query(
            current_message=normalized_message,
            mode=mode,
            recent_user_messages=recent_user_messages,
        )
        return QuestionAdvisorDraft(
            issue_summary=issue_summary,
            retrieval_query=retrieval_query,
        )

    def finalize(
        self,
        *,
        draft: QuestionAdvisorDraft,
        mode: ChatMode,
        matched_topics: list[str],
        reply: str,
    ) -> QuestionAdvisorPayload:
        """完成问题顾问数据构建。

        目的：根据当前上下文组装目标对象、消息或输出结构。
        结果：返回结构完整的结果，供后续流程直接使用。
        """
        topics = self._deduplicate_strings(matched_topics)[:3]
        suggested_questions = self._build_suggested_questions(
            issue_summary=draft.issue_summary,
            retrieval_query=draft.retrieval_query,
            mode=mode,
            matched_topics=topics,
            reply=reply,
        )
        return QuestionAdvisorPayload(
            issue_summary=draft.issue_summary,
            retrieval_query=draft.retrieval_query,
            matched_topics=topics,
            suggested_questions=suggested_questions[:4],
        )

    def extract_matched_topics(self, raw_topics: list[str]) -> list[str]:
        """提取检索命中的主题，优先保留可读标题。

        目的：按指定条件读取目标数据、资源或结果集合。
        结果：返回可直接消费的查询结果，减少调用方重复处理。
        """
        topics = []
        for topic in raw_topics:
            normalized = self._normalize_text(topic)
            if not normalized:
                continue
            parts = [item.strip() for item in normalized.split("/") if item.strip()]
            topics.append(parts[-1] if parts else normalized)
        return self._deduplicate_strings(topics)

    def _build_issue_summary(
        self,
        *,
        current_message: str,
        recent_user_messages: list[str],
    ) -> str:
        """构建问题摘要。

        目的：统一处理输入值的边界情况、格式约束和清洗规则。
        结果：返回满足约束的结果，避免脏数据影响后续逻辑。
        """
        if not recent_user_messages:
            return current_message

        recent_context = "，".join(recent_user_messages[-2:])
        if current_message in recent_context:
            return recent_context
        return f"{recent_context}，当前最想解决的是：{current_message}"

    def _build_retrieval_query(
        self,
        *,
        current_message: str,
        mode: ChatMode,
        recent_user_messages: list[str],
    ) -> str:
        """构建检索查询。

        目的：根据当前上下文组装目标对象、消息或输出结构。
        结果：返回结构完整的结果，供后续流程直接使用。
        """
        snippets = self._deduplicate_strings([*recent_user_messages[-2:], current_message])
        mode_hint = {
            "companion": "情感陪伴",
            "advice": "恋爱建议",
            "style_clone": "表达改写",
            "soothing": "情绪安抚",
        }.get(mode, "情感支持")

        scenario_hint = self._detect_scenario_hint(" ".join(snippets))
        if scenario_hint:
            return f"{mode_hint}：{scenario_hint}；用户情况：{'；'.join(snippets)}"
        return f"{mode_hint}：{'；'.join(snippets)}"

    def _build_suggested_questions(
        self,
        *,
        issue_summary: str,
        retrieval_query: str,
        mode: ChatMode,
        matched_topics: list[str],
        reply: str,
    ) -> list[str]:
        """构建建议问题列表。

        目的：根据当前上下文组装目标对象、消息或输出结构。
        结果：返回结构完整的结果，供后续流程直接使用。
        """
        context_text = " ".join([issue_summary, retrieval_query, *matched_topics, reply]).strip()
        intent = self._detect_followup_intent(context_text)
        topic = self._pick_followup_topic(
            issue_summary=issue_summary,
            retrieval_query=retrieval_query,
            matched_topics=matched_topics,
        )

        suggestions = self._build_followup_candidates(intent=intent, topic=topic, mode=mode)
        filtered = self._filter_suggested_questions(
            suggestions,
            current_message=issue_summary,
        )
        return filtered[:3]

    def _collect_recent_user_messages(
        self,
        recent_messages: list[ConversationHistoryMessage],
    ) -> list[str]:
        """收集最近的用户消息。

        目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        user_messages = [
            self._normalize_text(item.content)
            for item in recent_messages
            if item.role == "user" and self._normalize_text(item.content)
        ]
        return self._deduplicate_strings(user_messages)[-3:]

    def _detect_scenario_hint(self, text: str) -> str:
        """检测场景提示。

        目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        scenario_map = {
            "breakup": "分手后的情绪恢复、降温和体面表达",
            "cold_reply": "对方冷淡、不回消息时的判断和回应",
            "comfort": "情绪低落、失恋后的安抚和支持表达",
            "conflict": "吵架、冲突后的修复沟通",
            "boundary": "边界表达、拒绝回应和避免越界",
            "dating": "暧昧推进、邀约和关系升级",
        }
        scenario_key = self._detect_scenario_key(text)
        return scenario_map.get(scenario_key, "")

    def _detect_followup_intent(self, text: str) -> str:
        """识别用户下一步最可能会追问的意图类型。"""
        normalized = self._normalize_text(text)
        checks = [
            ("study", ["备考", "复习", "资料", "题型", "考试", "刷题", "学习计划", "怎么考"]),
            ("process", ["流程", "步骤", "报名", "报考", "申请", "办理", "怎么报名", "怎么报", "怎么办理"]),
            ("eligibility", ["条件", "资格", "要求", "能不能", "可以报", "是否符合"]),
            ("cost", ["费用", "预算", "彩礼", "花销", "太贵", "值不值", "多少钱"]),
            ("decision", ["要不要", "该不该", "怎么选", "值不值得", "合适吗", "要不要继续"]),
            ("troubleshooting", ["报错", "失败", "启动不了", "异常", "无法", "错误", "连不上", "出问题"]),
        ]
        for intent, keywords in checks:
            if any(keyword in normalized for keyword in keywords):
                return intent
        if self._detect_scenario_key(normalized):
            return "relationship"
        return "generic"

    def _pick_followup_topic(
        self,
        *,
        issue_summary: str,
        retrieval_query: str,
        matched_topics: list[str],
    ) -> str:
        """按固定优先级提取下一问主题。"""
        if matched_topics:
            return self._normalize_topic(matched_topics[-1])

        query_topic = self._extract_topic_from_retrieval_query(retrieval_query)
        if query_topic:
            return query_topic
        return self._normalize_topic(issue_summary)

    def _extract_topic_from_retrieval_query(self, retrieval_query: str) -> str:
        """从检索 query 中抽取更适合展示的核心主题。"""
        normalized = self._normalize_text(retrieval_query)
        if not normalized:
            return ""

        if "用户情况：" in normalized:
            normalized = normalized.split("用户情况：", 1)[0]
        if "：" in normalized:
            normalized = normalized.split("：", 1)[-1]
        normalized = re.sub(r"[；;,，]\s*", " ", normalized)
        return self._normalize_topic(normalized)

    def _normalize_topic(self, topic: str) -> str:
        """清洗主题文本，避免把系统提示或长串拼接直接展示给用户。"""
        normalized = self._normalize_text(topic)
        if not normalized:
            return ""

        parts = [item.strip() for item in normalized.split("/") if item.strip()]
        if parts:
            normalized = parts[-1]

        normalized = re.sub(r"^(情感陪伴|恋爱建议|表达改写|情绪安抚|情感支持)[：:]\s*", "", normalized)
        normalized = re.sub(r"(知识库|命中|检索|证据|通用建议|我先说明一下)", "", normalized)
        normalized = normalized.strip("：:；;，,。！？!? ")

        if len(normalized) > 24:
            candidates = re.split(r"[，,；;。！？!?]", normalized)
            normalized = next((item.strip() for item in candidates if item.strip()), normalized[:24])
        return normalized

    def _build_followup_candidates(
        self,
        *,
        intent: str,
        topic: str,
        mode: ChatMode,
    ) -> list[str]:
        """基于意图和主题生成候选下一问。"""
        subject = topic or "这件事"
        templates = {
            "process": [
                f"{subject}的流程是什么？",
                f"{subject}需要满足什么条件？",
                f"{subject}一般要准备哪些材料和时间节点？",
            ],
            "eligibility": [
                f"{subject}需要满足哪些条件？",
                f"我这种情况符合{subject}的要求吗？",
                f"{subject}最容易忽略的限制是什么？",
            ],
            "study": [
                f"{subject}的报考流程是什么？",
                f"{subject}主要考哪些内容或题型？",
                f"{subject}怎么备考更高效？",
            ],
            "cost": [
                f"{subject}怎么谈更不容易谈崩？",
                "我的底线应该怎么定？",
                "如果实在谈不拢，下一步该怎么办？",
            ],
            "decision": [
                f"{subject}这件事我该先看哪个标准？",
                f"如果按最坏情况想，{subject}可能会带来什么结果？",
                f"{subject}这件事下一步我该怎么选更稳？",
            ],
            "troubleshooting": [
                f"{subject}最先该排查什么？",
                f"{subject}最常见的原因有哪些？",
                f"{subject}下一步怎么修比较稳？",
            ],
            "relationship": [
                f"{subject}这件事我下一句该怎么说？",
                f"{subject}里我最该先想清楚的一点是什么？",
                f"{subject}如果继续聊下去，最容易踩的坑是什么？",
            ],
            "generic": [
                "下一步我该先做什么？",
                f"{subject}里最关键的一点是什么？",
                f"{subject}最容易踩坑的地方是什么？",
            ],
        }
        suggestions = templates.get(intent, templates["generic"])
        if mode == "soothing" and intent == "generic":
            suggestions = [
                "我现在最该先稳住哪一点？",
                "如果我只想先缓一缓，先做什么比较好？",
                "这件事里我最需要想清楚的是什么？",
            ]
        return suggestions

    def _filter_suggested_questions(
        self,
        suggestions: list[str],
        *,
        current_message: str,
    ) -> list[str]:
        """清洗、去重并过滤与当前问题过近的建议问题。"""
        result: list[str] = []
        seen: set[str] = set()
        current_normalized = self._normalize_compare_text(current_message)
        forbidden_terms = ("知识库", "命中", "检索", "证据", "通用建议", "我先说明一下", "需要我帮你")

        for suggestion in suggestions:
            normalized = self._normalize_text(suggestion)
            if not normalized:
                continue
            if any(term in normalized for term in forbidden_terms):
                continue
            if not normalized.endswith("？"):
                normalized = normalized.rstrip("。！？!? ") + "？"

            compare_value = self._normalize_compare_text(normalized)
            if not compare_value or compare_value in seen:
                continue
            if current_normalized and compare_value == current_normalized:
                continue

            seen.add(compare_value)
            result.append(normalized)

        fallback = [
            "下一步我该先做什么？",
            "这里最关键的一点是什么？",
            "最容易踩坑的地方是什么？",
        ]
        for item in fallback:
            if len(result) >= 2:
                break
            compare_value = self._normalize_compare_text(item)
            if compare_value not in seen:
                seen.add(compare_value)
                result.append(item)
        return result

    def _normalize_compare_text(self, text: str) -> str:
        """标准化比较文本，用于去重和相似判断。"""
        normalized = self._normalize_text(text).replace("？", "").replace("?", "")
        return re.sub(r"\s+", "", normalized)

    def _detect_scenario_key(self, text: str) -> str:
        """检测场景关键词。

        目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        lowered = text.lower()
        checks = [
            ("breakup", ["分手", "失恋", "复联", "前任", "挽回"]),
            ("cold_reply", ["冷淡", "不回", "断联", "已读不回", "回得慢", "异地"]),
            ("comfort", ["心情不好", "难受", "低落", "崩溃", "委屈", "哭", "失眠"]),
            ("conflict", ["吵架", "冲突", "闹矛盾", "误会", "争执"]),
            ("boundary", ["边界", "拒绝", "越界", "纠缠", "拉扯"]),
            ("dating", ["暧昧", "邀约", "约会", "推进关系", "升温"]),
        ]
        for key, keywords in checks:
            if any(keyword in text for keyword in keywords):
                return key
        if "comfort" in lowered:
            return "comfort"
        return ""

    def _deduplicate_strings(self, values: list[str]) -> list[str]:
        """去重字符串列表。

        目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            normalized = self._normalize_text(value)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            result.append(normalized)
        return result

    def _normalize_text(self, text: str) -> str:
        """标准化文本。

        目的：统一处理输入值的边界情况、格式约束和清洗规则。
        结果：返回满足约束的结果，避免脏数据影响后续逻辑。
        """
        return " ".join(text.strip().split())
