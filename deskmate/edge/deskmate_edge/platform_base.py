"""DeskMate Edge 操作系统平台抽象接口 (platform_base.py)
定义桌面、窗口编排、键鼠监控与系统交互的标准接口规范
使 Windows 原生实现与 Mock 虚拟实现解耦
"""

from abc import ABC, abstractmethod
from typing import Any


class PlatformBase(ABC):
    """操作系统抽象基类"""

    @abstractmethod
    def set_dpi_awareness(self) -> None:
        """设置高分屏 DPI 感知，消除缩放坐标偏移"""
        pass

    @abstractmethod
    def get_open_windows(self) -> list[dict[str, Any]]:
        """获取当前可见窗口列表 [{"title": str, "process": str, "rect": [x, y, w, h]}]"""
        pass

    @abstractmethod
    def arrange_windows(self, layout: str, custom: dict[str, Any] | None = None) -> int:
        """规整排列窗口，返回规整成功的窗口数量"""
        pass

    @abstractmethod
    def take_screenshot(self, target: str = "screen", max_side: int = 1280) -> dict[str, str]:
        """截屏或抓取桌面最新图片，返回 {"image_b64": str, "mime": "image/jpeg"}"""
        pass

    @abstractmethod
    def read_clipboard(self) -> str:
        """读取剪贴板文本"""
        pass

    @abstractmethod
    def write_clipboard(self, text: str) -> None:
        """写入文本至系统剪贴板"""
        pass

    @abstractmethod
    def show_toast(self, title: str, message: str) -> None:
        """弹出系统右下角通知气泡"""
        pass

    @abstractmethod
    def open_app(self, name: str) -> str:
        """启动白名单内的应用程序"""
        pass

    @abstractmethod
    def open_folder(self, path: str, in_vscode: bool = False) -> str:
        """打开文件夹（资源管理器或 VS Code）"""
        pass

    @abstractmethod
    def open_url(self, url: str) -> None:
        """打开浏览器网址"""
        pass

    @abstractmethod
    def find_files(self, keyword: str, directory: str | None = None, limit: int = 5) -> list[dict[str, Any]]:
        """查找文件"""
        pass
