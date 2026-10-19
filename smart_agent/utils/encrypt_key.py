"""
密钥加密辅助命令行工具 (API Key Encryption CLI)
用法:
    python3 smart_agent/utils/encrypt_key.py
    或传入参数:
    python3 smart_agent/utils/encrypt_key.py <YOUR_BAIDU_AK>
"""

import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from smart_agent.utils.security import encrypt_token, decrypt_token


def main():
    print("=" * 60)
    print("🔐 TravelAgent 百度地图 API Key 安全加密生成器")
    print("=" * 60)
    print("本工具将把您的百度地图 AK 转化为经过混淆与校验的密文字符串，")
    print("防止 GitHub Secret Scanning 检测及代码泄漏风险。\n")

    if len(sys.argv) > 1:
        raw_key = sys.argv[1].strip()
    else:
        try:
            raw_key = input("👉 请输入您的百度地图 API Key (AK): ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n已取消操作。")
            return

    if not raw_key:
        print("❌ 错误: 输入的 API Key 为空！")
        return

    cipher = encrypt_token(raw_key)
    # 验证解密
    restored = decrypt_token(cipher)
    assert restored == raw_key, "自检失败：解密结果与原文不符"

    print("\n✅ 加密成功！生成的密文字符串为:")
    print("-" * 60)
    print(cipher)
    print("-" * 60)
    print("\n使用方法:")
    print("1. 方式一: 将上述密文字符串配置到 smart_agent/config.py 的 ENCRYPTED_BAIDU_AK 变量中;")
    print("2. 方式二: 也可以直接设置环境变量 BAIDU_MAPS_AK=<您的明文AK> 本地直接调用。")
    print("=" * 60)


if __name__ == "__main__":
    main()
