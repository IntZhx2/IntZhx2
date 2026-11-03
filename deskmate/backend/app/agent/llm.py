"""OpenAI 兼容异步流式客户端，支持工具调用及可控超时。"""

import json
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from app.agent.tools import ToolError
from app.config import Config


class LLMClient:
    def __init__(self, config: Config, http: httpx.AsyncClient) -> None:
        self.config, self.http = config, http

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        model: str,
        on_delta: Callable[[str], Awaitable[None]] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.config.llm_api_key.get_secret_value():
            raise ToolError("LLM_UNAVAILABLE", "尚未配置 LLM_API_KEY，复杂任务需要模型服务")
        body: dict[str, Any] = {"model": model, "messages": messages, "stream": True}
        if tools:
            body["tools"] = tools
        body.update(extra or {})
        calls: dict[int, dict[str, Any]] = {}
        content = ""
        async with self.http.stream(
            "POST",
            self.config.llm_base_url.rstrip("/") + "/chat/completions",
            headers={"Authorization": "Bearer " + self.config.llm_api_key.get_secret_value()},
            json=body,
            timeout=self.config.llm_timeout_s,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if raw == "[DONE]":
                    break
                chunk = json.loads(raw)
                choices = chunk.get("choices", [])
                if not choices:
                    continue
                delta = choices[0].get("delta", {})
                if delta.get("content"):
                    text = delta["content"]
                    content += text
                    if len(content) > 16000:
                        raise ToolError("BAD_MODEL_RESPONSE")
                    if on_delta:
                        await on_delta(text)
                for item in delta.get("tool_calls", []):
                    index = item["index"]
                    if index not in calls:
                        if len(calls) >= 8:
                            raise ToolError("BAD_MODEL_RESPONSE")
                        calls[index] = {
                            "id": "",
                            "type": "function",
                            "function": {"name": "", "arguments": ""},
                        }
                    call = calls[index]
                    call["id"] += item.get("id", "")
                    function = item.get("function", {})
                    call["function"]["name"] += function.get("name", "")
                    call["function"]["arguments"] += function.get("arguments", "")
                    if len(call["function"]["arguments"]) > 16000:
                        raise ToolError("BAD_MODEL_RESPONSE")
        return {
            "role": "assistant",
            "content": content or None,
            **({"tool_calls": list(calls.values())} if calls else {}),
        }
