"""评价指标计算 — 需求覆盖率、幻觉率、自愈成功率、RL 收敛指标"""
import json
import os
from pathlib import Path
from typing import List, Dict, Set, Tuple


class Evaluator:
    """实验评价器

    支持指标:
      - requirement_coverage: 需求覆盖率
      - hallucination_rate: 幻觉率
      - healing_success_rate: 自愈成功率
      - rl_convergence: RL 收敛指标
      - compare_ablation: 消融实验对比
    """

    def __init__(self, ground_truth_path: str):
        with open(ground_truth_path, "r", encoding="utf-8") as f:
            self.ground_truth = json.load(f)

    def requirement_coverage(self, generated_cases: List[Dict]) -> Dict:
        """计算需求覆盖率

        优先按 test_id 匹配，避免生成用例缺少 requirement 字段时被误判为 0 覆盖；
        若无 test_id，再退化为 requirement/title 文本匹配。
        """
        gt_by_id = {tc.get("test_id", ""): tc for tc in self.ground_truth}
        gt_requirements = {tc["requirement"] for tc in self.ground_truth}
        gen_ids = {tc.get("test_id", "") for tc in generated_cases if tc.get("test_id")}
        gen_requirements = {tc.get("requirement", "") for tc in generated_cases if tc.get("requirement")}
        gen_titles = {tc.get("title", "") for tc in generated_cases if tc.get("title")}

        covered_ids = set(gt_by_id.keys()) & gen_ids
        covered_reqs = gt_requirements & (gen_requirements | gen_titles)
        covered = covered_ids | {
            tc.get("test_id", "") for tc in self.ground_truth
            if tc.get("requirement") in covered_reqs
        }
        coverage = len(covered) / len(gt_by_id) * 100 if gt_by_id else 0

        missing = [
            tc.get("requirement", tc.get("test_id", ""))
            for tc in self.ground_truth
            if tc.get("test_id", "") not in covered
        ]

        return {
            "total_requirements": len(gt_by_id),
            "covered": len(covered),
            "coverage_pct": round(coverage, 2),
            "missing": missing,
        }

    def hallucination_rate(self, generated_cases: List[Dict],
                           requirement_chunks: List[Dict]) -> Dict:
        """计算幻觉率"""
        req_text = ""
        for chunk in requirement_chunks:
            content = (chunk.get("content", "") if isinstance(chunk, dict)
                       else getattr(chunk, "content", ""))
            req_text += content

        hallucinated = []
        valid = []

        for case in generated_cases:
            title = case.get("title", "")
            if not title:
                continue

            title_keywords = set(
                title.lower().replace("（", " ").replace("）", " ")
                    .replace("(", " ").replace(")", " ").split()
            )
            stop_words = {"的", "了", "在", "是", "我", "有", "和", "就",
                          "不", "人", "都", "一", "一个", "可以", "应该",
                          "需要", "进行", "通过", "到"}

            keywords = title_keywords - stop_words
            if len(keywords) < 2:
                expected = case.get("expected", "")
                if expected:
                    expected_kw = set(
                        expected.lower().replace("，", " ").replace("。", " ").split()
                    )
                    expected_kw -= stop_words
                    found = any(kw in req_text.lower() for kw in expected_kw)
                else:
                    found = False
            else:
                found = any(kw in req_text.lower() for kw in keywords)

            if found:
                valid.append(case)
            else:
                hallucinated.append(case)

        total = len(hallucinated) + len(valid)
        return {
            "total_cases": total,
            "hallucinated": len(hallucinated),
            "valid": len(valid),
            "hallucination_pct": round(
                len(hallucinated) / total * 100, 2
            ) if total else 0,
            "hallucinated_cases": [c.get("title", "") for c in hallucinated],
        }

    def healing_success_rate(self, healing_results: List[Dict]) -> Dict:
        """计算自愈成功率"""
        total = len(healing_results)
        successes = sum(1 for r in healing_results if r.get("success", False))
        return {
            "total_attempts": total,
            "successful": successes,
            "success_rate_pct": round(successes / total * 100, 2) if total else 0,
        }

    def rl_convergence(self, training_log_path: str) -> Dict:
        """分析 RL 训练日志中的收敛指标"""
        import re

        result = {
            "episodes": [],
            "avg_rewards": [],
            "converged": False,
            "convergence_episode": None,
            "summary": {},
        }

        try:
            with open(training_log_path, "r") as f:
                content = f.read()
        except (FileNotFoundError, json.JSONDecodeError):
            return result

        # 解析训练日志中的奖励变化
        reward_pattern = re.findall(r"ep_rew_mean[\s\|\|]+([\d\.\-\+e]+)", content)
        if reward_pattern:
            rewards = [float(r) for r in reward_pattern]
            result["avg_rewards"] = rewards
            result["episodes"] = list(range(1, len(rewards) + 1))

            # 判断收敛: 最后 20% 的奖励标准差小于阈值
            if len(rewards) > 5:
                recent = rewards[-max(len(rewards) // 5, 5):]
                std = __import__("numpy").std(recent) if len(recent) > 1 else float("inf")
                mean = sum(recent) / len(recent)
                result["converged"] = std < mean * 0.1 if mean != 0 else False
                result["convergence_threshold"] = mean * 0.1
                result["recent_std"] = round(std, 4)
                result["final_avg_reward"] = round(mean, 4)

            result["summary"] = {
                "total_episodes": len(rewards),
                "initial_reward": round(rewards[0], 4) if rewards else None,
                "final_reward": round(rewards[-1], 4) if rewards else None,
                "improvement": round(rewards[-1] - rewards[0], 4) if len(rewards) > 1 else None,
                "converged": result["converged"],
            }

        return result

    def compare_strategies(self, fixed_results: Dict, rl_results: Dict) -> Dict:
        """比较固定轮次 vs RL-AGS 策略"""
        return {
            "comparison": "固定轮次 vs RL-AGS",
            "fixed_iterations": fixed_results.get("total_iterations", 0),
            "rl_iterations": rl_results.get("total_iterations", 0),
            "iteration_reduction": max(0, fixed_results.get("total_iterations", 0)
                                       - rl_results.get("total_iterations", 0)),
            "fixed_coverage": fixed_results.get("coverage_pct", 0),
            "rl_coverage": rl_results.get("coverage_pct", 0),
            "fixed_hallucination": fixed_results.get("hallucination_pct", 0),
            "rl_hallucination": rl_results.get("hallucination_pct", 0),
            "improvement": {
                "coverage_change": round(
                    rl_results.get("coverage_pct", 0) - fixed_results.get("coverage_pct", 0), 2
                ),
                "hallucination_reduction": round(
                    fixed_results.get("hallucination_pct", 0) - rl_results.get("hallucination_pct", 0), 2
                ),
                "iteration_efficiency": f"减少 {max(0, fixed_results.get('total_iterations', 0) - rl_results.get('total_iterations', 0))} 轮",
            },
        }

    def compare_ablation(self, with_auditor: Dict, without_auditor: Dict,
                         label_a: str = "with_auditor",
                         label_b: str = "without_auditor") -> Dict:
        """消融实验对比"""
        return {
            "comparison": f"{label_a} vs {label_b}",
            label_a: {
                "coverage_pct": with_auditor.get("coverage_pct", 0),
                "hallucination_pct": with_auditor.get("hallucination_pct", 0),
            },
            label_b: {
                "coverage_pct": without_auditor.get("coverage_pct", 0),
                "hallucination_pct": without_auditor.get("hallucination_pct", 0),
            },
            "improvement": {
                "coverage_improvement": round(
                    with_auditor.get("coverage_pct", 0) - without_auditor.get("coverage_pct", 0), 2
                ),
                "hallucination_reduction": round(
                    without_auditor.get("hallucination_pct", 0) - with_auditor.get("hallucination_pct", 0), 2
                ),
            },
        }

    def print_report(self, results: Dict) -> None:
        """打印综合实验报告"""
        print("\n" + "=" * 60)
        print("  实验评价报告")
        print("=" * 60)

        cov = results.get("coverage", {})
        print(f"\n[覆盖率] 需求覆盖率: {cov.get('coverage_pct', 'N/A')}%")
        print(f"   (覆盖 {cov.get('covered', 0)}/{cov.get('total_requirements', 0)} 个需求)")

        hal = results.get("hallucination", {})
        print(f"\n[幻觉率] 幻觉率: {hal.get('hallucination_pct', 'N/A')}%")
        print(f"   (幻觉 {hal.get('hallucinated', 0)}/{hal.get('total_cases', 0)} 个用例)")

        heal = results.get("healing", {})
        print(f"\n[自愈率] 自愈成功率: {heal.get('success_rate_pct', 'N/A')}%")
        print(f"   (成功 {heal.get('successful', 0)}/{heal.get('total_attempts', 0)} 次)")

        # RL 对比
        rl_cmp = results.get("rl_comparison", {})
        if rl_cmp:
            print(f"\n[RL对比] {rl_cmp.get('comparison', '')}")
            print(f"  固定轮次迭代: {rl_cmp.get('fixed_iterations', 'N/A')} 轮")
            print(f"  RL-AGS 迭代: {rl_cmp.get('rl_iterations', 'N/A')} 轮")
            print(f"  迭代减少: {rl_cmp.get('iteration_reduction', 'N/A')} 轮")

        # 消融实验
        abl = results.get("ablation", {})
        if abl:
            print(f"\n[消融实验] 有 Auditor 覆盖率: {abl.get('with_auditor', {}).get('coverage_pct', 'N/A')}%")
            print(f"   无 Auditor 覆盖率: {abl.get('without_auditor', {}).get('coverage_pct', 'N/A')}%")
            print(f"   幻觉率降幅: {abl.get('improvement', {}).get('hallucination_reduction', 'N/A')}%")

        print("\n" + "=" * 60)
