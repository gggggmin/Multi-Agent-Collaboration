"""Run RCP-TCP test case prioritization on a generated pipeline report."""
import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from framework.rl import TestCasePrioritizer

DEFAULT_REPORT = ROOT / "experiments" / "results" / "agent_pipeline_20260921_210235.json"
DEFAULT_OUTPUT = ROOT / "experiments" / "results" / "prioritization_latest.json"


def load_cases(report: Dict) -> List[Dict]:
    """Extract generated cases from the existing pipeline report format."""
    cases = []
    for module_result in report.get("generation", {}).values():
        if isinstance(module_result, dict):
            cases.extend(module_result.get("cases", []))

    if cases:
        return cases

    for module_result in report.get("module_results", []):
        cases.extend(module_result.get("cases", []))

    if cases:
        return cases

    for module_result in report.get("results", {}).values():
        if isinstance(module_result, dict):
            cases.extend(module_result.get("cases", []))
    return cases


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    report_path = Path(args.report)
    with report_path.open("r", encoding="utf-8") as f:
        report = json.load(f)

    cases = load_cases(report)
    prioritizer = TestCasePrioritizer()
    ranked = prioritizer.rank(cases)

    result = {
        "source_report": str(report_path),
        "total_cases": len(ranked),
        "top_10": [
            {
                "priority_rank": case.get("priority_rank"),
                "priority_score": case.get("priority_score"),
                "test_id": case.get("test_id"),
                "module": case.get("module"),
                "type": case.get("type"),
                "title": case.get("title"),
                "features": case.get("priority_rank_features"),
            }
            for case in ranked[:10]
        ],
        "ranked_cases": ranked,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"RCP-TCP ranked {len(ranked)} cases")
    print(f"output={output_path}")
    for item in result["top_10"][:5]:
        print(
            f"#{item['priority_rank']} {item['test_id']} "
            f"score={item['priority_score']} type={item['type']}"
        )


if __name__ == "__main__":
    main()
