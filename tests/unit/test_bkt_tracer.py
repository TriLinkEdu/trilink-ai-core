import pytest
from plugins.tracers.bkt_tracer import BKTTracer
from tests.contract.test_contracts import KnowledgeTracerContract

PARAMS = {"p_init": 0.1, "p_learn": 0.3, "p_slip": 0.1, "p_guess": 0.25}


class TestBKTTracer(KnowledgeTracerContract):
    """BKT satisfies the KnowledgeTracer contract + BKT-specific math."""

    @pytest.fixture
    def tracer(self):
        return BKTTracer(PARAMS)

    def test_known_correct_answer_values(self, tracer):
        # With mastery=0.5, correct answer:
        # posterior = 0.5*(1-0.1) / (0.5*0.9 + 0.5*0.25) = 0.45/0.575 ≈ 0.7826
        # new = 0.7826 + (1-0.7826)*0.3 ≈ 0.8478
        result = tracer.update(0.5, True)
        assert result.new == pytest.approx(0.8478, abs=1e-3)

    def test_known_incorrect_answer_values(self, tracer):
        # With mastery=0.5, wrong answer:
        # posterior = 0.5*0.1 / (0.5*0.1 + 0.5*0.75) = 0.05/0.425 ≈ 0.1176
        # new = 0.1176 + (1-0.1176)*0.3 ≈ 0.3824
        result = tracer.update(0.5, False)
        assert result.new == pytest.approx(0.3824, abs=1e-3)

    def test_mastery_converges_with_all_correct(self, tracer):
        mastery = tracer.predict_mastery([True] * 20)
        assert mastery > 0.95

    def test_cold_start_uses_p_init(self, tracer):
        mastery = tracer.predict_mastery([])
        assert mastery == pytest.approx(PARAMS["p_init"])
