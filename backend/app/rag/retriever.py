class KnowledgeRetriever:
    """先提供占位检索结果，后续再接 pgvector 与重排能力。"""

    def search(self, query: str) -> list[str]:
        return [f"围绕“{query}”建议先共情、再澄清、最后给行动建议"]
