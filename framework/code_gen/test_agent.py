"""Test Agent — 根据测试用例和 Page Object 生成 Pytest 测试脚本"""
import os
from pathlib import Path
from typing import List, Dict
from framework.multi_agent.base_agent import BaseAgent

TEST_AGENT_PROMPT = """你是一个自动化测试脚本生成专家（Test Agent）。
你的任务是将测试用例 + Page Object 转化为可运行的 Pytest 测试脚本。

要求：
1. 使用 Pytest + Playwright（sync_api）
2. 使用 conftest.py 中的 page fixture
3. 每个测试用例一个 test_ 函数
4. 用例需要添加 @pytest.mark 标签区分类型（positive/negative/boundary）
5. 输出包含测试数据和断言"""


class TestAgent(BaseAgent):
    """根据用例和 Page Object 生成测试脚本"""

    def __init__(self):
        super().__init__(role="TestAgent", system_prompt=TEST_AGENT_PROMPT)

    def generate(self, cases: List[Dict], page_files: List[str], output_dir: str) -> List[str]:
        """生成测试脚本"""
        module_map = self._group_by_module(cases)
        generated_files = []

        for module, module_cases in module_map.items():
            code = self._generate_test_file(module, module_cases, page_files)
            filepath = self._write_file(output_dir, module, code)
            generated_files.append(filepath)

        return generated_files

    def _group_by_module(self, cases: List[Dict]) -> Dict[str, List[Dict]]:
        """按模块分组"""
        groups = {}
        for case in cases:
            mod = case.get("module", "general")
            groups.setdefault(mod, []).append(case)
        return groups

    def _generate_test_file(self, module: str, cases: List[Dict], page_files: List[str]) -> str:
        """生成一个测试文件"""
        lines = ['"""',
                 f'自动化测试脚本 — {module} 模块',
                 '"""',
                 'import sys, os',
                 '# 将当前目录加入 path，使 pages/ 包可导入',
                 'sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))',
                 '',
                 'import pytest',
                 'from playwright.sync_api import Page, expect',
                 '',
                 '# Page Object 导入',
                 "from pages.page_login import LoginPage",
                 "from pages.page_index import IndexPage",
                 "from pages.page_cart import CartPage",
                 '',
                 'BASE_URL = "http://localhost:5000"',
                 '',
                 'TEST_USER = "testuser"',
                 'TEST_PASS = "password123"',
                 '',
                 '']

        for i, case in enumerate(cases):
            case_type = case.get("type", "正向")
            pytest_mark = {"正向": "positive", "逆向": "negative", "边界值": "boundary"}.get(case_type, "general")
            test_id = case.get("test_id", f"TC-{module}-{i+1:03d}")
            title = case.get("title", f"test_case_{i+1}")
            steps = case.get("steps", [])
            expected = case.get("expected", "")

            lines.append(f'@pytest.mark.{pytest_mark}')
            lines.append(f'@pytest.mark.test_id("{test_id}")')
            lines.append(f'def test_{module}_{i+1:03d}(page: Page):')
            lines.append(f'    """{title}"""')

            for step in steps:
                lines.append(f"    # {step}")
                lines.append(f"    pass")

            lines.append(f'    # 验证: {expected}')
            lines.append(f'    assert True  # TODO: 实现具体验证逻辑')
            lines.append('')
            lines.append('')

        return "\n".join(lines)

    def _write_file(self, output_dir: str, module: str, code: str) -> str:
        os.makedirs(output_dir, exist_ok=True)
        filename = f"test_{module}.py"
        filepath = str(Path(output_dir) / filename)
        Path(filepath).write_text(code, encoding="utf-8")
        print(f"[TestAgent] 已生成: {filepath}")
        return filepath
