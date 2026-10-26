"""OpenAI-compatible model client. Configuration is not proof of connectivity."""
import json
import urllib.request
import urllib.error
from urllib.parse import urlsplit, urlunsplit
from typing import Any, Dict, List, Optional
from smart_agent.config import API_BASE, API_KEY, DEFAULT_MODEL


def normalize_model_name(model_name: str) -> str:
    """Model identifiers are supplied by the provider; never guess replacements."""
    return (model_name or "").strip()


def validate_api_base(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("模型 API 地址不能为空")
    parsed = urlsplit(value.strip())
    if (not parsed.hostname or parsed.username is not None or parsed.password is not None
            or parsed.query or parsed.fragment):
        raise ValueError("模型地址不能包含用户名、密码、查询参数或片段")
    local = parsed.hostname.lower() in {"localhost", "127.0.0.1", "::1"}
    if parsed.scheme != "https" and not (local and parsed.scheme == "http"):
        raise ValueError("远程模型地址必须使用 HTTPS；HTTP 仅允许本机回环地址")
    try:
        parsed.port
    except ValueError as exc:
        raise ValueError("模型端口无效") from exc
    path = parsed.path.rstrip("/")
    if path.endswith("/chat/completions"):
        path = path[:-len("/chat/completions")]
    if not path:
        path = "/v1"
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward credentials to a redirected host.
        return None


class LLMClient:
    def __init__(self, api_base: str = API_BASE, api_key: str = API_KEY,
                 model: str = DEFAULT_MODEL):
        self.api_base = api_base.strip()
        self.api_key = api_key.strip()
        self.model = normalize_model_name(model)

    @property
    def normalized_api_base(self) -> str:
        return validate_api_base(self.api_base)

    def has_valid_key(self) -> bool:
        """Only checks that a key is configured; remote authentication is separate."""
        return bool(self.api_key and len(self.api_key) >= 5)

    def chat_completion(self, messages: List[Dict[str, Any]],
                        tools: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        if not self.has_valid_key():
            raise RuntimeError("未配置大模型 API Key，请在 API 设置或环境变量中配置")
        return self._call_remote_api(messages, tools)

    def _call_remote_api(self, messages, tools=None):
        url = self.normalized_api_base + "/chat/completions"
        payload = {"model": self.model, "messages": messages, "temperature": 0.6}
        if tools:
            payload.update(tools=tools, tool_choice="auto")
        request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + self.api_key},
            method="POST")
        handlers = [_NoRedirect()]
        if urlsplit(url).hostname in {"127.0.0.1", "localhost", "::1"}:
            handlers.append(urllib.request.ProxyHandler({}))
        opener = urllib.request.build_opener(*handlers)
        try:
            with opener.open(request, timeout=45) as response:
                raw = response.read(4 * 1024 * 1024 + 1)
            if len(raw) > 4 * 1024 * 1024:
                raise RuntimeError("模型响应过大")
            body = json.loads(raw)
            message = body["choices"][0]["message"]
            if not isinstance(message, dict):
                raise ValueError("invalid message")
            return message
        except urllib.error.HTTPError as exc:
            explanations = {401: "鉴权失败，请检查 API Key", 403: "服务拒绝访问",
                404: "接口或模型不存在，请检查服务商文档", 429: "服务限流或额度不足"}
            # Provider bodies may contain credentials or user input: do not echo them.
            raise RuntimeError("模型调用失败：HTTP %s，%s" % (
                exc.code, explanations.get(exc.code, "请检查模型服务状态"))) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise RuntimeError("无法连接模型服务，请检查地址和网络") from None
        except (ValueError, KeyError, IndexError, TypeError):
            raise RuntimeError("模型响应不符合 Chat Completions 格式") from None
