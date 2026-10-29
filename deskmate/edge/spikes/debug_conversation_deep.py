"""DeskMate Edge - 对话接口深度探测脚本
测试不同的 deviceId、hardware 大小写、Query 参数
"""

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

edge_dir = Path(__file__).resolve().parent.parent
token_file = edge_dir / ".mi.token"

with open(token_file, "r", encoding="utf-8") as f:
    token_data = json.load(f)

user_id = str(token_data.get("userId", ""))
login_device_id = str(token_data.get("deviceId", "")) # IDIUCHNJW5XQB6PJ
service_token = token_data.get("micoapi", ["", ""])[1]
speaker_device_id = "f91bfdb1-8b3a-427b-8a47-ce85269c6ca1"

# 测试矩阵
tests = [
    # 组合 1：Cookie 用音箱真实 deviceID
    (
        "Cookie 使用音箱 deviceID",
        "https://userprofile.mina.mi.com/device_profile/v2/conversation?source=dialogu&hardware=L05C&limit=10",
        f"deviceId={speaker_device_id}; userId={user_id}; serviceToken={service_token}"
    ),
    # 组合 2：URL 带 deviceId 参数
    (
        "URL Query 带 deviceId 参数",
        f"https://userprofile.mina.mi.com/device_profile/v2/conversation?source=dialogu&hardware=L05C&deviceId={speaker_device_id}&limit=10",
        f"deviceId={login_device_id}; userId={user_id}; serviceToken={service_token}"
    ),
    # 组合 3：小写 l05c
    (
        "Hardware 小写 l05c",
        "https://userprofile.mina.mi.com/device_profile/v2/conversation?source=dialogu&hardware=l05c&limit=10",
        f"deviceId={login_device_id}; userId={user_id}; serviceToken={service_token}"
    ),
    # 组合 4：api2.mina.mi.com 对话接口
    (
        "api2 域名",
        "https://api2.mina.mi.com/device_profile/v2/conversation?source=dialogu&hardware=L05C&limit=10",
        f"deviceId={login_device_id}; userId={user_id}; serviceToken={service_token}"
    ),
    # 组合 5：不带 hardware 并在 Cookie 中指定音箱 deviceId
    (
        "不带 hardware + 音箱 deviceId",
        "https://userprofile.mina.mi.com/device_profile/v2/conversation?source=dialogu&limit=10",
        f"deviceId={speaker_device_id}; userId={user_id}; serviceToken={service_token}"
    ),
]

print("=== 深度诊断各种设备参数与 Cookie 组合 ===\n")
for label, url, cookie in tests:
    print(f"[{label}]")
    headers = {"User-Agent": "MISpeaker/1.0", "Cookie": cookie}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            raw = resp.read().decode("utf-8")
            data = json.loads(raw)
            code = data.get("code")
            payload = data.get("data", "")
            if isinstance(payload, str) and payload.startswith("{"):
                p_obj = json.loads(payload)
                rec_len = len(p_obj.get("records", []))
                print(f"   -> HTTP 200, code={code}, records 数量: {rec_len}")
                if rec_len > 0:
                    first = p_obj['records'][0]
                    print(f"   🎉 成功抓到对话: '{first.get('query')}' (时间: {first.get('time')})")
            else:
                print(f"   -> HTTP 200, data: {payload[:150]}")
    except urllib.error.HTTPError as e:
        print(f"   -> HTTP 错误 {e.code}: {e.read().decode('utf-8', errors='ignore')[:150]}")
    except Exception as e:
        print(f"   -> 异常: {e}")
    print()
