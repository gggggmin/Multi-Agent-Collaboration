"""Reproducible ablation suite for the thesis experiments.

The suite focuses on deterministic, evidence-producing comparisons:
  1. Full RAG context vs truncated RAG context vs no RAG context.
  2. Auditor enabled vs no Auditor on noisy requirements.
  3. Raw PPO decision vs Safety-gated RL-AGS decision.

Every run writes a timestamped JSON report and refreshes a latest pointer.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import GROUND_TRUTH_FILE, REQUIREMENTS_DIR, RESULTS_DIR
from experiments.run_robustness_experiment import _cases as noisy_cases
from experiments.run_robustness_experiment import _chunks as noisy_chunks
from framework.multi_agent import CaseAuditor
from framework.rag import DocumentParser, SemanticChunker
from framework.rl import AGSTrainer


def _load_ground_truth() -> List[Dict]:
    return json.loads(Path(GROUND_TRUTH_FILE).read_text(encoding="utf-8"))


def _group_by_module(items: List[Dict]) -> Dict[str, List[Dict]]:
    grouped: Dict[str, List[Dict]] = {}
    for item in items:
        grouped.setdefault(item.get("module", "unknown"), []).append(item)
    return grouped


def _chunk_to_dict(chunk) -> Dict:
    return chunk.to_dict() if hasattr(chunk, "to_dict") else chunk


def _count_issues(audit: Dict) -> Dict:
    counts: Dict[str, int] = {}
    severities: Dict[str, int] = {}
    for issue in audit.get("issues", []):
        issue_type = issue.get("type", "unknown")
        severity = issue.get("severity", "unknown")
        counts[issue_type] = counts.get(issue_type, 0) + 1
        severities[severity] = severities.get(severity, 0) + 1
    return {
        "passed": audit.get("passed", False),
        "total_issues": len(audit.get("issues", [])),
        "issue_counts": counts,
        "severity_counts": severities,
    }


def _rag_context_ablation() -> Dict:
    auditor = CaseAuditor()
    ground_truth = _load_ground_truth()
    cases_by_module = _group_by_module(ground_truth)
    chunks = [
        _chunk_to_dict(chunk)
        for chunk in SemanticChunker(DocumentParser()).create_chunks(str(REQUIREMENTS_DIR))
    ]
    chunks_by_module = _group_by_module(chunks)

    modes = {
        "full_rag": lambda module: chunks_by_module.get(module, []),
        "truncated_rag_top5": lambda module: chunks_by_module.get(module, [])[:5],
        "no_rag": lambda module: [],
    }

    results = {}
    for mode, chunk_selector in modes.items():
        module_results = {}
        aggregate = {
            "total_cases": 0,
            "total_issues": 0,
            "error_issues": 0,
            "hallucination_issues": 0,
            "passed_modules": 0,
        }
        for module, cases in cases_by_module.items():
            audit = auditor.audit(cases, chunk_selector(module))
            summary = _count_issues(audit)
            module_results[module] = summary
            aggregate["total_cases"] += len(cases)
            aggregate["total_issues"] += summary["total_issues"]
            aggregate["error_issues"] += summary["severity_counts"].get("error", 0)
            aggregate["hallucination_issues"] += summary["issue_counts"].get("hallucination", 0)
            if summary["passed"]:
                aggregate["passed_modules"] += 1

        aggregate["false_positive_issue_rate_pct"] = round(
            aggregate["total_issues"] / max(aggregate["total_cases"], 1) * 100, 2
        )
        results[mode] = {
            "aggregate": aggregate,
            "modules": module_results,
        }
    return results


def _auditor_ablation() -> Dict:
    auditor = CaseAuditor()
    cases = noisy_cases()
    chunks = noisy_chunks()
    audit = auditor.audit(cases, chunks)
    with_auditor = _count_issues(audit)
    without_auditor = {
        "passed": True,
        "total_issues": 0,
        "issue_counts": {},
        "severity_counts": {},
        "accepted_cases": len(cases),
        "accepted_known_bad_cases": len(cases),
    }
    return {
        "dataset": "noisy_ambiguous_conflicting_requirements",
        "with_auditor": with_auditor,
        "without_auditor": without_auditor,
        "detected_issue_gain": with_auditor["total_issues"] - without_auditor["total_issues"],
    }


def _safety_gate_ablation() -> Dict:
    auditor = CaseAuditor()
    audit = auditor.audit(noisy_cases(), noisy_chunks())
    state = {
        "current_iteration": 1,
        "max_iterations": 3,
        "num_issues": len(audit.get("issues", [])),
        "num_cases": len(noisy_cases()),
        "coverage_estimate": 0.35,
        "has_hallucination": any(
            issue.get("type") == "hallucination"
            for issue in audit.get("issues", [])
        ),
    }

    try:
        raw_action = AGSTrainer().predict(state)
    except Exception:
        raw_action = None

    has_error = any(issue.get("severity") == "error" for issue in audit.get("issues", []))
    gated_action = 0 if has_error else raw_action
    action_names = {0: "continue", 1: "accept", None: "unavailable"}

    return {
        "state": state,
        "has_error_issue": has_error,
        "raw_ppo_action": raw_action,
        "raw_ppo_action_name": action_names.get(raw_action, "unknown"),
        "safety_gated_action": gated_action,
        "safety_gated_action_name": action_names.get(gated_action, "unknown"),
        "unsafe_accept_prevented": raw_action == 1 and gated_action == 0,
    }


def run() -> Dict:
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    report = {
        "run_id": run_id,
        "experiments": {
            "rag_context_ablation": _rag_context_ablation(),
            "auditor_ablation": _auditor_ablation(),
            "safety_gate_ablation": _safety_gate_ablation(),
        },
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = RESULTS_DIR / f"ablation_suite_{run_id}.json"
    latest_path = RESULTS_DIR / "ablation_suite_latest.json"
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    output_path.write_text(payload, encoding="utf-8")
    latest_path.write_text(payload, encoding="utf-8")

    print(f"[ablation] report={output_path}")
    print(f"[ablation] latest={latest_path}")
    rag = report["experiments"]["rag_context_ablation"]
    print("[ablation] full_rag issues=", rag["full_rag"]["aggregate"]["total_issues"])
    print("[ablation] truncated_rag_top5 issues=", rag["truncated_rag_top5"]["aggregate"]["total_issues"])
    print("[ablation] no_rag issues=", rag["no_rag"]["aggregate"]["total_issues"])
    print("[ablation] auditor detected issues=", report["experiments"]["auditor_ablation"]["with_auditor"]["total_issues"])
    print("[ablation] safety gate action=", report["experiments"]["safety_gate_ablation"]["safety_gated_action_name"])
    return report


if __name__ == "__main__":
    run()
