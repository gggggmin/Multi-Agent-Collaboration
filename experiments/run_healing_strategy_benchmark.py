"""Controlled benchmark for healing-strategy selection policies.

The benchmark is deliberately labelled as a controlled simulation.  It uses
paired potential outcomes so every policy faces the same fault sequence and
the same random outcome for each candidate strategy.  Browser-level fault
injection remains a separate external-validity experiment.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import RESULTS_DIR
from framework.rl import (
    ContextualHealingBandit,
    HealingContextEncoder,
    cost_sensitive_healing_reward,
)


STRATEGIES = (
    "rule_locator",
    "rule_timeout",
    "rule_assertion",
    "data_reset",
    "llm_rewrite",
    "fallback",
)
CATEGORIES = ("locator", "timeout", "assertion", "data", "syntax", "import")
COSTS = {
    "rule_locator": 0.10,
    "rule_timeout": 0.08,
    "rule_assertion": 0.14,
    "data_reset": 0.12,
    "llm_rewrite": 0.90,
    "fallback": 0.03,
}
FIXED_MAPPING = {
    "locator": "rule_locator",
    "timeout": "rule_timeout",
    "assertion": "rule_assertion",
    "data": "data_reset",
    "syntax": "llm_rewrite",
    "import": "llm_rewrite",
}


@dataclass(frozen=True)
class FaultEvent:
    context: Dict
    vector: np.ndarray
    probabilities: Dict[str, float]
    regression_probabilities: Dict[str, float]
    outcomes: Dict[str, Dict[str, bool]]
    expected_rewards: Dict[str, float]


def _clip(value: float) -> float:
    return max(0.02, min(0.98, value))


def _success_probability(category: str, strategy: str, context: Dict) -> float:
    dom = float(context["dom_change"])
    complexity = float(context["script_complexity"])
    locator_type = context["locator_type"]

    probability = 0.05
    if category == "locator":
        if strategy == "rule_locator":
            probability = 0.96 - 0.72 * dom - (0.08 if locator_type == "xpath" else 0.0)
        elif strategy == "llm_rewrite":
            probability = 0.58 + 0.34 * dom + 0.05 * complexity
        elif strategy == "fallback":
            probability = 0.18
    elif category == "timeout":
        if strategy == "rule_timeout":
            probability = 0.93 - 0.58 * complexity
        elif strategy == "llm_rewrite":
            probability = 0.52 + 0.32 * complexity
        elif strategy == "fallback":
            probability = 0.16
    elif category == "assertion":
        if strategy == "rule_assertion":
            probability = 0.91 - 0.60 * complexity
        elif strategy == "llm_rewrite":
            probability = 0.48 + 0.40 * complexity
        elif strategy == "fallback":
            probability = 0.12
    elif category == "data":
        if strategy == "data_reset":
            probability = 0.94 - 0.28 * complexity
        elif strategy == "llm_rewrite":
            probability = 0.38 + 0.22 * complexity
        elif strategy == "fallback":
            probability = 0.22
    elif category == "syntax":
        if strategy == "llm_rewrite":
            probability = 0.88 - 0.10 * complexity
        elif strategy == "rule_assertion":
            probability = 0.18 + 0.10 * (1.0 - complexity)
        elif strategy == "fallback":
            probability = 0.16
    elif category == "import":
        if strategy == "llm_rewrite":
            probability = 0.82 - 0.08 * complexity
        elif strategy == "fallback":
            probability = 0.30
        elif strategy == "data_reset":
            probability = 0.10

    return _clip(probability)


def _regression_probability(strategy: str, context: Dict) -> float:
    complexity = float(context["script_complexity"])
    if strategy == "llm_rewrite":
        return _clip(0.91 - 0.18 * complexity)
    if strategy == "fallback":
        return 0.99
    return _clip(0.985 - 0.05 * complexity)


def _expected_reward(success_p: float, regression_p: float, strategy: str) -> float:
    success_and_safe = success_p * regression_p
    success_and_regression = success_p * (1.0 - regression_p)
    failed = 1.0 - success_p
    cost_penalty = 0.3 * COSTS[strategy]
    return (
        success_and_safe * (1.0 + 0.15 - cost_penalty)
        + success_and_regression * (1.0 - 0.5 - cost_penalty)
        + failed * (-0.6 - 0.5 - cost_penalty)
    )


def build_fault_sequence(seed: int, trials: int, encoder: HealingContextEncoder) -> List[FaultEvent]:
    rng = random.Random(seed)
    events: List[FaultEvent] = []
    locator_types = ("css", "text", "role", "xpath")

    for _ in range(trials):
        category = rng.choice(CATEGORIES)
        context = {
            "error_category": category,
            "locator_type": rng.choice(locator_types) if category == "locator" else "none",
            "dom_change": rng.random() if category == "locator" else rng.random() * 0.25,
            "attempt": rng.randint(1, 3),
            "script_complexity": rng.random(),
            "historical_success": rng.random(),
            "estimated_cost": rng.random() * 0.5,
        }
        probabilities = {
            strategy: _success_probability(category, strategy, context)
            for strategy in STRATEGIES
        }
        regression_probabilities = {
            strategy: _regression_probability(strategy, context)
            for strategy in STRATEGIES
        }
        outcomes = {}
        expected_rewards = {}
        for strategy in STRATEGIES:
            success = rng.random() < probabilities[strategy]
            regression_passed = success and (
                rng.random() < regression_probabilities[strategy]
            )
            outcomes[strategy] = {
                "success": success,
                "regression_passed": regression_passed,
            }
            expected_rewards[strategy] = _expected_reward(
                probabilities[strategy], regression_probabilities[strategy], strategy
            )
        events.append(
            FaultEvent(
                context=context,
                vector=encoder.encode(context),
                probabilities=probabilities,
                regression_probabilities=regression_probabilities,
                outcomes=outcomes,
                expected_rewards=expected_rewards,
            )
        )
    return events


class Policy:
    def select(self, event: FaultEvent) -> str:
        raise NotImplementedError

    def update(self, event: FaultEvent, strategy: str, reward: float, success: bool) -> None:
        return None


class RandomPolicy(Policy):
    def __init__(self, seed: int):
        self.rng = random.Random(seed)

    def select(self, event: FaultEvent) -> str:
        return self.rng.choice(STRATEGIES)


class FixedRulePolicy(Policy):
    def select(self, event: FaultEvent) -> str:
        return FIXED_MAPPING[event.context["error_category"]]


class AlwaysLLMPolicy(Policy):
    def select(self, event: FaultEvent) -> str:
        return "llm_rewrite"


class EpsilonGreedyPolicy(Policy):
    def __init__(self, seed: int, epsilon: float = 0.1):
        self.rng = random.Random(seed)
        self.epsilon = epsilon
        self.q = {category: {strategy: 0.0 for strategy in STRATEGIES} for category in CATEGORIES}
        self.counts = {category: {strategy: 0 for strategy in STRATEGIES} for category in CATEGORIES}

    def select(self, event: FaultEvent) -> str:
        category = event.context["error_category"]
        unseen = [strategy for strategy in STRATEGIES if self.counts[category][strategy] == 0]
        if unseen:
            return self.rng.choice(unseen)
        if self.rng.random() < self.epsilon:
            return self.rng.choice(STRATEGIES)
        return max(STRATEGIES, key=lambda strategy: self.q[category][strategy])

    def update(self, event: FaultEvent, strategy: str, reward: float, success: bool) -> None:
        category = event.context["error_category"]
        self.counts[category][strategy] += 1
        count = self.counts[category][strategy]
        self.q[category][strategy] += (reward - self.q[category][strategy]) / count


class UCB1Policy(Policy):
    def __init__(self, exploration: float = 1.2):
        self.exploration = exploration
        self.rewards = {category: {strategy: 0.0 for strategy in STRATEGIES} for category in CATEGORIES}
        self.counts = {category: {strategy: 0 for strategy in STRATEGIES} for category in CATEGORIES}

    def select(self, event: FaultEvent) -> str:
        category = event.context["error_category"]
        for strategy in STRATEGIES:
            if self.counts[category][strategy] == 0:
                return strategy
        total = sum(self.counts[category].values())
        return max(
            STRATEGIES,
            key=lambda strategy: (
                self.rewards[category][strategy] / self.counts[category][strategy]
                + self.exploration
                * math.sqrt(math.log(max(total, 1)) / self.counts[category][strategy])
            ),
        )

    def update(self, event: FaultEvent, strategy: str, reward: float, success: bool) -> None:
        category = event.context["error_category"]
        self.counts[category][strategy] += 1
        self.rewards[category][strategy] += reward


class LinUCBPolicy(Policy):
    def __init__(self, dimension: int, alpha: float = 0.6):
        self.bandit = ContextualHealingBandit(
            strategies=STRATEGIES,
            context_dimension=dimension,
            alpha=alpha,
        )

    def select(self, event: FaultEvent) -> str:
        return self.bandit.select_strategy(event.vector)

    def update(self, event: FaultEvent, strategy: str, reward: float, success: bool) -> None:
        self.bandit.update(strategy, event.vector, reward)


class ExpectedOraclePolicy(Policy):
    def select(self, event: FaultEvent) -> str:
        return max(STRATEGIES, key=lambda strategy: event.expected_rewards[strategy])


def _policy_factories(seed: int, dimension: int):
    return {
        "random": lambda: RandomPolicy(seed + 11),
        "fixed_rule": FixedRulePolicy,
        "epsilon_greedy": lambda: EpsilonGreedyPolicy(seed + 23),
        "ucb1": UCB1Policy,
        "always_llm": AlwaysLLMPolicy,
        "cost_sensitive_linucb": lambda: LinUCBPolicy(dimension),
        "expected_oracle_upper_bound": ExpectedOraclePolicy,
    }


def evaluate_policy(policy: Policy, events: Iterable[FaultEvent]) -> Dict:
    total_reward = 0.0
    expected_regret = 0.0
    successes = 0
    regression_passes = 0
    total_cost = 0.0
    llm_calls = 0
    counts = {strategy: 0 for strategy in STRATEGIES}
    category_successes = {category: 0 for category in CATEGORIES}
    category_totals = {category: 0 for category in CATEGORIES}

    events = list(events)
    for event in events:
        strategy = policy.select(event)
        outcome = event.outcomes[strategy]
        reward = cost_sensitive_healing_reward(
            success=outcome["success"],
            regression_passed=outcome["regression_passed"],
            normalized_cost=COSTS[strategy],
        )
        policy.update(event, strategy, reward, outcome["success"])

        total_reward += reward
        best_expected = max(event.expected_rewards.values())
        expected_regret += best_expected - event.expected_rewards[strategy]
        successes += int(outcome["success"])
        regression_passes += int(outcome["regression_passed"])
        total_cost += COSTS[strategy]
        llm_calls += int(strategy == "llm_rewrite")
        counts[strategy] += 1
        category = event.context["error_category"]
        category_totals[category] += 1
        category_successes[category] += int(outcome["success"])

    total = len(events)
    return {
        "trials": total,
        "success_rate_pct": round(successes / max(total, 1) * 100, 3),
        "regression_pass_rate_pct": round(
            regression_passes / max(successes, 1) * 100, 3
        ),
        "avg_normalized_cost": round(total_cost / max(total, 1), 6),
        "llm_call_rate_pct": round(llm_calls / max(total, 1) * 100, 3),
        "cumulative_reward": round(total_reward, 6),
        "avg_reward": round(total_reward / max(total, 1), 6),
        "cumulative_expected_regret": round(expected_regret, 6),
        "strategy_counts": counts,
        "category_success_rate_pct": {
            category: round(
                category_successes[category] / max(category_totals[category], 1) * 100,
                3,
            )
            for category in CATEGORIES
        },
    }


def _aggregate(seed_results: List[Dict]) -> Dict:
    scalar_metrics = (
        "success_rate_pct",
        "regression_pass_rate_pct",
        "avg_normalized_cost",
        "llm_call_rate_pct",
        "cumulative_reward",
        "avg_reward",
        "cumulative_expected_regret",
    )
    result = {"num_seeds": len(seed_results)}
    for metric in scalar_metrics:
        values = [float(item[metric]) for item in seed_results]
        result[metric] = {
            "mean": round(statistics.mean(values), 6),
            "std": round(statistics.pstdev(values), 6),
        }
    return result


def _paired_comparisons(per_policy: Dict[str, List[Dict]], target: str) -> Dict:
    comparisons = {}
    target_rows = per_policy[target]
    for baseline, rows in per_policy.items():
        if baseline == target:
            continue
        reward_differences = [
            target_row["avg_reward"] - baseline_row["avg_reward"]
            for target_row, baseline_row in zip(target_rows, rows)
        ]
        success_differences = [
            target_row["success_rate_pct"] - baseline_row["success_rate_pct"]
            for target_row, baseline_row in zip(target_rows, rows)
        ]
        llm_reductions = [
            baseline_row["llm_call_rate_pct"] - target_row["llm_call_rate_pct"]
            for target_row, baseline_row in zip(target_rows, rows)
        ]
        standard_error = (
            statistics.stdev(reward_differences) / math.sqrt(len(reward_differences))
            if len(reward_differences) > 1
            else 0.0
        )
        mean_reward_difference = statistics.mean(reward_differences)
        comparisons[baseline] = {
            "linucb_minus_baseline_avg_reward": round(mean_reward_difference, 6),
            "reward_difference_95pct_ci": [
                round(mean_reward_difference - 1.96 * standard_error, 6),
                round(mean_reward_difference + 1.96 * standard_error, 6),
            ],
            "linucb_minus_baseline_success_pct": round(
                statistics.mean(success_differences), 6
            ),
            "baseline_minus_linucb_llm_call_pct": round(
                statistics.mean(llm_reductions), 6
            ),
            "linucb_reward_wins": sum(value > 0 for value in reward_differences),
        }
    return comparisons


def run(trials: int = 2000, seeds: int = 10) -> Dict:
    encoder = HealingContextEncoder()
    per_policy: Dict[str, List[Dict]] = {}

    for seed in range(seeds):
        events = build_fault_sequence(seed, trials, encoder)
        for name, factory in _policy_factories(seed, encoder.dimension).items():
            per_policy.setdefault(name, []).append(evaluate_policy(factory(), events))

    report = {
        "run_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "benchmark_type": "controlled_contextual_fault_simulation",
        "limitations": [
            "Potential outcomes are generated from seeded fault-response models, not browser executions.",
            "The benchmark validates online strategy selection; browser fault injection is required for external validity.",
        ],
        "settings": {
            "trials_per_seed": trials,
            "num_seeds": seeds,
            "fault_categories": list(CATEGORIES),
            "strategies": list(STRATEGIES),
            "paired_potential_outcomes": True,
        },
        "aggregate": {
            name: _aggregate(results) for name, results in per_policy.items()
        },
        "comparisons_vs_cost_sensitive_linucb": _paired_comparisons(
            per_policy, "cost_sensitive_linucb"
        ),
        "per_seed": per_policy,
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamped = RESULTS_DIR / f"healing_strategy_benchmark_{report['run_id']}.json"
    latest = RESULTS_DIR / "healing_strategy_benchmark_latest.json"
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    timestamped.write_text(payload, encoding="utf-8")
    latest.write_text(payload, encoding="utf-8")

    print(f"[healing-benchmark] report={timestamped}")
    print("policy\tsuccess%\tavg_cost\tllm%\tavg_reward\tregret")
    for name, metrics in report["aggregate"].items():
        print(
            f"{name}\t{metrics['success_rate_pct']['mean']:.2f}\t"
            f"{metrics['avg_normalized_cost']['mean']:.3f}\t"
            f"{metrics['llm_call_rate_pct']['mean']:.2f}\t"
            f"{metrics['avg_reward']['mean']:.3f}\t"
            f"{metrics['cumulative_expected_regret']['mean']:.2f}"
        )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=2000)
    parser.add_argument("--seeds", type=int, default=10)
    args = parser.parse_args()
    run(trials=args.trials, seeds=args.seeds)


if __name__ == "__main__":
    main()
