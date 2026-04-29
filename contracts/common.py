"""通用响应契约。"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """目的：统一普通 JSON API 的响应外层结构。
    结果：所有 JSON 接口都可以稳定返回 code、message 和 data。
    """

    code: int = Field(default=200, description="HTTP 状态码或对应业务处理状态")
    message: str = Field(default="success", description="响应提示信息")
    data: T | None = Field(default=None, description="业务响应数据")


class ApiErrorData(BaseModel):
    """目的：承载错误响应中的可选业务上下文。
    结果：调用方可以在统一错误结构中读取业务错误码和补充信息。
    """

    error_code: str = Field(default="", description="业务错误码")
    remaining: int | None = Field(default=None, description="剩余次数")
    limit: int | None = Field(default=None, description="限制次数")
    errors: list[dict[str, Any]] = Field(default_factory=list, description="参数校验错误详情")


def success_response(data: T | None = None, message: str = "success") -> ApiResponse[T]:
    """目的：创建统一成功响应对象。
    结果：路由层可以用一致格式返回业务数据。
    """
    return ApiResponse[T](code=200, message=message, data=data)


def error_response(
    code: int,
    message: str,
    data: Any | None = None,
) -> ApiResponse[Any]:
    """目的：创建统一错误响应对象。
    结果：异常处理和特殊失败分支可以用一致格式返回错误信息。
    """
    return ApiResponse[Any](code=code, message=message, data=data)


class DependencyHealthItem(BaseModel):
    """目的：描述启动探活或健康检查中某个外部依赖的状态。
    结果：健康接口可以稳定返回依赖名称、状态、端点和详情。
    """

    # 目的：保存 name 字段，用于 DependencyHealthItem 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 name 值。
    name: str = Field(default="")
    # 目的：保存 status 字段，用于 DependencyHealthItem 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 status 值。
    status: str = Field(default="")
    # 目的：保存 endpoint 字段，用于 DependencyHealthItem 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 endpoint 值。
    endpoint: str = Field(default="")
    # 目的：保存 detail 字段，用于 DependencyHealthItem 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 detail 值。
    detail: str = Field(default="")


class HealthResponse(BaseModel):
    """目的：描述健康检查响应的数据结构和字段约束。
    结果：对象在校验、序列化和模块传输时保持一致。
    """

    # 目的：保存 status 字段，用于 HealthResponse 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 status 值。
    status: str = Field(default="ok")
    # 目的：保存 service 字段，用于 HealthResponse 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 service 值。
    service: str = Field(default="ai-love")
    # 目的：保存 timestamp 字段，用于 HealthResponse 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 timestamp 值。
    timestamp: str = Field(default="")
    # 目的：保存 summary 字段，用于 HealthResponse 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 summary 值。
    summary: str = Field(default="")
    # 目的：保存 dependencies 字段，用于 HealthResponse 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 dependencies 值。
    dependencies: list[DependencyHealthItem] = Field(default_factory=list)


class ApiErrorResponse(BaseModel):
    """目的：表达特定场景下的异常语义，方便上层统一识别和处理失败分支。
    结果：调用方可以按异常类型捕获并执行对应的降级、重试或告警逻辑。
    """

    # 目的：保存 detail 字段，用于 ApiErrorResponse 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 detail 值。
    detail: str = Field(default="")
