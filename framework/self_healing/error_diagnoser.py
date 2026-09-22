"""错误诊断器 — 解析 Traceback 并分类错误类型"""
import re
from typing import Dict, List


class ErrorDiagnoser:
    """分析执行错误并分类"""

    ERROR_CATEGORIES = {
        "locator": ["ElementNotFound", "TimeoutError", "NoSuchElement",
                    "not found", "is not visible", "element not interactable",
                    "strict mode violation", "resolved to",
                    "waiting for locator", "Locator", "get_by_role", "aka"],
        "assertion": ["AssertionError", "assert", "assertion"],
        "timeout": ["timeout", "TimedOut", "Timeout"],
        "syntax": ["SyntaxError", "IndentationError", "NameError"],
        "attribute": ["AttributeError", "has no attribute"],
        "import": ["ModuleNotFoundError", "ImportError"],
    }

    def diagnose(self, exec_result: Dict) -> Dict:
        """诊断执行结果"""
        errors = []

        # 从 stderr 提取错误
        stderr = exec_result.get("stderr", "")
        stdout = exec_result.get("stdout", "")
        combined = stderr + "\n" + stdout

        if not combined.strip():
            return {"has_error": False, "category": "none",
                    "errors": [], "traceback": "", "suggestion": ""}

        # 提取 traceback
        traceback = self._extract_traceback(combined)

        # 分类错误
        category, matched_keyword = self._classify(combined)

        # 生成建议
        suggestion = self._suggest_fix(category, traceback)

        return {
            "has_error": not exec_result.get("success", True),
            "category": category,
            "matched_keyword": matched_keyword,
            "traceback": traceback,
            "errors": errors,
            "suggestion": suggestion,
        }

    def _extract_traceback(self, text: str) -> str:
        """提取 traceback 部分"""
        tb_match = re.search(r'(Traceback.*?)(?=\n\n|\Z)', text, re.DOTALL)
        return tb_match.group(1).strip() if tb_match else text[:500]

    def _classify(self, text: str) -> tuple:
        """分类错误类型"""
        for category, keywords in self.ERROR_CATEGORIES.items():
            for kw in keywords:
                if kw.lower() in text.lower():
                    return category, kw
        return "unknown", ""

    def _suggest_fix(self, category: str, traceback: str) -> str:
        """根据错误类型生成修复建议"""
        suggestions = {
            "locator": "元素定位器可能已失效，请检查页面元素选择器是否正确",
            "assertion": "断言条件可能与实际结果不符，请检查预期结果是否正确",
            "timeout": "页面加载或元素等待超时，建议增加等待时间或检查网络状态",
            "syntax": "代码存在语法错误，请检查代码格式",
            "attribute": "引用了不存在的属性或方法，请检查对象类型",
            "import": "缺少依赖包或导入路径错误",
            "unknown": "未知错误，请查看详细的错误信息",
        }
        base = suggestions.get(category, "请查看错误信息定位问题")
        return f"{base}\nTraceback:\n{traceback[:300]}"
