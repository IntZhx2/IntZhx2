"""DeskMate Edge Windows 键鼠统计与在座活动采集 (input_monitor.py)
无摄像头疲劳检测特征源
严格遵循隐私底线：严禁保存/上传任何具体按键字符内容，仅在后台维护无状态自增计数器
每 60 秒汇总打包为标准 InputMinute 数据包
"""

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Callable
from ..protocol import InputMinute

logger = logging.getLogger("deskmate_edge.input_monitor")

# 分类字典
STUDY_PROCESSES = {"code.exe", "idea64.exe", "pycharm64.exe", "typora.exe", "obsidian.exe", "devenv.exe"}
ENTERTAINMENT_KEYWORDS = {"bilibili", "douyin", "weibo", "steam.exe", "cloudmusic.exe", "genshin"}


class InputActivityMonitor:
    """Windows 键鼠活动率后台监听器"""

    def __init__(self, on_minute_callback: Callable[[dict], None] | None = None, on_session_callback: Callable[[bool], None] | None = None):
        self.on_minute_callback = on_minute_callback
        self.on_session_callback = on_session_callback

        # 内部统计计数器（每分钟重置）
        self._lock = threading.Lock()
        self._keys_count = 0
        self._clicks_count = 0
        self._scrolls_count = 0
        self._app_switches = 0
        self._active_seconds_set = set() # 记录哪几秒有活动

        self._last_front_process = ""
        self._current_front_process = "explorer.exe"
        self._current_category = "study"

        self._running = False
        self._poll_thread: threading.Thread | None = None
        self._keyboard_listener = None
        self._mouse_listener = None

    def start(self):
        """启动后台监听线程"""
        self._running = True

        # 1. 尝试挂载 pynput 监听钩子
        try:
            from pynput import keyboard, mouse

            def on_press(key):
                # 隐私底线：忽略 key 的具体内容，仅累加击键总次数
                with self._lock:
                    self._keys_count += 1
                    sec = int(time.time())
                    self._active_seconds_set.add(sec)

            def on_click(x, y, button, pressed):
                if pressed:
                    with self._lock:
                        self._clicks_count += 1
                        sec = int(time.time())
                        self._active_seconds_set.add(sec)

            def on_scroll(x, y, dx, dy):
                with self._lock:
                    self._scrolls_count += 1
                    sec = int(time.time())
                    self._active_seconds_set.add(sec)

            self._keyboard_listener = keyboard.Listener(on_press=on_press)
            self._mouse_listener = mouse.Listener(on_click=on_click, on_scroll=on_scroll)
            self._keyboard_listener.daemon = True
            self._mouse_listener.daemon = True
            self._keyboard_listener.start()
            self._mouse_listener.start()
            logger.info("pynput 键鼠活跃度监听器已在后台启动（隐私保护已启用：无按键内容记录）")
        except Exception as e:
            logger.warning(f"启动 pynput 键鼠监听失败 (可能在无显示环境): {e}")

        # 2. 启动 60 秒打包及前台窗口检测轮询线程
        self._poll_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._poll_thread.start()

    def stop(self):
        """停止监听"""
        self._running = False
        if self._keyboard_listener:
            self._keyboard_listener.stop()
        if self._mouse_listener:
            self._mouse_listener.stop()

    def _get_front_window_info(self) -> tuple[str, str]:
        """获取前台窗口进程名与分类"""
        try:
            import win32gui
            import win32process
            import psutil

            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return "unknown", "other"
            title = win32gui.GetWindowText(hwnd).lower()
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            proc_name = psutil.Process(pid).name()
            proc_lower = proc_name.lower()

            category = "other"
            if proc_lower in STUDY_PROCESSES:
                category = "study"
            elif any(kw in title for kw in ENTERTAINMENT_KEYWORDS) or any(kw in proc_lower for kw in ENTERTAINMENT_KEYWORDS):
                category = "entertainment"
            elif "chrome" in proc_lower or "msedge" in proc_lower:
                # 浏览器根据标题关键字二次推断
                if any(kw in title for kw in ("csdn", "github", "stackoverflow", "掘金", "文档", "edu", "cnblogs")):
                    category = "study"
                elif any(kw in title for kw in ("bilibili", "youtube", "爱奇艺", "微博", "知乎")):
                    category = "entertainment"

            return proc_name, category
        except Exception:
            return "explorer.exe", "study"

    def _monitor_loop(self):
        """每 1 秒检测前台窗口切换，每 60 秒汇总 InputMinute"""
        last_minute_time = time.time()

        while self._running:
            time.sleep(1.0)

            # 1. 监测前台窗口切换
            proc_name, category = self._get_front_window_info()
            if proc_name != self._current_front_process:
                with self._lock:
                    self._app_switches += 1
                self._current_front_process = proc_name
                self._current_category = category

            # 2. 是否到达 60 秒汇总周期
            now = time.time()
            if (now - last_minute_time) >= 60.0:
                last_minute_time = now
                minute_data = self._harvest_minute()
                logger.info(
                    f"[InputMinute] 敲击: {minute_data.keys} | 点击: {minute_data.clicks} | "
                    f"滚动: {minute_data.scrolls} | 活跃秒: {minute_data.active_seconds}s | "
                    f"速率: {minute_data.activity_rate}/min | 前台: {minute_data.front_process} ({minute_data.front_title_category})"
                )
                if self.on_minute_callback:
                    try:
                        self.on_minute_callback(minute_data.model_dump())
                    except Exception as e:
                        logger.error(f"回调推送 InputMinute 异常: {e}")

    def _harvest_minute(self) -> InputMinute:
        """打包并重置计数器"""
        with self._lock:
            keys = self._keys_count
            clicks = self._clicks_count
            scrolls = self._scrolls_count
            switches = self._app_switches
            active_sec = len(self._active_seconds_set)

            # 重置本周期计数
            self._keys_count = 0
            self._clicks_count = 0
            self._scrolls_count = 0
            self._app_switches = 0
            self._active_seconds_set.clear()

        # 计算综合活跃率 (按键 + 点击*0.8 + 滚轮*0.5)
        activity_rate = float(keys + clicks * 0.8 + scrolls * 0.5)
        iso_min = datetime.now(timezone.utc).astimezone().isoformat()

        return InputMinute(
            minute=iso_min,
            keys=keys,
            clicks=clicks,
            scrolls=scrolls,
            active_seconds=min(active_sec, 60),
            app_switches=switches,
            front_process=self._current_front_process,
            front_title_category=self._current_category,
            activity_rate=round(activity_rate, 1)
        )
