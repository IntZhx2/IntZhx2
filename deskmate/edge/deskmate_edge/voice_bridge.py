"""DeskMate Edge 小爱语音输入监听桥 (voice_bridge.py)
在后台持续轮询小米官方对话历史接口
捕获用户对小爱说出的语句，触发 voice.heard 契约事件并上报云端智能体
遵循 CONTRACTS.md §3.1 规范
"""

import asyncio
import json
import logging
import time
import urllib.request
from typing import Callable, Coroutine, Any
from pathlib import Path
from .config import settings, EDGE_ROOT

logger = logging.getLogger("deskmate_edge.voice_bridge")


class VoiceBridge:
    """小爱音箱语音监听桥"""

    def __init__(self, on_voice_heard: Callable[[str, int], Coroutine[Any, Any, None]] | None = None):
        self.on_voice_heard = on_voice_heard
        self._running = False
        self._task: asyncio.Task | None = None
        self._last_timestamp = 0

        self.token_file = EDGE_ROOT / ".mi.token"
        self.speaker_device_id = settings.SPEAKER_DEVICE_ID or "f91bfdb1-8b3a-427b-8a47-ce85269c6ca1"
        self.hardware = settings.SPEAKER_HARDWARE or "L05C"

    def _load_auth(self) -> tuple[str, str]:
        """读取认证信息：userId, serviceToken"""
        if not self.token_file.exists():
            return "", ""
        try:
            with open(self.token_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            uid = str(data.get("userId", ""))
            s_token = data.get("micoapi", ["", ""])[1]
            return uid, s_token
        except Exception:
            return "", ""

    def start(self):
        """启动后台轮询任务"""
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("小爱语音输入桥 (VoiceBridge) 已在后台启动")

    def stop(self):
        """停止轮询"""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None

    async def _poll_loop(self):
        """1.2 秒间隔异步轮询对话记录"""
        user_id, service_token = self._load_auth()
        if not user_id or not service_token:
            logger.warning("未检测到有效的 .mi.token 凭证，语音桥将以静默模式等待配置")
            return

        cookie_str = f"deviceId={self.speaker_device_id}; userId={user_id}; serviceToken={service_token}"
        headers = {"User-Agent": "MISpeaker/1.0", "Cookie": cookie_str}

        # 先拉取一条初始化最新时间戳
        self._last_timestamp = int(time.time() * 1000)

        while self._running:
            try:
                # 放在 executor 中执行阻塞式 HTTP 请求
                records = await asyncio.to_thread(self._fetch_records, headers)
                for r in records:
                    msg_time = r.get("time", 0)
                    if msg_time > self._last_timestamp:
                        self._last_timestamp = msg_time
                        query = r.get("query", "").strip()
                        if query:
                            logger.info(f"[小爱语音桥捕获] \"{query}\" (时间戳: {msg_time})")
                            if self.on_voice_heard:
                                await self.on_voice_heard(query, msg_time)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"轮询对话接口异常: {e}")

            await asyncio.sleep(1.2)

    def _fetch_records(self, headers: dict[str, str]) -> list[dict]:
        """同步发起 HTTP 请求"""
        ts = int(time.time() * 1000)
        url = f"https://userprofile.mina.mi.com/device_profile/v2/conversation?source=dialogu&hardware={self.hardware}&timestamp={ts}&limit=2"
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("code") == 0:
                    payload_str = data.get("data", "{}")
                    return json.loads(payload_str).get("records", [])
        except Exception:
            pass
        return []
