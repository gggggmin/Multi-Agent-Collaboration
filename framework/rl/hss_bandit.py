"""RL-HSS: 自愈策略选择的 Multi-Armed Bandit

RL-HSS (Healing Strategy Selection) 使用多臂赌博机算法，
根据历史修复效果动态选择最佳修复策略。

策略池:
  - llm_rewrite:   调 LLM 重写代码（默认，成本高但通用）
  - rule_locator:  规则替换元素定位器（低成本）
  - rule_timeout:  增加超时等待（低成本）
  - fallback:      回退到上一个可用版本（保底）

算法: ε-greedy / UCB
"""
import json
import random
from typing import Dict, List, Optional
from pathlib import Path

from config import RL_HSS_CONFIG, RESULTS_DIR


class HSSBandit:
    """自愈策略选择的 Bandit

    用法:
        bandit = HSSBandit()
        strategy = bandit.select_strategy(error_category="locator")
        success = execute_strategy(strategy)
        bandit.update(strategy, success)
    """

    def __init__(self, config: Optional[Dict] = None):
        cfg = config or RL_HSS_CONFIG
        self.strategies = cfg.get("strategies", [
            "llm_rewrite", "rule_locator", "rule_timeout", "fallback",
        ])
        self.epsilon = cfg.get("epsilon", 0.1)
        self.alpha = cfg.get("alpha", 0.5)

        # Q 值: {error_category: {strategy: q_value}}
        self.q_values: Dict[str, Dict[str, float]] = {}

        # 计数: {error_category: {strategy: count}}
        self.counts: Dict[str, Dict[str, int]] = {}

        self.total_trials = 0
        self.total_successes = 0

    def select_strategy(self, error_category: str) -> str:
        """为指定错误类型选择修复策略

        使用 ε-greedy 策略:
          - 以 ε 概率随机探索
          - 以 1-ε 概率选择当前 Q 值最高的策略

        Args:
            error_category: 错误分类 (locator/timeout/assertion/syntax/attribute/import)

        Returns:
            策略名称
        """
        # 初始化该错误类型的记录
        if error_category not in self.q_values:
            self.q_values[error_category] = {s: 1.0 for s in self.strategies}
            self.counts[error_category] = {s: 0 for s in self.strategies}

        # ε-greedy 探索
        if random.random() < self.epsilon:
            return random.choice(self.strategies)

        # 利用: 选 Q 值最高的
        qs = self.q_values[error_category]
        return max(qs, key=qs.get)

    def update(self, strategy: str, error_category: str, success: bool):
        """更新 Bandit 的 Q 值

        使用增量式更新:
            Q_new = Q_old + α * (reward - Q_old)

        Args:
            strategy: 使用的策略
            error_category: 错误分类
            success: 修复是否成功
        """
        # 确保记录存在
        if error_category not in self.q_values:
            self.q_values[error_category] = {s: 1.0 for s in self.strategies}
            self.counts[error_category] = {s: 0 for s in self.strategies}

        if strategy not in self.q_values[error_category]:
            self.q_values[error_category][strategy] = 1.0
            self.counts[error_category][strategy] = 0

        # 奖励: 成功=1.0, 失败=-0.5
        reward = 1.0 if success else -0.5

        # 增量更新 Q 值
        old_q = self.q_values[error_category][strategy]
        self.q_values[error_category][strategy] = old_q + self.alpha * (reward - old_q)

        # 更新计数
        self.counts[error_category][strategy] += 1
        self.total_trials += 1
        if success:
            self.total_successes += 1

    def get_best_strategy(self, error_category: str) -> str:
        """获取指定错误类型的最佳策略"""
        if error_category not in self.q_values:
            return self.strategies[0]
        return max(self.q_values[error_category], key=self.q_values[error_category].get)

    def get_stats(self) -> Dict:
        """获取策略选择统计"""
        overall = {
            "total_trials": self.total_trials,
            "total_successes": self.total_successes,
            "overall_success_rate": round(
                self.total_successes / max(self.total_trials, 1), 3
            ),
        }

        details = {}
        for cat, qs in self.q_values.items():
            details[cat] = {
                "best_strategy": max(qs, key=qs.get),
                "q_values": {s: round(v, 3) for s, v in qs.items()},
                "counts": self.counts.get(cat, {}),
            }

        return {"overall": overall, "details": details}

    def save(self, path: Optional[str] = None):
        """保存 Bandit 状态"""
        save_path = path or str(RESULTS_DIR / "hss_bandit.json")
        data = {
            "q_values": {k: {s: round(v, 4) for s, v in qs.items()}
                         for k, qs in self.q_values.items()},
            "counts": self.counts,
            "total_trials": self.total_trials,
            "total_successes": self.total_successes,
        }
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self, path: str):
        """加载 Bandit 状态"""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.q_values = data.get("q_values", {})
        self.counts = data.get("counts", {})
        self.total_trials = data.get("total_trials", 0)
        self.total_successes = data.get("total_successes", 0)
