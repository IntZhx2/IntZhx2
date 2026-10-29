"""DeskMate Edge - A-02/A-03 全链路真机联动探针 (Full Voice & Hardware Loop)
打通小爱语音输入抓取 -> 智能响应 -> 台灯专注光 -> 红外开空调 -> 电脑弹出 VS Code
已加入原生语音打断 (Interrupt) 与响应优先机制
"""

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

# 配置路径
edge_dir = Path(__file__).resolve().parent.parent
token_file = edge_dir / ".mi.token"
env_path = edge_dir / ".env"

if not token_file.exists():
    print(f"[错误] 未找到 Token 文件: {token_file}")
    exit(1)

with open(token_file, "r", encoding="utf-8") as f:
    token_data = json.load(f)

user_id = str(token_data.get("userId", ""))
service_token = token_data.get("micoapi", ["", ""])[1]

# 关键：Cookie 必须使用音箱本机的 DeviceID
speaker_device_id = "f91bfdb1-8b3a-427b-8a47-ce85269c6ca1"
hardware = "L05C"

# Home Assistant 配置与实体
ha_token = ""
ha_url = "http://127.0.0.1:8123"
speaker_media_player = "media_player.xiaomi_cn_567257618_l05c"
lamp_entity = "light.yeelink_cn_313523278_lamp4_s_2_light"
notify_tts = "notify.xiaomi_cn_567257618_l05c_play_text_a_5_3"
notify_directive = "notify.xiaomi_cn_567257618_l05c_execute_text_directive_a_5_4"

if env_path.exists():
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("HA_TOKEN="):
                ha_token = line.split("=", 1)[1].strip()
            elif line.startswith("HA_URL="):
                ha_url = line.split("=", 1)[1].strip()
            elif line.startswith("SPEAKER_DEVICE_ID="):
                speaker_device_id = line.split("=", 1)[1].strip()


def ha_post(endpoint: str, payload: dict):
    """调用 Home Assistant REST API 服务"""
    if not ha_token:
        return
    url = f"{ha_url.rstrip('/')}/{endpoint.lstrip('/')}"
    headers = {
        "Authorization": f"Bearer {ha_token}",
        "Content-Type": "application/json",
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=6) as resp:
            content = resp.read().decode("utf-8")
            return json.loads(content) if content else {}
    except Exception as e:
        print(f"   [HA 请求异常] {endpoint}: {e}")


def execute_study_scene():
    """触发场景 1：专注工作台闭环联动（优先打断与发声）"""
    print("\n   🚀 >>> 触发场景 1：专注工作台联动执行中 <<<")

    # 0. 毫秒打断小爱原生声音（截断小爱自带的“没听懂”提示音）
    ha_post("api/services/media_player/media_stop", {
        "entity_id": speaker_media_player
    })

    # 1. 优先发送 DeskMate 自定义语音播报（抢占音频输出通道）
    print("   [1/4 动作] 小爱音箱播报回应...")
    ha_post("api/services/notify/send_message", {
        "entity_id": notify_tts,
        "message": "工作台已配置就绪，台灯切入专注模式，空调调到26度，加油！",
    })

    # 2. 台灯渐亮至冷白专注光 (4000K, 80% 亮度)
    print("   [2/4 动作] 台灯切入专注模式 (4000K 冷白光, 80% 亮度)...")
    ha_post("api/services/light/turn_on", {
        "entity_id": lamp_entity,
        "brightness": 204,
        "color_temp_kelvin": 4000,
    })

    # 3. 小爱音箱发送红外遥控开空调 (26℃)
    print("   [3/4 动作] 音箱下发红外指令：把空调调到26度...")
    ha_post("api/services/notify/send_message", {
        "entity_id": notify_directive,
        "message": '["把空调调到26度", false]',
    })

    # 4. 电脑端自动打开当前工程 VS Code
    print("   [4/4 动作] Windows 屏幕唤醒并打开工程工作区...")
    try:
        project_dir = str(Path(__file__).resolve().parent.parent.parent)
        subprocess.Popen(f'code "{project_dir}"', shell=True)
        print("   -> 已调起 VS Code 窗口。")
    except Exception as e:
        print(f"   -> 调起应用异常: {e}")

    print("   ✅ 全链路联动完成！\n")


def get_latest_conversation(limit: int = 5) -> list[dict]:
    """通过小米官方接口拉取用户对话历史记录"""
    ts = int(time.time() * 1000)
    url = f"https://userprofile.mina.mi.com/device_profile/v2/conversation?source=dialogu&hardware={hardware}&timestamp={ts}&limit={limit}"
    
    cookie_str = f"deviceId={speaker_device_id}; userId={user_id}; serviceToken={service_token}"
    headers = {
        "User-Agent": "MISpeaker/1.0",
        "Cookie": cookie_str,
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("code") == 0:
                payload_str = data.get("data", "{}")
                return json.loads(payload_str).get("records", [])
    except Exception:
        pass
    return []


def main():
    print("============================================================")
    print("  DeskMate 贾维斯桌面智能体 - 软硬件全链路真机演示系统")
    print("============================================================")
    print(f"用户ID: {user_id} | 音箱型号: {hardware}")
    print(f"监听通道: https://userprofile.mina.mi.com (轮询周期 1.2s)")
    print(f"控制中枢: Home Assistant ({ha_url})\n")

    print("正在拉取最新基准对话...")
    init_records = get_latest_conversation(limit=1)
    last_timestamp = 0
    if init_records:
        r = init_records[0]
        last_timestamp = r.get("time", 0)
        query = r.get("query", "")
        timestr = time.strftime("%H:%M:%S", time.localtime(last_timestamp/1000))
        print(f"[连接成功] 上一条历史对话: \"{query}\" (时间: {timestr})")
    else:
        last_timestamp = int(time.time() * 1000)

    print("\n-----------------------------------------------------------")
    print("【系统已处于待命状态】")
    print("请对着小爱音箱说：")
    print("   👉 “小爱同学，我要开始写作业了，帮我准备一下”")
    print("-----------------------------------------------------------\n")

    try:
        while True:
            records = get_latest_conversation(limit=3)
            for r in records:
                msg_time = r.get("time", 0)
                if msg_time > last_timestamp:
                    last_timestamp = msg_time
                    query = r.get("query", "").strip()
                    timestr = time.strftime("%H:%M:%S", time.localtime(msg_time / 1000))
                    
                    print(f"\n[🎤 捕获语音输入 - {timestr}]")
                    print(f"   你说: \"{query}\"")

                    # 关键词匹配触发闭环动作
                    if any(kw in query for kw in ["写作业", "学习", "大作业", "工作台", "准备", "专注"]):
                        execute_study_scene()

            time.sleep(1.2)
    except KeyboardInterrupt:
        print("\n\n已退出监听。")


if __name__ == "__main__":
    main()
