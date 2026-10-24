"""
密钥加密辅助命令行工具 (API Key Encryption CLI)
用法:
    python3 smart_agent/utils/encrypt_key.py
    或传入参数:
    python3 smart_agent/utils/encrypt_key.py <YOUR_BAIDU_AK>
"""

import sys
import getpass
from pathlib import Path

# 确保项目根目录在 sys.path 中
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from smart_agent.utils.security import encrypt_token, decrypt_token


def main():
    print("=" * 60)
    print("TravelAgent 旧版可逆混淆转换器（不可用于保护公开仓库中的真实 Key）")
    print("=" * 60)
    print("仅用于兼容旧格式。任何人都能从公开算法恢复内容，不提供保密能力。")
    print("请优先使用 BAIDU_MAPS_AK 环境变量；不要把真实凭据或转换结果提交仓库。\n")

    if len(sys.argv) > 1:
        raw_key = sys.argv[1].strip()
    else:
        try:
            raw_key = getpass.getpass("请输入待转换内容（不回显）: ").strip()
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

    print("\n转换完成（可逆，不能公开提交）:")
    print("-" * 60)
    print(cipher)
    print("-" * 60)
    print("\n使用方法:")
    print("旧版兼容：仅在本机设置 ENCRYPTED_BAIDU_AK 环境变量，不要修改源码默认值。")
    print("推荐方式：本机设置 BAIDU_MAPS_AK 环境变量。")
    print("=" * 60)


if __name__ == "__main__":
    main()
