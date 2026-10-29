"""DeskMate Edge - A-02 小爱音箱与红外空调控制测试（基于 Home Assistant 官方通道）
利用已接入 HA 的 L05C 音箱进行稳定 TTS 播报与红外空调控制
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# 读取 .env 文件
env_path = Path(__file__).resolve().parent.parent / ".env"
ha_token = ""
ha_url = "http://127.0.0.1:8123"

# 设备实体
notify_tts = "notify.xiaomi_cn_567257618_l05c_play_text_a_5_3"
notify_directive = "notify.xiaomi_cn_567257618_l05c_execute_text_directive_a_5_4"

if env_path.exists():
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("HA_TOKEN="):
                ha_token = line.split("=", 1)[1].strip()
            elif line.startswith("HA_URL="):
                ha_url = line.split("=", 1)[1].strip()

if not ha_token:
    print("错误：未在 edge/.env 中找到 HA_TOKEN。")
    sys.exit(1)


def ha_send_notify(entity_id: str, message: str):
    url = f"{ha_url.rstrip('/')}/api/services/notify/send_message"
    headers = {
        "Authorization": f"Bearer {ha_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "entity_id": entity_id,
        "message": message,
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read().decode("utf-8")
            return json.loads(content) if content else {}
    except urllib.error.HTTPError as e:
        print(f"HTTP 请求失败 [{e.code}]: {e.read().decode('utf-8', errors='ignore')}")
        raise
    except Exception as e:
        print(f"请求异常: {e}")
        raise


def test_speaker_and_ac():
    print("=== DeskMate 小爱音箱与红外空调控制测试 (HA 官方通道) ===")
    print(f"TTS 实体: {notify_tts}")
    print(f"指令实体: {notify_directive}\n")

    # 1. 测试 TTS 播报
    print("1. 发送 TTS 自定义语音播报指令...")
    test_text = "桌伴系统已连接，小爱语音测试成功！"
    ha_send_notify(notify_tts, test_text)
    print(f"   -> 指令已下发，播放文本: '{test_text}'")
    print("   -> 等待小爱音箱发声播报（请听音箱）...")
    time.sleep(5)

    # 2. 测试红外控制空调指令
    print("\n2. 发送红外空调控制指令（下发文本指令）...")
    # xiaomi_home 官方规范：execute_text_directive 的 message 为 yaml 数组：["文本", silent: bool]
    ac_cmd = '["把空调调到26度", false]'
    ha_send_notify(notify_directive, ac_cmd)
    print("   -> 红外控制指令已发送：'把空调调到26度'")
    print("   -> 请观察小爱音箱红外发射以及实体空调是否有嘀嗒响应...")
    time.sleep(5)

    print("\n[SUCCESS] 测试指令全部下发完成！")


if __name__ == "__main__":
    test_speaker_and_ac()
