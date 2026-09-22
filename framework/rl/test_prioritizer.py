"""RCP-TCP: requirement-coverage-priority test case prioritization.

The prioritizer ranks generated test cases before execution so that high-risk,
high-coverage, and historically unstable cases run earlier.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional


@dataclass(frozen=True)
class PrioritizationWeights:
    """Weights used by the RCP-TCP scoring function."""

    requirement_coverage: float = 0.35
    risk_level: float = 0.25
    historical_failure: float = 0.20
    boundary_case: float = 0.10
    execution_cost: float = 0.10


class TestCasePrioritizer:
    """Rank generated test cases using a deterministic weighted score."""

    TYPE_RISK = {
        "negative": 0.9,
        "逆向": 0.9,
        "boundary": 0.8,
        "边界值": 0.8,
        "positive": 0.5,
        "正向": 0.5,
    }

    def __init__(
        self,
        weights: Optional[PrioritizationWeights] = None,
        execution_costs: Optional[Mapping[str, float]] = None,
        history: Optional[Mapping[str, Mapping[str, float]]] = None,
    ):
        self.weights = weights or PrioritizationWeights()
        self.execution_costs = dict(execution_costs or {})
        self.history = dict(history or {})

    def rank(
        self,
        test_cases: Iterable[Dict],
        requirement_chunks: Optional[Iterable[Dict]] = None,
    ) -> List[Dict]:
        """Return test cases sorted by descending priority score."""
        requirement_terms = self._requirement_terms(requirement_chunks or [])
        scored_cases = []

        for index, case in enumerate(test_cases):
            test_id = case.get("test_id", f"case_{index}")
            score_parts = self._score_parts(case, requirement_terms)
            priority_score = self._weighted_sum(score_parts)
            enriched = dict(case)
            enriched["priority_score"] = round(priority_score, 4)
            enriched["priority_rank_features"] = score_parts
            enriched["_original_index"] = index
            scored_cases.append(enriched)

        ranked = sorted(
            scored_cases,
            key=lambda item: (
                -item["priority_score"],
                item.get("test_id", ""),
                item["_original_index"],
            ),
        )

        for rank, case in enumerate(ranked, start=1):
            case["priority_rank"] = rank
            case.pop("_original_index", None)

        return ranked

    def _score_parts(self, case: Dict, requirement_terms: set[str]) -> Dict[str, float]:
        test_id = case.get("test_id", "")
        case_type = str(case.get("type", "positive")).strip()
        risk_key = case_type.lower() if case_type.isascii() else case_type
        text = " ".join(
            str(case.get(field, ""))
            for field in ("requirement", "title", "precondition", "expected")
        ).lower()

        return {
            "requirement_coverage": self._requirement_coverage(text, requirement_terms),
            "risk_level": self.TYPE_RISK.get(risk_key, 0.6),
            "historical_failure": self._historical_failure(test_id),
            "boundary_case": 1.0 if risk_key in {"boundary", "边界值"} else 0.0,
            "execution_cost": self._normalized_cost(test_id),
        }

    def _weighted_sum(self, parts: Dict[str, float]) -> float:
        w = self.weights
        return (
            w.requirement_coverage * parts["requirement_coverage"]
            + w.risk_level * parts["risk_level"]
            + w.historical_failure * parts["historical_failure"]
            + w.boundary_case * parts["boundary_case"]
            - w.execution_cost * parts["execution_cost"]
        )

    def _requirement_coverage(self, text: str, requirement_terms: set[str]) -> float:
        if not requirement_terms:
            return 0.5
        matched = sum(1 for term in requirement_terms if term in text)
        return min(matched / max(len(requirement_terms), 1), 1.0)

    def _historical_failure(self, test_id: str) -> float:
        stats = self.history.get(test_id, {})
        runs = float(stats.get("runs", 0))
        failures = float(stats.get("failures", 0))
        if runs <= 0:
            return 0.0
        return min(max(failures / runs, 0.0), 1.0)

    def _normalized_cost(self, test_id: str) -> float:
        if not self.execution_costs:
            return 0.0
        max_cost = max(self.execution_costs.values()) or 1.0
        return min(self.execution_costs.get(test_id, 0.0) / max_cost, 1.0)

    @staticmethod
    def _requirement_terms(chunks: Iterable[Dict]) -> set[str]:
        terms = set()
        for chunk in chunks:
            module = str(chunk.get("module", "")).strip().lower()
            requirement_id = str(chunk.get("requirement_id", "")).strip().lower()
            title = str(chunk.get("title", "")).strip().lower()
            for value in (module, requirement_id, title):
                if value:
                    terms.add(value)
        return terms
