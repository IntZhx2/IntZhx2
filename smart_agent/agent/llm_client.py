"""
大语言模型客户端 (LLM Client)
强制通过 OpenAI 兼容接口标准连接云端真实大模型（如通义千问百炼、DeepSeek、智谱等），
全面移除伪离线规则模式，保证智能体所有思考、规划与生成全部由真实大语言模型驱动。
"""

import json
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional
import logging
from smart_agent.config import API_BASE, API_KEY, DEFAULT_MODEL

logger = logging.getLogger("agent.llm")


class LLMClient:
    """真实在线大语言模型客户端"""

    def __init__(
        self,
        api_base: str = API_BASE,
        api_key: str = API_KEY,
        model: str = DEFAULT_MODEL,
    ):
        self.api_base = api_base.strip()
        self.api_key = api_key.strip()
        self.model = model.strip()

    @property
    def normalized_api_base(self) -> str:
        """规范化 API 端点 URL，自动去除末尾斜杠并在缺失时补充 /v1"""
        base = self.api_base.rstrip("/")
        if base.endswith("/chat/completions"):
            return base[:-17]
        # 如果是本地或第三方域名但没有 /v1 且没有 /v1beta，自动规范化补齐 /v1
        if not (base.endswith("/v1") or base.endswith("/v1beta") or "/v1/" in base):
            return f"{base}/v1"
        return base

    def has_valid_key(self) -> bool:
        """检查是否已配置有效格式的 API Key"""
        return bool(self.api_key and len(self.api_key) >= 5)

    def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """向云端大模型 API 发送对话与工具规划请求（强制要求 API KEY）"""
        if not self.has_valid_key():
            raise RuntimeError(
                "【未配置大模型 API Key】当前系统已关闭伪离线模式，必须接入真实大模型 API！"
                "请点击右上角【⚙️ API 设置】填入您的 API Key（支持本地 CPA、阿里云百炼、DeepSeek等）。"
            )

        logger.info(f"正在向云端大模型发送请求: Model={self.model}, Endpoint={self.normalized_api_base}")
        return self._call_remote_api(messages, tools)

    def _call_remote_api(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """使用标准 HTTP POST 调用大模型兼容接口"""
        url = f"{self.normalized_api_base}/chat/completions"
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.6,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "SmartAgent-Travel/1.0",
        }

        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=45.0) as resp:
                resp_body = resp.read().decode("utf-8")
                result = json.loads(resp_body)
                if "choices" not in result or not result["choices"]:
                    raise RuntimeError(f"大模型响应格式异常: {resp_body[:300]}")
                choice = result["choices"][0]["message"]
                return choice
        except urllib.error.HTTPError as he:
            err_msg = he.read().decode("utf-8", errors="ignore")
            logger.error(f"云端大模型接口报错 HTTP {he.code}: {err_msg}")
            if he.code == 401:
                raise RuntimeError(
                    "API Key 鉴权失败 (401 Unauthorized)！请检查填写的 API Key 是否正确。"
                    "若使用本地 CPA 代理，默认访问密钥通常为 123456。"
                )
            elif he.code == 404:
                raise RuntimeError(
                    f"大模型服务端点未找到 (404 Not Found)！请求路径为: {url}。"
                    "若使用本地 CPA 代理，请确保 API 端点为 http://127.0.0.1:8317/v1。"
                )
            elif he.code == 400 and ("unknown provider" in err_msg or "model_not_found" in err_msg):
                raise RuntimeError(
                    f"模型名称未匹配 (HTTP 400): 服务端未找到模型 '{self.model}'。"
                    "当前本地 CPA 绑定的 Google Gemini 模型名称通常为 gemini-3.5-flash-lite 或 gemini-3.8-flash-high，请在【⚙️ API 设置】中修改模型名称！"
                )
            elif he.code == 429:
                raise RuntimeError("大模型调用超出额度限制 (429 Too Many Requests / Quota Exceeded)！请检查账户余额。")
            raise RuntimeError(f"大模型服务返回错误 (HTTP {he.code}): {err_msg[:250]}")
        except urllib.error.URLError as ue:
            logger.error(f"网络连接失败: {ue.reason}")
            raise RuntimeError(f"无法连接至大模型服务端点 ({self.normalized_api_base})，请检查网络或 CPA 代理是否在运行: {ue.reason}")
        except Exception as e:
            logger.error(f"请求发生未知异常: {e}")
            raise RuntimeError(f"大模型服务请求异常: {str(e)}")
