class MemoryManager:
    """先返回模拟记忆，后续再接 Redis、MySQL 和向量检索。"""

    def recall(self, user_id: str) -> list[str]:
        return [f"用户 {user_id} 更偏好温柔、直接的沟通方式"]
