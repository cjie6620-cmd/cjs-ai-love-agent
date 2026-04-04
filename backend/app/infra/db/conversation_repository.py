from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload, sessionmaker

from ...schemas.chat import (
    ChatRequest,
    ChatResponse,
    ChatTrace,
    ConversationHistoryItem,
    ConversationHistoryMessage,
)
from .base import get_session_factory
from .models import ConversationMessage, ConversationSession, User

DEFAULT_CONVERSATION_TITLE = "新对话"


class ConversationRepository:
    """负责会话持久化，隔离业务层与 SQLAlchemy 细节。"""

    def __init__(self, session_factory: sessionmaker[Session] | None = None) -> None:
        self.session_factory = session_factory or get_session_factory()

    def save_turn(self, request: ChatRequest, response: ChatResponse) -> None:
        """一次性保存一轮完整问答，适合非流式接口。"""
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
        """先保存用户输入，避免流式回复中途失败后整轮数据完全丢失。"""
        with self.session_factory() as session:
            user = self._get_or_create_user(session, request.user_id)
            conversation = self._get_or_create_conversation(session, user, request)

            self._apply_user_message_updates(conversation, request.message, request.mode)
            session.add(self._build_user_message(conversation.id, request.message))
            conversation.message_count += 1
            user.last_active_at = self._now()

            session.commit()

    def save_assistant_message(self, request: ChatRequest, response: ChatResponse) -> None:
        """流式完成后补写助手回复与 trace。"""
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
        """按最近更新时间倒序返回指定用户的历史会话。"""
        with self.session_factory() as session:
            statement = (
                select(ConversationSession)
                .join(User, ConversationSession.user_id == User.id)
                .options(selectinload(ConversationSession.messages))
                .where(User.external_user_id == external_user_id)
                .order_by(ConversationSession.updated_at.desc(), ConversationSession.created_at.desc())
            )
            conversations = list(session.scalars(statement))
            return [self._serialize_conversation(item) for item in conversations]

    def _get_or_create_user(self, session: Session, external_user_id: str) -> User:
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
        conversation.risk_level = trace.safety_level
        conversation.memory_digest = {
            "memory_hits": trace.memory_hits,
            "knowledge_hits": trace.knowledge_hits,
        }
        conversation.updated_at = self._now()

    def _build_user_message(self, conversation_id: str, content: str) -> ConversationMessage:
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
        return ConversationMessage(
            conversation_id=conversation_id,
            role="assistant",
            content=response.reply,
            trace_json=response.trace.model_dump(),
            safety_tags={"safety_level": response.trace.safety_level},
            token_count=len(response.reply),
        )

    def _serialize_conversation(self, conversation: ConversationSession) -> ConversationHistoryItem:
        messages = [
            ConversationHistoryMessage(
                id=item.id,
                role="user" if item.role == "user" else "assistant",
                content=item.content,
                created_at=item.created_at,
            )
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

    def _deserialize_trace(self, payload: dict[str, object]) -> ChatTrace:
        return ChatTrace(
            memory_hits=[
                item for item in payload.get("memory_hits", []) if isinstance(item, str)
            ],
            knowledge_hits=[
                item for item in payload.get("knowledge_hits", []) if isinstance(item, str)
            ],
            safety_level=str(payload.get("safety_level", "low")),
        )

    def _now(self) -> datetime:
        return datetime.now(UTC)
