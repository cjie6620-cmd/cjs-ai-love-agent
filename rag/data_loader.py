"""知识库文件加载与清洗。"""

from __future__ import annotations

from pathlib import Path


class KnowledgeDataLoader:
    """目的：封装当前领域对象的核心职责，统一相关行为和数据边界。
    结果：相关模块可以围绕该对象稳定协作，提升代码可读性和可维护性。
    """

    # 目的：保存 SUPPORTED_SUFFIXES 字段，用于 KnowledgeDataLoader 的业务状态、配置或序列化。
    # 结果：实例在读写、校验和协作时可以获得稳定的 SUPPORTED_SUFFIXES 值。
    SUPPORTED_SUFFIXES = {
        ".md",
        ".markdown",
        ".txt",
        ".pdf",
        ".docx",
        ".html",
        ".json",
        ".csv",
        ".xml",
    }

    def iter_supported_files(self, directory: str | Path) -> list[Path]:
        """目的：根据当前输入执行条件判断，统一布尔分支的判定逻辑。
        结果：返回明确的判断结果，供上层决定后续流程。
        """
        dir_path = Path(directory)
        if not dir_path.is_dir():
            return []
        return sorted(
            file_path
            for file_path in dir_path.rglob("*")
            if file_path.is_file()
            and not any(part.startswith(".") for part in file_path.relative_to(dir_path).parts)
            and file_path.suffix.lower() in self.SUPPORTED_SUFFIXES
        )

    def clean_text(self, text: str) -> str:
        """目的：统一处理输入值的边界情况、格式约束和清洗规则。
        结果：返回满足约束的结果，避免脏数据影响后续逻辑。
        """
        return "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").splitlines()).strip()
