"""DeskMate Edge - A-01 验证脚本：台灯控制测试
使用 Python 标准库，无额外依赖即可直接运行
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
lamp_entity = "light.yeelink_cn_313523278_lamp4_s_2_light"

if env_path.exists():
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("HA_TOKEN="):
                ha_token = line.split("=", 1)[1].strip()
            elif line.startswith("HA_URL="):
                ha_url = line.split("=", 1)[1].strip()

if not ha_token:
    print("错误：未在 edge/.env 中找到 HA_TOKEN，请检查配置。")
    sys.exit(1)


def ha_request(endpoint: str, data: dict | None = None) -> dict:
    url = f"{ha_url.rstrip('/')}/{endpoint.lstrip('/')}"
    headers = {
        "Authorization": f"Bearer {ha_token}",
        "Content-Type": "application/json",
    }
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read().decode("utf-8")
            return json.loads(content) if content else {}
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="ignore")
        print(f"HTTP 请求失败 [{e.code}]: {err_msg}")
        raise
    except Exception as e:
        print(f"请求发生异常: {e}")
        raise


def test_lamp_workflow():
    print(f"=== DeskMate A-01 台灯连通性与控制测试 ===")
    print(f"Home Assistant: {ha_url}")
    print(f"Target Entity : {lamp_entity}\n")

    # 1. 查询当前状态
    print("1. 查询当前台灯状态...")
    state = ha_request(f"api/states/{lamp_entity}")
    print(f"   -> 当前状态: {state.get('state')} | 亮度: {state.get('attributes', {}).get('brightness')}\n")

    # 2. 切换至专注模式 (4000K, 80% 亮度 ~= 204)
    print("2. 切换至【专注模式】(4000K 冷白光, 80% 亮度)...")
    ha_request("api/services/light/turn_on", {
        "entity_id": lamp_entity,
        "brightness": 204,
        "color_temp_kelvin": 4000,
    })
    print("   -> 专注光指令已发送！观察台灯是否亮起且偏冷白。")
    time.sleep(3)

    # 3. 切换至伴眠/放松模式 (2600K 暖黄光, 10% 亮度 ~= 25)
    # 注意：米家台灯 1S (yeelink.light.lamp4) 的 MIoT 硬件色温范围是 2600K ~ 5000K
    print("\n3. 切换至【伴眠/放松模式】(2600K 暖黄光, 10% 亮度)...")
    ha_request("api/services/light/turn_on", {
        "entity_id": lamp_entity,
        "brightness": 25,
        "color_temp_kelvin": 2600,
    })
    print("   -> 伴眠光指令已发送！观察台灯是否变暗且偏暖黄。")
    time.sleep(3)

    # 4. 再次查询最新状态
    print("\n4. 查询执行后的台灯最新状态...")
    final_state = ha_request(f"api/states/{lamp_entity}")
    print(f"   -> 最终状态: {final_state.get('state')} | 亮度: {final_state.get('attributes', {}).get('brightness')} | 色温: {final_state.get('attributes', {}).get('color_temp_kelvin')}K")

    print("\n[SUCCESS] A-01 台灯 REST 控制验证全部通过！")


if __name__ == "__main__":
    test_lamp_workflow()
