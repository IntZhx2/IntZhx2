"""DeskMate Edge 桌面与窗口控制工具集 (desktop_tools.py)
实现 CONTRACTS §3.3 中电脑 Agent 相关工具规范
"""

from typing import Any, Literal
from pydantic import BaseModel, Field
from ..tool_registry import registry
from ..platform_factory import get_platform

platform = get_platform()


class OpenAppArgs(BaseModel):
    name: str = Field(description="应用程序名称，如 chrome, code, notepad")


class OpenFolderArgs(BaseModel):
    path: str = Field(description="目标目录路径")
    in_vscode: bool = Field(default=False, description="是否直接在 VS Code 中打开该目录")


class OpenUrlArgs(BaseModel):
    url: str = Field(description="要打开的网页 URL")


class FindFilesArgs(BaseModel):
    keyword: str = Field(description="文件名检索关键字")
    directory: str | None = Field(default=None, description="搜索根目录，默认桌面")
    limit: int = Field(default=5, description="最多返回文件数量")


class ArrangeWindowsArgs(BaseModel):
    layout: Literal["code_left_browser_right", "maximize", "split_half", "custom"] = Field(
        default="code_left_browser_right",
        description="窗口布局模式：code_left_browser_right (左IDE右浏览器) | maximize | split_half"
    )
    custom: dict[str, Any] | None = Field(default=None, description="自定义布局比例")


class WriteClipboardArgs(BaseModel):
    text: str = Field(description="写入剪贴板的纯文本内容")


class TakeScreenshotArgs(BaseModel):
    target: Literal["screen", "latest_desktop_file"] = Field(
        default="screen",
        description="截图目标：screen (当前屏幕) | latest_desktop_file (桌面最近生成的图片文件)"
    )
    max_side: int = Field(default=1280, description="长边最大像素，等比缩放")


class ShowWinToastArgs(BaseModel):
    title: str = Field(description="通知标题")
    message: str = Field(description="通知详细正文")


# 注册工具

@registry.register(
    name="open_app",
    description="在 Windows 电脑上启动白名单内的应用程序",
    args_schema=OpenAppArgs,
    timeout_s=8
)
async def tool_open_app(name: str) -> dict[str, Any]:
    opened = platform.open_app(name)
    return {"opened": opened}


@registry.register(
    name="open_folder",
    description="打开本地文件夹，支持在资源管理器或 VS Code 中打开",
    args_schema=OpenFolderArgs,
    timeout_s=8
)
async def tool_open_folder(path: str, in_vscode: bool = False) -> dict[str, Any]:
    opened = platform.open_folder(path, in_vscode)
    return {"opened": opened}


@registry.register(
    name="open_url",
    description="在默认浏览器中打开指定网址",
    args_schema=OpenUrlArgs,
    timeout_s=5
)
async def tool_open_url(url: str) -> dict[str, Any]:
    platform.open_url(url)
    return {}


@registry.register(
    name="find_files",
    description="在本地目录查找名称包含关键字的文件或目录",
    args_schema=FindFilesArgs,
    timeout_s=10
)
async def tool_find_files(keyword: str, directory: str | None = None, limit: int = 5) -> dict[str, Any]:
    files = platform.find_files(keyword, directory, limit)
    return {"files": files}


@registry.register(
    name="arrange_windows",
    description="规整排列屏幕窗口，如 VS Code 左侧 60% / 浏览器右侧 40% 分屏",
    args_schema=ArrangeWindowsArgs,
    timeout_s=10
)
async def tool_arrange_windows(layout: str, custom: dict[str, Any] | None = None) -> dict[str, Any]:
    count = platform.arrange_windows(layout, custom)
    return {"arranged_count": count}


@registry.register(
    name="get_open_windows",
    description="获取当前所有可见窗口的标题、进程名与几何坐标",
    timeout_s=5
)
async def tool_get_open_windows() -> dict[str, Any]:
    windows = platform.get_open_windows()
    return {"windows": windows}


@registry.register(
    name="read_clipboard",
    description="读取系统剪贴板中的最新纯文本（截断至 8000 字）",
    timeout_s=3
)
async def tool_read_clipboard() -> dict[str, Any]:
    text = platform.read_clipboard()
    return {"text": text[:8000]}


@registry.register(
    name="write_clipboard",
    description="将文本写入系统剪贴板（如代码片段、提炼结论）",
    args_schema=WriteClipboardArgs,
    timeout_s=3
)
async def tool_write_clipboard(text: str) -> dict[str, Any]:
    platform.write_clipboard(text)
    return {}


@registry.register(
    name="take_screenshot",
    description="截取主屏幕或获取桌面最新图片，自动压缩为 JPEG Base64",
    args_schema=TakeScreenshotArgs,
    timeout_s=10
)
async def tool_take_screenshot(target: str = "screen", max_side: int = 1280) -> dict[str, Any]:
    res = platform.take_screenshot(target, max_side)
    return res


@registry.register(
    name="show_win_toast",
    description="在 Windows 屏幕右下角弹出系统通知气泡",
    args_schema=ShowWinToastArgs,
    timeout_s=4
)
async def tool_show_win_toast(title: str, message: str) -> dict[str, Any]:
    platform.show_toast(title, message)
    return {}
