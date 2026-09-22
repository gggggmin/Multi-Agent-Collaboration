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
        self._write_conftest(output_dir)

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
                 '# 将 output/ 与项目根目录加入 path，使 pages/ 和 framework/ 均可导入',
                 'CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))',
                 'PROJECT_ROOT = os.path.dirname(CURRENT_DIR)',
                 'sys.path.insert(0, CURRENT_DIR)',
                 'sys.path.insert(0, PROJECT_ROOT)',
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
                 '',
                 'def _assert_text(page: Page, text: str):',
                 '    expect(page.locator("body")).to_contain_text(text)',
                 '',
                 '',
                 'def _login(page: Page):',
                 '    login_page = LoginPage(page)',
                 '    login_page.login(TEST_USER, TEST_PASS)',
                 '    _assert_text(page, "欢迎回来")',
                 '',
                 '',
                 'def _add_product(page: Page, product_id: str = "p001"):',
                 '    index_page = IndexPage(page)',
                 '    index_page.add_to_cart(product_id)',
                 '    _assert_text(page, "加入购物车")',
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
            body = self._render_case_body(module, title, steps, expected, case_type)
            lines.extend(body)
            lines.append('')
            lines.append('')

        return "\n".join(lines)

    def _render_case_body(
        self,
        module: str,
        title: str,
        steps: List[str],
        expected: str,
        case_type: str = "",
    ) -> List[str]:
        """Render executable Playwright code for the supported demo app modules."""
        title_text = title.lower()
        expected_text = expected.lower()
        module = (module or "").lower()

        if module == "login":
            return self._render_login_case(title_text, expected_text, case_type)
        if module == "search":
            return self._render_search_case(title_text)
        if module == "cart":
            return self._render_cart_case(title_text)
        if module == "checkout":
            return self._render_checkout_case(title_text)

        return self._render_generic_case(steps, expected)

    def _render_login_case(self, title: str, expected: str = "", case_type: str = "") -> List[str]:
        if "登出" in title and "访问结算" not in title:
            return [
                "    _login(page)",
                '    page.locator("a:has-text(\'退出\')").click()',
                '    expect(page).to_have_url(f"{BASE_URL}/")',
                '    _assert_text(page, "已安全退出")',
                '    _assert_text(page, "登录")',
            ]
        if "登出后访问结算" in title:
            return [
                "    _login(page)",
                '    page.locator("a:has-text(\'退出\')").click()',
                "    page.goto(f'{BASE_URL}/checkout')",
                '    expect(page).to_have_url(f"{BASE_URL}/login")',
                '    _assert_text(page, "请先登录后再下单")',
            ]
        if "管理员" in title:
            return [
                "    login_page = LoginPage(page)",
                '    login_page.login("admin", "admin123")',
                '    expect(page).to_have_url(f"{BASE_URL}/")',
                '    _assert_text(page, "欢迎回来")',
                '    _assert_text(page, "admin")',
            ]
        if "登录页初始展示" in title:
            return [
                "    page.goto(f'{BASE_URL}/login')",
                '    expect(page.locator("input[name=\'username\']")).to_be_visible()',
                '    expect(page.locator("input[name=\'password\']")).to_be_visible()',
                '    expect(page.locator("button[type=\'submit\']")).to_be_visible()',
            ]
        if "必填字段" in title:
            return [
                "    page.goto(f'{BASE_URL}/login')",
                '    expect(page.locator("input[name=\'username\']")).to_have_attribute("required", "")',
                '    expect(page.locator("input[name=\'password\']")).to_have_attribute("required", "")',
            ]
        if "未登录访问结算" in title:
            return [
                "    page.goto(f'{BASE_URL}/checkout')",
                '    expect(page).to_have_url(f"{BASE_URL}/login")',
                '    _assert_text(page, "请先登录后再下单")',
            ]
        if "未登录访问购物车" in title:
            return [
                "    page.goto(f'{BASE_URL}/cart')",
                '    _assert_text(page, "购物车是空的")',
            ]
        if "保持会话" in title:
            return [
                "    _login(page)",
                "    page.goto(f'{BASE_URL}/')",
                '    _assert_text(page, TEST_USER)',
                "    page.goto(f'{BASE_URL}/cart')",
                '    _assert_text(page, TEST_USER)',
            ]
        if "重复登录" in title:
            return [
                "    _login(page)",
                "    page.goto(f'{BASE_URL}/login')",
                '    _assert_text(page, "用户登录")',
            ]
        is_positive_login = (
            ("正确" in title or "成功" in title or "正向" in title)
            or ("登录成功" in expected)
            or (case_type == "正向" and "登录" in title)
        )
        if is_positive_login:
            return [
                "    login_page = LoginPage(page)",
                "    login_page.login(TEST_USER, TEST_PASS)",
                '    expect(page).to_have_url(f"{BASE_URL}/")',
                '    _assert_text(page, "欢迎回来")',
                '    _assert_text(page, TEST_USER)',
            ]
        if "错误密码" in title:
            return [
                "    login_page = LoginPage(page)",
                '    login_page.login(TEST_USER, "wrong-password")',
                '    expect(page).to_have_url(f"{BASE_URL}/login")',
                '    _assert_text(page, "用户名或密码错误")',
            ]
        if "空用户名和空密码" in title:
            return [
                "    page.goto(f'{BASE_URL}/login')",
                '    page.locator("input[name=\'username\']").evaluate("el => el.removeAttribute(\'required\')")',
                '    page.locator("input[name=\'password\']").evaluate("el => el.removeAttribute(\'required\')")',
                '    page.locator("input[name=\'password\']").fill("")',
                '    page.locator("button[type=\'submit\']").click()',
                '    _assert_text(page, "用户名和密码不能为空")',
            ]
        if "空用户名" in title:
            return [
                "    page.goto(f'{BASE_URL}/login')",
                '    page.locator("input[name=\'username\']").evaluate("el => el.removeAttribute(\'required\')")',
                '    page.locator("input[name=\'password\']").fill(TEST_PASS)',
                '    page.locator("button[type=\'submit\']").click()',
                '    _assert_text(page, "用户名和密码不能为空")',
            ]
        if "空密码" in title:
            return [
                "    page.goto(f'{BASE_URL}/login')",
                '    page.locator("input[name=\'password\']").evaluate("el => el.removeAttribute(\'required\')")',
                '    page.locator("input[name=\'username\']").fill(TEST_USER)',
                '    page.locator("button[type=\'submit\']").click()',
                '    _assert_text(page, "用户名和密码不能为空")',
            ]
        return [
            "    login_page = LoginPage(page)",
            '    login_page.login("missing-user", "whatever")',
            '    expect(page).to_have_url(f"{BASE_URL}/login")',
            '    _assert_text(page, "用户名或密码错误")',
        ]

    def _render_search_case(self, title: str) -> List[str]:
        if "无结果" in title:
            return [
                "    index_page = IndexPage(page)",
                '    index_page.search("不存在的商品xyz")',
                '    _assert_text(page, "没有找到匹配的商品")',
            ]
        if "apple" in title:
            return [
                "    index_page = IndexPage(page)",
                '    index_page.search("Apple")',
                '    _assert_text(page, "Apple MacBook Air M3")',
            ]
        if "小米" in title:
            return [
                "    index_page = IndexPage(page)",
                '    index_page.search("小米")',
                '    _assert_text(page, "小米14 Ultra")',
            ]
        if "samsung" in title:
            return [
                "    index_page = IndexPage(page)",
                '    index_page.search("Samsung")',
                '    _assert_text(page, "Samsung Galaxy S25")',
            ]
        if "sony" in title:
            return [
                "    index_page = IndexPage(page)",
                '    index_page.search("Sony")',
                '    _assert_text(page, "Sony WH-1000XM6")',
            ]
        if "airpods" in title:
            return [
                "    index_page = IndexPage(page)",
                '    index_page.search("AirPods")',
                '    _assert_text(page, "AirPods Pro 3")',
                '    _assert_text(page, "无货")',
            ]
        if "不匹配" in title:
            return [
                "    page.goto(f'{BASE_URL}/')",
                '    page.locator("input[name=\'keyword\']").fill("Apple")',
                '    page.locator("select[name=\'category\']").select_option("手机")',
                '    page.get_by_role("button", name="搜索").click()',
                '    _assert_text(page, "没有找到匹配的商品")',
            ]
        if "保留关键词" in title:
            return [
                "    index_page = IndexPage(page)",
                '    index_page.search("华为")',
                '    expect(page.locator("input[name=\'keyword\']")).to_have_value("华为")',
            ]
        if "全部分类" in title:
            return [
                "    index_page = IndexPage(page)",
                '    index_page.filter_category("全部")',
                '    expect(page.locator(".card")).to_have_count(8)',
            ]
        if "大小写" in title or "iphone" in title:
            return [
                "    index_page = IndexPage(page)",
                '    index_page.search("iphone")',
                '    _assert_text(page, "iPhone 16 Pro")',
            ]
        if "空" in title:
            return [
                "    index_page = IndexPage(page)",
                '    index_page.search("")',
                '    _assert_text(page, "华为MateBook X Pro")',
                '    _assert_text(page, "iPhone 16 Pro")',
                '    expect(page.locator(".card")).to_have_count(8)',
            ]
        if "分类" in title and "手机" in title:
            return [
                "    index_page = IndexPage(page)",
                '    index_page.filter_category("手机")',
                '    _assert_text(page, "iPhone 16 Pro")',
                '    _assert_text(page, "小米14 Ultra")',
                '    expect(page.locator("body")).not_to_contain_text("华为MateBook X Pro")',
            ]
        if "分类" in title and "笔记本" in title:
            return [
                "    index_page = IndexPage(page)",
                '    index_page.filter_category("笔记本")',
                '    _assert_text(page, "华为MateBook X Pro")',
                '    _assert_text(page, "Apple MacBook Air M3")',
                '    expect(page.locator("body")).not_to_contain_text("iPhone 16 Pro")',
            ]
        if "分类" in title and "耳机" in title:
            return [
                "    index_page = IndexPage(page)",
                '    index_page.filter_category("耳机")',
                '    _assert_text(page, "Sony WH-1000XM6")',
                '    _assert_text(page, "AirPods Pro 3")',
                '    _assert_text(page, "无货")',
            ]
        if "组合" in title:
            return [
                "    page.goto(f'{BASE_URL}/')",
                '    page.locator("input[name=\'keyword\']").fill("Apple")',
                '    page.locator("select[name=\'category\']").select_option("笔记本")',
                '    page.get_by_role("button", name="搜索").click()',
                '    _assert_text(page, "Apple MacBook Air M3")',
                '    expect(page.locator("body")).not_to_contain_text("iPhone 16 Pro")',
            ]
        if "无货" in title:
            return [
                "    index_page = IndexPage(page)",
                '    index_page.search("ThinkPad")',
                '    _assert_text(page, "ThinkPad X1 Carbon")',
                '    _assert_text(page, "无货")',
            ]
        return [
            "    index_page = IndexPage(page)",
            '    index_page.search("华为")',
            '    _assert_text(page, "华为MateBook X Pro")',
            '    expect(page.locator("body")).not_to_contain_text("Apple MacBook Air M3")',
        ]

    def _render_cart_case(self, title: str) -> List[str]:
        if "多种" in title:
            return [
                '    _add_product(page, "p001")',
                "    page.goto(f'{BASE_URL}/')",
                '    _add_product(page, "p004")',
                '    _assert_text(page, "华为MateBook X Pro")',
                '    _assert_text(page, "iPhone 16 Pro")',
            ]
        if "连续增加" in title:
            return [
                '    _add_product(page, "p001")',
                '    page.locator("button:has-text(\'+\')").click()',
                '    page.locator("button:has-text(\'+\')").click()',
                '    expect(page.locator("text=3")).to_be_visible()',
            ]
        if "仍保留" in title:
            return [
                '    _add_product(page, "p001")',
                '    page.locator("button:has-text(\'+\')").click()',
                '    page.locator("button:has-text(\'−\')").click()',
                '    expect(page.locator("text=1")).to_be_visible()',
                '    _assert_text(page, "华为MateBook X Pro")',
            ]
        if "多商品" in title:
            return [
                '    _add_product(page, "p001")',
                "    page.goto(f'{BASE_URL}/')",
                '    _add_product(page, "p004")',
                '    page.locator("form:has(input[name=\'product_id\'][value=\'p001\']) button:has-text(\'删除\')").click()',
                '    expect(page.locator("body")).not_to_contain_text("华为MateBook X Pro")',
                '    _assert_text(page, "iPhone 16 Pro")',
            ]
        if "合计" in title:
            return [
                '    _add_product(page, "p001")',
                '    _assert_text(page, "合计")',
                '    _assert_text(page, "¥8999.00")',
            ]
        if "单价" in title:
            return [
                '    _add_product(page, "p001")',
                '    _assert_text(page, "¥8999.00")',
            ]
        if "数量展示" in title:
            return [
                '    _add_product(page, "p001")',
                '    expect(page.locator("text=1")).to_be_visible()',
            ]
        if "去逛逛" in title:
            return [
                "    cart_page = CartPage(page)",
                "    cart_page.go_to_cart()",
                '    _assert_text(page, "购物车是空的")',
                '    _assert_text(page, "去逛逛")',
            ]
        if "手机商品" in title:
            return [
                '    _add_product(page, "p004")',
                '    _assert_text(page, "iPhone 16 Pro")',
            ]
        if "耳机商品" in title:
            return [
                '    _add_product(page, "p007")',
                '    _assert_text(page, "Sony WH-1000XM6")',
            ]
        if "无货" in title:
            return [
                "    page.goto(f'{BASE_URL}/')",
                '    out_of_stock = page.locator("form:has(input[name=\'product_id\'][value=\'p003\']) button")',
                "    expect(out_of_stock).to_be_disabled()",
                '    expect(out_of_stock).to_contain_text("暂时缺货")',
            ]
        if "超过库存" in title:
            return [
                "    page.goto(f'{BASE_URL}/')",
                '    for _ in range(6):',
                '        page.locator("form:has(input[name=\'product_id\'][value=\'p002\']) button").click()',
                '        page.wait_for_load_state("networkidle")',
                '        if "库存不足" in page.locator("body").inner_text():',
                '            break',
                '        page.goto(f"{BASE_URL}/")',
                '    _assert_text(page, "库存不足")',
            ]
        if "空" in title:
            return [
                "    cart_page = CartPage(page)",
                "    cart_page.go_to_cart()",
                '    _assert_text(page, "购物车是空的")',
            ]
        if "查看购物车" in title:
            return [
                '    _add_product(page, "p001")',
                '    _assert_text(page, "华为MateBook X Pro")',
                '    _assert_text(page, "合计")',
            ]
        if "至0" in title:
            return [
                '    _add_product(page, "p001")',
                '    page.locator("button:has-text(\'−\')").click()',
                '    _assert_text(page, "购物车是空的")',
            ]
        if "删除" in title:
            return [
                '    _add_product(page, "p001")',
                '    page.locator("button:has-text(\'删除\')").click()',
                '    _assert_text(page, "已从购物车移除")',
                '    _assert_text(page, "购物车是空的")',
            ]
        if "增加" in title:
            return [
                '    _add_product(page, "p001")',
                '    page.locator("button:has-text(\'+\')").click()',
                '    expect(page.locator("text=2")).to_be_visible()',
            ]
        if "减少" in title:
            return [
                '    _add_product(page, "p001")',
                '    page.locator("button:has-text(\'+\')").click()',
                '    page.locator("button:has-text(\'−\')").click()',
                '    expect(page.locator("text=1")).to_be_visible()',
            ]
        return [
            '    _add_product(page, "p001")',
            '    expect(page).to_have_url(f"{BASE_URL}/cart")',
            '    _assert_text(page, "华为MateBook X Pro")',
            '    _assert_text(page, "合计")',
        ]

    def _render_checkout_case(self, title: str) -> List[str]:
        if "已登录访问不存在订单" in title:
            return [
                "    _login(page)",
                "    page.goto(f'{BASE_URL}/order/non-existent-order')",
                '    expect(page).to_have_url(f"{BASE_URL}/")',
                '    _assert_text(page, "订单不存在")',
            ]
        if "未登录查看订单" in title:
            return [
                "    page.goto(f'{BASE_URL}/order/non-existent-order')",
                '    expect(page).to_have_url(f"{BASE_URL}/login")',
                '    _assert_text(page, "请先登录")',
            ]
        if "未登录" in title:
            return [
                "    page.goto(f'{BASE_URL}/checkout')",
                '    expect(page).to_have_url(f"{BASE_URL}/login")',
                '    _assert_text(page, "请先登录后再下单")',
            ]
        if "空购物车" in title:
            return [
                "    _login(page)",
                "    page.goto(f'{BASE_URL}/checkout')",
                '    expect(page).to_have_url(f"{BASE_URL}/cart")',
                '    _assert_text(page, "购物车为空，请先添加商品")',
            ]
        if "不填写" in title or "空地址" in title:
            return [
                "    _login(page)",
                '    _add_product(page, "p001")',
                '    page.locator("a:has-text(\'去结算\')").click()',
                '    page.locator("input[name=\'address\']").evaluate("el => el.removeAttribute(\'required\')")',
                '    page.locator("button:has-text(\'提交订单\')").click()',
                '    _assert_text(page, "请填写收货地址")',
            ]
        if "银行卡" in title:
            return [
                "    _login(page)",
                '    _add_product(page, "p004")',
                '    page.locator("a:has-text(\'去结算\')").click()',
                '    page.locator("input[name=\'address\']").fill("上海市测试路 600 号")',
                '    page.locator("select[name=\'payment\']").select_option("银行卡")',
                '    page.locator("button:has-text(\'提交订单\')").click()',
                '    _assert_text(page, "订单提交成功")',
                '    _assert_text(page, "银行卡")',
            ]
        if "支付宝支付" in title:
            return [
                "    _login(page)",
                '    _add_product(page, "p004")',
                '    page.locator("a:has-text(\'去结算\')").click()',
                '    page.locator("input[name=\'address\']").fill("上海市测试路 900 号")',
                '    page.locator("select[name=\'payment\']").select_option("支付宝")',
                '    page.locator("button:has-text(\'提交订单\')").click()',
                '    _assert_text(page, "订单提交成功")',
                '    _assert_text(page, "支付宝")',
            ]
        if "微信支付" in title:
            return [
                "    _login(page)",
                '    _add_product(page, "p004")',
                '    page.locator("a:has-text(\'去结算\')").click()',
                '    page.locator("input[name=\'address\']").fill("上海市测试路 901 号")',
                '    page.locator("select[name=\'payment\']").select_option("微信支付")',
                '    page.locator("button:has-text(\'提交订单\')").click()',
                '    _assert_text(page, "订单提交成功")',
                '    _assert_text(page, "微信支付")',
            ]
        if "支付方式" in title:
            return [
                "    _login(page)",
                '    _add_product(page, "p004")',
                '    page.locator("a:has-text(\'去结算\')").click()',
                '    page.locator("input[name=\'address\']").fill("上海市测试路 200 号")',
                '    page.locator("select[name=\'payment\']").select_option("微信支付")',
                '    page.locator("button:has-text(\'提交订单\')").click()',
                '    _assert_text(page, "订单提交成功")',
                '    _assert_text(page, "微信支付")',
            ]
        if "库存扣减" in title:
            return [
                "    _login(page)",
                '    _add_product(page, "p005")',
                '    page.locator("a:has-text(\'去结算\')").click()',
                '    page.locator("input[name=\'address\']").fill("上海市测试路 300 号")',
                '    page.locator("select[name=\'payment\']").select_option("支付宝")',
                '    page.locator("button:has-text(\'提交订单\')").click()',
                '    _assert_text(page, "订单提交成功")',
                "    page.goto(f'{BASE_URL}/')",
                '    _assert_text(page, "Samsung Galaxy S25")',
            ]
        if "库存耗尽" in title:
            return [
                "    _login(page)",
                '    for _ in range(5):',
                '        _add_product(page, "p002")',
                '        page.goto(f"{BASE_URL}/")',
                '    page.goto(f"{BASE_URL}/cart")',
                '    page.locator("a:has-text(\'去结算\')").click()',
                '    page.locator("input[name=\'address\']").fill("上海市测试路 400 号")',
                '    page.locator("select[name=\'payment\']").select_option("支付宝")',
                '    page.locator("button:has-text(\'提交订单\')").click()',
                '    _assert_text(page, "订单提交成功")',
                "    page.goto(f'{BASE_URL}/')",
                '    expect(page.locator("form:has(input[name=\'product_id\'][value=\'p002\']) button")).to_be_disabled()',
                '    _assert_text(page, "暂时缺货")',
            ]
        if "刚好有货" in title:
            return [
                "    _login(page)",
                '    _add_product(page, "p006")',
                '    page.locator("a:has-text(\'去结算\')").click()',
                '    page.locator("input[name=\'address\']").fill("上海市测试路 500 号")',
                '    page.locator("select[name=\'payment\']").select_option("银行卡")',
                '    page.locator("button:has-text(\'提交订单\')").click()',
                '    _assert_text(page, "订单提交成功")',
            ]
        if "购物车清空" in title:
            return [
                "    _login(page)",
                '    _add_product(page, "p007")',
                '    page.locator("a:has-text(\'去结算\')").click()',
                '    page.locator("input[name=\'address\']").fill("上海市测试路 700 号")',
                '    page.locator("select[name=\'payment\']").select_option("支付宝")',
                '    page.locator("button:has-text(\'提交订单\')").click()',
                '    _assert_text(page, "订单提交成功")',
                "    page.goto(f'{BASE_URL}/cart')",
                '    _assert_text(page, "购物车是空的")',
            ]
        if "结算页展示" in title:
            return [
                "    _login(page)",
                '    _add_product(page, "p001")',
                '    page.locator("a:has-text(\'去结算\')").click()',
                '    _assert_text(page, "确认订单")',
                '    _assert_text(page, "华为MateBook X Pro")',
                '    _assert_text(page, "合计")',
            ]
        if "地址前后空格" in title:
            return [
                "    _login(page)",
                '    _add_product(page, "p006")',
                '    page.locator("a:has-text(\'去结算\')").click()',
                '    page.locator("input[name=\'address\']").fill("  上海市测试路 800 号  ")',
                '    page.locator("select[name=\'payment\']").select_option("支付宝")',
                '    page.locator("button:has-text(\'提交订单\')").click()',
                '    _assert_text(page, "订单提交成功")',
                '    _assert_text(page, "上海市测试路 800 号")',
            ]
        if "订单详情" in title:
            return [
                "    _login(page)",
                '    _add_product(page, "p001")',
                '    page.locator("a:has-text(\'去结算\')").click()',
                '    page.locator("input[name=\'address\']").fill("上海市测试路 100 号")',
                '    page.locator("select[name=\'payment\']").select_option("支付宝")',
                '    page.locator("button:has-text(\'提交订单\')").click()',
                '    _assert_text(page, "订单提交成功")',
                '    _assert_text(page, "上海市测试路 100 号")',
                '    _assert_text(page, "华为MateBook X Pro")',
            ]
        if "订单状态" in title:
            return [
                "    _login(page)",
                '    _add_product(page, "p001")',
                '    page.locator("a:has-text(\'去结算\')").click()',
                '    page.locator("input[name=\'address\']").fill("上海市测试路 902 号")',
                '    page.locator("select[name=\'payment\']").select_option("支付宝")',
                '    page.locator("button:has-text(\'提交订单\')").click()',
                '    _assert_text(page, "pending")',
            ]
        if "下单时间" in title:
            return [
                "    _login(page)",
                '    _add_product(page, "p001")',
                '    page.locator("a:has-text(\'去结算\')").click()',
                '    page.locator("input[name=\'address\']").fill("上海市测试路 903 号")',
                '    page.locator("select[name=\'payment\']").select_option("支付宝")',
                '    page.locator("button:has-text(\'提交订单\')").click()',
                '    _assert_text(page, "下单时间")',
            ]
        if "订单总价" in title:
            return [
                "    _login(page)",
                '    _add_product(page, "p001")',
                '    page.locator("a:has-text(\'去结算\')").click()',
                '    page.locator("input[name=\'address\']").fill("上海市测试路 904 号")',
                '    page.locator("select[name=\'payment\']").select_option("支付宝")',
                '    page.locator("button:has-text(\'提交订单\')").click()',
                '    _assert_text(page, "¥8999.00")',
            ]
        return [
            "    _login(page)",
            '    _add_product(page, "p001")',
            '    page.locator("a:has-text(\'去结算\')").click()',
            '    _assert_text(page, "确认订单")',
            '    page.locator("input[name=\'address\']").fill("上海市测试路 100 号")',
            '    page.locator("select[name=\'payment\']").select_option("支付宝")',
            '    page.locator("button:has-text(\'提交订单\')").click()',
            '    _assert_text(page, "订单提交成功")',
            '    _assert_text(page, "上海市测试路 100 号")',
        ]

    def _render_generic_case(self, steps: List[str], expected: str) -> List[str]:
        lines = ["    page.goto(BASE_URL)"]
        for step in steps:
            lines.append(f"    # {step}")
        if expected:
            lines.append(f'    _assert_text(page, "{expected[:30]}")')
        else:
            lines.append("    expect(page.locator('body')).to_be_visible()")
        return lines

    def _write_file(self, output_dir: str, module: str, code: str) -> str:
        os.makedirs(output_dir, exist_ok=True)
        filename = f"test_{module}.py"
        filepath = str(Path(output_dir) / filename)
        Path(filepath).write_text(code, encoding="utf-8")
        print(f"[TestAgent] 已生成: {filepath}")
        return filepath

    def _write_conftest(self, output_dir: str) -> str:
        """生成 pytest/Playwright 运行所需的 fixture。"""
        os.makedirs(output_dir, exist_ok=True)
        code = '''"""Pytest fixtures for generated Playwright tests."""
import pytest
import urllib.request
from playwright.sync_api import sync_playwright


def pytest_configure(config):
    config.addinivalue_line("markers", "positive: positive-path generated cases")
    config.addinivalue_line("markers", "negative: negative-path generated cases")
    config.addinivalue_line("markers", "boundary: boundary-value generated cases")
    config.addinivalue_line("markers", "general: generic generated cases")
    config.addinivalue_line("markers", "test_id(id): source test case id")


@pytest.fixture
def page():
    try:
        urllib.request.urlopen("http://localhost:5000/test/reset", timeout=2).read()
    except Exception:
        pass
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        try:
            yield page
        finally:
            context.close()
            browser.close()
'''
        filepath = str(Path(output_dir) / "conftest.py")
        Path(filepath).write_text(code, encoding="utf-8")
        print(f"[TestAgent] 已生成: {filepath}")
        return filepath
