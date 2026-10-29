"""DeskMate Edge - 对话接口诊断脚本 (Debug Conversation API)
打印云端返回的完整原始数据，排查 records 为空的原因
"""

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

edge_dir = Path(__file__).resolve().parent.parent
token_file = edge_dir / ".mi.token"

if not token_file.exists():
    print("未找到 .mi.token 文件")
    exit(1)

with open(token_file, "r", encoding="utf-8") as f:
    token_data = json.load(f)

user_id = str(token_data.get("userId", ""))
device_id = str(token_data.get("deviceId", ""))
pass_token = str(token_data.get("passToken", ""))
service_token = token_data.get("micoapi", ["", ""])[1]

cookie_str = f"deviceId={device_id}; userId={user_id}; serviceToken={service_token}"
headers = {"User-Agent": "MISpeaker/1.0", "Cookie": cookie_str}

test_urls = [
    # 1. 默认带 hardware 与 timestamp
    ("带 hardware 与当前时间戳", f"https://userprofile.mina.mi.com/device_profile/v2/conversation?source=dialogu&hardware=L05C&timestamp={int(time.time()*1000)}&limit=5"),
    # 2. 不带 timestamp
    ("不带时间戳（直接拉取最新）", "https://userprofile.mina.mi.com/device_profile/v2/conversation?source=dialogu&hardware=L05C&limit=5"),
    # 3. 不带 hardware
    ("不带 hardware", f"https://userprofile.mina.mi.com/device_profile/v2/conversation?source=dialogu&limit=5"),
]

print("=== 开始测试小米云端对话接口各种参数组合 ===\n")
for label, url in test_urls:
    print(f"--- 测试: {label} ---")
    print(f"URL: {url}")
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read().decode("utf-8")
            print(f"返回结果 (前 300 字符): {content[:300]}")
            data = json.loads(content)
            if "data" in data and isinstance(data["data"], str):
                inner = json.loads(data["data"])
                records = inner.get("records", [])
                print(f"解析到 records 数量: {len(records)}")
                if records:
                    for i, r in enumerate(records[:3]):
                        print(f"  [{i+1}] 问: {r.get('query')} | 答: {r.get('answers', [{}])[0].get('tts', {}).get('text', '')[:20] if r.get('answers') else '无'}")
            elif "data" in data and isinstance(data["data"], dict):
                records = data["data"].get("records", [])
                print(f"解析到 records (dict) 数量: {len(records)}")
    except Exception as e:
        print(f"请求失败: {e}")
    print()
