"""FastAPI 依赖定义。"""

from __future__ import annotations

import logging
import re
import hashlib
import hmac
import time
from dataclasses import dataclass
from uuid import uuid4

from fastapi import HTTPException, Request
from starlette.responses import Response

from core.container import AppContainer
from security import AuthService, CurrentUser, GuestQuotaResult, GuestQuotaService

logger = logging.getLogger(__name__)

GUEST_COOKIE_NAME = "ai_love_guest_id"
_GUEST_ID_PATTERN = re.compile(r"^[a-f0-9-]{32,36}$")
GUEST_DEBUG_HEADER_NAMES = [
    "X-Stream-Id",
    "X-Guest-Identity",
    "X-Guest-Limit",
    "X-Guest-Remaining",
    "X-Guest-Count",
    "X-Guest-Quota-Reason",
]


@dataclass(frozen=True)
class RequestIdentity:
    """目的：当前请求的业务身份。
    结果：提供 RequestIdentity 的结构化能力，供业务流程复用。
    """

    # 目的：保存 user_id 字段，用于 RequestIdentity 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 user_id 值。
    user_id: str
    # 目的：保存 authenticated 字段，用于 RequestIdentity 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 authenticated 值。
    authenticated: bool
    # 目的：保存 current_user 字段，用于 RequestIdentity 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 current_user 值。
    current_user: CurrentUser | None = None
    # 目的：保存 guest_id 字段，用于 RequestIdentity 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 guest_id 值。
    guest_id: str = ""
    # 目的：保存 should_set_guest_cookie 字段，用于 RequestIdentity 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 should_set_guest_cookie 值。
    should_set_guest_cookie: bool = False


def get_container(request: Request) -> AppContainer:
    """目的：获取从应用状态中获取容器。
    结果：返回当前流程需要的对象、配置或查询结果。
    """
    return request.app.state.container


def get_optional_current_user(request: Request, container: AppContainer) -> CurrentUser | None:
    """目的：解析可选登录态：没有 token 允许继续，坏 token 直接拒绝。
    结果：返回查询到的业务数据；未满足条件时按约定抛出异常或返回空结果。
    """
    authorization = request.headers.get("Authorization", "")
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="无效的登录凭证。")
    try:
        return AuthService(settings=container.settings).resolve_current_user(token.strip())
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def require_login(request: Request, container: AppContainer | None = None) -> CurrentUser:
    """目的：要求当前请求必须登录。
    结果：校验访问条件并返回授权后的上下文。
    """
    resolved_container = container or get_container(request)
    current_user = get_optional_current_user(request, resolved_container)
    if current_user is None:
        raise HTTPException(status_code=401, detail="未登录。")
    return current_user


def require_permission(
    request: Request,
    permission_code: str,
    container: AppContainer | None = None,
) -> CurrentUser:
    """目的：要求当前登录用户拥有指定权限。
    结果：校验访问条件并返回授权后的上下文。
    """
    current_user = require_login(request, container)
    if permission_code not in current_user.permissions:
        raise HTTPException(status_code=403, detail="没有权限执行该操作。")
    return current_user


def require_admin_access(request: Request, container: AppContainer | None = None) -> CurrentUser:
    """目的：要求具备后台访问权限。
    结果：校验访问条件并返回授权后的上下文。
    """
    return require_permission(request, "admin:access", container)


def normalize_guest_id(raw_value: str | None) -> str:
    """目的：标准化访客 ID，兼容 guest:uuid 和 uuid 两种输入。
    结果：返回标准化后的业务值。
    """
    value = str(raw_value or "").strip().lower()
    if value.startswith("guest:"):
        value = value.split("guest:", 1)[1].strip()
    return value if _GUEST_ID_PATTERN.match(value) else ""


def _guest_cookie_signature(guest_id: str, expires_at: int, secret: str) -> str:
    """目的：执行 _guest_cookie_signature 对应的模块级处理逻辑。
    结果：返回或落地稳定结果，供调用方继续使用。
    """
    payload = f"{guest_id}.{expires_at}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()[:32]


def _encode_guest_cookie(guest_id: str, container: AppContainer) -> str:
    """目的：执行 _encode_guest_cookie 对应的模块级处理逻辑。
    结果：返回或落地稳定结果，供调用方继续使用。
    """
    expires_at = int(time.time()) + 60 * 60 * 24 * 180
    signature = _guest_cookie_signature(guest_id, expires_at, container.settings.auth_jwt_secret)
    return f"{guest_id}.{expires_at}.{signature}"


