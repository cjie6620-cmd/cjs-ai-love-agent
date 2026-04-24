from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload, sessionmaker

from contracts.chat import (
    AnswerConfidence,
    ChatRequest,
    ChatResponse,
    ChatTrace,
    ConversationHistoryItem,
    ConversationHistoryMessage,
    KnowledgeEvidence,
    MemoryHit,
    QuestionAdvisorPayload,
)

from .db_base import get_session_factory
from .models import ConversationMessage, ConversationSession, User

DEFAULT_CONVERSATION_TITLE = "新对话"


class ConversationRepository:
    """负责会话持久化，隔离业务层与 SQLAlchemy 细节。

    目的：封装持久化读写逻辑，隔离数据库访问细节和查询实现。
    结果：业务层可以通过统一仓储接口完成数据操作，降低存储实现耦合。
    """

    def __init__(self, session_factory: sessionmaker[Session] | None = None) -> None:
        """初始化会话存储库实例。

        目的：接收并保存运行所需的依赖、配置和初始状态。
        结果：实例初始化完成，可直接执行后续业务调用。
        """
        self.session_factory = session_factory or get_session_factory()

    def save_turn(self, request: ChatRequest, response: ChatResponse) -> None:
        """一次性保存一轮完整问答，适合非流式接口。

        目的：持久化、上传或补充目标数据，保持状态同步。
        结果：相关数据被成功写入或更新，便于后续流程继续使用。
        """
        with self.session_factory() as session:
            user = self._get_or_create_user(session, request.user_id)
            conversation = self._get_or_create_conversation(session, user, request)

            self._apply_user_message_updates(conversation, request.message, request.mode)
            session.add(self._build_user_message(conversation.id, request.message))
            conversation.message_count += 1

            self._apply_assistant_message_updates(conversation, response.trace)
            session.add(self._build_assistant_message(conversation.id, response))
            conversation.message_count += 1

            user.last_active_at = self._now()
            session.commit()

    def save_user_message(self, request: ChatRequest) -> None:
        """先保存用户输入，避免流式回复中途失败后整轮数据完全丢失。

        目的：持久化、上传或补充目标数据，保持状态同步。
        结果：相关数据被成功写入或更新，便于后续流程继续使用。
        """
        with self.session_factory() as session:
            user = self._get_or_create_user(session, request.user_id)
            conversation = self._get_or_create_conversation(session, user, request)

            self._apply_user_message_updates(conversation, request.message, request.mode)
            session.add(self._build_user_message(conversation.id, request.message))
            conversation.message_count += 1
            user.last_active_at = self._now()

            session.commit()

    def save_assistant_message(self, request: ChatRequest, response: ChatResponse) -> None:
        """流式完成后补写助手回复与 trace。

        目的：持久化、上传或补充目标数据，保持状态同步。
        结果：相关数据被成功写入或更新，便于后续流程继续使用。
        """
        with self.session_factory() as session:
            user = self._get_or_create_user(session, request.user_id)
            conversation = self._find_conversation(session, user.id, request.session_id)
            if conversation is None:
                # 不补建新会话，避免出现“只有助手回复，没有用户输入”的脏数据。
                return

            self._apply_assistant_message_updates(conversation, response.trace)
            session.add(self._build_assistant_message(conversation.id, response))
            conversation.message_count += 1
            user.last_active_at = self._now()

            session.commit()

    def list_conversations(self, external_user_id: str) -> list[ConversationHistoryItem]:
        """按最近更新时间倒序返回指定用户的历史会话。

        目的：按指定条件读取目标数据、资源或结果集合。
        结果：返回可直接消费的查询结果，减少调用方重复处理。
        """
        with self.session_factory() as session:
            statement = (
                select(ConversationSession)
                .join(User, ConversationSession.user_id == User.id)
                .options(selectinload(ConversationSession.messages))
                .where(User.external_user_id == external_user_id)
                .order_by(
                    ConversationSession.updated_at.desc(), ConversationSession.created_at.desc()
                )
            )
            conversations = list(session.scalars(statement))
            return [self._serialize_conversation(item) for item in conversations]

    def list_recent_messages(
        self,
        external_user_id: str,
        session_id: str,
        *,
        limit: int = 6,
    ) -> list[ConversationHistoryMessage]:
        """返回指定会话最近若干条用户/助手消息，供 advisor 构造上下文。

        目的：按指定条件读取目标数据、资源或结果集合。
        结果：返回可直接消费的查询结果，减少调用方重复处理。
        """
        with self.session_factory() as session:
            statement = (
                select(ConversationMessage)
                .join(
                    ConversationSession,
                    ConversationMessage.conversation_id == ConversationSession.id,
                )
                .join(User, ConversationSession.user_id == User.id)
                .where(
                    User.external_user_id == external_user_id,
                    ConversationSession.id == session_id,
                    ConversationMessage.role.in_(("user", "assistant")),
                )
                .order_by(ConversationMessage.created_at.desc())
                .limit(limit)
            )
            rows = list(session.scalars(statement))
            rows.reverse()
            return [self._serialize_message(item) for item in rows]

    def _get_or_create_user(self, session: Session, external_user_id: str) -> User:
        """获取或创建用户记录。

        目的：根据当前上下文组装目标对象、消息或输出结构。
        结果：返回结构完整的结果，供后续流程直接使用。
        """
        statement = select(User).where(User.external_user_id == external_user_id)
        user = session.scalar(statement)
        if user is not None:
            return user

        user = User(
            external_user_id=external_user_id,
            nickname=external_user_id,
        )
        session.add(user)
        session.flush()
        return user

    def _get_or_create_conversation(
        self,
        session: Session,
        user: User,
        request: ChatRequest,
    ) -> ConversationSession:
        """获取或创建会话记录。

        目的：根据当前上下文组装目标对象、消息或输出结构。
        结果：返回结构完整的结果，供后续流程直接使用。
        """
        conversation = self._find_conversation(session, user.id, request.session_id)
        if conversation is not None:
            return conversation

        conversation = ConversationSession(
            id=request.session_id,
            user_id=user.id,
            title=DEFAULT_CONVERSATION_TITLE,
            mode=request.mode,
            summary="",
            memory_digest={},
            message_count=0,
            risk_level="low",
        )
        session.add(conversation)
        session.flush()
        return conversation

    def _find_conversation(
        self,
        session: Session,
        user_id: str,
        session_id: str,
    ) -> ConversationSession | None:
        """查找会话记录。

        目的：持久化、上传或补充目标数据，保持状态同步。
        结果：相关数据被成功写入或更新，便于后续流程继续使用。
        """
        statement = select(ConversationSession).where(
            ConversationSession.id == session_id,
            ConversationSession.user_id == user_id,
        )
        return session.scalar(statement)

    def _apply_user_message_updates(
        self,
        conversation: ConversationSession,
        message: str,
        mode: str,
    ) -> None:
        """应用用户消息相关的会话更新。

        目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        conversation.mode = mode
        conversation.summary = message[:18]
        conversation.updated_at = self._now()
        if not conversation.title.strip() or conversation.title == DEFAULT_CONVERSATION_TITLE:
            conversation.title = message[:10] or DEFAULT_CONVERSATION_TITLE

    def _apply_assistant_message_updates(
        self,
        conversation: ConversationSession,
        trace: ChatTrace,
    ) -> None:
        """应用助手消息相关的会话更新。

        目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        conversation.risk_level = trace.safety_level
        conversation.memory_digest = {
            "memory_hits": trace.memory_hits,
            "knowledge_hits": trace.knowledge_hits,
            "knowledge_evidences": [item.model_dump() for item in trace.knowledge_evidences],
            "answer_confidence": trace.answer_confidence,
        }
        conversation.updated_at = self._now()

    def _build_user_message(self, conversation_id: str, content: str) -> ConversationMessage:
        """构建用户消息记录。

        目的：根据当前上下文组装目标对象、消息或输出结构。
        结果：返回结构完整的结果，供后续流程直接使用。
        """
        return ConversationMessage(
            conversation_id=conversation_id,
            role="user",
            content=content,
            trace_json={},
            safety_tags={},
            token_count=len(content),
        )

    def _build_assistant_message(
        self,
        conversation_id: str,
        response: ChatResponse,
    ) -> ConversationMessage:
        """构建助手消息记录。

        目的：根据当前上下文组装目标对象、消息或输出结构。
        结果：返回结构完整的结果，供后续流程直接使用。
        """
        trace_payload = {
            "trace": response.trace.model_dump(),
            "advisor": response.advisor.model_dump() if response.advisor else None,
        }
        return ConversationMessage(
            conversation_id=conversation_id,
            role="assistant",
            content=response.reply,
            trace_json=trace_payload,
            safety_tags={"safety_level": response.trace.safety_level},
            token_count=len(response.reply),
        )

    def _serialize_conversation(self, conversation: ConversationSession) -> ConversationHistoryItem:
        """序列化会话记录为 API 响应格式。

        目的：持久化、上传或补充目标数据，保持状态同步。
        结果：相关数据被成功写入或更新，便于后续流程继续使用。
        """
        messages = [
            self._serialize_message(item)
            for item in conversation.messages
            if item.role in {"user", "assistant"}
        ]

        latest_trace: ChatTrace | None = None
        for item in reversed(conversation.messages):
            if item.role != "assistant" or not item.trace_json:
                continue
            latest_trace = self._deserialize_trace(item.trace_json)
            break

        preview = conversation.summary or (messages[-1].content[:18] if messages else "")
        return ConversationHistoryItem(
            id=conversation.id,
            title=conversation.title or DEFAULT_CONVERSATION_TITLE,
            preview=preview,
            mode=conversation.mode,  # type: ignore[arg-type]
            messages=messages,
            latest_trace=latest_trace,
        )

    def _serialize_message(self, message: ConversationMessage) -> ConversationHistoryMessage:
        """序列化消息记录为 API 响应格式。

        目的：持久化、上传或补充目标数据，保持状态同步。
        结果：相关数据被成功写入或更新，便于后续流程继续使用。
        """
        advisor = None
        if message.role == "assistant" and message.trace_json:
            advisor = self._deserialize_advisor(message.trace_json)
        return ConversationHistoryMessage(
            id=message.id,
            role="user" if message.role == "user" else "assistant",
            content=message.content,
            created_at=message.created_at,
            advisor=advisor,
        )

    def _deserialize_trace(self, payload: dict[str, object]) -> ChatTrace:
        """反序列化追踪信息。

        目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        trace_payload = payload.get("trace")
        if not isinstance(trace_payload, dict):
            return ChatTrace()
        raw_memory_hits = trace_payload.get("memory_hits", [])
        memory_hits = [
            self._deserialize_memory_hit(item) for item in raw_memory_hits if isinstance(item, dict)
        ]
        raw_evidences = trace_payload.get("knowledge_evidences", [])
        knowledge_evidences = [
            KnowledgeEvidence.model_validate(item)
            for item in raw_evidences
            if isinstance(item, dict)
        ]
        raw_confidence = str(trace_payload.get("answer_confidence", "low"))
        answer_confidence = raw_confidence if raw_confidence in {"high", "medium", "low"} else "low"
        return ChatTrace(
            memory_hits=memory_hits,
            knowledge_hits=[
                item for item in trace_payload.get("knowledge_hits", []) if isinstance(item, str)
            ],
            knowledge_evidences=knowledge_evidences,
            retrieval_query=str(trace_payload.get("retrieval_query", "")),
            safety_level=str(trace_payload.get("safety_level", "low")),
            answer_confidence=cast(AnswerConfidence, answer_confidence),
            answer_confidence_reason=str(trace_payload.get("answer_confidence_reason", "")),
            rerank_applied=bool(trace_payload.get("rerank_applied", False)),
        )

    def _deserialize_advisor(self, payload: dict[str, object]) -> QuestionAdvisorPayload | None:
        """反序列化问题顾问信息。

        目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        advisor_payload = payload.get("advisor")
        if not isinstance(advisor_payload, dict):
            return None
        return QuestionAdvisorPayload(
            issue_summary=str(advisor_payload.get("issue_summary", "")),
            retrieval_query=str(advisor_payload.get("retrieval_query", "")),
            matched_topics=[
                item for item in advisor_payload.get("matched_topics", []) if isinstance(item, str)
            ],
            suggested_questions=[
                item
                for item in advisor_payload.get("suggested_questions", [])
                if isinstance(item, str)
            ],
        )

    def _deserialize_memory_hit(self, payload: dict[str, object]) -> MemoryHit:
        """反序列化单条记忆命中项。

        目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        raw_score = payload.get("score", 0.0)
        try:
            score = float(raw_score) if isinstance(raw_score, (int, float, str)) else 0.0
        except (TypeError, ValueError):
            score = 0.0
        return {
            "content": str(payload.get("content", "")),
            "score": score,
            "chunk_id": str(payload.get("chunk_id", "")),
        }

    def _now(self) -> datetime:
        """获取当前 UTC 时间。

        目的：按指定条件读取目标数据、资源或结果集合。
        结果：返回可直接消费的查询结果，减少调用方重复处理。
        """
        return datetime.now(UTC)
