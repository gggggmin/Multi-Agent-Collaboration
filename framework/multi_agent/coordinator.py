"""协调器 — 多智能体博弈 + RL 自适应终止

整合 AutoGen GroupChat 管理 Creator-Auditor 对话，
同时集成 RL-AGS（Adaptive Game Stopping）智能决策博弈终止。

工作流程:
  1. Creator 生成测试用例
  2. Auditor 审计用例
  3. RL-AGS 评估当前状态，决定继续迭代还是接受输出
  4. 如果继续，携带审计反馈重新生成
  5. 如果接受，输出最终用例集
"""
import json
from typing import List, Dict, Optional
from .case_creator import CaseCreator
from .case_auditor import CaseAuditor
from config import MAX_ITERATIONS


class Coordinator:
    """多智能体博弈协调器

    支持两种模式:
      - RL 模式（默认）: 使用 RL-AGS 模块动态决策终止
      - 固定轮次模式: 兼容原有逻辑，固定迭代 MAX_ITERATIONS 轮
    """

    def __init__(self, use_rl: bool = True):
        """
        Args:
            use_rl: 是否启用 RL-AGS 决策。默认为 True
        """
        self.creator = CaseCreator()
        self.auditor = CaseAuditor()
        self.history: List[Dict] = []
        self.use_rl = use_rl
        self._ags_env = None
        self._ags_model = None

    @property
    def ags_available(self) -> bool:
        """RL-AGS 是否可用"""
        if not self.use_rl:
            return False
        try:
            from framework.rl import AGSTrainer
            return True
        except ImportError:
            return False

    def run(self, requirement_chunks: List[Dict], module: str = "") -> Dict:
        """执行博弈流程

        Args:
            requirement_chunks: 需求片段列表
            module: 模块名

        Returns:
            博弈结果
        """
        iteration = 0
        current_cases = []
        audit_result = {"passed": False, "issues": []}
        max_iter = MAX_ITERATIONS

        # RL-AGS: 延迟加载训练器
        ags_trainer = self._init_ags() if self.use_rl else None

        while iteration < MAX_ITERATIONS:
            iteration += 1
            print(f"\n{'='*40}")
            print(f"[博弈] 第 {iteration}/{MAX_ITERATIONS} 轮")
            print(f"{'='*40}")

            # Creator 生成或重新生成
            if iteration == 1:
                current_cases = self.creator.generate(requirement_chunks, module)
            else:
                current_cases = self._regenerate(
                    current_cases, requirement_chunks,
                    audit_result.get("issues", [])
                )

            # Auditor 审计
            audit_result = self.auditor.audit(current_cases, requirement_chunks)
            passed = audit_result.get("passed", False)

            # 计算覆盖率估计（基于审计通过的用例比例）
            coverage_estimate = self._estimate_coverage(
                current_cases, audit_result
            )

            # 记录历史
            self.history.append({
                "iteration": iteration,
                "cases": current_cases,
                "audit_result": audit_result,
                "coverage_estimate": coverage_estimate,
            })

            print(f"[博弈] 审计结论: {'通过' if passed else '不通过'}")
            if audit_result.get("issues"):
                for issue in audit_result["issues"][:3]:
                    print(f"   - [{issue['severity']}] {issue['description']}")

            # RL-AGS 决策: 是否终止？
            should_stop = self._decide_stop(
                ags_trainer, iteration, audit_result, coverage_estimate
            )

            if passed or should_stop:
                reason = "审计通过" if passed else "RL 决策终止"
                print(f"[博弈] 第 {iteration} 轮结束: {reason}")
                break

        return {
            "module": module,
            "total_iterations": iteration,
            "passed": audit_result.get("passed", False),
            "cases": current_cases,
            "audit_summary": audit_result.get("summary", ""),
            "history": self.history,
            "use_rl": self.use_rl,
        }

    def _init_ags(self):
        """初始化 RL-AGS"""
        try:
            from framework.rl import AGSTrainer
            trainer = AGSTrainer()
            trainer.load()
            return trainer
        except Exception as e:
            print(f"[Coordinator] RL-AGS 加载失败: {e}，使用固定轮次逻辑")
            return None

    def _decide_stop(self, ags_trainer, iteration: int,
                     audit_result: Dict, coverage: float) -> bool:
        """使用 RL-AGS 判断是否应该终止"""
        if ags_trainer is None:
            return False

        blocking_errors = [
            issue for issue in audit_result.get("issues", [])
            if issue.get("severity") == "error"
        ]
        if blocking_errors:
            return False

        has_hallucination = any(
            i.get("type") == "hallucination"
            for i in audit_result.get("issues", [])
        )

        try:
            state = {
                "current_iteration": iteration,
                "max_iterations": MAX_ITERATIONS,
                "num_issues": len(audit_result.get("issues", [])),
                "num_cases": 0,
                "coverage_estimate": coverage,
                "has_hallucination": has_hallucination,
            }
            action = ags_trainer.predict(state)
            return action == 1  # 1 = 接受输出并停止
        except Exception as e:
            print(f"[Coordinator] RL-AGS 决策失败: {e}")
            return False

    def _estimate_coverage(self, cases: List[Dict], audit_result: Dict) -> float:
        """粗略估计覆盖率"""
        if not cases:
            return 0.0
        num_issues = len(audit_result.get("issues", []))
        # 问题越少，覆盖率估计越高
        issue_penalty = min(num_issues / max(len(cases), 1), 1.0)
        return max(0.0, 1.0 - issue_penalty * 0.5)

    def _regenerate(self, old_cases: List[Dict], requirement_chunks: List[Dict],
                    issues: List[Dict]) -> List[Dict]:
        """根据审计反馈重新生成用例"""
        req_text = "\n\n".join(c.get("content", "") for c in requirement_chunks)
        issues_text = json.dumps(issues, ensure_ascii=False, indent=2)
        old_text = json.dumps(old_cases, ensure_ascii=False, indent=2)

        prompt = f"""根据以下审计反馈，重新生成测试用例。

## 原始需求
{req_text}

## 上一轮生成的用例
{old_text}

## 审计问题
{issues_text}

请根据审计意见修正所有问题，重新生成完整的测试用例集。"""

        response = self.creator.chat([{"role": "user", "content": prompt}])

        try:
            start = response.index("[")
            end = response.rindex("]") + 1
            return json.loads(response[start:end])
        except (ValueError, json.JSONDecodeError):
            return old_cases

    def print_summary(self, result: Dict) -> None:
        """打印博弈结果摘要"""
        print(f"\n{'='*50}")
        print(f"  博弈结果")
        print(f"{'='*50}")
        print(f"  模块: {result['module']}")
        print(f"  迭代次数: {result['total_iterations']}")
        print(f"  最终状态: {'通过' if result['passed'] else '未完全通过'}")
        print(f"  生成用例数: {len(result['cases'])}")
        print(f"  决策模式: {'RL-AGS' if result.get('use_rl') else '固定轮次'}")
        print(f"  审计摘要: {result['audit_summary']}")
        print("-" * 50)
