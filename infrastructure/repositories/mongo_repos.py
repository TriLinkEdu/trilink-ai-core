"""
MongoDB repositories — chat logs and audit trails.
These are the only two collections the AI engine writes to.
"""
from datetime import datetime, timezone
from infrastructure.db.mongo import get_db


class AuditRepository:
    """Immutable audit trail — every AI action logged here."""

    _collection = "audit_logs"

    def log(self, actor_id: str, action: str, entity: str, entity_id: str, metadata: dict | None = None) -> None:
        try:
            db = get_db()
            db[self._collection].insert_one({
                "actor_id": actor_id,
                "action": action,
                "entity": entity,
                "entity_id": entity_id,
                "metadata": metadata or {},
                "timestamp": datetime.now(timezone.utc),
            })
        except Exception:
            pass  # audit failure must never break business logic


class ChatLogRepository:
    """Stores AI assistant conversation history per student."""

    _collection = "ai_chat_logs"

    def save_message(self, student_id: str, role: str, content: str) -> None:
        """role: 'user' | 'assistant'"""
        try:
            get_db()[self._collection].insert_one({
                "student_id": student_id,
                "role": role,
                "content": content,
                "timestamp": datetime.now(timezone.utc),
            })
        except Exception:
            pass  # never crash the chat response on a log write failure

    def get_history(self, student_id: str, limit: int = 20) -> list[dict]:
        try:
            cursor = (
                get_db()[self._collection]
                .find({"student_id": student_id}, {"_id": 0})
                .sort("timestamp", -1)
                .limit(limit)
            )
            return list(reversed(list(cursor)))
        except Exception:
            return []
