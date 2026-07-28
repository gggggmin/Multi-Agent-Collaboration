"""登录页面 Page Object"""
from .pom_base import BasePage


class LoginPage(BasePage):
    """登录页面对象"""

    # 元素定位器
    USERNAME_INPUT = "#username"
    PASSWORD_INPUT = "#password"
    LOGIN_BUTTON = "button[type='submit']"
    ERROR_FLASH = ".flash.error"
    SUCCESS_FLASH = ".flash.success"

    def login(self, username: str, password: str):
        """执行登录操作"""
        self.navigate("/login")
        self.page.fill(self.USERNAME_INPUT, username)
        self.page.fill(self.PASSWORD_INPUT, password)
        self.page.click(self.LOGIN_BUTTON)
        self.page.wait_for_load_state("networkidle")

    def get_error_message(self) -> str:
        """获取错误提示"""
        return self.get_text(self.ERROR_FLASH)

    def is_login_success(self) -> bool:
        """检查登录是否成功"""
        return self.is_visible(self.SUCCESS_FLASH)
