import pytest
from plugins.embedders.minilm_embedder import MiniLMEmbedder
from tests.contract.test_contracts import EmbedderContract


class TestMiniLMEmbedder(EmbedderContract):
    """MiniLM satisfies the Embedder contract."""

    @pytest.fixture(scope="class")
    def embedder(self):
        return MiniLMEmbedder()

    def test_similar_texts_have_higher_similarity(self, embedder):
        import numpy as np
        v1 = np.array(embedder.embed("Newton's Laws of Motion"))
        v2 = np.array(embedder.embed("Force and acceleration"))
        v3 = np.array(embedder.embed("Photosynthesis in plants"))
        sim_related = float(v1 @ v2)
        sim_unrelated = float(v1 @ v3)
        assert sim_related > sim_unrelated
