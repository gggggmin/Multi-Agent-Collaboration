"""RL-AGS: Gymnasium 环境定义

RL-AGS (Adaptive Game Stopping) 是强化学习智能体，负责决定
Creator-Auditor 博弈何时终止。它将博弈过程建模为 MDP：

  状态 (State)     →  动作 (Action)     →  奖励 (Reward)
  ─────────────────────────────────────────────────
  当前轮次/最大轮次    0=继续迭代          +覆盖率提升
  Auditor 问题数      1=接受输出          -迭代成本
  覆盖率估计                              -幻觉惩罚
                                          +审计通过奖励
"""
import math
import gymnasium as gym
import numpy as np
from gymnasium import spaces
from typing import Dict, List, Optional


class AGSEnvironment(gym.Env):
    """自适应博弈终止环境

    在每个时间步，环境接收"当前博弈状态"作为输入，
    RL 智能体输出决策（继续/停止），环境返回奖励。

    用法:
        env = AGSEnvironment()
        obs, info = env.reset(state={
            "current_iteration": 1,
            "max_iterations": 6,
            "num_issues": 3,
            "num_cases": 5,
            "coverage_estimate": 0.6,
            "has_hallucination": True,
        })
        action, _ = model.predict(obs)  # 0=继续 1=停止
        obs, reward, terminated, truncated, info = env.step(action)
    """

    def __init__(self, config: Optional[Dict] = None):
        super().__init__()

        cfg = config or {}
        self.max_iterations = cfg.get("max_iterations", 6)
        self.reward_pass = cfg.get("reward_pass", 20.0)
        self.reward_coverage_gain = cfg.get("reward_coverage_gain", 10.0)
        self.penalty_iteration = cfg.get("penalty_iteration", -1.0)
        self.penalty_hallucination = cfg.get("penalty_hallucination", -5.0)
        self.penalty_force_exit = cfg.get("penalty_force_exit", -5.0)

        # 内部状态
        self.current_iteration = 0
        self.max_iter = self.max_iterations
        self.num_issues = 0
        self.num_cases = 0
        self.prev_coverage = 0.0
        self.coverage = 0.0
        self.has_hallucination = False
        self.audit_passed = False

        # 观测空间: 连续向量 [0,1]^5
        #   dim0: current_iteration / max_iterations
        #   dim1: num_issues / max(issues, 10)
        #   dim2: coverage_estimate
        #   dim3: hallucination_flag
        #   dim4: audit_passed_flag
        self.observation_space = spaces.Box(
            low=0.0, high=1.0, shape=(5,), dtype=np.float32
        )

        # 动作空间: 离散 2
        #   0 = 继续迭代 (Continue)
        #   1 = 接受输出并停止 (Accept)
        self.action_space = spaces.Discrete(2)

    def reset(self, *, seed=None, options=None):
        """重置环境，返回初始观测"""
        super().reset(seed=seed)

        state = options or {}
        self.current_iteration = state.get("current_iteration", 1)
        self.max_iter = state.get("max_iterations", self.max_iterations)
        self.num_issues = state.get("num_issues", 0)
        self.num_cases = state.get("num_cases", 0)
        self.prev_coverage = state.get("coverage_estimate", 0.0)
        self.coverage = state.get("coverage_estimate", 0.0)
        self.has_hallucination = state.get("has_hallucination", False)
        self.audit_passed = False

        return self._get_obs(), self._get_info()

    def step(self, action):
        """执行动作，返回 (obs, reward, terminated, truncated, info)"""
        terminated = False
        reward = 0.0

        if action == 0:
            # 继续迭代 — 支付迭代成本
            reward += self.penalty_iteration
            self.current_iteration += 1

            # 模拟覆盖率小幅提升（真实场景由外部计算后传入）
            coverage_gain = max(0, self.coverage - self.prev_coverage)
            reward += self.reward_coverage_gain * coverage_gain
            self.prev_coverage = self.coverage

            # 检查是否超限
            if self.current_iteration >= self.max_iter:
                terminated = True
                reward += self.penalty_force_exit

        else:
            # 接受输出 — 终止
            terminated = True
            if self.audit_passed:
                reward += self.reward_pass
                # 最终覆盖率奖励
                reward += self.reward_coverage_gain * self.coverage
            # 幻觉惩罚
            if self.has_hallucination:
                reward += self.penalty_hallucination

        # 训练场景下 truncated 为 False
        truncated = False

        return self._get_obs(), reward, terminated, truncated, self._get_info()

    def update_from_audit(self, audit_result: Dict, coverage_estimate: float):
        """从外部更新审计状态（在每轮博弈后由 Coordinator 调用）"""
        self.num_issues = len(audit_result.get("issues", []))
        self.audit_passed = audit_result.get("passed", False)
        self.has_hallucination = any(
            i.get("type") == "hallucination" for i in audit_result.get("issues", [])
        )
        self.prev_coverage = self.coverage
        self.coverage = coverage_estimate

    def _get_obs(self) -> np.ndarray:
        """构建观测向量"""
        return np.array([
            min(self.current_iteration / max(self.max_iter, 1), 1.0),
            min(self.num_issues / 10.0, 1.0),
            min(self.coverage, 1.0),
            1.0 if self.has_hallucination else 0.0,
            1.0 if self.audit_passed else 0.0,
        ], dtype=np.float32)

    def _get_info(self) -> Dict:
        return {
            "iteration": self.current_iteration,
            "max_iterations": self.max_iter,
            "num_issues": self.num_issues,
            "coverage": self.coverage,
            "audit_passed": self.audit_passed,
            "has_hallucination": self.has_hallucination,
        }
