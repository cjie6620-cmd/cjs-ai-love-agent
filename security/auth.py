"""账号密码登录、JWT 签发和当前用户解析。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from core.config import Settings, get_settings
from persistence import AdminRepository, AuthRepository, User


@dataclass(frozen=True)
class CurrentUser:
    """目的：请求中的已认证用户。
    结果：提供 CurrentUser 的结构化能力，供业务流程复用。
    """

    # 目的：保存 id 字段，用于 CurrentUser 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 id 值。
    id: str
    # 目的：保存 tenant_id 字段，用于 CurrentUser 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 tenant_id 值。
    tenant_id: str
    # 目的：保存 external_user_id 字段，用于 CurrentUser 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 external_user_id 值。
    external_user_id: str
    # 目的：保存 nickname 字段，用于 CurrentUser 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 nickname 值。
    nickname: str
    # 目的：保存 avatar_url 字段，用于 CurrentUser 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 avatar_url 值。
    avatar_url: str
    # 目的：保存 roles 字段，用于 CurrentUser 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 roles 值。
    roles: list[str]
    # 目的：保存 permissions 字段，用于 CurrentUser 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 permissions 值。
    permissions: list[str]


@dataclass(frozen=True)
class TokenPair:
    """目的：登录后返回给前端的 token 对。
    结果：提供 TokenPair 的结构化能力，供业务流程复用。
    """

    # 目的：保存 access_token 字段，用于 TokenPair 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 access_token 值。
    access_token: str
    # 目的：保存 refresh_token 字段，用于 TokenPair 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 refresh_token 值。
    refresh_token: str
    # 目的：保存 expires_in 字段，用于 TokenPair 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 expires_in 值。
    expires_in: int


def _b64url_encode(data: bytes) -> str:
    """目的：执行 _b64url_encode 对应的模块级处理逻辑。
    结果：返回或落地稳定结果，供调用方继续使用。
    """
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    """目的：执行 _b64url_decode 对应的模块级处理逻辑。
    结果：返回或落地稳定结果，供调用方继续使用。
    """
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(f"{data}{padding}".encode("ascii"))


def hash_password(password: str) -> str:
    """目的：使用 PBKDF2 保存密码，避免明文落库。
    结果：完成当前业务处理并返回约定结果。
    """
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 210_000)
    return f"pbkdf2_sha256$210000${_b64url_encode(salt)}${_b64url_encode(digest)}"


def verify_password(password: str, password_hash: str) -> bool:
    """目的：校验用户输入密码。
    结果：完成当前业务处理并返回约定结果。
    """
    try:
        scheme, rounds_text, salt_text, digest_text = password_hash.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        rounds = int(rounds_text)
        salt = _b64url_decode(salt_text)
        expected = _b64url_decode(digest_text)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def _sign(data: bytes, secret: str) -> str:
    """目的：执行 _sign 对应的模块级处理逻辑。
    结果：返回或落地稳定结果，供调用方继续使用。
    """
    return _b64url_encode(hmac.new(secret.encode("utf-8"), data, hashlib.sha256).digest())


def create_access_token(user_id: str, *, settings: Settings | None = None) -> str:
    """目的：签发 HS256 JWT access token。
    结果：创建业务资源并返回创建结果。
    """
    resolved = settings or get_settings()
    now = datetime.now(UTC)
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": user_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=resolved.auth_access_token_minutes)).timestamp()),
        "jti": str(uuid4()),
        "scope": "chat",
    }
    encoded_header = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    encoded_payload = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
    return f"{encoded_header}.{encoded_payload}.{_sign(signing_input, resolved.auth_jwt_secret)}"


def parse_access_token(token: str, *, settings: Settings | None = None) -> str:
    """目的：解析 access token，返回用户 ID。
    结果：返回解析后的结构化数据。
    """
    resolved = settings or get_settings()
    try:
        encoded_header, encoded_payload, signature = token.split(".", 2)
        signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
        expected = _sign(signing_input, resolved.auth_jwt_secret)
        if not hmac.compare_digest(signature, expected):
            raise ValueError("token 签名无效")
        payload = json.loads(_b64url_decode(encoded_payload))
        exp = int(payload.get("exp", 0))
        if exp <= int(datetime.now(UTC).timestamp()):
            raise ValueError("token 已过期")
        user_id = str(payload.get("sub") or "").strip()
        if not user_id:
            raise ValueError("token 缺少用户标识")
        return user_id
    except Exception as exc:
        raise ValueError("无效的登录凭证") from exc


def hash_refresh_token(token: str) -> str:
    """目的：refresh token 只保存哈希。
    结果：完成当前业务处理并返回约定结果。
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class AuthService:
    """目的：认证服务：注册、登录、刷新和 token 解析。
    结果：提供 AuthService 的结构化能力，供业务流程复用。
    """

    def __init__(
        self,
        repository: AuthRepository | None = None,
        admin_repository: AdminRepository | None = None,
        *,
        settings: Settings | None = None,
    ) -> None:
        """目的：执行 __init__ 对应的类内处理逻辑。
        结果：返回或更新当前对象状态，供后续流程继续使用。
        """
        self.repository = repository or AuthRepository()
        self.settings = settings or get_settings()
        self.admin_repository = admin_repository or AdminRepository(
            session_factory=self.repository.session_factory,
            settings=self.settings,
        )
        self.admin_repository.bootstrap_defaults()

    def register(
        self,
        *,
        login_name: str,
        password: str,
        nickname: str = "",
        user_agent: str = "",
    ) -> tuple[User, TokenPair]:
        """目的：执行 register 对应的类内处理逻辑。
        结果：返回或更新当前对象状态，供后续流程继续使用。
        """
        user = self.repository.create_account(
            login_name=login_name,
            password_hash=hash_password(password),
            nickname=nickname,
        )
        self.admin_repository.sync_user_bootstrap(user.id, login_name=login_name)
        return user, self._issue_token_pair(user.id, user_agent=user_agent)

    def login(self, *, login_name: str, password: str, user_agent: str = "") -> tuple[User, TokenPair] | None:
        """目的：执行 login 对应的类内处理逻辑。
        结果：返回或更新当前对象状态，供后续流程继续使用。
        """
        account = self.repository.get_account(login_name)
        if account is None or account.status != "active":
            return None
        if not verify_password(password, account.password_hash):
            return None
        user = self.repository.get_user_by_id(account.user_id)
        if user is None or user.status != "active":
            return None
        self.admin_repository.sync_user_bootstrap(user.id, login_name=account.login_name)
        return user, self._issue_token_pair(user.id, user_agent=user_agent)

    def refresh(self, refresh_token: str, *, user_agent: str = "") -> tuple[User, TokenPair] | None:
        """目的：执行 refresh 对应的类内处理逻辑。
        结果：返回或更新当前对象状态，供后续流程继续使用。
        """
        token_hash = hash_refresh_token(refresh_token)
        stored = self.repository.get_active_refresh_token(token_hash)
        if stored is None:
            return None
        self.repository.revoke_refresh_token(token_hash)
        user = self.repository.get_user_by_id(stored.user_id)
        if user is None or user.status != "active":
            return None
        login_name = self.repository.get_login_name_by_user_id(user.id)
        self.admin_repository.sync_user_bootstrap(user.id, login_name=login_name)
        return user, self._issue_token_pair(user.id, user_agent=user_agent)

    def logout(self, refresh_token: str) -> bool:
        """目的：执行 logout 对应的类内处理逻辑。
        结果：返回或更新当前对象状态，供后续流程继续使用。
        """
        return self.repository.revoke_refresh_token(hash_refresh_token(refresh_token))

    def resolve_current_user(self, access_token: str) -> CurrentUser:
        """目的：执行 resolve_current_user 对应的类内处理逻辑。
        结果：返回或更新当前对象状态，供后续流程继续使用。
        """
        user_id = parse_access_token(access_token, settings=self.settings)
        user = self.repository.get_user_by_id(user_id)
        if user is None or user.status != "active":
            raise ValueError("用户不存在")
        login_name = self.repository.get_login_name_by_user_id(user.id)
        self.admin_repository.sync_user_bootstrap(user.id, login_name=login_name)
        authz = self.admin_repository.get_user_authz(user.id)
        if authz is None:
            raise ValueError("用户不可用")
        return CurrentUser(
            id=user.id,
            tenant_id=str(authz["tenant_id"]),
            external_user_id=user.external_user_id,
            nickname=user.nickname,
            avatar_url=user.avatar_url,
            roles=list(authz["roles"]),
            permissions=list(authz["permissions"]),
        )

    def update_profile(self, *, user_id: str, nickname: str) -> User | None:
        """目的：执行 update_profile 对应的类内处理逻辑。
        结果：返回或更新当前对象状态，供后续流程继续使用。
        """
        return self.repository.update_user_profile(user_id, nickname=nickname)

    def update_avatar(self, *, user_id: str, avatar_url: str) -> User | None:
        """目的：执行 update_avatar 对应的类内处理逻辑。
        结果：返回或更新当前对象状态，供后续流程继续使用。
        """
        return self.repository.update_user_avatar(user_id, avatar_url=avatar_url)

    def _issue_token_pair(self, user_id: str, *, user_agent: str = "") -> TokenPair:
        """目的：执行 _issue_token_pair 对应的类内处理逻辑。
        结果：返回或更新当前对象状态，供后续流程继续使用。
        """
        access_token = create_access_token(user_id, settings=self.settings)
        refresh_token = secrets.token_urlsafe(48)
        expires_at = datetime.now(UTC) + timedelta(days=self.settings.auth_refresh_token_days)
        self.repository.save_refresh_token(
            user_id=user_id,
            token_hash=hash_refresh_token(refresh_token),
            expires_at=expires_at,
            user_agent=user_agent,
        )
        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=self.settings.auth_access_token_minutes * 60,
        )
