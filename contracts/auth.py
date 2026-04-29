"""认证接口契约。"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class AuthCredentials(BaseModel):
    """目的：账号密码请求。
    结果：提供 AuthCredentials 的结构化能力，供业务流程复用。
    """

    # 目的：保存 login_name 字段，用于 AuthCredentials 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 login_name 值。
    login_name: str = Field(..., min_length=3, max_length=64)
    # 目的：保存 password 字段，用于 AuthCredentials 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 password 值。
    password: str = Field(..., min_length=6, max_length=128)

    @field_validator("login_name", mode="before")
    @classmethod
    def normalize_login_name(cls, value: object) -> str:
        """目的：执行 normalize_login_name 对应的类内处理逻辑。
        结果：返回或更新当前对象状态，供后续流程继续使用。
        """
        return str(value or "").strip().lower()


class AuthRegisterRequest(AuthCredentials):
    """目的：注册请求。
    结果：提供 AuthRegisterRequest 的结构化能力，供业务流程复用。
    """

    # 目的：保存 nickname 字段，用于 AuthRegisterRequest 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 nickname 值。
    nickname: str = Field(default="", max_length=64)

    @field_validator("nickname", mode="before")
    @classmethod
    def normalize_nickname(cls, value: object) -> str:
        """目的：执行 normalize_nickname 对应的类内处理逻辑。
        结果：返回或更新当前对象状态，供后续流程继续使用。
        """
        return str(value or "").strip()


class UpdateProfileRequest(BaseModel):
    """目的：修改个人资料请求。
    结果：提供 UpdateProfileRequest 的结构化能力，供业务流程复用。
    """

    # 目的：保存 nickname 字段，用于 UpdateProfileRequest 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 nickname 值。
    nickname: str = Field(..., min_length=1, max_length=64)

    @field_validator("nickname", mode="before")
    @classmethod
    def normalize_nickname(cls, value: object) -> str:
        """目的：执行 normalize_nickname 对应的类内处理逻辑。
        结果：返回或更新当前对象状态，供后续流程继续使用。
        """
        return str(value or "").strip()


class RefreshTokenRequest(BaseModel):
    """目的：刷新或退出请求。
    结果：提供 RefreshTokenRequest 的结构化能力，供业务流程复用。
    """

    # 目的：保存 refresh_token 字段，用于 RefreshTokenRequest 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 refresh_token 值。
    refresh_token: str = Field(..., min_length=20)


class AuthUserPayload(BaseModel):
    """目的：前端展示用用户信息。
    结果：提供 AuthUserPayload 的结构化能力，供业务流程复用。
    """

    # 目的：保存 id 字段，用于 AuthUserPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 id 值。
    id: str
    # 目的：保存 tenant_id 字段，用于 AuthUserPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 tenant_id 值。
    tenant_id: str = "default"
    # 目的：保存 nickname 字段，用于 AuthUserPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 nickname 值。
    nickname: str
    # 目的：保存 external_user_id 字段，用于 AuthUserPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 external_user_id 值。
    external_user_id: str = ""
    # 目的：保存 avatar_url 字段，用于 AuthUserPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 avatar_url 值。
    avatar_url: str = ""
    # 目的：保存 roles 字段，用于 AuthUserPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 roles 值。
    roles: list[str] = Field(default_factory=list)
    # 目的：保存 permissions 字段，用于 AuthUserPayload 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 permissions 值。
    permissions: list[str] = Field(default_factory=list)


class AuthTokenResponse(BaseModel):
    """目的：登录/注册/刷新响应。
    结果：提供 AuthTokenResponse 的结构化能力，供业务流程复用。
    """

    # 目的：保存 access_token 字段，用于 AuthTokenResponse 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 access_token 值。
    access_token: str
    # 目的：保存 refresh_token 字段，用于 AuthTokenResponse 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 refresh_token 值。
    refresh_token: str
    # 目的：保存 token_type 字段，用于 AuthTokenResponse 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 token_type 值。
    token_type: str = "bearer"
    # 目的：保存 expires_in 字段，用于 AuthTokenResponse 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 expires_in 值。
    expires_in: int
    # 目的：保存 user 字段，用于 AuthTokenResponse 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 user 值。
    user: AuthUserPayload


class AuthMeResponse(BaseModel):
    """目的：当前用户响应。
    结果：提供 AuthMeResponse 的结构化能力，供业务流程复用。
    """

    # 目的：保存 user 字段，用于 AuthMeResponse 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 user 值。
    user: AuthUserPayload
