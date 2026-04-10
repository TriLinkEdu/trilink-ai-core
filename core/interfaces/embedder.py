from abc import ABC, abstractmethod


class Embedder(ABC):
    """Contract for any text embedding model (MiniLM, OpenAI, etc.)."""

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Embed a single text. Returns normalized vector."""
        ...

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts efficiently in one pass."""
        ...

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Dimensionality of the output vectors."""
        ...
