"""DeskMate Edge 平台工厂 (platform_factory.py)
自动根据系统平台与配置选择 Windows 原生平台或 Mock 虚拟平台
"""

import sys
from .platform_base import PlatformBase
from .config import settings


def get_platform(mock: bool | None = None) -> PlatformBase:
    """获取当前平台驱动单例"""
    use_mock = mock if mock is not None else settings.MOCK_MODE

    if not use_mock and sys.platform == "win32":
        try:
            from .platform_win.platform_impl import WindowsPlatform
            return WindowsPlatform()
        except ImportError:
            pass

    from .platform_mock.platform_impl import MockPlatform
    return MockPlatform()
