"""
text_processor.py
负责文本读取、自适应编码检测、HTML标签容错与文本清洗归一化
"""
import os
import re
import html
import unicodedata

class TextProcessor:
    """文本处理类：提供文件读取、编码检测、字符过滤与归一化功能"""

    SUPPORTED_ENCODINGS = ['utf-8', 'utf-8-sig', 'gb18030', 'gbk', 'big5', 'utf-16']

    @classmethod
    def read_file(cls, file_path: str) -> str:
        """
        读取文件内容，自动尝试常见中文与 Unicode 编码。
        若文件为保存的网页 HTML，能够自动剔除标签提取纯文本内容。
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")
        if os.path.isdir(file_path):
            raise IsADirectoryError(f"指定的路径是目录而不是文件: {file_path}")

        with open(file_path, 'rb') as f:
            raw_bytes = f.read()

        if not raw_bytes:
            return ""

        text = None
        for enc in cls.SUPPORTED_ENCODINGS:
            try:
                text = raw_bytes.decode(enc)
                break
            except (UnicodeDecodeError, LookupError):
                continue

        if text is None:
            text = raw_bytes.decode('utf-8', errors='replace')

        text = text.lstrip('\ufeff')

        if '<!DOCTYPE html>' in text or '<html' in text:
            inner_lines = re.findall(r'<td[^>]*class="[^"]*blob-code-inner[^"]*"[^>]*>(.*?)</td>', text)
            if inner_lines:
                clean_lines = [html.unescape(re.sub(r'<[^>]+>', '', line)) for line in inner_lines]
                text = '\n'.join(clean_lines)
            else:
                text = html.unescape(re.sub(r'<[^>]+>', '', text))

        return text

    @classmethod
    def normalize(cls, text: str) -> str:
        """
        对文本进行清洗与归一化：
        1. NFKC 统一全角/半角符号
        2. 统一英文字母为小写
        3. 仅保留中文汉字、英文字母及阿拉伯数字，去除标点、空白和特殊控制字符
        """
        if not text:
            return ""

        text = unicodedata.normalize('NFKC', text)
        text = text.lower()
        cleaned_chars = re.findall(r'[\u4e00-\u9fa5a-z0-9]', text)
        return "".join(cleaned_chars)
