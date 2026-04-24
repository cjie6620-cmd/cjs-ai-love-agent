"""解析策略注册表：按后缀/MIME 选择具体 DocumentParser（简单工厂）。

目的：作为文档解析器的统一入口，根据文件扩展名和 MIME 类型自动选择合适的解析器，
使文档摄入流程可以透明地处理多种文档格式，无需关心底层解析细节。
"""

from __future__ import annotations

from .base import DocumentParser, ParsedDocument
from .parsers import default_parser_chain


class ParserRegistry:
    """维护有序策略列表，先注册先匹配；最后一项通常为兜底策略。

    目的：封装特定格式的解析逻辑，将原始内容转换为标准文本结果。
    结果：上游流程可以复用统一解析接口处理不同文件类型，降低适配成本。
    """

    def __init__(self, parsers: list[DocumentParser] | None = None) -> None:
        """初始化解析器注册表。

        目的：接收并保存运行所需的依赖、配置和初始状态。
        结果：实例初始化完成，可直接执行后续业务调用。
        """
        self._parsers: list[DocumentParser] = list(parsers or default_parser_chain())

    def register_first(self, parser: DocumentParser) -> None:
        """插入到队首，用于覆盖默认策略。

        目的：封装当前步骤的核心处理逻辑，统一该能力的执行入口。
        结果：返回或落地稳定结果，供后续流程直接使用。
        """
        self._parsers.insert(0, parser)

    def register_last(self, parser: DocumentParser) -> None:
        """插入到兜底之前（倒数第二个位置）；若列表为空则直接追加。

        目的：持久化、上传或补充目标数据，保持状态同步。
        结果：相关数据被成功写入或更新，便于后续流程继续使用。
        """
        if len(self._parsers) <= 1:
            self._parsers.append(parser)
        else:
            self._parsers.insert(-1, parser)

    def parse(self, data: bytes, *, filename: str = "", mime: str | None = None) -> ParsedDocument:
        """根据文件特征解析文档内容。

        目的：将输入内容转换为统一的内部表示，屏蔽原始格式差异。
        结果：返回标准化解析结果，便于后续链路复用和扩展。
        """
        suffix = ""
        if filename and "." in filename:
            suffix = filename[filename.rfind(".") :].lower()
        for parser in self._parsers:
            if parser.supports(mime, suffix):
                return parser.parse(data, filename=filename)
        raise RuntimeError("解析器链配置错误：缺少兜底策略")

