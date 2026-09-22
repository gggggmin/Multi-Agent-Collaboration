"""Agent 基类 — 基于 AutoGen 的智能体封装

将原有的 OpenAI SDK 直调方式替换为微软 AutoGen 框架，
利用其 AssistantAgent 管理对话历史和 LLM 调用。
提供降级方案保证 AutoGen 不可用时系统仍可运行。
"""
import json
import os
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict

from config import LLM_MODEL, LLM_TEMPERATURE, LLM_MAX_TOKENS, \
    LLM_API_KEY, AUTOGEN_CONFIG_LIST, AGENT_TRACE_ENABLED, AGENT_TRACE_DIR


class BaseAgent:
    """基于 AutoGen 的智能体基类

    内部使用 autogen.AssistantAgent 管理对话，
    对外保持原有 generate/chat 接口不变。
    """

    def __init__(self, role: str, system_prompt: str):
        self.role = role
        self.system_prompt = system_prompt

        # AutoGen 智能体实例（延迟初始化）
        self._agent = None

    @property
    def agent(self):
        """获取 AutoGen AssistantAgent 实例（惰性初始化）"""
        if self._agent is None:
            self._agent = self._build_autogen_agent()
        return self._agent

    def _build_autogen_agent(self):
        """构建 AutoGen AssistantAgent（含降级）"""
        try:
            import autogen
            return autogen.AssistantAgent(
                name=self.role,
                system_message=self.system_prompt,
                llm_config={
                    "config_list": AUTOGEN_CONFIG_LIST,
                    "temperature": LLM_TEMPERATURE,
                    "max_tokens": LLM_MAX_TOKENS,
                    "timeout": 60,
                },
            )
        except Exception as e:
            print(f"[{self.role}] AutoGen 初始化失败: {e}")
            print(f"[{self.role}] 降级为直接 LLM 调用模式")
            return None

    def chat(self, messages: List[Dict], temperature: Optional[float] = None) -> str:
        """调用 LLM

        优先通过 AutoGen Agent 处理，降级为直接 OpenAI SDK 调用。

        Args:
            messages: 对话消息列表
            temperature: 可选，覆盖默认温度

        Returns:
            LLM 的文本响应
        """
        if self._agent is not None:
            response = self._chat_via_autogen(messages)
            self._trace_interaction("autogen", messages, response)
            return response
        response = self._chat_direct(messages, temperature)
        self._trace_interaction("direct", messages, response)
        return response

    def _trace_interaction(self, mode: str, messages: List[Dict], response: str) -> None:
        """Persist agent prompts/responses for experiment reproducibility."""
        if not AGENT_TRACE_ENABLED:
            return
        try:
            trace_dir = Path(AGENT_TRACE_DIR)
            trace_dir.mkdir(parents=True, exist_ok=True)
            payload = {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "role": self.role,
                "mode": mode,
                "model": LLM_MODEL,
                "used_fallback": bool(response and response.startswith("__FALLBACK__")),
                "messages": messages,
                "response": response,
            }
            trace_path = trace_dir / f"{self.role}.jsonl"
            with trace_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def _chat_via_autogen(self, messages: List[Dict]) -> str:
        """通过 AutoGen 调用 LLM"""
        try:
            import autogen

            # 构造临时 UserAgent 来发起对话
            user = autogen.UserProxyAgent(
                name="__user__",
                human_input_mode="NEVER",
                code_execution_config=False,
            )

            # 提取最后一条 user 消息作为输入
            user_msg = messages[-1]["content"] if messages else ""
            user.send(user_msg, self._agent, request_reply=True, silent=True)

            # 从 agent 的历史消息中获取最后一条回复
            last_msg = self._agent.chat_messages.get(user, [])
            if last_msg:
                return last_msg[-1]["content"]
            return ""

        except Exception as e:
            print(f"[{self.role}] AutoGen 对话失败: {e}")
            return self._fallback_response()

    def _chat_direct(self, messages: List[Dict],
                     temperature: Optional[float] = None) -> str:
        """直接调用 OpenAI SDK（降级方案）"""
        if os.getenv("LLM_MOCK", "0") == "1" or not LLM_API_KEY:
            return self._fallback_response()
        from openai import OpenAI
        try:
            client = OpenAI(api_key=LLM_API_KEY)
            full_messages = [{"role": "system", "content": self.system_prompt}]
            full_messages.extend(messages)

            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=full_messages,
                temperature=temperature or LLM_TEMPERATURE,
                max_tokens=LLM_MAX_TOKENS,
                timeout=60,
            )
            return response.choices[0].message.content.strip()

        except Exception as e:
            print(f"[{self.role}] 直接 LLM 调用失败: {e}")
            return self._fallback_response()

    def _fallback_response(self) -> str:
        """API 不可用时的降级响应"""
        return self._get_fallback_content()

    def _get_fallback_content(self) -> str:
        """获取降级内容 — 子类可覆盖"""
        return "__FALLBACK__LLM_UNAVAILABLE__"
