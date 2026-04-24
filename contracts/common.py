"""通用响应契约。"""

from pydantic import BaseModel, Field


class DependencyHealthItem(BaseModel):
    """单个依赖健康状态。"""

    name: str = Field(default="")
    status: str = Field(default="")
    endpoint: str = Field(default="")
    detail: str = Field(default="")


class HealthResponse(BaseModel):
    """健康检查响应。
    
    目的：描述健康检查响应的数据结构和字段约束。
    结果：对象在校验、序列化和模块传输时保持一致。
    """

    status: str = Field(default="ok")
    service: str = Field(default="ai-love")
    timestamp: str = Field(default="")
    summary: str = Field(default="")
    dependencies: list[DependencyHealthItem] = Field(default_factory=list)


class ApiErrorResponse(BaseModel):
    """统一错误响应。

    目的：表达特定场景下的异常语义，方便上层统一识别和处理失败分支。
    结果：调用方可以按异常类型捕获并执行对应的降级、重试或告警逻辑。
    """

    detail: str = Field(default="")