def _decode_guest_cookie(raw_value: str | None, container: AppContainer) -> str:
    """目的：执行 _decode_guest_cookie 对应的模块级处理逻辑。
    结果：返回或落地稳定结果，供调用方继续使用。
    """
    value = str(raw_value or "").strip()
    parts = value.split(".")
    if len(parts) != 3:
        return ""
    guest_id = normalize_guest_id(parts[0])
    if not guest_id:
        return ""
    try:
        expires_at = int(parts[1])
    except ValueError:
        return ""
    if expires_at <= int(time.time()):
        return ""
    expected = _guest_cookie_signature(guest_id, expires_at, container.settings.auth_jwt_secret)
    return guest_id if hmac.compare_digest(parts[2], expected) else ""


def extract_request_guest_id(request: Request) -> str:
    """目的：从签名 Cookie 中提取访客 ID，旧 Header 不再可信。
    结果：返回提取后的结构化结果。
    """
    return _decode_guest_cookie(request.cookies.get(GUEST_COOKIE_NAME), get_container(request))


def get_request_identity(request: Request, container: AppContainer) -> RequestIdentity:
    """目的：获取登录用户或匿名访客身份。
    结果：返回查询到的业务数据；未满足条件时按约定抛出异常或返回空结果。
    """
    current_user = get_optional_current_user(request, container)
    if current_user is not None:
        return RequestIdentity(
            user_id=current_user.id,
            authenticated=True,
            current_user=current_user,
        )

    cookie_guest_id = _decode_guest_cookie(request.cookies.get(GUEST_COOKIE_NAME), container)
    guest_id = cookie_guest_id
    should_set_cookie = False
    if not guest_id:
        guest_id = str(uuid4())
        should_set_cookie = True
    return RequestIdentity(
        user_id=f"guest:{guest_id}",
        authenticated=False,
        guest_id=guest_id,
        should_set_guest_cookie=should_set_cookie,
    )


def attach_guest_cookie(response: Response, identity: RequestIdentity, container: AppContainer) -> None:
    """目的：必要时把匿名访客 ID 写入 HttpOnly Cookie。
    结果：把辅助信息写入响应或上下文并返回更新结果。
    """
    if not identity.should_set_guest_cookie or not identity.guest_id:
        return
    response.set_cookie(
        GUEST_COOKIE_NAME,
        _encode_guest_cookie(identity.guest_id, container),
        max_age=60 * 60 * 24 * 180,
        httponly=True,
        secure=container.settings.guest_cookie_secure,
        samesite="lax",
    )


def attach_guest_debug_headers(
    response: Response,
    identity: RequestIdentity,
    quota: GuestQuotaResult | None = None,
) -> None:
    """目的：把访客额度调试信息挂到响应头，便于前后端联调。
    结果：把辅助信息写入响应或上下文并返回更新结果。
    """
    response.headers["X-Guest-Identity"] = identity.user_id if not identity.authenticated else "authenticated"
    if quota is None:
        return
    response.headers["X-Guest-Limit"] = str(quota.limit)
    response.headers["X-Guest-Remaining"] = str(quota.remaining)
    response.headers["X-Guest-Count"] = str(quota.count)
    if quota.reason:
        response.headers["X-Guest-Quota-Reason"] = quota.reason


def consume_guest_quota(
    identity: RequestIdentity,
    container: AppContainer,
    request: Request | None = None,
) -> GuestQuotaResult | None:
    """目的：登录用户跳过访客额度；匿名用户消费一次试用额度。
    结果：完成额度或资源消费并返回消费结果。
    """
    if identity.authenticated:
        logger.info(
            "访客额度跳过: identity=authenticated user_id=%s",
            identity.user_id,
        )
        return None
    ip_key = ""
    if request is not None and request.client is not None:
        ip_key = hashlib.sha256(request.client.host.encode("utf-8")).hexdigest()[:24]
    quota = GuestQuotaService(
        container.redis_service,
        settings=getattr(container, "settings", None),
    ).consume(identity.guest_id, ip_key=ip_key)
    log_method = logger.info if quota.allowed else logger.warning
    log_method(
        "访客额度结果: identity=guest guest_id=%s limit=%d quota_key=%s count=%d remaining=%d allowed=%s reason=%s",
        identity.guest_id,
        quota.limit,
        quota.quota_key,
        quota.count,
        quota.remaining,
        quota.allowed,
        quota.reason or "-",
    )
    return quota


def ensure_rate_limit(user_id: str, container: AppContainer) -> None:
    """目的：执行统一限流检查相关逻辑。
    结果：返回当前步骤的处理结果，供后续流程继续使用。
    """
    if not container.redis_service.check_rate_limit(user_id):
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试。")
