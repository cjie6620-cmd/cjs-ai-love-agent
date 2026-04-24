from rag.chunking import (
    FixedSizeChunkStrategy,
    MarkdownHeadingChunkStrategy,
    ParentChildChunkStrategy,
)


def test_fixed_size_splits() -> None:
    """验证 fixed size splits。
    
    目的：覆盖当前场景的核心行为或边界条件，避免回归引入隐性问题。
    结果：断言关键输出与副作用符合预期，保证实现行为稳定。
    """
    s = FixedSizeChunkStrategy(chunk_size=10, overlap=2)
    chunks = s.split("0123456789abcdefghij")
    assert len(chunks) >= 2
    assert all(len(c.text) <= 10 for c in chunks)


def test_markdown_headings() -> None:
    """验证 markdown headings。
    
    目的：覆盖当前场景的核心行为或边界条件，避免回归引入隐性问题。
    结果：断言关键输出与副作用符合预期，保证实现行为稳定。
    """
    s = MarkdownHeadingChunkStrategy(max_chunk_chars=500, overlap=50)
    text = "# H1\n\npara1\n\n## H2\n\npara2"
    chunks = s.split(text)
    assert len(chunks) >= 1
    assert any("para" in c.text for c in chunks)


def test_parent_child_generates_both_roles() -> None:
    """验证父子块策略生成 parent 和 child 两种角色的 chunk。"""
    s = ParentChildChunkStrategy(child_size=20, child_overlap=5)
    text = (
        "# 章节一\n\n这是第一个章节的内容，需要足够长才能产生子块。"
        "\n\n# 章节二\n\n这是第二个章节的内容。"
    )
    chunks = s.split(text)

    assert len(chunks) >= 2

    roles = [c.metadata.get("chunk_role") for c in chunks]
    assert "parent" in roles
    assert "child" in roles

    # 所有 child 都应该有 parent_id
    for c in chunks:
        if c.metadata.get("chunk_role") == "child":
            assert "parent_id" in c.metadata


def test_parent_child_empty_text() -> None:
    """验证空文本返回空列表。"""
    s = ParentChildChunkStrategy()
    chunks = s.split("")
    assert chunks == []


def test_parent_child_heading_path_and_parent_id_are_stable() -> None:
    """验证父子块保留层级标题路径，且 parent_id 稳定。"""
    s = ParentChildChunkStrategy(child_size=18, child_overlap=4)
    text = (
        "# 总纲\n\n"
        "这里是总纲内容。\n\n"
        "## 沟通策略\n\n"
        "当对方回复变少时，不要立刻追问，先给对方一点空间，再自然开启话题。"
    )
    base_metadata = {"title": "恋爱知识库", "source": "unit-test"}

    first = s.split(text, base_metadata)
    second = s.split(text, base_metadata)

    first_parents = [c for c in first if c.metadata.get("chunk_role") == "parent"]
    second_parents = [c for c in second if c.metadata.get("chunk_role") == "parent"]
    assert len(first_parents) == 2
    assert [c.metadata["parent_id"] for c in first_parents] == [
        c.metadata["parent_id"] for c in second_parents
    ]

    nested_parent = next(c for c in first_parents if c.metadata.get("heading_level") == 2)
    assert nested_parent.metadata["heading_path"] == "总纲 / 沟通策略"
    assert nested_parent.text.startswith("总纲 / 沟通策略")

    nested_children = [
        c
        for c in first
        if c.metadata.get("chunk_role") == "child"
        and c.metadata.get("parent_id") == nested_parent.metadata["parent_id"]
    ]
    assert nested_children
    assert all(c.metadata.get("heading_path") == "总纲 / 沟通策略" for c in nested_children)
    assert all("logical_chunk_id" in c.metadata for c in nested_children)


def test_fixed_size_invalid_params() -> None:
    """验证无效参数抛出 ValueError。"""
    import pytest

    with pytest.raises(ValueError):
        FixedSizeChunkStrategy(chunk_size=0, overlap=0)

    with pytest.raises(ValueError):
        FixedSizeChunkStrategy(chunk_size=10, overlap=10)

