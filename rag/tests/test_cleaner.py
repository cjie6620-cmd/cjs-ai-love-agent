from rag.cleaner import TextCleaner


def test_text_cleaner_removes_page_noise_and_merges_broken_lines() -> None:
    cleaner = TextCleaner()
    raw = (
        "第 1 页\n"
        "Confidential\n"
        "这是 OCR\n"
        "断开的句子。\n\n"
        "目录........1\n"
        "## 标题\n"
        "## 标题\n"
    )

    cleaned = cleaner.clean(raw, {"parser": "pdf"})

    assert "第 1 页" not in cleaned
    assert "Confidential" not in cleaned
    assert "目录" not in cleaned
    assert "这是 OCR 断开的句子。" in cleaned
    assert cleaned.count("## 标题") == 1
