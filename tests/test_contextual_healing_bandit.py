import numpy as np

from framework.rl.contextual_healing_bandit import (
    ContextualHealingBandit,
    HealingContextEncoder,
    cost_sensitive_healing_reward,
)


def test_encoder_has_stable_dimension_and_finite_values():
    encoder = HealingContextEncoder()
    vector = encoder.encode(
        {
            "error_category": "locator",
            "locator_type": "role",
            "dom_change": 0.7,
            "attempt": 2,
            "script_complexity": 0.4,
            "historical_success": 0.8,
            "estimated_cost": 0.2,
        }
    )

    assert vector.shape == (encoder.dimension,)
    assert np.isfinite(vector).all()
    assert vector[0] == 1.0


def test_linucb_learns_context_specific_strategy():
    bandit = ContextualHealingBandit(
        ["rule_locator", "llm_rewrite"], context_dimension=2, alpha=0.2
    )
    locator_context = np.array([1.0, 0.0])
    complex_context = np.array([0.0, 1.0])

    for _ in range(20):
        bandit.update("rule_locator", locator_context, 1.0)
        bandit.update("llm_rewrite", locator_context, -0.5)
        bandit.update("rule_locator", complex_context, -0.5)
        bandit.update("llm_rewrite", complex_context, 1.0)

    assert bandit.select_strategy(locator_context) == "rule_locator"
    assert bandit.select_strategy(complex_context) == "llm_rewrite"


def test_reward_penalizes_high_cost_and_regressions():
    low_cost = cost_sensitive_healing_reward(
        success=True, regression_passed=True, normalized_cost=0.1
    )
    high_cost = cost_sensitive_healing_reward(
        success=True, regression_passed=True, normalized_cost=0.9
    )
    regression = cost_sensitive_healing_reward(
        success=True, regression_passed=False, normalized_cost=0.1
    )

    assert low_cost > high_cost
    assert low_cost > regression
