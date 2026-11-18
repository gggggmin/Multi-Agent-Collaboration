"""Controlled environment for evidence-constrained generation decisions."""

from __future__ import annotations

from enum import IntEnum
from typing import Dict, Optional

import gymnasium as gym
import numpy as np
from gymnasium import spaces


class GenerationAction(IntEnum):
    ACCEPT = 0
    REVISE_COVERAGE = 1
    REVISE_CONSISTENCY = 2
    REVISE_BOUNDARY = 3
    REFRESH_EVIDENCE = 4


ACTION_NAMES = {
    int(GenerationAction.ACCEPT): "accept",
    int(GenerationAction.REVISE_COVERAGE): "revise_coverage",
    int(GenerationAction.REVISE_CONSISTENCY): "revise_consistency",
    int(GenerationAction.REVISE_BOUNDARY): "revise_boundary",
    int(GenerationAction.REFRESH_EVIDENCE): "refresh_evidence",
}


class SafeGenerationEnv(gym.Env):
    """A seeded quality/cost environment for generation-control research.

    This is a controlled policy environment, not a replacement for real LLM
    trajectories.  It exposes richer actions and explicit unsafe-accept and
    maximum-iteration outcomes so policies can be compared reproducibly.
    """

    metadata = {"render_modes": []}

    def __init__(self, config: Optional[Dict] = None):
        super().__init__()
        cfg = config or {}
        self.max_iterations = int(cfg.get("max_iterations", 6))
        self.min_coverage = float(cfg.get("min_coverage", 0.85))
        self.min_evidence = float(cfg.get("min_evidence", 0.60))
        self.unsafe_accept_penalty = float(cfg.get("unsafe_accept_penalty", -25.0))
        self.success_reward = float(cfg.get("success_reward", 20.0))
        self.cost_weight = float(cfg.get("cost_weight", 1.5))

        # iteration, errors, warnings, hallucinations, coverage,
        # coverage_delta, evidence_consistency, accumulated_cost
        self.observation_space = spaces.Box(
            low=np.zeros(8, dtype=np.float32),
            high=np.ones(8, dtype=np.float32),
            dtype=np.float32,
        )
        self.action_space = spaces.Discrete(len(GenerationAction))

        self.iteration = 1
        self.num_errors = 0
        self.num_warnings = 0
        self.num_hallucinations = 0
        self.coverage = 0.0
        self.coverage_delta = 0.0
        self.evidence_consistency = 0.0
        self.accumulated_cost = 0.0
        self.terminated_reason = "running"

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        state = (options or {}).get("state")
        if state is None:
            state = self._sample_initial_state()
        self.iteration = int(state.get("current_iteration", 1))
        self.num_errors = int(state.get("num_errors", 0))
        self.num_warnings = int(state.get("num_warnings", 0))
        self.num_hallucinations = int(state.get("num_hallucinations", 0))
        self.coverage = float(state.get("coverage", 0.0))
        self.coverage_delta = float(state.get("coverage_delta", 0.0))
        self.evidence_consistency = float(state.get("evidence_consistency", 0.0))
        self.accumulated_cost = float(state.get("accumulated_cost", 0.0))
        self.terminated_reason = "running"
        return self._get_obs(), self._get_info()

    def step(self, action):
        action = int(action)
        if action not in ACTION_NAMES:
            raise ValueError(f"unknown generation action: {action}")

        terminated = False
        truncated = False
        reward = 0.0
        unsafe_accept = False
        accepted = False

        if action == int(GenerationAction.ACCEPT):
            terminated = True
            if self.safe_to_accept:
                accepted = True
                self.terminated_reason = "accepted"
                reward = (
                    self.success_reward
                    + 8.0 * self.coverage
                    + 3.0 * self.evidence_consistency
                    - self.cost_weight * self.accumulated_cost
                )
            else:
                unsafe_accept = True
                self.terminated_reason = "unsafe_accept"
                reward = (
                    self.unsafe_accept_penalty
                    - 4.0 * self.num_errors
                    - 3.0 * self.num_hallucinations
                    - 5.0 * max(self.min_coverage - self.coverage, 0.0)
                )
        else:
            before = self._quality_snapshot()
            step_cost = self._apply_revision(action)
            self.accumulated_cost += step_cost
            self.iteration += 1
            after = self._quality_snapshot()

            reward = (
                8.0 * max(after["coverage"] - before["coverage"], 0.0)
                + 2.5 * max(before["errors"] - after["errors"], 0)
                + 2.0 * max(before["hallucinations"] - after["hallucinations"], 0)
                + 0.8 * max(before["warnings"] - after["warnings"], 0)
                + 3.0 * max(after["evidence"] - before["evidence"], 0.0)
                - self.cost_weight * step_cost
            )

            if self.iteration > self.max_iterations:
                truncated = True
                self.terminated_reason = "failed_max_iterations"
                reward -= 12.0 + 2.0 * self.num_errors + self.num_hallucinations

        info = self._get_info()
        info.update(
            {
                "action": action,
                "action_name": ACTION_NAMES[action],
                "accepted": accepted,
                "unsafe_accept": unsafe_accept,
                "failed_max_iterations": self.terminated_reason == "failed_max_iterations",
                "termination_reason": self.terminated_reason,
            }
        )
        return self._get_obs(), float(reward), terminated, truncated, info

    @property
    def safe_to_accept(self) -> bool:
        return (
            self.num_errors == 0
            and self.num_hallucinations == 0
            and self.coverage >= self.min_coverage
            and self.evidence_consistency >= self.min_evidence
        )

    def recommended_revision_action(self) -> int:
        """Select the most directly relevant repair action for the state."""
        if self.evidence_consistency < self.min_evidence:
            return int(GenerationAction.REFRESH_EVIDENCE)
        if self.num_errors > 0 or self.num_hallucinations > 0:
            return int(GenerationAction.REVISE_CONSISTENCY)
        if self.coverage < self.min_coverage:
            return int(GenerationAction.REVISE_COVERAGE)
        if self.num_warnings > 0:
            return int(GenerationAction.REVISE_BOUNDARY)
        return int(GenerationAction.ACCEPT)

    def project_safe_action(self, proposed_action: int) -> int:
        """Project a proposal onto the evidence-constrained action set."""
        proposed_action = int(proposed_action)
        allowed = self.allowed_actions()
        if proposed_action not in allowed:
            return self.recommended_revision_action()
        return proposed_action

    def allowed_actions(self) -> set[int]:
        """Return actions that do not violate the current quality constraints."""
        if self.safe_to_accept:
            return {
                int(GenerationAction.ACCEPT),
                int(GenerationAction.REVISE_BOUNDARY),
            }
        if self.evidence_consistency < self.min_evidence:
            return {
                int(GenerationAction.REFRESH_EVIDENCE),
                int(GenerationAction.REVISE_CONSISTENCY),
            }
        if self.num_errors > 0 or self.num_hallucinations > 0:
            return {
                int(GenerationAction.REVISE_CONSISTENCY),
                int(GenerationAction.REFRESH_EVIDENCE),
            }
        if self.coverage < self.min_coverage:
            return {
                int(GenerationAction.REVISE_COVERAGE),
                int(GenerationAction.REVISE_BOUNDARY),
            }
        return {
            int(GenerationAction.ACCEPT),
            int(GenerationAction.REVISE_BOUNDARY),
        }

    def _sample_initial_state(self) -> Dict:
        profiles = (
            {"errors": 0, "warnings": 1, "hallucinations": 0, "coverage": 0.94, "evidence": 0.90},
            {"errors": 2, "warnings": 2, "hallucinations": 2, "coverage": 0.72, "evidence": 0.82},
            {"errors": 0, "warnings": 3, "hallucinations": 0, "coverage": 0.55, "evidence": 0.88},
            {"errors": 1, "warnings": 1, "hallucinations": 1, "coverage": 0.78, "evidence": 0.35},
            {"errors": 0, "warnings": 4, "hallucinations": 0, "coverage": 0.88, "evidence": 0.76},
            {"errors": 3, "warnings": 4, "hallucinations": 2, "coverage": 0.42, "evidence": 0.28},
        )
        base = dict(profiles[int(self.np_random.integers(0, len(profiles)))])
        return {
            "current_iteration": 1,
            "num_errors": max(0, base["errors"] + int(self.np_random.integers(-1, 2))),
            "num_warnings": max(0, base["warnings"] + int(self.np_random.integers(-1, 2))),
            "num_hallucinations": max(
                0, base["hallucinations"] + int(self.np_random.integers(-1, 2))
            ),
            "coverage": float(np.clip(base["coverage"] + self.np_random.normal(0, 0.04), 0, 1)),
            "coverage_delta": 0.0,
            "evidence_consistency": float(
                np.clip(base["evidence"] + self.np_random.normal(0, 0.04), 0, 1)
            ),
            "accumulated_cost": 0.0,
        }

    def _apply_revision(self, action: int) -> float:
        previous_coverage = self.coverage
        if action == int(GenerationAction.REVISE_COVERAGE):
            self.coverage = float(
                np.clip(self.coverage + self.np_random.uniform(0.12, 0.30), 0, 1)
            )
            self.num_warnings = max(
                0, self.num_warnings - int(self.np_random.integers(0, 2))
            )
            step_cost = 0.70
        elif action == int(GenerationAction.REVISE_CONSISTENCY):
            self.num_errors = max(
                0, self.num_errors - int(self.np_random.integers(1, 3))
            )
            self.num_hallucinations = max(
                0, self.num_hallucinations - int(self.np_random.integers(1, 3))
            )
            self.evidence_consistency = float(
                np.clip(self.evidence_consistency + self.np_random.uniform(0.04, 0.14), 0, 1)
            )
            step_cost = 0.80
        elif action == int(GenerationAction.REVISE_BOUNDARY):
            self.num_warnings = max(
                0, self.num_warnings - int(self.np_random.integers(1, 4))
            )
            self.coverage = float(
                np.clip(self.coverage + self.np_random.uniform(0.03, 0.12), 0, 1)
            )
            step_cost = 0.55
        elif action == int(GenerationAction.REFRESH_EVIDENCE):
            self.evidence_consistency = float(
                np.clip(self.evidence_consistency + self.np_random.uniform(0.22, 0.42), 0, 1)
            )
            if self.num_hallucinations > 0 and self.np_random.random() < 0.75:
                self.num_hallucinations -= 1
            if self.num_errors > 0 and self.np_random.random() < 0.45:
                self.num_errors -= 1
            step_cost = 0.95
        else:
            raise ValueError(f"action {action} is not a revision action")

        self.coverage_delta = max(self.coverage - previous_coverage, 0.0)
        return step_cost

    def _quality_snapshot(self) -> Dict:
        return {
            "errors": self.num_errors,
            "warnings": self.num_warnings,
            "hallucinations": self.num_hallucinations,
            "coverage": self.coverage,
            "evidence": self.evidence_consistency,
        }

    def _get_obs(self) -> np.ndarray:
        return np.asarray(
            [
                min(self.iteration / max(self.max_iterations, 1), 1.0),
                min(self.num_errors / 5.0, 1.0),
                min(self.num_warnings / 8.0, 1.0),
                min(self.num_hallucinations / 5.0, 1.0),
                np.clip(self.coverage, 0, 1),
                np.clip(self.coverage_delta, 0, 1),
                np.clip(self.evidence_consistency, 0, 1),
                min(self.accumulated_cost / 6.0, 1.0),
            ],
            dtype=np.float32,
        )

    def _get_info(self) -> Dict:
        return {
            "iteration": self.iteration,
            "num_errors": self.num_errors,
            "num_warnings": self.num_warnings,
            "num_hallucinations": self.num_hallucinations,
            "coverage": self.coverage,
            "coverage_delta": self.coverage_delta,
            "evidence_consistency": self.evidence_consistency,
            "accumulated_cost": self.accumulated_cost,
            "safe_to_accept": self.safe_to_accept,
        }
