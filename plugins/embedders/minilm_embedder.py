from functools import cached_property
from sentence_transformers import SentenceTransformer
from core.interfaces.embedder import Embedder


class MiniLMEmbedder(Embedder):
    """
    all-MiniLM-L6-v2 — 384-dim, fast, free.
    Model is loaded once and reused (cached_property).
    """
    _MODEL_NAME = "all-MiniLM-L6-v2"

    @cached_property
    def _model(self) -> SentenceTransformer:
        return SentenceTransformer(self._MODEL_NAME)

    def embed(self, text: str) -> list[float]:
        return self._model.encode(text, normalize_embeddings=True).tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return self._model.encode(
            texts, normalize_embeddings=True, batch_size=64, show_progress_bar=False
        ).tolist()

    @property
    def dimensions(self) -> int:
        return 384
