"""Compare stopping and prioritization strategies for thesis evidence.

The experiment is deterministic and uses existing project artifacts:
  1. Clean generated cases from the latest pipeline report.
  2. Noisy cases from the robustness experiment fixture.
  3. RCP-TCP prioritization output over generated cases.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import RESULTS_DIR
from experiments.run_prioritization_experiment import load_cases
from experiments.run_robustness_experiment import _cases as noisy_cases
from experiments.run_robustness_experiment import _chunks as noisy_chunks
from framework.multi_agent import CaseAuditor
from framework.rl import AGSTrainer, TestCasePrioritizer


DEFAULT_REPORT = ROOT / "experiments" / "results" / "agent_pipeline_20260921_210235.json"
DEFAULT_OUTPUT = RESULTS_DIR / "strategy_comparison_latest.json"


def _load_clean_cases(report_path: Path) -> List[Dict]:
    with report_path.open("r", encoding="utf-8") as f:
        return load_cases(json.load(f))


def _has_error(audit_result: Dict) -> bool:
    return any(issue.get("severity") == "error" for issue in audit_result.get("issues", []))


def _has_hallucination(audit_result: Dict) -> bool:
    return any(issue.get("type") == "hallucination" for issue in audit_result.get("issues", []))


def _safe_accept(audit_result: Dict) -> bool:
    return bool(audit_result.get("passed")) and not _has_error(audit_result)


def _ppo_action(state: Dict) -> int | None:
    try:
        return AGSTrainer().predict(state)
    except Exception:
        return None


def _stopping_strategy_comparison(clean_cases: List[Dict]) -> Dict:
    auditor = CaseAuditor()
    noisy_audit = auditor.audit(noisy_cases(), noisy_chunks())

    scenarios = [
        {
            "name": "clean_passed_generation",
            "audit": {"passed": True, "issues": []},
            "coverage_estimate": 1.0,
            "case_count": len(clean_cases),
            "expected_safe_to_accept": True,
        },
        {
            "name": "noisy_conflict_and_hallucination",
            "audit": noisy_audit,
            "coverage_estimate": 0.35,
            "case_count": len(noisy_cases()),
            "expected_safe_to_accept": False,
        },
        {
            "name": "warning_only_incomplete_description",
            "audit": {
                "passed": True,
                "issues": [
                    {
                        "severity": "warning",
                        "type": "incomplete",
                        "description": "边界值描述不够明确",
                    }
                ],
            },
            "coverage_estimate": 0.85,
            "case_count": 20,
            "expected_safe_to_accept": True,
        },
        {
            "name": "hallucination_error",
            "audit": {
                "passed": False,
                "issues": [
                    {
                        "severity": "error",
                        "type": "hallucination",
                        "description": "用例在需求文本中找不到依据",
                    }
                ],
            },
            "coverage_estimate": 0.45,
            "case_count": 20,
            "expected_safe_to_accept": False,
        },
    ]

    fixed_rounds = [1, 3, 5]
    strategy_rows = {f"fixed_{r}_round": [] for r in fixed_rounds}
    strategy_rows["raw_ppo"] = []
    strategy_rows["safety_gated_rl_ags"] = []

    for scenario in scenarios:
        audit = scenario["audit"]
        state = {
            "current_iteration": 1,
            "max_iterations": 5,
            "num_issues": len(audit.get("issues", [])),
            "num_cases": scenario["case_count"],
            "coverage_estimate": scenario["coverage_estimate"],
            "has_hallucination": _has_hallucination(audit),
        }
        raw_action = _ppo_action(state)
        gated_action = 0 if _has_error(audit) else raw_action

        for rounds in fixed_rounds:
            strategy_rows[f"fixed_{rounds}_round"].append(
                _decision_record(scenario, True, rounds)
            )

        strategy_rows["raw_ppo"].append(
            _decision_record(scenario, raw_action == 1, 1, raw_action)
        )
        strategy_rows["safety_gated_rl_ags"].append(
            _decision_record(scenario, gated_action == 1, 1, gated_action)
        )

    summary = {}
    for strategy, rows in strategy_rows.items():
        unsafe_accepts = sum(1 for row in rows if row["unsafe_accept"])
        missed_safe_accepts = sum(1 for row in rows if row["missed_safe_accept"])
        summary[strategy] = {
            "num_scenarios": len(rows),
            "avg_iterations": round(
                sum(row["iterations"] for row in rows) / max(len(rows), 1), 3
            ),
            "unsafe_accepts": unsafe_accepts,
            "unsafe_accept_rate_pct": round(unsafe_accepts / max(len(rows), 1) * 100, 2),
            "missed_safe_accepts": missed_safe_accepts,
            "decisions": rows,
        }

    return {
        "description": "Stopping strategy comparison over clean and noisy audit states.",
        "summary": summary,
        "scenarios": [
            {
                "name": item["name"],
                "coverage_estimate": item["coverage_estimate"],
                "num_issues": len(item["audit"].get("issues", [])),
                "has_error": _has_error(item["audit"]),
                "expected_safe_to_accept": item["expected_safe_to_accept"],
            }
            for item in scenarios
        ],
    }


def _decision_record(
    scenario: Dict,
    accepted: bool,
    iterations: int,
    action: int | None = None,
) -> Dict:
    safe_to_accept = scenario["expected_safe_to_accept"]
    return {
        "scenario": scenario["name"],
        "accepted": accepted,
        "action": action,
        "iterations": iterations,
        "safe_to_accept": safe_to_accept,
        "unsafe_accept": accepted and not safe_to_accept,
        "missed_safe_accept": (not accepted) and safe_to_accept,
    }


def _prioritization_strategy_comparison(cases: Iterable[Dict]) -> Dict:
    cases = list(cases)
    history = {
        # The healing demo injects and repairs a locator conflict in TC-SEARCH-005.
        "TC-SEARCH-005": {"runs": 1, "failures": 1},
    }
    execution_costs = {
        case.get("test_id", ""): 1.4 if case.get("module") == "checkout" else 1.0
        for case in cases
    }
    strategies = {
        "original_order": cases,
        "module_order": sorted(cases, key=lambda c: (c.get("module", ""), c.get("test_id", ""))),
        "risk_only": sorted(cases, key=lambda c: (_risk_rank(c), c.get("test_id", ""))),
        "rcp_tcp": TestCasePrioritizer(
            history=history,
            execution_costs=execution_costs,
        ).rank(cases),
    }

    summary = {}
    for name, ordered_cases in strategies.items():
        top_20_count = max(1, int(len(ordered_cases) * 0.2))
        top_20 = ordered_cases[:top_20_count]
        high_risk_total = sum(1 for case in ordered_cases if _is_high_risk(case))
        high_risk_top = sum(1 for case in top_20 if _is_high_risk(case))
        boundary_total = sum(1 for case in ordered_cases if _case_type(case) == "边界值")
        boundary_top = sum(1 for case in top_20 if _case_type(case) == "边界值")
        brittle_total = sum(1 for case in ordered_cases if case.get("test_id") in history)
        brittle_top = sum(1 for case in top_20 if case.get("test_id") in history)

        summary[name] = {
            "total_cases": len(ordered_cases),
            "top_20_pct_count": top_20_count,
            "high_risk_total": high_risk_total,
            "high_risk_in_top_20_pct": high_risk_top,
            "high_risk_capture_pct": round(
                high_risk_top / max(high_risk_total, 1) * 100, 2
            ),
            "boundary_total": boundary_total,
            "boundary_in_top_20_pct": boundary_top,
            "boundary_capture_pct": round(boundary_top / max(boundary_total, 1) * 100, 2),
            "historical_failure_total": brittle_total,
            "historical_failure_in_top_20_pct": brittle_top,
            "historical_failure_capture_pct": round(
                brittle_top / max(brittle_total, 1) * 100, 2
            ),
            "top_10_ids": [case.get("test_id") for case in ordered_cases[:10]],
        }

    return {
        "description": "Prioritization comparison using top-20-percent high-risk capture.",
        "history_source": "experiments/results/healing_demo.json identified TC-SEARCH-005 as a repaired locator failure.",
        "summary": summary,
    }


def _case_type(case: Dict) -> str:
    return str(case.get("type", "")).strip()


def _is_high_risk(case: Dict) -> bool:
    return _case_type(case) in {"逆向", "边界值", "negative", "boundary"}


def _risk_rank(case: Dict) -> int:
    order = {"边界值": 0, "boundary": 0, "逆向": 1, "negative": 1, "正向": 2, "positive": 2}
    return order.get(_case_type(case), 3)


def run(report_path: Path, output_path: Path) -> Dict:
    clean_cases = _load_clean_cases(report_path)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    result = {
        "run_id": run_id,
        "source_report": str(report_path),
        "stopping_strategy_comparison": _stopping_strategy_comparison(clean_cases),
        "prioritization_strategy_comparison": _prioritization_strategy_comparison(clean_cases),
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamped_path = RESULTS_DIR / f"strategy_comparison_{run_id}.json"
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    timestamped_path.write_text(payload, encoding="utf-8")
    output_path.write_text(payload, encoding="utf-8")

    print(f"[strategy] report={timestamped_path}")
    print(f"[strategy] latest={output_path}")
    for name, metrics in result["stopping_strategy_comparison"]["summary"].items():
        print(
            f"[strategy] {name}: avg_iter={metrics['avg_iterations']} "
            f"unsafe_accepts={metrics['unsafe_accepts']}"
        )
    rcp = result["prioritization_strategy_comparison"]["summary"]["rcp_tcp"]
    print(
        "[strategy] rcp_tcp top20 high_risk_capture="
        f"{rcp['high_risk_capture_pct']}%"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()
    run(Path(args.report), Path(args.output))


if __name__ == "__main__":
    main()
