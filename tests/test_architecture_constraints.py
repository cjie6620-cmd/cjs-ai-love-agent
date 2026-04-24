"""架构约束测试：防止模块边界回退。"""

from __future__ import annotations

import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
IGNORED_PARTS = {"__pycache__", "tests"}


def _iter_python_files(package: str):
    """iter python files 测试辅助方法。
    
    目的：为当前测试文件提供公共构造、准备或提取逻辑。
    结果：减少重复测试代码，提升测试可读性和维护性。
    """
    root = PROJECT_ROOT / package
    for path in root.rglob("*.py"):
        if any(part in IGNORED_PARTS for part in path.parts):
            continue
        yield path


def _collect_absolute_imports(path: Path) -> list[str]:
    """collect absolute imports 测试辅助方法。
    
    目的：为当前测试文件提供公共构造、准备或提取逻辑。
    结果：减少重复测试代码，提升测试可读性和维护性。
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.append(node.module)
    return modules


def _assert_no_imports(package: str, forbidden_prefix: str) -> None:
    """assert no imports 测试辅助方法。
    
    目的：为当前测试文件提供公共构造、准备或提取逻辑。
    结果：减少重复测试代码，提升测试可读性和维护性。
    """
    violations: list[str] = []
    for path in _iter_python_files(package):
        imported_modules = _collect_absolute_imports(path)
        hits = sorted({
            module
            for module in imported_modules
            if module == forbidden_prefix or module.startswith(f"{forbidden_prefix}.")
        })
        if hits:
            violations.append(f"{path.relative_to(PROJECT_ROOT)} -> {', '.join(hits)}")

    assert not violations, (
        f"{package} 不应依赖 {forbidden_prefix}，当前违规如下：\n"
        + "\n".join(violations)
    )


def test_persistence_does_not_depend_on_agents() -> None:
    """验证 persistence does not depend on agents。
    
    目的：覆盖当前场景的核心行为或边界条件，避免回归引入隐性问题。
    结果：断言关键输出与副作用符合预期，保证实现行为稳定。
    """
    _assert_no_imports("persistence", "agents")


def test_prompt_does_not_depend_on_agents() -> None:
    """验证 prompt does not depend on agents。
    
    目的：覆盖当前场景的核心行为或边界条件，避免回归引入隐性问题。
    结果：断言关键输出与副作用符合预期，保证实现行为稳定。
    """
    _assert_no_imports("prompt", "agents")


def test_security_does_not_depend_on_llm() -> None:
    """验证 security does not depend on llm。
    
    目的：覆盖当前场景的核心行为或边界条件，避免回归引入隐性问题。
    结果：断言关键输出与副作用符合预期，保证实现行为稳定。
    """
    _assert_no_imports("security", "llm")


def test_business_modules_do_not_import_app_module() -> None:
    """验证 business modules do not import app module。
    
    目的：覆盖当前场景的核心行为或边界条件，避免回归引入隐性问题。
    结果：断言关键输出与副作用符合预期，保证实现行为稳定。
    """
    violations: list[str] = []
    for package in ("api", "agents", "rag", "persistence", "prompt", "security", "stream", "llm"):
        for path in _iter_python_files(package):
            imported_modules = _collect_absolute_imports(path)
            hits = sorted({
                module
                for module in imported_modules
                if module == "app" or module.startswith("app.")
            })
            if hits:
                violations.append(f"{path.relative_to(PROJECT_ROOT)} -> {', '.join(hits)}")

    assert not violations, "业务模块不应直接依赖 app.py：\n" + "\n".join(violations)


def test_legacy_files_were_removed() -> None:
    """验证 legacy files were removed。
    
    目的：覆盖当前场景的核心行为或边界条件，避免回归引入隐性问题。
    结果：断言关键输出与副作用符合预期，保证实现行为稳定。
    """
    legacy_files = [
        "agents/schemas.py",
        "rag/api_models.py",
        "llm/settings.py",
        "stream/stream_router.py",
        "mcp/client.py",
        "llm/tools/mcp_client.py",
        "llm/tools/tavily_client.py",
        "app_logging/__init__.py",
        "app_logging/ai_logger.py",
    ]
    missing = [relative for relative in legacy_files if not (PROJECT_ROOT / relative).exists()]
    assert missing == legacy_files
