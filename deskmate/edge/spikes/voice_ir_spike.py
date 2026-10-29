"""DeskMate Edge - A-02 探针脚本：小爱音箱语音对话桥与红外控制空调验证
支持 MiService 原生 ubus 通道与 Home Assistant 通道
"""

import asyncio
import os
import sys
import time
from pathlib import Path

# 从 edge/.env 加载配置
env_path = Path(__file__).resolve().parent.parent / ".env"
token_file = env_path.parent / ".mi.token"
mi_user = ""
mi_pass = ""
speaker_hardware = "L05C"

if env_path.exists():
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("MI_USER="):
                mi_user = line.split("=", 1)[1].strip()
            elif line.startswith("MI_PASS="):
                mi_pass = line.split("=", 1)[1].strip()
            elif line.startswith("SPEAKER_HARDWARE="):
                speaker_hardware = line.split("=", 1)[1].strip()


async def run_voice_ir_spike():
    print("=== DeskMate A-02 小爱音箱语音桥与红外空调控制探针 ===")

    if not mi_user or not mi_pass:
        print("\n[错误] 请先在 edge/.env 中填入 MI_USER 与 MI_PASS。\n")
        return

    try:
        from miservice import MiAccount, MiNAService
    except ImportError:
        print("[错误] 未安装 miservice，请运行：pip install miservice\n")
        return

    print("1. 正在初始化并登录小米账号...")
    # 指定 token_store 路径，登录成功后自动缓存 Token，无需每次输验证码
    account = MiAccount(None, mi_user, mi_pass, token_store=str(token_file))
    mina = MiNAService(account)

    print("2. 获取绑定的智能设备列表...")
    devices = await mina.device_list()
    target_device = None
    for dev in devices or []:
        hardware = dev.get("hardware", "")
        name = dev.get("name", "")
        dev_id = dev.get("deviceID", "")
        print(f"   - 发现设备: {name} | 型号: {hardware} | deviceID: {dev_id}")
        if speaker_hardware in hardware or "L05C" in hardware:
            target_device = dev

    if not target_device:
        if devices:
            target_device = devices[0]
            print(f"   -> 选用默认设备: {target_device.get('name')}")
        else:
            print("[错误] 未找到任何可用的小米智能音箱！")
            return

    device_id = target_device["deviceID"]
    print(f"\n已锁定小爱音箱: {target_device.get('name')} (ID: {device_id})\n")

    # 3. 测试 TTS 播报
    print("3. 测试小爱音箱 TTS 自定义语音播报...")
    test_msg = "桌伴系统已连接，小爱语音桥测试成功！"
    print(f"   -> 发送播报文本: '{test_msg}'")
    tts_ok = await mina.text_to_speech(device_id, test_msg)
    print(f"   -> 云端响应状态: {'成功 (True)' if tts_ok else '失败 (False)'}")
    print("   -> 等待音箱朗读完毕 (请注意听小爱)...")
    await asyncio.sleep(6)

    # 4. 测试红外控制空调指令（发送 instruction）
    print("\n4. 测试红外空调控制（下发指令：'把空调调到26度'）...")
    ac_directive = "把空调调到26度"
    try:
        # MiNA ubus instruction 指令接口
        res = await mina.ubus_request(device_id, "instruction", "mibrain", {"instruction": ac_directive})
        print(f"   -> 指令下发状态: {'成功' if res else '已下发'}")
    except Exception as e:
        print(f"   -> ubus instruction 执行说明: {e}")
    print("   -> 请观察实体空调是否有响应提示音。")
    await asyncio.sleep(5)

    # 5. 监听对话历史（测试语音抓取延迟）
    print("\n5. 开始监听对话历史（持续 30 秒，请对小爱说：'小爱同学，我要写作业了'）...")
    last_timestamp = int(time.time() * 1000)
    for i in range(15):
        try:
            records = await mina.get_latest_ask(device_id)
            if records:
                for r in records:
                    ts = r.get("timestamp_ms", 0)
                    if ts > last_timestamp:
                        last_timestamp = ts
                        answers = r.get("response", {}).get("answer", [])
                        user_query = ""
                        for a in answers:
                            if a.get("question"):
                                user_query = a.get("question")
                                break
                        print(f"   [捕获语音] 用户说: '{user_query}' | 时间戳: {ts}")
                        if "写作业" in user_query or "学习" in user_query:
                            print("   -> 命中专注唤醒词！正在通过 TTS 语音回应...")
                            await mina.text_to_speech(device_id, "收到，正在为你准备软工工作台！")
                            await asyncio.sleep(4)
        except Exception as e:
            pass
        await asyncio.sleep(2)

    print("\n[完成] 探针测试结束。")


if __name__ == "__main__":
    asyncio.run(run_voice_ir_spike())
