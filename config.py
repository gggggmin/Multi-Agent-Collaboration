"""全局配置 — 含 LLM、RAG、多智能体、RL、自愈等全部配置"""
import os
from pathlib import Path

# 项目根目录
ROOT_DIR = Path(__file__).parent

# ========== LLM 配置 ==========
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "deepseek")  # openai / deepseek / claude
LLM_API_KEY = os.getenv("LLM_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-v4-flash")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.3"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4096"))

# LLM 端点
LLM_BASE_URL_MAP = {
    "deepseek": "https://api.deepseek.com",
    "openai": "https://api.openai.com/v1",
    "claude": "https://api.anthropic.com/v1",
}

# ========== Embedding 配置 ==========
EMBEDDING_BACKEND = os.getenv("EMBEDDING_BACKEND", "tfidf")  # tfidf / sentence-transformers
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_CACHE_DIR = str(ROOT_DIR / ".cache" / "embeddings")

# ========== ChromaDB 配置 ==========
CHROMA_PERSIST_DIR = str(ROOT_DIR / ".cache" / "chroma_db")
CHROMA_COLLECTION_NAME = "requirement_chunks"

# ========== 检索配置 ==========
RETRIEVAL_TOP_K = 3

# ========== 博弈配置 ==========
MAX_ITERATIONS = 3
AUDIT_REQUIRED = True

# ========== 实验配置 ==========
EXPERIMENTS_DIR = ROOT_DIR / "experiments"
REQUIREMENTS_DIR = EXPERIMENTS_DIR / "requirements"
RESULTS_DIR = EXPERIMENTS_DIR / "results"
GROUND_TRUTH_FILE = EXPERIMENTS_DIR / "ground_truth.json"
AGENT_TRACE_ENABLED = os.getenv("AGENT_TRACE_ENABLED", "1") == "1"
AGENT_TRACE_DIR = os.getenv("AGENT_TRACE_DIR", str(RESULTS_DIR / "agent_traces"))

# ========== 被测系统配置 ==========
TARGET_APP_URL = "http://localhost:5000"
TARGET_APP_PORT = 5000

# ========== AutoGen 配置 ==========
AUTOGEN_CONFIG_LIST = [
    {
        "model": LLM_MODEL,
        "api_key": LLM_API_KEY,
        "base_url": LLM_BASE_URL_MAP.get(LLM_PROVIDER, LLM_BASE_URL_MAP["deepseek"]),
    }
]
AUTOGEN_MAX_ROUND = 10  # GroupChat 最大对话轮次

# ========== 强化学习 (RL-AGS) 配置 ==========
RL_AGS_CONFIG = {
    # 环境参数
    "env": {
        "max_iterations": 6,              # 最大博弈轮次
        "reward_pass": 20.0,              # 审计通过奖励
        "reward_coverage_gain": 10.0,     # 覆盖率提升奖励
        "penalty_iteration": -1.0,        # 每轮迭代惩罚
        "penalty_hallucination": -5.0,    # 幻觉惩罚
        "penalty_force_exit": -5.0,       # 超限强制退出惩罚
    },
    # PPO 训练参数
    "training": {
        "total_timesteps": 10000,
        "learning_rate": 3e-4,
        "gamma": 0.99,                    # 折扣因子
        "n_steps": 512,                   # 每轮采集步数
        "batch_size": 64,
    },
    # 模型路径
    "model_save_dir": str(ROOT_DIR / ".cache" / "rl_models"),
    "model_name": "ags_ppo",
}

# ========== 自愈策略选择 (RL-HSS / Bandit) 配置 ==========
RL_HSS_CONFIG = {
    "strategies": [
        "llm_rewrite",      # 调 LLM 重写（默认，成本高）
        "rule_locator",     # 规则替换定位器
        "rule_timeout",     # 增加超时等待
        "fallback",         # 回退版本
    ],
    "epsilon": 0.1,         # 探索率
    "alpha": 0.5,           # 学习率（用于增量更新）
}

# ========== 实验配置 ==========
EXPERIMENT_MODULES = ["login", "search", "cart", "checkout"]
