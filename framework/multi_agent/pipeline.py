"""End-to-end agent pipeline for thesis experiments.

The pipeline wires the research agents into a reproducible experimental
workflow:
RAG -> Creator/Auditor -> Page Agent -> Test Agent -> optional execution.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from config import (
    EXPERIMENT_MODULES,
    GROUND_TRUTH_FILE,
    REQUIREMENTS_DIR,
    RESULTS_DIR,
)
from experiments.evaluation import Evaluator
from framework.code_gen import PageAgent, TestAgent
from framework.rag import DocumentParser, Retriever, SemanticChunker
from framework.self_healing import ErrorDiagnoser, HealingAgent, SandboxExecutor

from .coordinator import Coordinator


class AgentPipeline:
    """Coordinate all thesis agents in one reproducible run."""

    def __init__(
        self,
        modules: Optional[List[str]] = None,
        use_rl: bool = True,
        output_dir: str = "output",
        execute_tests: bool = False,
        heal_failures: bool = False,
    ):
        self.modules = modules or list(EXPERIMENT_MODULES)
        self.use_rl = use_rl
        self.output_dir = Path(output_dir)
        self.execute_tests = execute_tests
        self.heal_failures = heal_failures

    def run(self) -> Dict:
        """Run the full agent workflow and persist a JSON experiment trace."""
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        print(f"[Pipeline] run_id={run_id}")
        print(f"[Pipeline] modules={', '.join(self.modules)}")

        chunks, retriever = self._build_rag()
        generation = self._run_generation(retriever)
        cases = [
            case
            for module_result in generation.values()
            for case in module_result.get("cases", [])
        ]

        page_files, test_files = self._run_code_generation(cases)
        execution_results = self._run_execution(test_files) if self.execute_tests else []
        healing_results = (
            self._run_healing(execution_results) if self.heal_failures else []
        )
        metrics = self._evaluate(cases, chunks, healing_results)

        result = {
            "run_id": run_id,
            "modules": self.modules,
            "use_rl": self.use_rl,
            "num_cases": len(cases),
            "generation": generation,
            "artifacts": {
                "output_dir": str(self.output_dir),
                "page_files": page_files,
                "test_files": test_files,
            },
            "execution": execution_results,
            "healing": healing_results,
            "metrics": metrics,
        }
        result_path = self._save_result(run_id, result)
        result["result_path"] = str(result_path)
        print(f"[Pipeline] result={result_path}")
        return result

    def _build_rag(self):
        print("[Pipeline] 1/5 build RAG index")
        parser = DocumentParser()
        chunker = SemanticChunker(parser)
        chunks = chunker.create_chunks(str(REQUIREMENTS_DIR))
        retriever = Retriever()
        retriever.build_index(chunks)
        print(f"[Pipeline] chunks={len(chunks)}")
        return chunks, retriever

    def _run_generation(self, retriever: Retriever) -> Dict[str, Dict]:
        print("[Pipeline] 2/5 run Creator/Auditor agents")
        results: Dict[str, Dict] = {}
        for module in self.modules:
            req_chunks = retriever.retrieve_by_module(module)
            if not req_chunks:
                results[module] = {
                    "skipped": True,
                    "reason": "no requirement chunks found",
                    "cases": [],
                }
                print(f"[Pipeline] {module}: skipped, no chunks")
                continue

            coordinator = Coordinator(use_rl=self.use_rl)
            result = coordinator.run(req_chunks, module)
            results[module] = {
                "skipped": False,
                "total_iterations": result.get("total_iterations", 0),
                "passed": result.get("passed", False),
                "audit_summary": result.get("audit_summary", ""),
                "cases": result.get("cases", []),
                "history": result.get("history", []),
            }
            print(
                f"[Pipeline] {module}: cases={len(results[module]['cases'])}, "
                f"iterations={results[module]['total_iterations']}"
            )
        return results

    def _run_code_generation(self, cases: List[Dict]):
        print("[Pipeline] 3/5 run Page/Test agents")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        page_agent = PageAgent()
        test_agent = TestAgent()
        page_files = page_agent.generate(cases, str(self.output_dir))
        test_files = test_agent.generate(cases, page_files, str(self.output_dir))
        return page_files, test_files

    def _run_execution(self, test_files: List[str]) -> List[Dict]:
        print("[Pipeline] 4/5 execute generated tests")
        executor = SandboxExecutor(str(self.output_dir))
        results = []
        for test_file in test_files:
            result = executor.run_script(test_file)
            result["script"] = test_file
            results.append(result)
        return results

    def _run_healing(self, execution_results: List[Dict]) -> List[Dict]:
        print("[Pipeline] 5/5 heal failed tests")
        diagnoser = ErrorDiagnoser()
        healer = HealingAgent()
        executor = SandboxExecutor(str(self.output_dir))
        healed = []
        for result in execution_results:
            if result.get("success"):
                continue
            script_path = Path(result["script"])
            diagnosis = diagnoser.diagnose(result)
            script_content = script_path.read_text(encoding="utf-8")
            heal_result = healer.heal(script_content, diagnosis)
            if heal_result.get("fixed_code"):
                fixed_path = script_path.with_name(f"{script_path.stem}_healed.py")
                fixed_path.write_text(heal_result["fixed_code"], encoding="utf-8")
                verification = executor.run_script(str(fixed_path))
                heal_result["fixed_script"] = str(fixed_path)
                heal_result["verification"] = verification
                heal_result["success"] = verification.get("success", False)
                healer.record_strategy_result(
                    heal_result.get("strategy", "unknown"),
                    heal_result.get("error_category", "unknown"),
                    heal_result["success"],
                )
            heal_result["script"] = str(script_path)
            heal_result["diagnosis"] = diagnosis
            healed.append(heal_result)
        return healed

    def _evaluate(
        self,
        cases: List[Dict],
        chunks: List[Dict],
        healing_results: List[Dict],
    ) -> Dict:
        evaluator = Evaluator(str(GROUND_TRUTH_FILE))
        chunk_dicts = [c.to_dict() if hasattr(c, "to_dict") else c for c in chunks]
        return {
            "coverage": evaluator.requirement_coverage(cases),
            "hallucination": evaluator.hallucination_rate(cases, chunk_dicts),
            "healing": evaluator.healing_success_rate(healing_results),
        }

    def _save_result(self, run_id: str, result: Dict) -> Path:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        output_path = RESULTS_DIR / f"agent_pipeline_{run_id}.json"
        output_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return output_path
