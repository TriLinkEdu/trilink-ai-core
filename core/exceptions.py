class TriLinkError(Exception):
    """Base exception for all TriLink AI engine errors."""


class MasteryNotFoundError(TriLinkError):
    def __init__(self, student_id: str, topic_id: str):
        super().__init__(f"No mastery record for student={student_id}, topic={topic_id}")


class TopicNotFoundError(TriLinkError):
    def __init__(self, topic_id: str):
        super().__init__(f"Topic not found: {topic_id}")


class ContentGenerationError(TriLinkError):
    def __init__(self, topic_id: str, reason: str):
        super().__init__(f"Content generation failed for topic={topic_id}: {reason}")


class EmbeddingError(TriLinkError):
    def __init__(self, reason: str):
        super().__init__(f"Embedding failed: {reason}")


class PluginNotConfiguredError(TriLinkError):
    def __init__(self, plugin_name: str):
        super().__init__(f"Plugin not configured: {plugin_name}")
