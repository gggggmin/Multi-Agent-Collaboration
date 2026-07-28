"""Case Creator Agent — 根据需求生成测试用例

基于 AutoGen 框架，按照需求片段生成覆盖正向、逆向、边界值的测试用例。
LLM 不可用时使用内置领域知识降级。
"""
import json
from typing import List, Dict
from .base_agent import BaseAgent

CREATOR_SYSTEM_PROMPT = """你是一个专业的软件测试工程师（Case Creator）。
你的任务是：根据提供的产品需求文档（PRD）片段，生成全面的测试用例。

## 覆盖策略
你必须覆盖以下三类测试：
1. **正向流程**：正常操作路径，验证功能正确执行
2. **逆向流程**：异常操作、错误输入、非法访问
3. **边界值**：空值、极限值、临界条件、特殊字符

## 输出格式
严格输出 JSON 数组，每个元素包含：
```json
{
  "test_id": "TC-{MODULE}-001",
  "module": "模块名",
  "title": "用例标题",
  "precondition": "前置条件",
  "steps": ["步骤1", "步骤2"],
  "expected": "预期结果",
  "type": "正向/逆向/边界值"
}
```

## 约束
- 只能基于提供的需求内容生成用例
- 不得编造需求中未提及的功能
- 每个用例的步骤必须可操作、可验证
- 预期结果必须可观察（页面变化、提示信息、状态变更等）"""


