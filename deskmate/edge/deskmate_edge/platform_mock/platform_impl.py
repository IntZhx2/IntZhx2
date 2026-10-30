"""DeskMate Edge 虚拟 Mock 平台实现 (platform_mock)
用于非 Windows 环境（macOS/Linux CI）或测试模式下的降级模拟
"""

import logging
from typing import Any
from ..platform_base import PlatformBase

logger = logging.getLogger("deskmate_edge.platform_mock")


class MockPlatform(PlatformBase):
    """虚拟降级操作系统实现"""

    def __init__(self):
        self._clipboard: str = ""

    def set_dpi_awareness(self) -> None:
        logger.info("[MockPlatform] 设置 DPI 感知 (Mock 无操作)")

    def get_open_windows(self) -> list[dict[str, Any]]:
        return [
            {"title": "Visual Studio Code - DeskMate", "process": "Code.exe", "rect": [0, 0, 1152, 1080]},
            {"title": "DeskMate Web Console - Google Chrome", "process": "chrome.exe", "rect": [1152, 0, 768, 1080]}
        ]

    def arrange_windows(self, layout: str, custom: dict[str, Any] | None = None) -> int:
        logger.info(f"[MockPlatform] 规整窗口布局: {layout}")
        return 2

    def take_screenshot(self, target: str = "screen", max_side: int = 1280) -> dict[str, str]:
        # 1x1 像素纯白 JPEG base64
        mock_b64 = "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////wgALCAABAAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA="
        return {"image_b64": mock_b64, "mime": "image/jpeg"}

    def read_clipboard(self) -> str:
        return self._clipboard

    def write_clipboard(self, text: str) -> None:
        self._clipboard = text
        logger.info(f"[MockPlatform] 剪贴板已写入: {text[:30]}...")

    def show_toast(self, title: str, message: str) -> None:
        logger.info(f"[MockPlatform Toast] {title}: {message}")

    def open_app(self, name: str) -> str:
        logger.info(f"[MockPlatform] 启动应用: {name}")
        return name

    def open_folder(self, path: str, in_vscode: bool = False) -> str:
        target = f"code {path}" if in_vscode else f"explorer {path}"
        logger.info(f"[MockPlatform] 打开目录: {target}")
        return path

    def open_url(self, url: str) -> None:
        logger.info(f"[MockPlatform] 打开网址: {url}")

    def find_files(self, keyword: str, directory: str | None = None, limit: int = 5) -> list[dict[str, Any]]:
        return [{"path": f"D:/Projects/{keyword}", "name": keyword, "is_dir": True}]
