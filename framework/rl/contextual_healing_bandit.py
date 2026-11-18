"""Cost-sensitive contextual bandit for healing-strategy selection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

import numpy as np


class HealingContextEncoder:
    """Encode an execution failure into a stable numeric feature vector."""

    DEFAULT_CATEGORIES = (
        "locator",
        "timeout",
        "assertion",
        "data",
        "syntax",
        "import",
    )
    DEFAULT_LOCATORS = ("css", "text", "role", "xpath", "none")

    def __init__(
        self,
        categories: Sequence[str] = DEFAULT_CATEGORIES,
        locator_types: Sequence[str] = DEFAULT_LOCATORS,
    ):
        self.categories = tuple(categories)
        self.locator_types = tuple(locator_types)
        self.dimension = len(self.categories) + len(self.locator_types) + 5

    def encode(self, context: Dict) -> np.ndarray:
        vector = np.zeros(self.dimension, dtype=np.float64)

        category = str(context.get("error_category", "unknown"))
        if category in self.categories:
            vector[self.categories.index(category)] = 1.0

        offset = len(self.categories)
        locator_type = str(context.get("locator_type", "none"))
        if locator_type not in self.locator_types:
            locator_type = "none"
        vector[offset + self.locator_types.index(locator_type)] = 1.0

        numeric_offset = offset + len(self.locator_types)
        numeric_values = (
            context.get("dom_change", 0.0),
            min(float(context.get("attempt", 1)) / 3.0, 1.0),
            context.get("script_complexity", 0.0),
            context.get("historical_success", 0.0),
            context.get("estimated_cost", 0.0),
        )
        vector[numeric_offset:] = np.clip(
            np.asarray(numeric_values, dtype=np.float64), 0.0, 1.0
        )
        return vector


class ContextualHealingBandit:
    """Independent-arm LinUCB policy with optional action availability masks."""

    def __init__(
        self,
        strategies: Sequence[str],
        context_dimension: int,
        alpha: float = 0.6,
        ridge: float = 1.0,
    ):
        if not strategies:
            raise ValueError("at least one strategy is required")
        if context_dimension <= 0:
            raise ValueError("context_dimension must be positive")

        self.strategies = tuple(strategies)
        self.context_dimension = int(context_dimension)
        self.alpha = float(alpha)
        self.ridge = float(ridge)
        self._a = {
            strategy: np.eye(self.context_dimension, dtype=np.float64) * self.ridge
            for strategy in self.strategies
        }
        self._b = {
            strategy: np.zeros(self.context_dimension, dtype=np.float64)
            for strategy in self.strategies
        }
        self.counts = {strategy: 0 for strategy in self.strategies}
        self.total_reward = 0.0

    def select_strategy(
        self,
        context: Iterable[float],
        available: Optional[Sequence[str]] = None,
    ) -> str:
        vector = self._validate_context(context)
        candidates = tuple(available or self.strategies)
        if not candidates:
            raise ValueError("no available strategies")
        unknown = set(candidates) - set(self.strategies)
        if unknown:
            raise ValueError(f"unknown strategies: {sorted(unknown)}")

        scores = self.score_strategies(vector, candidates)
        return max(candidates, key=lambda item: (scores[item], -self.strategies.index(item)))

    def score_strategies(
        self,
        context: Iterable[float],
        strategies: Optional[Sequence[str]] = None,
    ) -> Dict[str, float]:
        vector = self._validate_context(context)
        candidates = tuple(strategies or self.strategies)
        scores: Dict[str, float] = {}
        for strategy in candidates:
            inverse = np.linalg.inv(self._a[strategy])
            theta = inverse @ self._b[strategy]
            mean = float(theta @ vector)
            uncertainty = float(np.sqrt(max(vector @ inverse @ vector, 0.0)))
            scores[strategy] = mean + self.alpha * uncertainty
        return scores

    def update(
        self,
        strategy: str,
        context: Iterable[float],
        reward: float,
    ) -> None:
        if strategy not in self._a:
            raise ValueError(f"unknown strategy: {strategy}")
        vector = self._validate_context(context)
        self._a[strategy] += np.outer(vector, vector)
        self._b[strategy] += float(reward) * vector
        self.counts[strategy] += 1
        self.total_reward += float(reward)

    def get_stats(self) -> Dict:
        return {
            "algorithm": "LinUCB",
            "alpha": self.alpha,
            "ridge": self.ridge,
            "context_dimension": self.context_dimension,
            "counts": dict(self.counts),
            "total_reward": round(self.total_reward, 6),
        }

    def save(self, path: str | Path) -> None:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "strategies": list(self.strategies),
            "context_dimension": self.context_dimension,
            "alpha": self.alpha,
            "ridge": self.ridge,
            "a": {key: value.tolist() for key, value in self._a.items()},
            "b": {key: value.tolist() for key, value in self._b.items()},
            "counts": self.counts,
            "total_reward": self.total_reward,
        }
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "ContextualHealingBandit":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        bandit = cls(
            strategies=payload["strategies"],
            context_dimension=payload["context_dimension"],
            alpha=payload.get("alpha", 0.6),
            ridge=payload.get("ridge", 1.0),
        )
        bandit._a = {
            key: np.asarray(value, dtype=np.float64)
            for key, value in payload["a"].items()
        }
        bandit._b = {
            key: np.asarray(value, dtype=np.float64)
            for key, value in payload["b"].items()
        }
        bandit.counts = {
            key: int(value) for key, value in payload.get("counts", {}).items()
        }
        bandit.total_reward = float(payload.get("total_reward", 0.0))
        return bandit

    def _validate_context(self, context: Iterable[float]) -> np.ndarray:
        vector = np.asarray(tuple(context), dtype=np.float64)
        if vector.shape != (self.context_dimension,):
            raise ValueError(
                f"expected context shape {(self.context_dimension,)}, got {vector.shape}"
            )
        return vector


def cost_sensitive_healing_reward(
    *,
    success: bool,
    regression_passed: bool,
    normalized_cost: float,
    attempts: int = 1,
    success_reward: float = 1.0,
    failure_penalty: float = -0.6,
    regression_bonus: float = 0.15,
    regression_penalty: float = -0.5,
    cost_weight: float = 0.3,
    retry_weight: float = 0.05,
) -> float:
    """Combine repair quality and resource use into one observable reward."""

    reward = success_reward if success else failure_penalty
    reward += regression_bonus if regression_passed else regression_penalty
    reward -= cost_weight * max(0.0, float(normalized_cost))
    reward -= retry_weight * max(0, int(attempts) - 1)
    return float(reward)
