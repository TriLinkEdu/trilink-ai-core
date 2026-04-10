from core.interfaces.knowledge_tracer import KnowledgeTracer
from core.models.mastery import MasteryUpdate


class BKTTracer(KnowledgeTracer):
    """
    Bayesian Knowledge Tracing implementation.

    Parameters (tunable via settings):
        p_init  — prior probability student already knows the topic
        p_learn — probability of learning after each attempt
        p_slip  — probability of wrong answer despite knowing
        p_guess — probability of correct answer despite not knowing
    """

    def __init__(self, params: dict):
        self._p_init  = params["p_init"]
        self._p_learn = params["p_learn"]
        self._p_slip  = params["p_slip"]
        self._p_guess = params["p_guess"]

    def update(self, current_mastery: float, is_correct: bool) -> MasteryUpdate:
        if is_correct:
            num = current_mastery * (1 - self._p_slip)
            den = num + (1 - current_mastery) * self._p_guess
        else:
            num = current_mastery * self._p_slip
            den = num + (1 - current_mastery) * (1 - self._p_guess)

        posterior = num / den if den > 0 else current_mastery
        new_mastery = posterior + (1 - posterior) * self._p_learn
        return MasteryUpdate(old=current_mastery, new=round(new_mastery, 6))

    def predict_mastery(self, history: list[bool]) -> float:
        mastery = self._p_init
        for correct in history:
            mastery = self.update(mastery, correct).new
        return mastery
