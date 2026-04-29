from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from core.config import get_settings

from .db_base import get_session_factory
from .models import AuthAccount, AuthRefreshToken, User


class AuthRepository:
    """目的：认证仓储：负责账号、用户和刷新令牌的持久化。
    结果：提供 AuthRepository 的结构化能力，供业务流程复用。
    """

    def __init__(self, session_factory: sessionmaker[Session] | None = None) -> None:
        """目的：执行 __init__ 对应的类内处理逻辑。
        结果：返回或更新当前对象状态，供后续流程继续使用。
        """
        self.session_factory = session_factory or get_session_factory()

    def create_account(self, *, login_name: str, password_hash: str, nickname: str = "") -> User:
        """目的：创建业务用户和登录账号。
        结果：创建业务资源并返回创建结果。
        """
        normalized = login_name.strip().lower()
        display_name = nickname.strip() or normalized
        with self.session_factory() as session:
            existing = session.scalar(
                select(AuthAccount).where(AuthAccount.login_name == normalized)
            )
            if existing is not None:
                raise ValueError("账号已存在")

            settings = get_settings()
            user = User(
                tenant_id=settings.default_tenant_id,
                external_user_id=normalized,
                nickname=display_name,
                status="active",
            )
            session.add(user)
            session.flush()
            session.add(
                AuthAccount(
                    user_id=user.id,
                    login_name=normalized,
                    password_hash=password_hash,
                    status="active",
                )
            )
            session.commit()
            session.refresh(user)
            return user

    def update_user_profile(self, user_id: str, *, nickname: str) -> User | None:
        """目的：更新用户基础资料。
        结果：更新业务资源并返回最新结果。
        """
        display_name = nickname.strip()
        if not display_name:
            return None
        with self.session_factory() as session:
            user = session.get(User, user_id)
            if user is None:
                return None
            user.nickname = display_name
            session.commit()
            session.refresh(user)
            return user

    def update_user_avatar(self, user_id: str, *, avatar_url: str) -> User | None:
        """目的：更新用户头像地址。
        结果：更新业务资源并返回最新结果。
        """
        with self.session_factory() as session:
            user = session.get(User, user_id)
            if user is None:
                return None
            user.avatar_url = avatar_url.strip()
            session.commit()
            session.refresh(user)
            return user

    def get_account(self, login_name: str) -> AuthAccount | None:
        """目的：按登录名读取账号。
        结果：返回查询到的业务数据；未满足条件时按约定抛出异常或返回空结果。
        """
        normalized = login_name.strip().lower()
        with self.session_factory() as session:
            return session.scalar(select(AuthAccount).where(AuthAccount.login_name == normalized))

    def get_user_by_id(self, user_id: str) -> User | None:
        """目的：按内部用户 ID 获取业务用户。
        结果：返回查询到的业务数据；未满足条件时按约定抛出异常或返回空结果。
        """
        with self.session_factory() as session:
            return session.get(User, user_id)

    def get_login_name_by_user_id(self, user_id: str) -> str:
        """目的：按用户 ID 获取登录名。
        结果：返回查询到的业务数据；未满足条件时按约定抛出异常或返回空结果。
        """
        with self.session_factory() as session:
            account = session.scalar(select(AuthAccount).where(AuthAccount.user_id == user_id))
            return account.login_name if account is not None else ""

    def save_refresh_token(
        self,
        *,
        user_id: str,
        token_hash: str,
        expires_at: datetime,
        user_agent: str = "",
    ) -> str:
        """目的：保存 refresh token 哈希。
        结果：完成当前实例行为并返回约定结果。
        """
        with self.session_factory() as session:
            token = AuthRefreshToken(
                user_id=user_id,
                token_hash=token_hash,
                expires_at=expires_at,
                user_agent=user_agent[:255],
                revoked=False,
            )
            session.add(token)
            session.commit()
            return token.id

    def get_active_refresh_token(self, token_hash: str) -> AuthRefreshToken | None:
        """目的：读取未吊销且未过期的 refresh token。
        结果：返回查询到的业务数据；未满足条件时按约定抛出异常或返回空结果。
        """
        now = datetime.now(UTC)
        with self.session_factory() as session:
            return session.scalar(
                select(AuthRefreshToken)
                .where(AuthRefreshToken.token_hash == token_hash)
                .where(AuthRefreshToken.revoked.is_(False))
                .where(AuthRefreshToken.expires_at > now)
            )

    def revoke_refresh_token(self, token_hash: str) -> bool:
        """目的：吊销单个 refresh token。
        结果：完成当前实例行为并返回约定结果。
        """
        with self.session_factory() as session:
            token = session.scalar(
                select(AuthRefreshToken).where(AuthRefreshToken.token_hash == token_hash)
            )
            if token is None:
                return False
            token.revoked = True
            session.commit()
            return True
