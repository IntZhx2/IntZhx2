"""
敏感密钥混淆与安全解密单元测试 (Security Key Vault Tests)
"""

import unittest
from smart_agent.utils.security import encrypt_token, decrypt_token


class TestSecurityKeyVault(unittest.TestCase):
    def test_encrypt_decrypt_roundtrip(self):
        plain_ak = "test_baidu_ak_random_token_1234567890abcdef"
        cipher = encrypt_token(plain_ak)
        self.assertTrue(cipher)
        self.assertNotEqual(cipher, plain_ak)
        # 确保密文中不包含原始 AK 特征片段
        self.assertNotIn("test_baidu_ak", cipher)

        # 解密还原
        restored = decrypt_token(cipher)
        self.assertEqual(restored, plain_ak)

    def test_empty_and_whitespace(self):
        self.assertEqual(encrypt_token(""), "")
        self.assertEqual(decrypt_token(""), "")
        self.assertEqual(encrypt_token("   "), "")

    def test_corrupted_cipher_safety(self):
        # 篡改密文不应抛出崩溃异常，应优雅返回空
        corrupted = "InvalidGarbageCipherString!@#"
        self.assertEqual(decrypt_token(corrupted), "")


if __name__ == "__main__":
    unittest.main()