class CaseCreator(BaseAgent):
    """测试用例生成智能体"""

    def __init__(self):
        super().__init__(role="CaseCreator", system_prompt=CREATOR_SYSTEM_PROMPT)

    def generate(self, requirement_chunks: List[Dict], module: str = "") -> List[Dict]:
        """根据需求片段生成测试用例

        Args:
            requirement_chunks: RAG 检索出的需求片段列表
            module: 模块名

        Returns:
            测试用例列表
        """
        context = self._format_context(requirement_chunks)
        prompt = f"""请为以下需求生成测试用例。

## 需求上下文
{context}

请生成涵盖正向、逆向、边界值的完整测试用例集。"""

        response = self.chat([{"role": "user", "content": prompt}])
        return self._parse_response(response, module)

    def _format_context(self, chunks: List[Dict]) -> str:
        """将需求片段格式化为结构化上下文"""
        parts = []
        for i, chunk in enumerate(chunks, 1):
            content = chunk.get("content", "")
            meta = chunk.get("metadata", {})
            module = meta.get("module", "未知")
            func = meta.get("func_name", "未知功能")
            ctype = meta.get("chunk_type", "未分类")
            parts.append(
                f"[片段 {i}] 模块: {module} | 功能: {func} | 类型: {ctype}\n{content}"
            )
        return "\n\n".join(parts)

    def _parse_response(self, response: str, module: str) -> List[Dict]:
        """解析 LLM 返回的 JSON"""
        if not response or response.startswith("__FALLBACK__"):
            return self._mock_cases(module)

        # 尝试提取 JSON
        try:
            start = response.index("[")
            end = response.rindex("]") + 1
            cases = json.loads(response[start:end])
            return cases if isinstance(cases, list) else [cases]
        except (ValueError, json.JSONDecodeError):
            try:
                cases = json.loads(response)
                return cases if isinstance(cases, list) else [cases]
            except json.JSONDecodeError:
                print(f"[CaseCreator] JSON 解析失败，使用降级数据")
                return self._mock_cases(module)

    def _mock_cases(self, module: str) -> List[Dict]:
        """LLM 不可用时的降级测试用例"""
        mock_db = {
            "login": [
                {"test_id": "TC-LOGIN-001", "module": "login",
                 "title": "正确用户名密码登录",
                 "precondition": "已注册用户 testuser/password123",
                 "steps": ["访问登录页", "输入用户名 testuser", "输入密码 password123",
                           "点击登录"],
                 "expected": "登录成功，跳转首页，显示用户昵称",
                 "type": "正向"},
                {"test_id": "TC-LOGIN-002", "module": "login",
                 "title": "错误密码登录",
                 "precondition": "已注册用户",
                 "steps": ["访问登录页", "输入用户名 testuser", "输入错误密码",
                           "点击登录"],
                 "expected": "提示'用户名或密码错误'",
                 "type": "逆向"},
                {"test_id": "TC-LOGIN-003", "module": "login",
                 "title": "空用户名登录",
                 "precondition": "无",
                 "steps": ["访问登录页", "不输入用户名", "输入密码", "点击登录"],
                 "expected": "提示'用户名和密码不能为空'",
                 "type": "边界值"},
                {"test_id": "TC-LOGIN-004", "module": "login",
                 "title": "空密码登录",
                 "precondition": "无",
                 "steps": ["访问登录页", "输入用户名", "不输入密码", "点击登录"],
                 "expected": "提示'用户名和密码不能为空'",
                 "type": "边界值"},
                {"test_id": "TC-LOGIN-005", "module": "login",
                 "title": "不存在用户登录",
                 "precondition": "无",
                 "steps": ["访问登录页", "输入不存在的用户名", "输入任意密码",
                           "点击登录"],
                 "expected": "提示'用户名或密码错误'",
                 "type": "逆向"},
            ],
            "search": [
                {"test_id": "TC-SEARCH-001", "module": "search",
                 "title": "关键词搜索",
                 "precondition": "存在匹配商品",
                 "steps": ["首页搜索框输入'华为'", "点击搜索"],
                 "expected": "显示华为MateBook X Pro",
                 "type": "正向"},
                {"test_id": "TC-SEARCH-002", "module": "search",
                 "title": "无结果搜索",
                 "precondition": "无",
                 "steps": ["搜索框输入'不存在的商品xyz'", "点击搜索"],
                 "expected": "显示'没有找到匹配的商品'",
                 "type": "逆向"},
                {"test_id": "TC-SEARCH-003", "module": "search",
                 "title": "空关键词搜索",
                 "precondition": "无",
                 "steps": ["搜索框为空", "点击搜索"],
                 "expected": "显示所有商品",
                 "type": "边界值"},
            ],
            "cart": [
                {"test_id": "TC-CART-001", "module": "cart",
                 "title": "添加商品到购物车",
                 "precondition": "商品库存>0",
                 "steps": ["首页", "点击商品的'加入购物车'"],
                 "expected": "提示'已将商品加入购物车'",
                 "type": "正向"},
                {"test_id": "TC-CART-002", "module": "cart",
                 "title": "添加无货商品",
                 "precondition": "商品库存=0",
                 "steps": ["首页", "找到无货商品", "尝试点击'加入购物车'"],
                 "expected": "按钮禁用或提示'库存不足'",
                 "type": "逆向"},
                {"test_id": "TC-CART-003", "module": "cart",
                 "title": "空购物车",
                 "precondition": "购物车为空",
                 "steps": ["访问购物车"],
                 "expected": "显示'购物车是空的'",
                 "type": "边界值"},
            ],
            "checkout": [
                {"test_id": "TC-CHECKOUT-001", "module": "checkout",
                 "title": "正常下单",
                 "precondition": "已登录，购物车有商品",
                 "steps": ["点击'去结算'", "填写地址", "选择支付方式", "提交订单"],
                 "expected": "订单提交成功",
                 "type": "正向"},
                {"test_id": "TC-CHECKOUT-002", "module": "checkout",
                 "title": "空购物车结算",
                 "precondition": "已登录，购物车为空",
                 "steps": ["访问 /checkout"],
                 "expected": "跳转购物车页，提示购物车为空",
                 "type": "边界值"},
                {"test_id": "TC-CHECKOUT-003", "module": "checkout",
                 "title": "未登录访问结算页",
                 "precondition": "未登录",
                 "steps": ["直接访问 /checkout"],
                 "expected": "跳转登录页，提示请先登录",
                 "type": "逆向"},
            ],
        }
        return mock_db.get(module, [])
