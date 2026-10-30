"""DeskMate Edge Windows 原生操作系统实现 (platform_win)
调用 Windows Win32 API、mss、pynput、pyperclip 实现桌面窗口编排、高分屏 DPI 感知与系统交互
"""

import base64
import ctypes
import io
import logging
import os
import subprocess
import time
import webbrowser
from pathlib import Path
from typing import Any
import mss
from PIL import Image
import pyperclip
from ..platform_base import PlatformBase

logger = logging.getLogger("deskmate_edge.platform_win")

# 应用白名单（防止恶意执行）
APP_WHITELIST = {
    "code": "Code.exe",
    "vscode": "Code.exe",
    "chrome": "chrome.exe",
    "edge": "msedge.exe",
    "notepad": "notepad.exe",
    "explorer": "explorer.exe",
    "typora": "Typora.exe",
    "obsidian": "Obsidian.exe"
}


class WindowsPlatform(PlatformBase):
    """Windows 原生平台实现"""

    def set_dpi_awareness(self) -> None:
        """解决 Windows 高分屏 (125%/150%/200%) 缩放导致窗口物理像素坐标偏移"""
        try:
            # Per-monitor DPI aware V2 (Win 10 1703+)
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
            logger.info("已成功启用 Per-Monitor V2 DPI 感知")
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
                logger.info("已启用基础 DPI 感知")
            except Exception as e:
                logger.warning(f"设置 DPI 感知失败: {e}")

    def get_open_windows(self) -> list[dict[str, Any]]:
        """遍历所有前台可见窗口"""
        import win32gui
        import win32process
        import psutil

        windows: list[dict[str, Any]] = []

        def enum_cb(hwnd: int, extra: Any):
            if win32gui.IsWindowVisible(hwnd) and not win32gui.IsIconic(hwnd):
                title = win32gui.GetWindowText(hwnd).strip()
                if title:
                    try:
                        _, pid = win32process.GetWindowThreadProcessId(hwnd)
                        proc_name = psutil.Process(pid).name()
                        rect = win32gui.GetWindowRect(hwnd) # (left, top, right, bottom)
                        w = rect[2] - rect[0]
                        h = rect[3] - rect[1]
                        if w > 100 and h > 100: # 过滤极小微件
                            windows.append({
                                "hwnd": hwnd,
                                "title": title,
                                "process": proc_name,
                                "rect": [rect[0], rect[1], w, h]
                            })
                    except Exception:
                        pass
            return True

        win32gui.EnumWindows(enum_cb, None)
        return windows

    def arrange_windows(self, layout: str, custom: dict[str, Any] | None = None) -> int:
        """窗口排布（如 VS Code 左 60% / Chrome 浏览器右 40% 分屏）"""
        import win32gui
        import win32con
        import win32api

        screen_w = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
        screen_h = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
        # 预留底部任务栏（通常约 48px）
        usable_h = screen_h - 48

        open_wins = self.get_open_windows()
        arranged_count = 0

        if layout == "code_left_browser_right":
            vscode_hwnd = None
            browser_hwnd = None

            for w in open_wins:
                proc = w["process"].lower()
                hwnd = w["hwnd"]
                if "code" in proc and not vscode_hwnd:
                    vscode_hwnd = hwnd
                elif ("chrome" in proc or "msedge" in proc or "firefox" in proc) and not browser_hwnd:
                    browser_hwnd = hwnd

            # 左侧 60%
            left_w = int(screen_w * 0.6)
            if vscode_hwnd:
                win32gui.ShowWindow(vscode_hwnd, win32con.SW_RESTORE)
                win32gui.SetWindowPos(
                    vscode_hwnd, win32con.HWND_TOP,
                    0, 0, left_w, usable_h,
                    win32con.SWP_SHOWWINDOW
                )
                arranged_count += 1

            # 右侧 40%
            if browser_hwnd:
                right_w = screen_w - left_w
                win32gui.ShowWindow(browser_hwnd, win32con.SW_RESTORE)
                win32gui.SetWindowPos(
                    browser_hwnd, win32con.HWND_TOP,
                    left_w, 0, right_w, usable_h,
                    win32con.SWP_SHOWWINDOW
                )
                arranged_count += 1

        elif layout == "split_half":
            half_w = screen_w // 2
            if len(open_wins) >= 2:
                for idx, w in enumerate(open_wins[:2]):
                    hwnd = w["hwnd"]
                    x = 0 if idx == 0 else half_w
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                    win32gui.SetWindowPos(
                        hwnd, win32con.HWND_TOP,
                        x, 0, half_w, usable_h,
                        win32con.SWP_SHOWWINDOW
                    )
                    arranged_count += 1

        elif layout == "maximize":
            if open_wins:
                top_hwnd = open_wins[0]["hwnd"]
                win32gui.ShowWindow(top_hwnd, win32con.SW_MAXIMIZE)
                arranged_count = 1

        return arranged_count

    def take_screenshot(self, target: str = "screen", max_side: int = 1280) -> dict[str, str]:
        """抓取主屏幕或桌面最新图片，自动等比压缩至长边 ≤ 1280px 并转为 JPEG base64"""
        img: Image.Image | None = None

        if target == "latest_desktop_file":
            desktop_path = Path.home() / "Desktop"
            image_files = []
            now = time.time()
            for ext in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
                for p in desktop_path.glob(ext):
                    # 10 分钟内创建的文件
                    if (now - p.stat().st_mtime) < 600:
                        image_files.append((p.stat().st_mtime, p))
            if image_files:
                image_files.sort(key=lambda x: x[0], reverse=True)
                latest_p = image_files[0][1]
                logger.info(f"读取到桌面最新截图: {latest_p}")
                img = Image.open(latest_p)

        # 默认回退到主屏幕截屏
        if img is None:
            with mss.mss() as sct:
                monitor = sct.monitors[1]  # 主显示器
                shot = sct.grab(monitor)
                img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")

        # 等比缩放
        w, h = img.size
        if max(w, h) > max_side:
            scale = max_side / float(max(w, h))
            img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)

        # 转为 JPEG Base64
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        return {"image_b64": b64, "mime": "image/jpeg"}

    def read_clipboard(self) -> str:
        return pyperclip.paste() or ""

    def write_clipboard(self, text: str) -> None:
        pyperclip.copy(text)

    def show_toast(self, title: str, message: str) -> None:
        """调用 Windows PowerShell 发送原生通知"""
        ps_cmd = f"""
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
        $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
        $textNodes = $template.GetElementsByTagName("text")
        $textNodes.Item(0).AppendChild($template.CreateTextNode("{title}")) > $null
        $textNodes.Item(1).AppendChild($template.CreateTextNode("{message}")) > $null
        $notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("DeskMate")
        $notification = [Windows.UI.Notifications.ToastNotification]::new($template)
        $notifier.Show($notification)
        """
        try:
            subprocess.Popen(["powershell", "-NoProfile", "-Command", ps_cmd], creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception as e:
            logger.warning(f"发送系统通知异常: {e}")

    def open_app(self, name: str) -> str:
        key = name.strip().lower()
        exe = APP_WHITELIST.get(key)
        if not exe:
            raise PermissionError(f"应用 '{name}' 不在白名单中")
        subprocess.Popen(exe, shell=True)
        return exe

    def open_folder(self, path: str, in_vscode: bool = False) -> str:
        p = Path(path).resolve()
        if not p.exists():
            raise FileNotFoundError(f"目录不存在: {p}")
        if in_vscode:
            subprocess.Popen(f'code "{p}"', shell=True)
            return f"code {p}"
        else:
            os.startfile(str(p))
            return f"explorer {p}"

    def open_url(self, url: str) -> None:
        webbrowser.open(url)

    def find_files(self, keyword: str, directory: str | None = None, limit: int = 5) -> list[dict[str, Any]]:
        target_dir = Path(directory).resolve() if directory else (Path.home() / "Desktop")
        if not target_dir.exists():
            target_dir = Path.home()

        matches = []
        for p in target_dir.rglob(f"*{keyword}*"):
            matches.append({
                "path": str(p),
                "name": p.name,
                "is_dir": p.is_dir()
            })
            if len(matches) >= limit:
                break
        return matches
