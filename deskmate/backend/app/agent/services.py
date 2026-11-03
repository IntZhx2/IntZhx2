"""受限联网搜索和内存截图分析，不将图像放入日志或会话历史。"""

from typing import TYPE_CHECKING, Any

from app.agent.tools import ToolError

if TYPE_CHECKING:
    from app.runtime import Runtime


async def web_search(rt: "Runtime", query: str) -> dict[str, Any]:
    if rt.config.search_provider == "bocha":
        key = rt.config.bocha_api_key.get_secret_value()
        if not key:
            raise ToolError("SEARCH_UNAVAILABLE", "未配置 BOCHA_API_KEY")
        response = await rt.http.post(
            "https://api.bochaai.com/v1/web-search",
            headers={"Authorization": "Bearer " + key},
            json={"query": query[:500], "summary": True, "count": 5},
            timeout=rt.config.llm_timeout_s,
        )
        response.raise_for_status()
        return {"search_results": response.json()}
    if rt.config.search_provider != "llm_builtin":
        raise ToolError("SEARCH_UNAVAILABLE")
    result = await rt.llm.complete(
        [
            {"role": "system", "content": "使用联网搜索回答，列明来源和链接。无法联网时明确说明。"},
            {"role": "user", "content": query[:500]},
        ],
        [],
        rt.config.llm_model,
        extra={"enable_search": True},
    )
    return {"summary": result.get("content", "")}


async def analyze_screen(rt: "Runtime", target: str, question: str) -> dict[str, Any]:
    image = await rt.edge.call("take_screenshot", {"target": target, "max_side": 1280})
    if rt.store.data["demo_mode"]:
        return {
            "analysis": (
                "VirtualEdge 仅提供协议占位图，不能据此诊断真实报错；请连接 Windows Edge 后重试。"
            )
        }
    data, mime = image.get("image_b64"), image.get("mime")
    if (
        not isinstance(data, str)
        or len(data) > 8_000_000
        or mime not in {"image/jpeg", "image/png"}
    ):
        raise ToolError("BAD_ARGS", "截图格式或大小无效")
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": question[:2000]},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}},
            ],
        }
    ]
    try:
        result = await rt.llm.complete(messages, [], rt.config.llm_vl_model)
        return {"analysis": result.get("content", "")}
    finally:
        messages.clear()
        image.clear()
