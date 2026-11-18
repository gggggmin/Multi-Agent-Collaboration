"""Robustness experiment for noisy, ambiguous, and conflicting requirements."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config import RESULTS_DIR
from framework.multi_agent import CaseAuditor
from framework.rl import AGSEnvironment, AGSTrainer


def _chunks():
    return [
        {
            "metadata": {"module": "checkout", "func_name": "冲突登录要求"},
            "content": (
                "## 功能1：结算登录要求冲突\n"
                "- **前置条件**：用户必须登录才能结算，同时无需登录也可以直接结算。\n"
                "- **操作路径**：访问 /checkout。\n"
                "- **预期结果**：跳转登录页，但也可以访问结算页。\n"
                "- **类型**：逆向"
            ),
        },
        {
            "metadata": {"module": "cart", "func_name": "模糊库存策略"},
            "content": (
                "## 功能2：库存不足处理\n"
                "- **前置条件**：库存可能不足。\n"
                "- **操作路径**：适当添加若干商品。\n"
                "- **预期结果**：系统尽快给出合理提示，具体文案待定。\n"
                "- **类型**：边界值"
            ),
        },
    ]


def _cases():
    return [
        {
            "test_id": "TC-NOISY-001",
            "module": "checkout",
            "requirement": "结算登录要求冲突",
            "title": "结算登录要求冲突",
            "steps": ["未登录访问 /checkout"],
            "expected": "既跳转登录页又显示结算页",
            "type": "逆向",
        },
        {
            "test_id": "TC-NOISY-002",
            "module": "cart",
            "requirement": "库存不足处理",
            "title": "库存不足处理",
            "steps": ["添加若干商品"],
            "expected": "尽快给出合理提示",
            "type": "边界值",
        },
        {
            "test_id": "TC-NOISY-003",
            "module": "promotion",
            "requirement": "优惠券满减",
            "title": "优惠券满减",
            "steps": ["输入优惠券码 SAVE100"],
            "expected": "订单减免 100 元",
            "type": "正向",
        },
        {
            "test_id": "TC-NOISY-004",
            "module": "refund",
            "requirement": "退款审核",
            "title": "退款审核",
            "steps": [],
            "expected": "",
            "type": "逆向",
        },
    ]


def run() -> dict:
    auditor = CaseAuditor()
    chunks = _chunks()
    cases = _cases()
    audit = auditor.audit(cases, chunks)

    state = {
        "current_iteration": 1,
        "max_iterations": 3,
        "num_issues": len(audit.get("issues", [])),
        "num_cases": len(cases),
        "coverage_estimate": 0.35,
        "has_hallucination": any(
            issue.get("type") == "hallucination"
            for issue in audit.get("issues", [])
        ),
    }

    env = AGSEnvironment()
    obs, _ = env.reset(options=state)
    env.update_from_audit(audit, state["coverage_estimate"])

    try:
        action = AGSTrainer().predict(state)
    except Exception:
        action = None

    safe_action = action
    if any(issue.get("severity") == "error" for issue in audit.get("issues", [])):
        safe_action = 0

    issue_counts = {}
    for issue in audit.get("issues", []):
        issue_type = issue.get("type", "unknown")
        issue_counts[issue_type] = issue_counts.get(issue_type, 0) + 1

    result = {
        "run_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "dataset": "noisy_ambiguous_conflicting_requirements",
        "num_requirements": len(chunks),
        "num_cases": len(cases),
        "audit_passed": audit.get("passed", False),
        "issue_counts": issue_counts,
        "issues": audit.get("issues", []),
        "rl_state": state,
        "rl_observation": obs.tolist(),
        "rl_action": action,
        "rl_action_name": {0: "continue", 1: "accept", None: "unavailable"}.get(action, "unknown"),
        "safety_gated_action": safe_action,
        "safety_gated_action_name": {0: "continue", 1: "accept", None: "unavailable"}.get(safe_action, "unknown"),
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = RESULTS_DIR / f"robustness_noisy_requirements_{result['run_id']}.json"
    latest_path = RESULTS_DIR / "robustness_noisy_requirements_latest.json"
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    output_path.write_text(payload, encoding="utf-8")
    latest_path.write_text(payload, encoding="utf-8")

    print(f"[robustness] report={output_path}")
    print(f"[robustness] latest={latest_path}")
    print(f"[robustness] issues={issue_counts}")
    print(f"[robustness] rl_action={result['rl_action_name']}")
    print(f"[robustness] safety_gated_action={result['safety_gated_action_name']}")
    return result


if __name__ == "__main__":
    run()
