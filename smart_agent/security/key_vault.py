"""
旧版 SafeKeyVault 导入兼容层；可逆混淆不提供安全保密能力。
适配 smart_agent/security/key_vault.py 模块路径，代理调用底层动态混淆加密引擎。
"""

from smart_agent.utils.security import SafeKeyVault, encrypt_token, decrypt_token

__all__ = ["SafeKeyVault", "encrypt_token", "decrypt_token"]
