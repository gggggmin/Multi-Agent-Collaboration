"""Controlled benchmark for adaptive multi-agent generation decisions."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from stable_baselines3 import PPO

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import RESULTS_DIR
from framework.rl import GenerationAction, SafeGenerationEnv


def build_scenarios(seed: int, episodes: int) -> List[Dict]:
    scenarios = []
    sampler = SafeGenerationEnv()
    for index in range(episodes):
        _, info = sampler.reset(seed=seed * 100_000 + index)
        scenarios.append(
            {
                "state": {
                    "current_iteration": 1,
                    "num_errors": info["num_errors"],
                    "num_warnings": info["num_warnings"],
                    "num_hallucinations": info["num_hallucinations"],
                    "coverage": info["coverage"],
                    "coverage_delta": 0.0,
                    "evidence_consistency": info["evidence_consistency"],
                    "accumulated_cost": 0.0,
                },
                "transition_seed": seed * 1_000_000 + index,
            }
        )
    return scenarios


def train_ppo(seed: int, timesteps: int, cost_weight: float = 1.5):
    env = SafeGenerationEnv({"cost_weight": cost_weight})
    model = PPO(
        "MlpPolicy",
        env,
        learning_rate=3e-4,
        gamma=0.97,
        n_steps=256,
        batch_size=64,
        ent_coef=0.01,
        verbose=0,
        seed=seed,
        device="cpu",
        policy_kwargs={"net_arch": [64, 64]},
    )
    start = time.time()
    model.learn(total_timesteps=timesteps)
    return model, time.time() - start


def _choose_action(
    policy_name: str,
    env: SafeGenerationEnv,
    observation,
    decision_index: int,
    model: PPO,
) -> int:
    if policy_name.startswith("fixed_"):
        target_round = int(policy_name.split("_")[1])
        if decision_index >= target_round:
            return int(GenerationAction.ACCEPT)
        action = env.recommended_revision_action()
        if action == int(GenerationAction.ACCEPT):
            return int(GenerationAction.REVISE_BOUNDARY)
        return action

    if policy_name == "audit_threshold_rule":
        return (
            int(GenerationAction.ACCEPT)
            if env.safe_to_accept
            else env.recommended_revision_action()
        )

    proposed, _ = model.predict(observation, deterministic=True)
    proposed = int(proposed)
    if policy_name == "safe_ppo":
        return env.project_safe_action(proposed)
    return proposed


def evaluate_policy(
    policy_name: str,
    model: PPO,
    scenarios: List[Dict],
    cost_weight: float = 1.5,
) -> Dict:
    totals = {
        "reward": 0.0,
        "accepted": 0,
        "unsafe_accept": 0,
        "failed_max_iterations": 0,
        "iterations": 0,
        "cost": 0.0,
        "coverage": 0.0,
        "evidence": 0.0,
    }
    action_counts = {name: 0 for name in (
        "accept",
        "revise_coverage",
        "revise_consistency",
        "revise_boundary",
        "refresh_evidence",
    )}

    for scenario in scenarios:
        env = SafeGenerationEnv({"cost_weight": cost_weight})
        obs, info = env.reset(
            seed=scenario["transition_seed"],
            options={"state": scenario["state"]},
        )
        episode_reward = 0.0
        decision_index = 1

        while True:
            action = _choose_action(policy_name, env, obs, decision_index, model)
            obs, reward, terminated, truncated, info = env.step(action)
            episode_reward += reward
            action_counts[info["action_name"]] += 1
            if terminated or truncated:
                break
            decision_index += 1

        totals["reward"] += episode_reward
        totals["accepted"] += int(info["accepted"])
        totals["unsafe_accept"] += int(info["unsafe_accept"])
        totals["failed_max_iterations"] += int(info["failed_max_iterations"])
        totals["iterations"] += int(info["iteration"])
        totals["cost"] += float(info["accumulated_cost"])
        totals["coverage"] += float(info["coverage"])
        totals["evidence"] += float(info["evidence_consistency"])

    count = len(scenarios)
    return {
        "episodes": count,
        "accept_rate_pct": round(totals["accepted"] / max(count, 1) * 100, 3),
        "unsafe_accept_rate_pct": round(
            totals["unsafe_accept"] / max(count, 1) * 100, 3
        ),
        "max_iteration_failure_rate_pct": round(
            totals["failed_max_iterations"] / max(count, 1) * 100, 3
        ),
        "avg_iterations": round(totals["iterations"] / max(count, 1), 6),
        "avg_cost": round(totals["cost"] / max(count, 1), 6),
        "avg_final_coverage": round(totals["coverage"] / max(count, 1), 6),
        "avg_final_evidence": round(totals["evidence"] / max(count, 1), 6),
        "avg_reward": round(totals["reward"] / max(count, 1), 6),
        "action_counts": action_counts,
    }


def _aggregate(results: List[Dict]) -> Dict:
    metrics = (
        "accept_rate_pct",
        "unsafe_accept_rate_pct",
        "max_iteration_failure_rate_pct",
        "avg_iterations",
        "avg_cost",
        "avg_final_coverage",
        "avg_final_evidence",
        "avg_reward",
    )
    aggregate = {"num_training_seeds": len(results)}
    for metric in metrics:
        values = [float(item[metric]) for item in results]
        aggregate[metric] = {
            "mean": round(statistics.mean(values), 6),
            "std": round(statistics.pstdev(values), 6),
        }
    return aggregate


def _paired_comparisons(per_policy: Dict[str, List[Dict]], target: str) -> Dict:
    comparisons = {}
    target_rows = per_policy[target]
    for baseline, rows in per_policy.items():
        if baseline == target:
            continue
        reward_diff = [
            target_row["avg_reward"] - baseline_row["avg_reward"]
            for target_row, baseline_row in zip(target_rows, rows)
        ]
        unsafe_diff = [
            baseline_row["unsafe_accept_rate_pct"]
            - target_row["unsafe_accept_rate_pct"]
            for target_row, baseline_row in zip(target_rows, rows)
        ]
        comparisons[baseline] = {
            "safe_ppo_minus_baseline_avg_reward": round(
                statistics.mean(reward_diff), 6
            ),
            "baseline_minus_safe_ppo_unsafe_accept_pct": round(
                statistics.mean(unsafe_diff), 6
            ),
            "safe_ppo_reward_wins": sum(value > 0 for value in reward_diff),
        }
    return comparisons


def run(
    training_seeds: int = 3,
    timesteps: int = 15_000,
    evaluation_episodes: int = 500,
) -> Dict:
    policies = (
        "fixed_1",
        "fixed_3",
        "fixed_5",
        "audit_threshold_rule",
        "raw_ppo",
        "safe_ppo",
    )
    scenarios = build_scenarios(seed=20260929, episodes=evaluation_episodes)
    per_policy: Dict[str, List[Dict]] = {name: [] for name in policies}
    training_seconds = []

    for seed in range(training_seeds):
        model, elapsed = train_ppo(seed=seed, timesteps=timesteps)
        training_seconds.append(elapsed)
        for policy in policies:
            per_policy[policy].append(evaluate_policy(policy, model, scenarios))

    report = {
        "run_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "benchmark_type": "controlled_generation_decision_environment",
        "limitations": [
            "State transitions model controlled quality changes and are not real LLM conversations.",
            "The benchmark tests policy and safety behavior; real Creator-Auditor trajectories are still required for external validity.",
        ],
        "settings": {
            "training_seeds": training_seeds,
            "ppo_timesteps_per_seed": timesteps,
            "evaluation_episodes": evaluation_episodes,
            "shared_evaluation_scenarios": True,
            "actions": [
                "accept",
                "revise_coverage",
                "revise_consistency",
                "revise_boundary",
                "refresh_evidence",
            ],
        },
        "training_seconds": [round(value, 3) for value in training_seconds],
        "aggregate": {
            policy: _aggregate(rows) for policy, rows in per_policy.items()
        },
        "comparisons_vs_safe_ppo": _paired_comparisons(per_policy, "safe_ppo"),
        "per_seed": per_policy,
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamped = RESULTS_DIR / f"generation_policy_benchmark_{report['run_id']}.json"
    latest = RESULTS_DIR / "generation_policy_benchmark_latest.json"
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    timestamped.write_text(payload, encoding="utf-8")
    latest.write_text(payload, encoding="utf-8")

    print(f"[generation-benchmark] report={timestamped}")
    print("policy\taccept%\tunsafe%\tmaxfail%\tavg_iter\tavg_cost\tavg_reward")
    for policy, metrics in report["aggregate"].items():
        print(
            f"{policy}\t{metrics['accept_rate_pct']['mean']:.2f}\t"
            f"{metrics['unsafe_accept_rate_pct']['mean']:.2f}\t"
            f"{metrics['max_iteration_failure_rate_pct']['mean']:.2f}\t"
            f"{metrics['avg_iterations']['mean']:.2f}\t"
            f"{metrics['avg_cost']['mean']:.3f}\t"
            f"{metrics['avg_reward']['mean']:.3f}"
        )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--training-seeds", type=int, default=3)
    parser.add_argument("--timesteps", type=int, default=15_000)
    parser.add_argument("--evaluation-episodes", type=int, default=500)
    args = parser.parse_args()
    run(
        training_seeds=args.training_seeds,
        timesteps=args.timesteps,
        evaluation_episodes=args.evaluation_episodes,
    )


if __name__ == "__main__":
    main()
