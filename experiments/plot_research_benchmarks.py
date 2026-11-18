"""Render paper-ready summary figures from the latest benchmark reports."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import RESULTS_DIR


FIGURE_DIR = RESULTS_DIR / "figures"


def _load(name: str):
    return json.loads((RESULTS_DIR / name).read_text(encoding="utf-8"))


def _style():
    plt.rcParams.update(
        {
            "font.sans-serif": ["Microsoft YaHei", "SimHei", "DejaVu Sans"],
            "axes.unicode_minus": False,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "figure.dpi": 150,
        }
    )


def plot_generation(report: dict) -> Path:
    aggregate = report["aggregate"]
    order = [
        "fixed_1",
        "fixed_3",
        "fixed_5",
        "audit_threshold_rule",
        "raw_ppo",
        "safe_ppo",
    ]
    labels = ["Fixed-1", "Fixed-3", "Fixed-5", "Rule", "Raw PPO", "Safe PPO"]
    x = np.arange(len(order))

    accept = [aggregate[key]["accept_rate_pct"]["mean"] for key in order]
    unsafe = [aggregate[key]["unsafe_accept_rate_pct"]["mean"] for key in order]
    reward = [aggregate[key]["avg_reward"]["mean"] for key in order]
    reward_std = [aggregate[key]["avg_reward"]["std"] for key in order]
    cost = [aggregate[key]["avg_cost"]["mean"] for key in order]

    fig, axes = plt.subplots(1, 3, figsize=(14, 4.4))
    width = 0.38
    axes[0].bar(x - width / 2, accept, width, label="Accepted", color="#2D6A9F")
    axes[0].bar(x + width / 2, unsafe, width, label="Unsafe accept", color="#C44E52")
    axes[0].set_ylabel("Rate (%)")
    axes[0].set_title("Decision outcomes")
    axes[0].legend(frameon=False, loc="lower right")

    axes[1].bar(x, reward, yerr=reward_std, capsize=4, color="#4C956C")
    axes[1].axhline(0, color="#666666", linewidth=0.8)
    axes[1].set_ylabel("Average reward")
    axes[1].set_title("Quality-cost reward")

    axes[2].bar(x, cost, color="#D08C60")
    axes[2].set_ylabel("Normalized cost")
    axes[2].set_title("Average decision cost")

    for axis in axes:
        axis.set_xticks(x)
        axis.set_xticklabels(labels, rotation=28, ha="right")
        axis.grid(axis="y", alpha=0.2)
    fig.suptitle("Controlled generation-policy benchmark", fontsize=14)
    fig.tight_layout()

    output = FIGURE_DIR / "generation_policy_benchmark.png"
    fig.savefig(output, bbox_inches="tight")
    plt.close(fig)
    return output


def plot_healing(report: dict) -> Path:
    aggregate = report["aggregate"]
    order = [
        "random",
        "fixed_rule",
        "epsilon_greedy",
        "ucb1",
        "always_llm",
        "cost_sensitive_linucb",
        "expected_oracle_upper_bound",
    ]
    labels = ["Random", "Fixed", "ε-greedy", "UCB1", "Always LLM", "LinUCB", "Oracle"]
    x = np.arange(len(order))

    success = [aggregate[key]["success_rate_pct"]["mean"] for key in order]
    success_std = [aggregate[key]["success_rate_pct"]["std"] for key in order]
    llm = [aggregate[key]["llm_call_rate_pct"]["mean"] for key in order]
    reward = [aggregate[key]["avg_reward"]["mean"] for key in order]
    reward_std = [aggregate[key]["avg_reward"]["std"] for key in order]

    fig, axes = plt.subplots(1, 3, figsize=(14, 4.4))
    axes[0].bar(x, success, yerr=success_std, capsize=4, color="#2D6A9F")
    axes[0].set_ylabel("Repair success (%)")
    axes[0].set_title("Repair effectiveness")

    axes[1].bar(x, llm, color="#D08C60")
    axes[1].set_ylabel("LLM calls (%)")
    axes[1].set_title("LLM usage")

    axes[2].bar(x, reward, yerr=reward_std, capsize=4, color="#4C956C")
    axes[2].axhline(0, color="#666666", linewidth=0.8)
    axes[2].set_ylabel("Average reward")
    axes[2].set_title("Cost-sensitive reward")

    for axis in axes:
        axis.set_xticks(x)
        axis.set_xticklabels(labels, rotation=28, ha="right")
        axis.grid(axis="y", alpha=0.2)
    fig.suptitle("Controlled healing-strategy benchmark", fontsize=14)
    fig.tight_layout()

    output = FIGURE_DIR / "healing_strategy_benchmark.png"
    fig.savefig(output, bbox_inches="tight")
    plt.close(fig)
    return output


def main():
    _style()
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    generation = plot_generation(_load("generation_policy_benchmark_latest.json"))
    healing = plot_healing(_load("healing_strategy_benchmark_latest.json"))
    print(f"[plot] {generation}")
    print(f"[plot] {healing}")


if __name__ == "__main__":
    main()
