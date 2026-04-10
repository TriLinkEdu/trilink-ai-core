"""
Contract tests — every plugin must pass these regardless of implementation.
These tests define the behavioral guarantees of each interface.
Run these first whenever a new plugin is added.
"""
import pytest
from core.interfaces.knowledge_tracer import KnowledgeTracer
from core.interfaces.embedder import Embedder
from core.models.mastery import MasteryUpdate


# ---------------------------------------------------------------------------
# KnowledgeTracer contract
# ---------------------------------------------------------------------------

class KnowledgeTracerContract:
    """Mixin: any tracer plugin test class inherits this."""

    @pytest.fixture
    def tracer(self) -> KnowledgeTracer:
        raise NotImplementedError

    def test_is_knowledge_tracer(self, tracer):
        assert isinstance(tracer, KnowledgeTracer)

    def test_update_returns_mastery_update(self, tracer):
        result = tracer.update(0.5, True)
        assert isinstance(result, MasteryUpdate)

    def test_correct_answer_increases_mastery(self, tracer):
        result = tracer.update(0.5, True)
        assert result.new > result.old

    def test_incorrect_answer_decreases_mastery(self, tracer):
        result = tracer.update(0.5, False)
        assert result.new < result.old

    def test_mastery_stays_in_bounds(self, tracer):
        for mastery in [0.0, 0.5, 1.0]:
            for correct in [True, False]:
                result = tracer.update(mastery, correct)
                assert 0.0 <= result.new <= 1.0

    def test_predict_mastery_from_history(self, tracer):
        history = [True, False, True, True, True]
        result = tracer.predict_mastery(history)
        assert 0.0 <= result <= 1.0

    def test_predict_all_correct_higher_than_all_wrong(self, tracer):
        all_correct = tracer.predict_mastery([True] * 10)
        all_wrong = tracer.predict_mastery([False] * 10)
        assert all_correct > all_wrong

    def test_old_value_preserved(self, tracer):
        result = tracer.update(0.42, True)
        assert result.old == pytest.approx(0.42)


# ---------------------------------------------------------------------------
# Embedder contract
# ---------------------------------------------------------------------------

class EmbedderContract:
    """Mixin: any embedder plugin test class inherits this."""

    @pytest.fixture
    def embedder(self) -> Embedder:
        raise NotImplementedError

    def test_is_embedder(self, embedder):
        assert isinstance(embedder, Embedder)

    def test_embed_returns_list_of_floats(self, embedder):
        result = embedder.embed("Natural Numbers")
        assert isinstance(result, list)
        assert all(isinstance(v, float) for v in result)

    def test_embed_correct_dimensions(self, embedder):
        result = embedder.embed("Kinematics")
        assert len(result) == embedder.dimensions

    def test_embed_batch_correct_shape(self, embedder):
        texts = ["Algebra", "Geometry", "Calculus"]
        result = embedder.embed_batch(texts)
        assert len(result) == 3
        assert all(len(v) == embedder.dimensions for v in result)

    def test_embed_batch_single_matches_embed(self, embedder):
        text = "Newton's Laws"
        single = embedder.embed(text)
        batch = embedder.embed_batch([text])[0]
        assert single == pytest.approx(batch, abs=1e-5)

    def test_dimensions_is_positive_int(self, embedder):
        assert isinstance(embedder.dimensions, int)
        assert embedder.dimensions > 0
