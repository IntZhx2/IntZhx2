"""DeskMate Edge 启动入口 (__main__.py)
命令行启动：python -m deskmate_edge [--mock]
负责初始化日志、启用 Windows DPI 感知、装载所有工具、启动键鼠监听、语音桥与长连接管道
"""

import argparse
import asyncio
from datetime import datetime, timezone
import logging
import sys
from .config import settings
from .platform_factory import get_platform
from .voice_bridge import VoiceBridge
from .ws_client import EdgeWsClient

# 配置根日志格式
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("deskmate_edge")


def parse_args():
    parser = argparse.ArgumentParser(description="DeskMate Windows Edge Service")
    parser.add_argument("--mock", action="store_true", help="以虚拟 Mock 模式运行（脱离真机环境）")
    return parser.parse_args()


async def main():
    args = parse_args()
    if args.mock:
        settings.MOCK_MODE = True
        logger.info("已显式开启 --mock 虚拟降级模式")

    logger.info("==================================================")
    logger.info("  DeskMate Edge 边缘端守护进程启动中...")
    logger.info("==================================================")

    # 1. 启动时设置 DPI 感知，消除高分屏坐标缩放偏移
    platform = get_platform()
    platform.set_dpi_awareness()

    # 2. 导入注册所有工具实现
    from .tools import desktop_tools, device_tools  # noqa: F401

    # 3. 创建 WebSocket 客户端
    client = EdgeWsClient()
    loop = asyncio.get_running_loop()

    # 4. 启动 A-12 键鼠活跃度与在座感知监听器 (无摄像头方案)
    monitor = None
    if not settings.MOCK_MODE and sys.platform == "win32":
        try:
            from .platform_win.input_monitor import InputActivityMonitor

            def on_minute(stats: dict):
                asyncio.run_coroutine_threadsafe(
                    client.send_event("pc.input_stats", stats),
                    loop
                )

            monitor = InputActivityMonitor(on_minute_callback=on_minute)
            monitor.start()
        except Exception as e:
            logger.warning(f"启动键鼠监听异常: {e}")

    # 5. 启动 A-02 小爱语音桥
    async def on_voice(text: str, timestamp_ms: int):
        iso_time = datetime.now(timezone.utc).astimezone().isoformat()
        await client.send_event("voice.heard", {
            "text": text,
            "heard_at": iso_time,
            "handled_by_edge": False
        })

    voice_bridge = VoiceBridge(on_voice_heard=on_voice)
    voice_bridge.start()

    # 6. 启动长连接主事件循环
    try:
        await client.start()
    except asyncio.CancelledError:
        logger.info("进程正在退出...")
    finally:
        if monitor:
            monitor.stop()
        voice_bridge.stop()
        await client.stop()
        logger.info("DeskMate Edge 进程已安全停止。")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n用户手动终止进程 (Ctrl+C)。")
        sys.exit(0)
