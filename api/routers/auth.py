"""登录认证路由。"""

from __future__ import annotations

from pathlib import PurePosixPath
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import Response

from api.deps import (
    extract_request_guest_id,
    get_container,
    get_optional_current_user,
)
from contracts.auth import (
    AuthCredentials,
    AuthMeResponse,
    AuthRegisterRequest,
    AuthTokenResponse,
    AuthUserPayload,
    RefreshTokenRequest,
    UpdateProfileRequest,
)
from contracts.common import ApiResponse, success_response
from security import AuthService

router = APIRouter()

_AVATAR_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
_MAX_AVATAR_BYTES = 2 * 1024 * 1024


def _user_payload(
    user_id: str,
    *,
    nickname: str,
    tenant_id: str = "default",
    external_user_id: str = "",
    avatar_url: str = "",
    roles: list[str] | None = None,
    permissions: list[str] | None = None,
) -> AuthUserPayload:
    """目的：执行 _user_payload 对应的模块级处理逻辑。
    结果：返回或落地稳定结果，供调用方继续使用。
    """
    return AuthUserPayload(
        id=user_id,
        tenant_id=tenant_id,
        nickname=nickname,
        external_user_id=external_user_id,
        avatar_url=avatar_url,
        roles=roles or [],
        permissions=permissions or [],
    )


def _token_response(result) -> AuthTokenResponse:
    """目的：执行 _token_response 对应的模块级处理逻辑。
    结果：返回或落地稳定结果，供调用方继续使用。
    """
    user, token_pair = result
    # 登录/注册后立即按 RBAC 读取一次完整权限，返回给前端路由守卫使用。
    from persistence import AdminRepository

    authz = AdminRepository().get_user_authz(user.id) or {}
    return AuthTokenResponse(
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
        expires_in=token_pair.expires_in,
        user=_user_payload(
            user.id,
            nickname=user.nickname or user.external_user_id,
            tenant_id=str(authz.get("tenant_id") or user.tenant_id),
            external_user_id=user.external_user_id,
            avatar_url=user.avatar_url,
            roles=list(authz.get("roles") or []),
            permissions=list(authz.get("permissions") or []),
        ),
    )


def _claim_guest_if_present(request: Request, user_id: str) -> None:
    """目的：执行 _claim_guest_if_present 对应的模块级处理逻辑。
    结果：返回或落地稳定结果，供调用方继续使用。
    """
    container = get_container(request)
    guest_id = extract_request_guest_id(request)
    if not guest_id:
        return
    container.conversation_repository.claim_guest_conversations(
        guest_user_id=f"guest:{guest_id}",
        target_user_id=user_id,
    )


