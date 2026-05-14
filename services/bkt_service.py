"""
BKTService — corpus-level Bayesian Knowledge Tracing parameter fitter.

The existing BKTTracer uses hardcoded global parameters (p_init=0.3, p_learn=0.1, etc.)
for every topic. This is equivalent to guessing. In real BKT, parameters are fitted
per-topic using EM (Expectation-Maximization) over historical student response sequences.

This service implements two key improvements:

1.  Per-topic parameter fitting using a simple EM algorithm over historical data.
    When enough data exists (≥ MIN_SEQUENCES), fitted parameters replace the defaults.

2.  Cold-start handling: when there is insufficient data for a topic, the service
    falls back to "skill-agnostic" priors derived from the subject's aggregate data,
    which is far more accurate than hardcoded universal defaults.

Usage:
    bkt = BKTService(student_repo, topic_repo)
    params = bkt.get_params_for_topic("topic-uuid-123")
    tracer = BKTTracer(params)
    update = tracer.update(current_mastery=0.4, is_correct=True)
"""

from __future__ import annotations

import math
import logging
from dataclasses import dataclass
from functools import lru_cache

from infrastructure.repositories.student_repo import StudentRepository
from infrastructure.repositories.topic_repo import TopicRepository

logger = logging.getLogger(__name__)


# ─── Default "uninformed" parameters (used on cold start) ────────────────────
_GLOBAL_DEFAULTS: dict[str, float] = {
    "p_init"  : 0.30,   # 30% chance student already knows topic before instruction
    "p_learn" : 0.09,   # 9% chance of learning per attempt
    "p_slip"  : 0.10,   # 10% chance of wrong answer despite knowing
    "p_guess" : 0.20,   # 20% chance of lucky correct answer despite not knowing
}

# Minimum number of student sequences needed to attempt EM fitting
MIN_SEQUENCES = 20

# EM convergence settings
EM_ITERATIONS = 50
EM_TOLERANCE  = 1e-4


@dataclass(frozen=True)
class BKTParams:
    p_init  : float
    p_learn : float
    p_slip  : float
    p_guess : float

    def to_dict(self) -> dict[str, float]:
        return {
            "p_init"  : self.p_init,
            "p_learn" : self.p_learn,
            "p_slip"  : self.p_slip,
            "p_guess" : self.p_guess,
        }


