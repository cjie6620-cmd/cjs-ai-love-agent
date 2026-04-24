from dataclasses import dataclass

from prompt.contracts import PromptSection, PromptSpec
from prompt.repository import PromptRepository


@dataclass
class _FakeMessage:
    """_FakeMessage 测试辅助类。

    目的：归类同一主题下的验证场景，集中描述预期行为和边界条件。
    结果：便于回归时快速定位测试范围，保证关键能力持续可验证。
    """
    type: str
    content: str


@dataclass
class _FakePromptValue:
    """_FakePromptValue 测试辅助类。

    目的：归类同一主题下的验证场景，集中描述预期行为和边界条件。
    结果：便于回归时快速定位测试范围，保证关键能力持续可验证。
    """
    messages: list[_FakeMessage]


class _FakePrompt:
    """_FakePrompt 测试辅助类。

    目的：归类同一主题下的验证场景，集中描述预期行为和边界条件。
    结果：便于回归时快速定位测试范围，保证关键能力持续可验证。
    """
    def invoke(self, variables):
        """执行 invoke 方法。

        目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        return _FakePromptValue(
            messages=[
                _FakeMessage(type="system", content=f"remote-system:{variables['message']}"),
                _FakeMessage(type="human", content=f"remote-user:{variables['mode']}"),
            ]
        )


def _build_local_spec() -> PromptSpec:
    """build local spec 测试辅助方法。
    
    目的：为当前测试文件提供公共构造、准备或提取逻辑。
    结果：减少重复测试代码，提升测试可读性和维护性。
    """
    return PromptSpec(
        name="chat.reply",
        prompt_version="local.v1",
        output_schema_name="ChatReplyModel",
        output_contract_version="chat_reply.v1",
        system_sections=[PromptSection(name="role", content="local-system")],
        user_sections=[PromptSection(name="context", content="local-user")],
        fallback_policy="fallback",
    )


def test_prompt_repository_falls_back_to_local_spec(monkeypatch) -> None:
    """验证 prompt repository falls back to local spec。
    
    目的：覆盖当前场景的核心行为或边界条件，避免回归引入隐性问题。
    结果：断言关键输出与副作用符合预期，保证实现行为稳定。
    """
    repository = PromptRepository()
    monkeypatch.setattr(repository._langsmith, "pull_prompt", lambda identifier: None)

    result = repository.resolve(
        prompt_identifier="",
        fallback_spec=_build_local_spec(),
        variables={"message": "你好", "mode": "companion"},
    )

    assert result.prompt_version == "local.v1"
    assert "local-system" in result.render_system_prompt()


def test_prompt_repository_prefers_langsmith_prompt(monkeypatch) -> None:
    """验证 prompt repository prefers langsmith prompt。
    
    目的：覆盖当前场景的核心行为或边界条件，避免回归引入隐性问题。
    结果：断言关键输出与副作用符合预期，保证实现行为稳定。
    """
    repository = PromptRepository()
    monkeypatch.setattr(repository._langsmith, "pull_prompt", lambda identifier: _FakePrompt())

    result = repository.resolve(
        prompt_identifier="prompt://chat.reply",
        fallback_spec=_build_local_spec(),
        variables={"message": "你好", "mode": "companion"},
    )

    assert result.prompt_version == "langsmith:prompt://chat.reply"
    assert "remote-system:你好" in result.render_system_prompt()
    assert "remote-user:companion" in result.render_user_prompt()
