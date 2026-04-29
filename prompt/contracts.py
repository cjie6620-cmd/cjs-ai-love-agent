# -*- coding: utf-8 -*-
"""
Prompt Contract 定义：统一描述可渲染、可追踪、可复用的提示词模板。

目的：提供结构化的 Prompt 描述能力，支持片段化管理、版本追踪和模板渲染。
结果：提供 PromptSection 和 PromptSpec 两个核心类，用于构建和渲染提示词模板。
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace


@dataclass(slots=True)
class PromptSection:
    """目的：封装当前领域对象的核心职责，统一相关行为和数据边界。
    结果：相关模块可以围绕该对象稳定协作，提升代码可读性和可维护性。
    """

    # 目的：保存 name 字段，用于 PromptSection 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 name 值。
    name: str
    # 目的：保存 content 字段，用于 PromptSection 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 content 值。
    content: str

    def render(self) -> str:
        """目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        body = self.content.strip() or "无"
        return f"<{self.name}>\n{body}\n</{self.name}>"


@dataclass(slots=True)
class PromptSpec:
    """目的：封装当前领域对象的核心职责，统一相关行为和数据边界。
    结果：相关模块可以围绕该对象稳定协作，提升代码可读性和可维护性。
    """

    # 目的：保存 name 字段，用于 PromptSpec 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 name 值。
    name: str
    # 目的：保存 prompt_version 字段，用于 PromptSpec 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 prompt_version 值。
    prompt_version: str
    # 目的：保存 output_schema_name 字段，用于 PromptSpec 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 output_schema_name 值。
    output_schema_name: str
    # 目的：保存 output_contract_version 字段，用于 PromptSpec 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 output_contract_version 值。
    output_contract_version: str = "v1"
    # 目的：保存 system_sections 字段，用于 PromptSpec 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 system_sections 值。
    system_sections: list[PromptSection] = field(default_factory=list)
    # 目的：保存 user_sections 字段，用于 PromptSpec 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 user_sections 值。
    user_sections: list[PromptSection] = field(default_factory=list)
    # 目的：保存 fallback_policy 字段，用于 PromptSpec 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 fallback_policy 值。
    fallback_policy: str = ""

    def with_examples_section(self, content: str) -> "PromptSpec":
        """目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        sections = [section for section in self.system_sections if section.name != "examples"]
        insert_index = len(sections)
        for index, section in enumerate(sections):
            if section.name == "output_contract":
                insert_index = index
                break
        sections.insert(insert_index, PromptSection(name="examples", content=content))
        return replace(self, system_sections=sections)

    def render_system_prompt(self) -> str:
        """目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        header = (
            f"prompt_name={self.name}\n"
            f"prompt_version={self.prompt_version}\n"
            f"output_schema={self.output_schema_name}\n"
            f"output_contract_version={self.output_contract_version}"
        )
        return self._render(header, self.system_sections)

    def render_user_prompt(self) -> str:
        """目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        header = "请严格基于以下上下文完成本轮任务。"
        return self._render(header, self.user_sections)

    def _render(self, header: str, sections: list[PromptSection]) -> str:
        """目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        rendered = [header.strip()]
        rendered.extend(section.render() for section in sections)
        return "\n\n".join(item for item in rendered if item.strip())
