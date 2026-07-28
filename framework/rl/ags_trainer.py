"""RL-AGS: PPO 训练器

基于 Stable-Baselines3 的 PPO 算法，训练智能体控制博弈终止。
训练完成后保存模型，供 Coordinator 推理时加载使用。
"""
import os
import json
import time
from typing import Dict, Optional
from pathlib import Path

import numpy as np
from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import EvalCallback

from .ags_environment import AGSEnvironment
from config import RL_AGS_CONFIG, RESULTS_DIR


class AGSTrainer:
    """PPO 训练器

    用法:
        trainer = AGSTrainer()
        trainer.train(total_timesteps=10000)
        trainer.save("ags_ppo.zip")
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or RL_AGS_CONFIG
        self.env = AGSEnvironment(self.config.get("env", {}))
        self.model: Optional[PPO] = None
        self.training_log: Dict = {
            "episode_rewards": [],
            "episode_lengths": [],
            "eval_results": [],
        }

        # 确保保存目录存在
        save_dir = Path(self.config.get("model_save_dir", ".cache/rl_models"))
        save_dir.mkdir(parents=True, exist_ok=True)
        self.model_save_dir = str(save_dir)

    def train(self, total_timesteps: Optional[int] = None, log_dir: Optional[str] = None):
        """训练 PPO 智能体

        Args:
            total_timesteps: 总训练步数，默认使用配置值
            log_dir: TensorBoard 日志目录
        """
        timesteps = total_timesteps or self.config.get("training", {}).get(
            "total_timesteps", 10000
        )
        train_cfg = self.config.get("training", {})

        # 创建评估环境（用于回调）
        eval_env = AGSEnvironment(self.config.get("env", {}))

        # 设置 TensorBoard
        tb_dir = log_dir or str(RESULTS_DIR / "tensorboard")
        os.makedirs(tb_dir, exist_ok=True)

        # 初始化 PPO 模型
        self.model = PPO(
            "MlpPolicy",
            self.env,
            learning_rate=train_cfg.get("learning_rate", 3e-4),
            gamma=train_cfg.get("gamma", 0.99),
            n_steps=train_cfg.get("n_steps", 512),
            batch_size=train_cfg.get("batch_size", 64),
            verbose=1,
            tensorboard_log=tb_dir,
        )

        # 评估回调
        eval_callback = EvalCallback(
            eval_env,
            best_model_save_path=self.model_save_dir,
            log_path=self.model_save_dir,
            eval_freq=max(timesteps // 20, 100),
            deterministic=True,
            render=False,
        )

        print(f"[RL-AGS] 开始训练 PPO (总步数={timesteps})")
        start = time.time()

        # 模拟训练数据收集（实际场景中 Coordinator 会通过环境交互产生数据）
        # 这里训练智能体学会：尽早通过审计 + 避免不必要的迭代
        self.model.learn(total_timesteps=timesteps, callback=eval_callback)

        elapsed = time.time() - start
        print(f"[RL-AGS] 训练完成，耗时 {elapsed:.1f}s")

        return self._collect_training_stats()

    def predict(self, state: Dict) -> int:
        """用训练好的模型做决策

        Args:
            state: 包含 current_iteration, max_iterations, num_issues,
                   coverage_estimate, has_hallucination 等字段

        Returns:
            动作: 0=继续, 1=停止
        """
        if self.model is None:
            self.load()

        env = AGSEnvironment()
        obs, _ = env.reset(options=state)
        action, _ = self.model.predict(obs, deterministic=True)
        return int(action)

    def save(self, name: Optional[str] = None):
        """保存模型"""
        if self.model is None:
            return
        filename = name or self.config.get("model_name", "ags_ppo")
        path = os.path.join(self.model_save_dir, f"{filename}.zip")
        self.model.save(path)

        # 同时保存训练日志
        log_path = os.path.join(self.model_save_dir, f"{filename}_log.json")
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(self.training_log, f, ensure_ascii=False, indent=2)

        print(f"[RL-AGS] 模型已保存至: {path}")
        return path

    def load(self, name: Optional[str] = None):
        """加载已训练的模型"""
        filename = name or self.config.get("model_name", "ags_ppo")
        path = os.path.join(self.model_save_dir, f"{filename}.zip")
        if not os.path.exists(path):
            print(f"[RL-AGS] 未找到训练好的模型: {path}")
            print("[RL-AGS] 使用随机策略（未训练的 PPO）")
            self.model = PPO("MlpPolicy", self.env, verbose=0)
            return

        self.env = AGSEnvironment(self.config.get("env", {}))
        self.model = PPO.load(path, env=self.env)
        print(f"[RL-AGS] 模型已加载: {path}")

    def _collect_training_stats(self) -> Dict:
        """收集训练统计"""
        return {
            "model_save_dir": self.model_save_dir,
            "config": self.config,
        }
