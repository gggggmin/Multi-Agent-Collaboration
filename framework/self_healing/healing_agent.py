"""自愈 Agent — 根据执行反馈修复测试脚本

集成 RL-HSS (Multi-Armed Bandit) 选择最佳修复策略，
避免每次都调用 LLM 重写，降低修复成本。

策略池:
  - llm_rewrite:    调 LLM 重写代码（通用但成本高）
  - rule_locator:   规则替换元素定位器（低成本）
  - rule_timeout:   增加超时等待（低成本）
  - fallback:       回退到上一个可用版本（保底）
"""
from typing import Dict, Optional
from framework.multi_agent.base_agent import BaseAgent

HEALING_PROMPT = """你是一个测试脚本自愈专家（Self-Healing Agent）。
你的任务是根据执行错误反馈，修复测试脚本。

## 要求
1. 分析 Traceback 定位根因
2. 给出修正后的完整代码
3. 只修改有问题的地方，保持其他代码不变
4. 输出格式：
```python
# 修复后的完整代码
```"""


class HealingAgent(BaseAgent):
    """自愈智能体（集成 RL-HSS Bandit 策略选择）"""

    def __init__(self):
        super().__init__(role="HealingAgent", system_prompt=HEALING_PROMPT)
        self._bandit = None

    @property
    def bandit(self):
        """延迟加载 HSS Bandit"""
        if self._bandit is None:
            try:
                from framework.rl import HSSBandit
                self._bandit = HSSBandit()
                # 尝试加载已保存的模型
                try:
                    from config import RESULTS_DIR
                    path = str(RESULTS_DIR / "hss_bandit.json")
                    import os
                    if os.path.exists(path):
                        self._bandit.load(path)
                except Exception:
                    pass
            except ImportError:
                self._bandit = None
        return self._bandit

    def heal(self, script_content: str, diagnosis: Dict,
             max_attempts: int = 3) -> Dict:
        """修复测试脚本

        使用 RL-HSS Bandit 选择策略:
          1. 获取错误分类
          2. Bandit 选择最佳策略
          3. 执行策略
          4. 反馈结果更新 Bandit

        Args:
            script_content: 原始脚本内容
            diagnosis: 错误诊断结果
            max_attempts: 最大尝试次数

        Returns:
            修复结果
        """
        error_category = diagnosis.get("category", "unknown")
        attempt = 0
        current_code = script_content
        history = []

        # RL-HSS: 选择修复策略
        strategy = self._select_strategy(error_category, diagnosis)
        print(f"[自愈] 选择策略: {strategy} (错误类型: {error_category})")

        while attempt < max_attempts:
            attempt += 1
            print(f"\n[自愈] 第 {attempt}/{max_attempts} 次修复尝试 (策略: {strategy})")

            # 执行修复
            fixed_code = self._execute_strategy(
                strategy, current_code, diagnosis, history
            )

            if fixed_code:
                history.append({
                    "attempt": attempt,
                    "strategy": strategy,
                    "previous_code": current_code,
                    "fixed_code": fixed_code,
                    "diagnosis": diagnosis,
                })

                return {
                    "success": True,
                    "attempts": attempt,
                    "strategy": strategy,
                    "error_category": error_category,
                    "fixed_code": fixed_code,
                    "history": history,
                }
            else:
                # 当前策略失败，记录负面反馈
                if self.bandit:
                    self.bandit.update(strategy, error_category, False)

                # 切换到下一个策略
                strategy = self._fallback_strategy(strategy)
                print(f"[自愈] 策略失败，切换至: {strategy}")

        return {
            "success": False,
            "attempts": attempt,
            "strategy": strategy,
            "error_category": error_category,
            "fixed_code": current_code,
            "history": history,
        }

    def record_strategy_result(self, strategy: str, error_category: str,
                               success: bool) -> None:
        """在外部验证完成后反馈策略效果。"""
        if self.bandit:
            self.bandit.update(strategy, error_category, success)
            self.bandit.save()

    def _select_strategy(self, error_category: str, diagnosis: Dict) -> str:
        """选择修复策略"""
        diagnosis_text = "\n".join([
            str(diagnosis.get("traceback", "")),
            str(diagnosis.get("suggestion", "")),
            str(diagnosis.get("matched_keyword", "")),
        ]).lower()
        if error_category == "locator" or "strict mode violation" in diagnosis_text:
            return "rule_locator"
        if error_category == "timeout":
            return "rule_timeout"

        if self.bandit:
            return self.bandit.select_strategy(error_category)

        # 无 Bandit 时的规则策略选择
        strategy_map = {
            "locator": "rule_locator",
            "timeout": "rule_timeout",
            "syntax": "llm_rewrite",
            "assertion": "llm_rewrite",
            "attribute": "llm_rewrite",
            "import": "llm_rewrite",
        }
        return strategy_map.get(error_category, "llm_rewrite")

    def _execute_strategy(self, strategy: str, code: str,
                          diagnosis: Dict, history: list) -> Optional[str]:
        """执行指定修复策略"""
        if strategy == "llm_rewrite":
            return self._fix_via_llm(code, diagnosis, history)
        elif strategy == "rule_locator":
            return self._fix_via_rule_locator(code, diagnosis)
        elif strategy == "rule_timeout":
            return self._fix_via_rule_timeout(code)
        elif strategy == "fallback":
            return self._fix_via_fallback(code)
        return None

    def _fix_via_llm(self, code: str, diagnosis: Dict, history: list) -> Optional[str]:
        """策略1: 调 LLM 重写（默认方案）"""
        prompt = self._build_prompt(code, diagnosis, history)
        response = self.chat([{"role": "user", "content": prompt}])
        return self._extract_code(response)

    def _fix_via_rule_locator(self, code: str, diagnosis: Optional[Dict] = None) -> Optional[str]:
        """策略2: 规则替换元素定位器

        处理常见的定位器失效场景:
          - text= → text= 精确匹配
          - 添加 wait_for_selector
          - 添加重试逻辑
        """
        import re
        diagnosis_text = ""
        if diagnosis:
            diagnosis_text = "\n".join([
                str(diagnosis.get("traceback", "")),
                str(diagnosis.get("suggestion", "")),
            ]).lower()

        replacements = {
            'page.locator("button[type=\'submit\']").click()':
                'page.get_by_role("button", name="搜索").click()',
            'page.locator(\'button[type="submit"]\').click()':
                'page.get_by_role("button", name="搜索").click()',
            'page.click("button[type=\'submit\']")':
                'page.get_by_role("button", name="搜索").click()',
            'self.page.click(self.SEARCH_BUTTON)':
                'self.page.get_by_role("button", name="搜索").click()',
        }

        fixed_code = code
        for before, after in replacements.items():
            fixed_code = fixed_code.replace(before, after)
        if fixed_code != code:
            return fixed_code

        lines = code.split("\n")
        fixed = []
        changed = False

        for line in lines:
            # 替换 click 为带等待的 click
            if ".click(" in line and "wait_for_selector" not in code:
                indent = " " * (len(line) - len(line.lstrip()))
                selector_match = re.search(r'\.click\(([^)]+)\)', line)
                if selector_match:
                    selector = selector_match.group(1)
                    fixed.append(f"{indent}self.page.wait_for_selector({selector}, timeout=5000)")
                    fixed.append(line)
                    changed = True
                    continue
            fixed.append(line)

        if changed:
            return "\n".join(fixed)
        return None

    def _fix_via_rule_timeout(self, code: str) -> Optional[str]:
        """策略3: 增加超时等待

        在关键操作前添加等待，解决页面加载超时问题。
        """
        import re
        lines = code.split("\n")
        fixed = []
        changed = False

        for line in lines:
            stripped = line.strip()
            # 在导航后添加等待
            if "goto(" in stripped or "navigate(" in stripped:
                indent = " " * (len(line) - len(line.lstrip()))
                fixed.append(line)
                fixed.append(f"{indent}self.page.wait_for_load_state(\"networkidle\", timeout=10000)")
                changed = True
            else:
                fixed.append(line)

        if changed:
            return "\n".join(fixed)
        return None

    def _fix_via_fallback(self, code: str) -> Optional[str]:
        """策略4: 回退（返回 None 表示无法修复）"""
        print("[自愈] 所有策略均失败，需要人工干预")
        return None

    def _fallback_strategy(self, current: str) -> str:
        """策略降级顺序"""
        order = ["llm_rewrite", "rule_locator", "rule_timeout", "fallback"]
        try:
            idx = order.index(current)
            return order[idx + 1] if idx + 1 < len(order) else "fallback"
        except ValueError:
            return "llm_rewrite"

    def _build_prompt(self, code: str, diagnosis: Dict, history: list) -> str:
        """构造修复 Prompt"""
        parts = [
            "## 需要修复的代码",
            f"```python\n{code}\n```",
            "",
            "## 错误诊断",
            f"错误类型: {diagnosis.get('category', 'unknown')}",
            f"Traceback:\n{diagnosis.get('traceback', '')}",
            f"建议: {diagnosis.get('suggestion', '')}",
        ]

        if history:
            parts.append("\n## 之前的修复尝试（失败）")
            for h in history:
                parts.append(f"第 {h['attempt']} 次 ({h.get('strategy', '?')}): 仍存在问题")

        return "\n".join(parts)

    def _extract_code(self, response: str) -> Optional[str]:
        """从 LLM 响应中提取 Python 代码"""
        if not response or response.startswith("__FALLBACK__"):
            return None
        import re
        code_match = re.search(r'```python\n(.*?)\n```', response, re.DOTALL)
        if code_match:
            return code_match.group(1).strip()
        # 如果不是代码块格式，直接返回响应
        if response and len(response) > 50:
            return response.strip()
        return None
