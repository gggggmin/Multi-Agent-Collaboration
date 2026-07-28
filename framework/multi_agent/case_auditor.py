"""Case Auditor Agent — 审计测试用例的一致性和完备性

基于 AutoGen 框架，从两个维度审查用例质量：
1. 一致性：检测"幻觉"——用例中包含需求中未提及的功能
2. 完备性：检查是否遗漏重要场景
LLM 不可用时使用规则检查降级。
"""
import json
from typing import List, Dict, Set
from .base_agent import BaseAgent

AUDITOR_SYSTEM_PROMPT = """你是一个严格的测试用例审计专家（Case Auditor）。
你的职责是审查测试工程师生成的用例，确保质量。

## 审查维度

### 1. 一致性（Consistency）
检查用例中的每个步骤和预期结果是否都能在原始需求中找到依据。
如果生成了需求中未提及的功能或行为，标记为"幻觉（Hallucination）"。
特别关注：
- 需求中不存在某个功能，但用例测试了它 → 幻觉
- 需求描述的行为和用例描述的不一致 → 不一致

### 2. 完备性（Completeness）
检查是否有遗漏的关键场景：
- 正向用例是否覆盖了所有主要功能？
- 逆向用例是否覆盖了常见错误场景？
- 边界值用例是否覆盖了空值、极限值、临界条件？

## 输出格式
严格输出 JSON：
```json
{
  "passed": true/false,
  "issues": [
    {
      "severity": "error/warning",
      "type": "hallucination/incomplete/inconsistent",
      "test_id": "TC-xxx-xxx",
      "description": "问题描述",
      "suggestion": "修改建议"
    }
  ],
  "summary": "总体评价（一句话）"
}
```

如果 passed 为 false，Creator 需要根据 issues 重新生成。"""


class CaseAuditor(BaseAgent):
    """测试用例审计智能体"""

    def __init__(self):
        super().__init__(role="CaseAuditor", system_prompt=AUDITOR_SYSTEM_PROMPT)

    def audit(self, cases: List[Dict], requirement_chunks: List[Dict]) -> Dict:
        """审计测试用例

        Args:
            cases: 生成的测试用例列表
            requirement_chunks: 原始需求片段

        Returns:
            审计结果: {"passed": bool, "issues": [...], "summary": str}
        """
        cases_text = json.dumps(cases, ensure_ascii=False, indent=2)
        req_text = self._format_requirements(requirement_chunks)

        prompt = f"""请审计以下测试用例。

## 原始需求
{req_text}

## 生成的测试用例
{cases_text}

请逐一检查每个用例的一致性和完备性。"""

        response = self.chat([{"role": "user", "content": prompt}])
        return self._parse_response(response, cases)

    def _format_requirements(self, chunks: List[Dict]) -> str:
        """格式化需求片段"""
        parts = []
        for i, chunk in enumerate(chunks, 1):
            meta = chunk.get("metadata", {})
            module = meta.get("module", "未知")
            func = meta.get("func_name", "未知")
            content = chunk.get("content", "")
            parts.append(f"[{i}] 模块={module}, 功能={func}\n{content}")
        return "\n\n".join(parts)

    def _parse_response(self, response: str, cases: List[Dict]) -> Dict:
        """解析审计结果"""
        if not response or response.startswith("__FALLBACK__"):
            return self._mock_audit(cases)

        try:
            start = response.index("{")
            end = response.rindex("}") + 1
            return json.loads(response[start:end])
        except (ValueError, json.JSONDecodeError):
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                return self._mock_audit(cases)

    def _mock_audit(self, cases: List[Dict]) -> Dict:
        """降级审计：基于规则的一致性/完备性检查"""
        issues = []
        for case in cases:
            tid = case.get("test_id", "unknown")
            steps = case.get("steps", [])
            expected = case.get("expected", "")
            case_type = case.get("type", "")

            if not steps:
                issues.append({
                    "severity": "error",
                    "type": "incomplete",
                    "test_id": tid,
                    "description": "用例缺少操作步骤",
                    "suggestion": "补充详细操作步骤",
                })

            if not expected:
                issues.append({
                    "severity": "error",
                    "type": "incomplete",
                    "test_id": tid,
                    "description": "用例缺少预期结果",
                    "suggestion": "补充预期结果",
                })

            if case_type == "边界值":
                title = case.get("title", "")
                if not any(kw in title for kw in ["空", "不", "无", "0", "超", "边界", "极限"]):
                    issues.append({
                        "severity": "warning",
                        "type": "incomplete",
                        "test_id": tid,
                        "description": f"边界值用例 '{title}' 未明确描述边界条件",
                        "suggestion": "在标题或前置条件中明确边界条件",
                    })

            # 检查 steps 中的占位符
            for step in steps:
                if "pass" in step.lower() and len(step) < 10:
                    issues.append({
                        "severity": "warning",
                        "type": "incomplete",
                        "test_id": tid,
                        "description": f"用例步骤'{step}'似乎是占位符，缺少具体操作",
                        "suggestion": "替换为具体的操作指令",
                    })

        passed = len([i for i in issues if i["severity"] == "error"]) == 0
        return {
            "passed": passed,
            "issues": issues,
            "summary": "审计通过" if passed else f"发现 {len(issues)} 个问题",
        }
