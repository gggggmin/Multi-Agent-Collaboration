"""Page Object Model 基类 — Playwright 实现"""
from playwright.sync_api import Page


class BasePage:
    """所有 Page Object 的基类"""

    def __init__(self, page: Page):
        self.page = page
        self.base_url = "http://localhost:5000"

    def navigate(self, path: str = "/"):
        """导航到指定路径"""
        self.page.goto(f"{self.base_url}{path}")
        self.page.wait_for_load_state("networkidle")

    def get_text(self, selector: str) -> str:
        """获取元素文本"""
        return self.page.text_content(selector) or ""

    def is_visible(self, selector: str) -> bool:
        """检查元素是否可见"""
        try:
            return self.page.is_visible(selector)
        except Exception:
            return False

    def wait_for_selector(self, selector: str, timeout: int = 5000):
        """等待元素出现"""
        self.page.wait_for_selector(selector, timeout=timeout)

    def screenshot(self, path: str = "screenshot.png"):
        """截取页面截图"""
        self.page.screenshot(path=path)
