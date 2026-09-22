"""Page Agent — 根据测试用例生成 Page Object 页面类"""
import os
from pathlib import Path
from typing import List, Dict, Optional
from framework.multi_agent.base_agent import BaseAgent

PAGE_AGENT_PROMPT = """你是一个 Page Object Model 代码生成专家（Page Agent）。
你的任务是根据测试用例中的页面操作描述，生成 Playwright 风格的 Page Object 类。

要求：
1. 每个页面一个类，继承 BasePage
2. 使用有意义的元素定位器（优先 text=, css=, role=）
3. 封装高层次的业务方法（如 login(), search()）
4. 输出可直接运行的 Python 代码"""


class PageAgent(BaseAgent):
    """根据测试用例生成 Page Object 代码"""

    def __init__(self):
        super().__init__(role="PageAgent", system_prompt=PAGE_AGENT_PROMPT)

    def generate(self, cases: List[Dict], output_dir: str) -> List[str]:
        """生成 Page Object 文件"""
        pages = self._analyze_pages(cases)
        generated_files = []

        for page_name, page_info in pages.items():
            code = self._generate_page_code(page_name, page_info)
            filepath = self._write_file(output_dir, page_name, code)
            generated_files.append(filepath)

        return generated_files

    def _analyze_pages(self, cases: List[Dict]) -> Dict:
        """分析测试用例，提取页面元素和操作"""
        # 简单规则：根据模块名确定页面
        pages = {}
        pages["login"] = {
            "class_name": "LoginPage",
            "elements": {
                "username_input": "input[name='username']",
                "password_input": "input[name='password']",
                "login_button": "button[type='submit']",
                "error_flash": ".flash.error",
                "success_flash": ".flash.success",
            },
            "methods": [
                {"name": "login", "params": ["username: str", "password: str"],
                 "steps": ["self.navigate(\"/login\")",
                           "self.page.fill(self.USERNAME_INPUT, username)",
                           "self.page.fill(self.PASSWORD_INPUT, password)",
                           "self.page.click(self.LOGIN_BUTTON)",
                           "self.page.wait_for_load_state(\"networkidle\")"]},
                {"name": "get_error_message", "params": [],
                 "steps": ["return self.get_text(self.ERROR_FLASH)"]},
                {"name": "get_success_message", "params": [],
                 "steps": ["return self.get_text(self.SUCCESS_FLASH)"]},
            ]
        }
        pages["index"] = {
            "class_name": "IndexPage",
            "elements": {
                "search_input": "input[name='keyword']",
                "search_button": "button[type='submit']",
                "category_select": "select[name='category']",
                "cart_buttons": "form button:has-text('加入购物车')",
                "product_cards": ".card",
                "logout_link": "a:has-text('退出')",
            },
            "methods": [
                {"name": "search", "params": ["keyword: str = \"\""],
                 "steps": ["self.navigate(\"/\")",
                           "self.page.fill(self.SEARCH_INPUT, keyword)",
                           "self.page.click(self.SEARCH_BUTTON)",
                           "self.page.wait_for_load_state(\"networkidle\")"]},
                {"name": "filter_category", "params": ["category: str"],
                 "steps": ["self.navigate(\"/\")",
                           "self.page.select_option(self.CATEGORY_SELECT, category)",
                           "self.page.click(self.SEARCH_BUTTON)",
                           "self.page.wait_for_load_state(\"networkidle\")"]},
                {"name": "add_to_cart", "params": ["product_id: str"],
                 "steps": ["self.navigate(\"/\")",
                           "self.page.click(f\"form:has(input[name='product_id'][value='{product_id}']) button[type='submit']\")",
                           "self.page.wait_for_load_state(\"networkidle\")"]},
            ]
        }
        pages["cart"] = {
            "class_name": "CartPage",
            "elements": {
                "checkout_link": "a:has-text('去结算')",
                "delete_buttons": "button:has-text('删除')",
                "increase_buttons": "button:has-text('+')",
                "decrease_buttons": "button:has-text('−')",
                "empty_cart_text": "text=购物车是空的",
            },
            "methods": [
                {"name": "go_to_cart", "params": [],
                 "steps": ["self.navigate(\"/cart\")"]},
                {"name": "checkout", "params": [],
                 "steps": ["self.page.click(self.CHECKOUT_LINK)",
                           "self.page.wait_for_load_state(\"networkidle\")"]},
            ]
        }
        return pages

    def _generate_page_code(self, page_name: str, page_info: Dict) -> str:
        """生成 Page Object Python 代码"""
        lines = [f'"""Page Object — {page_info["class_name"]}"""',
                 'from framework.code_gen.templates.pom_base import BasePage',
                 '',
                 f'class {page_info["class_name"]}(BasePage):',
                 f'    """{page_info["class_name"]} 页面对象"""',
                 '']

        # 元素定位器常量
        lines.append("    # 元素定位器")
        for name, selector in page_info["elements"].items():
            lines.append(f'    {name.upper()} = "{selector}"')

        lines.append("")

        # 方法
        for method in page_info["methods"]:
            params_str = ", ".join(method["params"])
            lines.append(f'    def {method["name"]}(self, {params_str}):')
            for step in method["steps"]:
                lines.append(f"        {step}")
            lines.append("")

        return "\n".join(lines)

    def _write_file(self, output_dir: str, page_name: str, code: str) -> str:
        pages_dir = os.path.join(output_dir, "pages")
        os.makedirs(pages_dir, exist_ok=True)
        # 创建 __init__.py，使 pages/ 成为 Python 包
        init_file = os.path.join(pages_dir, "__init__.py")
        if not os.path.exists(init_file):
            Path(init_file).write_text(f'"""Page Objects 包"""\n', encoding="utf-8")
        filename = f"page_{page_name}.py"
        filepath = str(Path(pages_dir) / filename)
        Path(filepath).write_text(code, encoding="utf-8")
        print(f"[PageAgent] 已生成: {filepath}")
        return filepath
