"""
旧版凭据 XOR 混淆格式兼容工具。
固定种子和算法均公开，任何人均可还原内容；这不是安全加密或密钥存储。
混淆结果仍是敏感凭据，不应提交到仓库。部署时应使用环境变量或专用秘密管理服务。
"""

import base64
import hashlib
# 保留固定种子以兼容已有数据；它不是秘密密钥。
_SALT_SEED = b"GDUT-CS-TravelAgent-Sec2026-SafeKeyVault-SaltSeed"


def _derive_keystream(length: int) -> bytes:
    """根据确定性伪随机流生成等长异或密钥流"""
    stream = bytearray()
    counter = 0
    while len(stream) < length:
        h = hashlib.sha256(_SALT_SEED + counter.to_bytes(4, "big")).digest()
        stream.extend(h)
        counter += 1
    return bytes(stream[:length])


def encrypt_token(plain_text: str) -> str:
    """
    将文本编码为可逆的旧版 XOR 混淆格式，不提供保密性。
    MD5 截断值仅用于检测意外损坏，不提供防篡改保证。
    """
    if not plain_text or not plain_text.strip():
        return ""
    data = plain_text.strip().encode("utf-8")
    key = _derive_keystream(len(data))
    xored = bytes(b ^ k for b, k in zip(data, key))
    chk = hashlib.md5(data).digest()[:4]
    payload = chk + xored
    return base64.b85encode(payload).decode("ascii")


def decrypt_token(cipher_text: str) -> str:
    """
    还原旧版 XOR 混淆文本；格式损坏或校验失败时返回空字符串。
    """
    if not cipher_text or not cipher_text.strip():
        return ""
    try:
        raw = base64.b85decode(cipher_text.strip().encode("ascii"))
        if len(raw) <= 4:
            return ""
        chk = raw[:4]
        xored = raw[4:]
        key = _derive_keystream(len(xored))
        data = bytes(b ^ k for b, k in zip(xored, key))
        if hashlib.md5(data).digest()[:4] != chk:
            return ""
        return data.decode("utf-8")
    except Exception:
        return ""


class SafeKeyVault:
    """旧版兼容名称；仅包装可逆混淆，不是安全保险箱。"""

    @classmethod
    def encrypt_key(cls, plain_text: str) -> str:
        """以旧版格式混淆凭据，不提供安全加密。"""
        return encrypt_token(plain_text)

    @classmethod
    def decrypt_key(cls, cipher_text: str) -> str:
        """还原旧版混淆凭据。"""
        return decrypt_token(cipher_text)
