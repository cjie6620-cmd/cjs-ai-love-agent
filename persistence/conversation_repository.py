from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from sqlalchemy import or_, select, update
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
    ReplyStatus,
)

from .db_base import get_session_factory
from .models import ConversationMessage, ConversationSession, User

DEFAULT_CONVERSATION_TITLE = "新对话"


class ConversationRepository:
    """目的：封装持久化读写逻辑，隔离数据库访问细节和查询实现。
    结果：业务层可以通过统一仓储接口完成数据操作，降低存储实现耦合。
    """

    def __init__(self, session_factory: sessionmaker[Session] | None = None) -> None:
        """目的：接收并保存运行所需的依赖、配置和初始状态。
        结果：实例初始化完成，可直接执行后续业务调用。
        """
        self.session_factory = session_factory or get_session_factory()

    def save_turn(self, request: ChatRequest, response: ChatResponse) -> None:
        """目的：持久化、上传或补充目标数据，保持状态同步。
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
        """目的：持久化、上传或补充目标数据，保持状态同步。
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
        """目的：持久化、上传或补充目标数据，保持状态同步。
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

    def save_interrupted_assistant_message(
        self,
        request: ChatRequest,
        partial_reply: str,
        *,
        stream_id: str,
    ) -> None:
        """目的：保存用户手动中断时已经生成的 assistant 部分回复。
        结果：部分回复进入会话短期上下文，但通过状态标记排除长期记忆提取。
        """
        normalized_reply = partial_reply.strip()
        if not normalized_reply:
            return
        with self.session_factory() as session:
            user = self._get_or_create_user(session, request.user_id)
            conversation = self._find_conversation(session, user.id, request.session_id)
            if conversation is None:
                # 用户消息未落库时不补建助手消息，避免出现孤立 assistant 记录。
                return

            session.add(
                self._build_interrupted_assistant_message(
                    conversation.id,
                    normalized_reply,
                    stream_id=stream_id,
                )
            )
            conversation.message_count += 1
            conversation.updated_at = self._now()
            user.last_active_at = self._now()

            session.commit()

    def list_conversations(self, user_identifier: str) -> list[ConversationHistoryItem]:
        """目的：按指定条件读取目标数据、资源或结果集合。
        结果：返回可直接消费的查询结果，减少调用方重复处理。
        """
        with self.session_factory() as session:
            statement = (
                select(ConversationSession)
                .join(User, ConversationSession.user_id == User.id)
                .options(selectinload(ConversationSession.messages))
                .where(
                    or_(
                        User.id == user_identifier,
                        User.external_user_id == user_identifier,
                    )
                )
                .order_by(
                    ConversationSession.updated_at.desc(), ConversationSession.created_at.desc()
                )
            )
            conversations = list(session.scalars(statement))
            return [self._serialize_conversation(item) for item in conversations]

    def list_recent_messages(
        self,
        user_identifier: str,
        session_id: str,
        *,
        limit: int = 6,
    ) -> list[ConversationHistoryMessage]:
        """目的：按指定条件读取目标数据、资源或结果集合。
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
                    or_(
                        User.id == user_identifier,
                        User.external_user_id == user_identifier,
                    ),
                    ConversationSession.id == session_id,
                    ConversationMessage.role.in_(("user", "assistant")),
                )
                .order_by(ConversationMessage.created_at.desc(), ConversationMessage.id.desc())
                .limit(limit)
            )
            rows = list(session.scalars(statement))
            rows.reverse()
            return [self._serialize_message(item) for item in rows]

    def get_conversation_context_seed(
        self,
        user_identifier: str,
        session_id: str,
        *,
        limit: int = 40,
    ) -> dict[str, object]:
        """目的：返回构造会话上下文所需的摘要元信息和最近消息。
        结果：返回查询到的业务数据；未满足条件时按约定抛出异常或返回空结果。
        """
        with self.session_factory() as session:
            conversation = (
                session.execute(
                    select(ConversationSession)
                    .join(User, ConversationSession.user_id == User.id)
                    .where(
                        or_(
                            User.id == user_identifier,
                            User.external_user_id == user_identifier,
                        ),
                        ConversationSession.id == session_id,
                    )
                )
                .scalars()
                .first()
            )
            if conversation is None:
                return {
                    "summary_text": "",
                    "covered_message_count": 0,
                    "last_message_id": "",
                    "updated_at": None,
                    "recent_messages": [],
                }

            statement = (
                select(ConversationMessage)
                .where(
                    ConversationMessage.conversation_id == conversation.id,
                    ConversationMessage.role.in_(("user", "assistant")),
                )
                .order_by(ConversationMessage.created_at.desc(), ConversationMessage.id.desc())
                .limit(limit)
            )
            rows = list(session.scalars(statement))
            rows.reverse()
            digest = conversation.memory_digest or {}
            return {
                "summary_text": conversation.summary or "",
                "covered_message_count": int(digest.get("covered_message_count", 0) or 0),
                "last_message_id": str(digest.get("last_summary_message_id", "") or ""),
                "updated_at": conversation.updated_at,
                "recent_messages": [self._serialize_message(item) for item in rows],
            }

    def list_messages_after(
        self,
        session_id: str,
        last_message_id: str,
        *,
        limit: int = 80,
    ) -> list[ConversationHistoryMessage]:
        """目的：返回指定消息之后的会话消息，供滚动摘要任务消费。
        结果：返回符合条件的数据列表。
        """
        with self.session_factory() as session:
            lower_bound = None
            if last_message_id:
                anchor = session.get(ConversationMessage, last_message_id)
                if anchor is not None:
                    lower_bound = anchor.created_at

            statement = select(ConversationMessage).where(
                ConversationMessage.conversation_id == session_id,
                ConversationMessage.role.in_(("user", "assistant")),
            )
            if lower_bound is not None:
                statement = statement.where(ConversationMessage.created_at > lower_bound)
            statement = statement.order_by(
                ConversationMessage.created_at.asc(),
                ConversationMessage.id.asc(),
            ).limit(limit)
            return [self._serialize_message(item) for item in session.scalars(statement)]

    def update_session_summary(
        self,
        session_id: str,
        *,
        summary_text: str,
        covered_message_count: int,
        last_message_id: str,
        summary_version: str = "session_summary.v1",
    ) -> None:
        """目的：更新会话滚动摘要和摘要覆盖位置。
        结果：更新业务资源并返回最新结果。
        """
        with self.session_factory() as session:
            conversation = session.get(ConversationSession, session_id)
            if conversation is None:
                return
            digest = dict(conversation.memory_digest or {})
            digest.update(
                {
                    "covered_message_count": covered_message_count,
                    "last_summary_message_id": last_message_id,
                    "summary_version": summary_version,
                }
            )
            conversation.summary = summary_text
            conversation.memory_digest = digest
            conversation.updated_at = self._now()
            session.commit()

    def get_summary_checkpoint(self, session_id: str) -> dict[str, object]:
        """目的：读取摘要任务需要的当前摘要和覆盖位置。
        结果：返回查询到的业务数据；未满足条件时按约定抛出异常或返回空结果。
        """
        with self.session_factory() as session:
            conversation = session.get(ConversationSession, session_id)
            if conversation is None:
                return {
                    "summary_text": "",
                    "covered_message_count": 0,
                    "last_message_id": "",
                }
            digest = conversation.memory_digest or {}
            return {
                "summary_text": conversation.summary or "",
                "covered_message_count": int(digest.get("covered_message_count", 0) or 0),
                "last_message_id": str(digest.get("last_summary_message_id", "") or ""),
            }

    def _get_or_create_user(self, session: Session, external_user_id: str) -> User:
        """目的：根据当前上下文组装目标对象、消息或输出结构。
        结果：返回结构完整的结果，供后续流程直接使用。
        """
        statement = select(User).where(
            or_(User.id == external_user_id, User.external_user_id == external_user_id)
        )
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

    def claim_guest_conversations(self, *, guest_user_id: str, target_user_id: str) -> int:
        """目的：把访客会话归并到登录用户。
        结果：完成当前实例行为并返回约定结果。
        """
        with self.session_factory() as session:
            guest_user = session.scalar(
                select(User).where(User.external_user_id == guest_user_id)
            )
            target_user = session.get(User, target_user_id)
            if guest_user is None or target_user is None:
                return 0
            result = session.execute(
                update(ConversationSession)
                .where(ConversationSession.user_id == guest_user.id)
                .values(user_id=target_user.id, updated_at=self._now())
            )
            session.commit()
            return int(getattr(result, "rowcount", 0) or 0)

    def _get_or_create_conversation(
        self,
        session: Session,
        user: User,
        request: ChatRequest,
    ) -> ConversationSession:
        """目的：根据当前上下文组装目标对象、消息或输出结构。
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
        """目的：持久化、上传或补充目标数据，保持状态同步。
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
        """目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        conversation.mode = mode
        conversation.updated_at = self._now()
        if not conversation.title.strip() or conversation.title == DEFAULT_CONVERSATION_TITLE:
            conversation.title = message[:10] or DEFAULT_CONVERSATION_TITLE

    def _apply_assistant_message_updates(
        self,
        conversation: ConversationSession,
        trace: ChatTrace,
    ) -> None:
        """目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        conversation.risk_level = trace.safety_level
        digest = dict(conversation.memory_digest or {})
        digest.update({
            "memory_hits": trace.memory_hits,
            "knowledge_hits": trace.knowledge_hits,
            "knowledge_evidences": [item.model_dump() for item in trace.knowledge_evidences],
            "answer_confidence": trace.answer_confidence,
        })
        conversation.memory_digest = digest
        conversation.updated_at = self._now()

    def _build_user_message(self, conversation_id: str, content: str) -> ConversationMessage:
        """目的：根据当前上下文组装目标对象、消息或输出结构。
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
        """目的：根据当前上下文组装目标对象、消息或输出结构。
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

    def _build_interrupted_assistant_message(
        self,
        conversation_id: str,
        partial_reply: str,
        *,
        stream_id: str,
    ) -> ConversationMessage:
        """目的：构造带中断状态的 assistant 部分回复消息。
        结果：DB 中保留原始部分内容和可审计的取消元数据。
        """
        stream_payload = {
            "status": "interrupted",
            "finish_reason": "user_cancelled",
            "stream_id": stream_id,
            "partial": True,
            "exclude_from_long_term_memory": True,
        }
        return ConversationMessage(
            conversation_id=conversation_id,
            role="assistant",
            content=partial_reply,
            trace_json={"stream": stream_payload},
            safety_tags={
                "reply_status": "interrupted",
                "finish_reason": "user_cancelled",
                "exclude_from_long_term_memory": True,
            },
            token_count=len(partial_reply),
        )

    def _serialize_conversation(self, conversation: ConversationSession) -> ConversationHistoryItem:
        """目的：持久化、上传或补充目标数据，保持状态同步。
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

        latest_user = next((item for item in reversed(messages) if item.role == "user"), None)
        preview = latest_user.content[:18] if latest_user is not None else (
            messages[-1].content[:18] if messages else ""
        )
        return ConversationHistoryItem(
            id=conversation.id,
            title=conversation.title or DEFAULT_CONVERSATION_TITLE,
            preview=preview,
            mode=conversation.mode,  # type: ignore[arg-type]
            messages=messages,
            latest_trace=latest_trace,
        )

    def _serialize_message(self, message: ConversationMessage) -> ConversationHistoryMessage:
        """目的：持久化、上传或补充目标数据，保持状态同步。
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
            reply_status=self._resolve_reply_status(message),
        )

    def _resolve_reply_status(self, message: ConversationMessage) -> ReplyStatus:
        """目的：从 JSON 元数据中解析消息完成状态。
        结果：兼容旧数据，未标记的消息默认视为 completed。
        """
        if message.role != "assistant":
            return "completed"
        safety_status = (message.safety_tags or {}).get("reply_status")
        if safety_status == "interrupted":
            return "interrupted"
        stream_raw = (message.trace_json or {}).get("stream")
        if isinstance(stream_raw, dict) and stream_raw.get("status") == "interrupted":
            return "interrupted"
        return "completed"

    def _deserialize_trace(self, payload: dict[str, object]) -> ChatTrace:
        """目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
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
        """目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
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
        """目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
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
        """目的：按指定条件读取目标数据、资源或结果集合。
        结果：返回可直接消费的查询结果，减少调用方重复处理。
        """
        return datetime.now(UTC)