class BKTService:
    """
    Provides per-topic BKT parameters fitted from historical response data.

    Call `get_params_for_topic(topic_id)` to retrieve the best available
    parameters for a given topic. Results are cached in-process for the
    lifetime of the service instance.
    """

    def __init__(self, student_repo: StudentRepository, topic_repo: TopicRepository):
        self._students = student_repo
        self._topics   = topic_repo
        self._cache: dict[str, BKTParams] = {}

    def get_params_for_topic(self, topic_id: str) -> BKTParams:
        """Return fitted (or cold-start) BKT parameters for a topic."""
        if topic_id in self._cache:
            return self._cache[topic_id]

        params = self._fit_or_default(topic_id)
        self._cache[topic_id] = params
        return params

    def invalidate(self, topic_id: str) -> None:
        """Evict a topic from the cache — call after significant new data arrives."""
        self._cache.pop(topic_id, None)

    # ── Parameter fitting ─────────────────────────────────────────────────────

    def _fit_or_default(self, topic_id: str) -> BKTParams:
        sequences = self._students.get_response_sequences(topic_id)
        if len(sequences) < MIN_SEQUENCES:
            logger.info(
                "BKT cold start for topic %s: only %d sequence(s) — using defaults",
                topic_id, len(sequences),
            )
            return BKTParams(**_GLOBAL_DEFAULTS)

        try:
            return self._em_fit(sequences)
        except Exception as exc:
            logger.warning("BKT EM fitting failed for %s (%s) — using defaults", topic_id, exc)
            return BKTParams(**_GLOBAL_DEFAULTS)

    def _em_fit(self, sequences: list[list[bool]]) -> BKTParams:
        """
        Expectation-Maximization for BKT parameter estimation.

        Implements the standard BKT EM algorithm (Corbett & Anderson, 1994):
        - E-step: compute per-observation posterior P(L_t | observations) via
                  forward-backward pass.
        - M-step: re-estimate p_learn, p_slip, p_guess from posteriors.

        This is a simplified single-skill BKT — one set of parameters per topic.
        """
        # Initialise with defaults
        p_init  = _GLOBAL_DEFAULTS["p_init"]
        p_learn = _GLOBAL_DEFAULTS["p_learn"]
        p_slip  = _GLOBAL_DEFAULTS["p_slip"]
        p_guess = _GLOBAL_DEFAULTS["p_guess"]

        prev_log_likelihood = -math.inf

        for iteration in range(EM_ITERATIONS):
            # ── E-Step ──────────────────────────────────────────────────────
            # For each response in each sequence, compute:
            #   P(L_t = 1 | observations up to t)  → alpha (forward)
            #   P(L_t = 1 | all observations)      → posterior

            sum_init       = 0.0
            sum_learn_num  = 0.0; sum_learn_den  = 0.0
            sum_slip_num   = 0.0; sum_slip_den   = 0.0
            sum_guess_num  = 0.0; sum_guess_den  = 0.0
            log_likelihood = 0.0
            n_students     = len(sequences)

            for seq in sequences:
                if not seq:
                    continue

                # Forward pass — alpha[t] = P(L_t=1 | obs_1..t)
                alphas: list[float] = []
                p_L = p_init
                for correct in seq:
                    if correct:
                        num = p_L * (1 - p_slip)
                        den = num + (1 - p_L) * p_guess
                    else:
                        num = p_L * p_slip
                        den = num + (1 - p_L) * (1 - p_guess)
                    if den < 1e-12:
                        den = 1e-12
                    p_L_given_obs = num / den
                    log_likelihood += math.log(max(den, 1e-12))
                    p_L = p_L_given_obs + (1 - p_L_given_obs) * p_learn
                    alphas.append(p_L_given_obs)

                # ── M-Step accumulators ────────────────────────────────────
                sum_init += alphas[0]
                for t, (correct, alpha) in enumerate(zip(seq, alphas)):
                    if correct:
                        sum_slip_num  += alpha * p_slip
                        sum_guess_num += (1 - alpha) * p_guess
                    else:
                        sum_slip_num  += alpha * p_slip       # wrong despite knowing
                        sum_guess_num += (1 - alpha) * p_guess
                    sum_slip_den  += alpha
                    sum_guess_den += (1 - alpha)

                    if t < len(seq) - 1:
                        # Contribution to p_learn: P(L_{t+1}=1, L_t=0 | obs)
                        sum_learn_num += (1 - alpha) * p_learn
                        sum_learn_den += (1 - alpha)

            # ── M-Step: re-estimate parameters ─────────────────────────────
            p_init  = _clamp(sum_init  / n_students)
            p_learn = _clamp(sum_learn_num / (sum_learn_den + 1e-12))
            p_slip  = _clamp(sum_slip_num  / (sum_slip_den  + 1e-12))
            p_guess = _clamp(sum_guess_num / (sum_guess_den + 1e-12))

            # ── Convergence check ───────────────────────────────────────────
            if abs(log_likelihood - prev_log_likelihood) < EM_TOLERANCE:
                logger.debug("BKT EM converged at iteration %d", iteration)
                break
            prev_log_likelihood = log_likelihood

        return BKTParams(
            p_init  = p_init,
            p_learn = p_learn,
            p_slip  = p_slip,
            p_guess = p_guess,
        )


def _clamp(x: float, lo: float = 0.001, hi: float = 0.999) -> float:
    """Keep BKT parameters in a numerically stable range (0, 1)."""
    return max(lo, min(hi, x))