@router.post("/register", response_model=ApiResponse[AuthTokenResponse])
async def register(payload: AuthRegisterRequest, request: Request) -> ApiResponse[AuthTokenResponse]:
    """目的：注册账号并登录。
    结果：完成账号创建并返回登录态信息。
    """
    service = AuthService(settings=get_container(request).settings)
    try:
        result = service.register(
            login_name=payload.login_name,
            password=payload.password,
            nickname=payload.nickname,
            user_agent=request.headers.get("User-Agent", ""),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _claim_guest_if_present(request, result[0].id)
    return success_response(_token_response(result))


@router.post("/login", response_model=ApiResponse[AuthTokenResponse])
async def login(payload: AuthCredentials, request: Request) -> ApiResponse[AuthTokenResponse]:
    """目的：账号密码登录。
    结果：完成登录校验并返回登录态信息。
    """
    service = AuthService(settings=get_container(request).settings)
    result = service.login(
        login_name=payload.login_name,
        password=payload.password,
        user_agent=request.headers.get("User-Agent", ""),
    )
    if result is None:
        raise HTTPException(status_code=401, detail="账号或密码错误。")
    _claim_guest_if_present(request, result[0].id)
    return success_response(_token_response(result))


@router.post("/refresh", response_model=ApiResponse[AuthTokenResponse])
async def refresh(payload: RefreshTokenRequest, request: Request) -> ApiResponse[AuthTokenResponse]:
    """目的：刷新 access token。
    结果：刷新登录凭证并返回新的登录态信息。
    """
    service = AuthService(settings=get_container(request).settings)
    result = service.refresh(
        payload.refresh_token,
        user_agent=request.headers.get("User-Agent", ""),
    )
    if result is None:
        raise HTTPException(status_code=401, detail="刷新凭证无效或已过期。")
    return success_response(_token_response(result))


@router.post("/logout", response_model=ApiResponse[dict[str, bool]])
async def logout(payload: RefreshTokenRequest, request: Request) -> ApiResponse[dict[str, bool]]:
    """目的：退出登录，吊销 refresh token。
    结果：清理登录态并返回退出结果。
    """
    service = AuthService(settings=get_container(request).settings)
    return success_response({"ok": service.logout(payload.refresh_token)})


@router.get("/me", response_model=ApiResponse[AuthMeResponse])
async def me(request: Request) -> ApiResponse[AuthMeResponse]:
    """目的：获取当前登录用户。
    结果：完成当前业务处理并返回约定结果。
    """
    container = get_container(request)
    current_user = get_optional_current_user(request, container)
    if current_user is None:
        raise HTTPException(status_code=401, detail="未登录。")
    return success_response(AuthMeResponse(
        user=_user_payload(
            current_user.id,
            nickname=current_user.nickname or current_user.external_user_id,
            tenant_id=current_user.tenant_id,
            external_user_id=current_user.external_user_id,
            avatar_url=current_user.avatar_url,
            roles=current_user.roles,
            permissions=current_user.permissions,
        )
    ))


@router.put("/me", response_model=ApiResponse[AuthMeResponse])
async def update_me(payload: UpdateProfileRequest, request: Request) -> ApiResponse[AuthMeResponse]:
    """目的：修改当前登录用户资料。
    结果：更新业务资源并返回最新结果。
    """
    container = get_container(request)
    current_user = get_optional_current_user(request, container)
    if current_user is None:
        raise HTTPException(status_code=401, detail="未登录。")
    service = AuthService(settings=container.settings)
    user = service.update_profile(user_id=current_user.id, nickname=payload.nickname)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在。")
    return success_response(AuthMeResponse(
        user=_user_payload(
            user.id,
            nickname=user.nickname or user.external_user_id,
            tenant_id=user.tenant_id,
            external_user_id=user.external_user_id,
            avatar_url=user.avatar_url,
        )
    ))


@router.post("/me/avatar", response_model=ApiResponse[AuthMeResponse])
async def upload_avatar(
    request: Request,
    file: UploadFile = File(..., description="用户头像图片"),
) -> ApiResponse[AuthMeResponse]:
    """目的：上传当前用户头像到 MinIO。
    结果：完成上传处理并返回资源信息。
    """
    container = get_container(request)
    current_user = get_optional_current_user(request, container)
    if current_user is None:
        raise HTTPException(status_code=401, detail="未登录。")

    content_type = str(file.content_type or "").lower()
    suffix = _AVATAR_CONTENT_TYPES.get(content_type)
    if suffix is None:
        raise HTTPException(status_code=400, detail="头像仅支持 jpg、png、webp、gif。")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="头像文件不能为空。")
    if len(data) > _MAX_AVATAR_BYTES:
        raise HTTPException(status_code=413, detail="头像不能超过 2MB。")

    object_name = container.minio_client.upload_file(
        data,
        f"{uuid4().hex}{suffix}",
        content_type=content_type,
        prefix="avatars",
    )
    if object_name is None:
        raise HTTPException(status_code=503, detail="头像上传服务暂不可用。")

    avatar_url = f"/auth/avatar/{object_name}"
    service = AuthService(settings=container.settings)
    user = service.update_avatar(user_id=current_user.id, avatar_url=avatar_url)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在。")

    old_object = _avatar_object_name(current_user.avatar_url)
    if old_object and old_object != object_name:
        container.minio_client.delete_file(old_object)

    return success_response(AuthMeResponse(
        user=_user_payload(
            user.id,
            nickname=user.nickname or user.external_user_id,
            tenant_id=user.tenant_id,
            external_user_id=user.external_user_id,
            avatar_url=user.avatar_url,
        )
    ))


@router.get("/avatar/{object_path:path}")
async def get_avatar(object_path: str, request: Request) -> Response:
    """目的：读取头像对象，供前端 img 直接展示。
    结果：返回查询到的业务数据；未满足条件时按约定抛出异常或返回空结果。
    """
    normalized = str(PurePosixPath(object_path))
    if not normalized.startswith("avatars/") or ".." in PurePosixPath(normalized).parts:
        raise HTTPException(status_code=404, detail="头像不存在。")
    data = get_container(request).minio_client.download_file(normalized)
    if data is None:
        raise HTTPException(status_code=404, detail="头像不存在。")
    content_type = _content_type_from_name(normalized)
    return Response(content=data, media_type=content_type)


def _avatar_object_name(avatar_url: str) -> str:
    """目的：执行 _avatar_object_name 对应的模块级处理逻辑。
    结果：返回或落地稳定结果，供调用方继续使用。
    """
    prefix = "/auth/avatar/"
    if avatar_url.startswith(prefix):
        return avatar_url[len(prefix):]
    return ""


def _content_type_from_name(object_name: str) -> str:
    """目的：执行 _content_type_from_name 对应的模块级处理逻辑。
    结果：返回或落地稳定结果，供调用方继续使用。
    """
    suffix = PurePosixPath(object_name).suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    if suffix == ".webp":
        return "image/webp"
    if suffix == ".gif":
        return "image/gif"
    return "application/octet-stream"
