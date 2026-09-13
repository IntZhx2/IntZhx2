"""
similarity_checker.py
核心论文查重算法：基于 2-gram 滑动窗口特征、SimHash 指纹（MD5 加权降维）与余弦相似度融合
"""
import math
import hashlib
from collections import Counter
from typing import Counter as CounterType

class SimilarityChecker:
    """相似度计算器"""

    def __init__(self, ngram_size: int = 2, hash_bits: int = 64):
        self.ngram_size = ngram_size
        self.hash_bits = hash_bits

    def extract_ngrams(self, text: str) -> CounterType[str]:
        """
        提取 n-gram 特征频次表
        若文本长度小于 n-gram 大小，则退化为 1-gram（单字符频次）
        """
        if not text:
            return Counter()

        length = len(text)
        if length < self.ngram_size:
            return Counter(text)

        shingles = [text[i:i + self.ngram_size] for i in range(length - self.ngram_size + 1)]
        return Counter(shingles)

    def compute_simhash(self, ngram_counts: CounterType[str]) -> int:
        """
        计算 64 位 SimHash 文本指纹：
        1. 对每个特征计算 MD5 哈希
        2. 根据词频加权累加各位权重向量
        3. 降维输出 64 位二进制指纹整数
        """
        if not ngram_counts:
            return 0

        vector = [0] * self.hash_bits

        for shingle, weight in ngram_counts.items():
            md5_digest = hashlib.md5(shingle.encode('utf-8')).hexdigest()
            hash_val = int(md5_digest[:16], 16)

            for bit in range(self.hash_bits):
                if (hash_val >> bit) & 1:
                    vector[bit] += weight
                else:
                    vector[bit] -= weight

        fingerprint = 0
        for bit in range(self.hash_bits):
            if vector[bit] > 0:
                fingerprint |= (1 << bit)

        return fingerprint

    def hamming_distance(self, hash1: int, hash2: int) -> int:
        """计算两个 64 位哈希的海明距离（异或后 1 的个数）"""
        return bin(hash1 ^ hash2).count('1')

    def compute_cosine(self, c1: CounterType[str], c2: CounterType[str], common_keys: set) -> float:
        """计算两个频次 Counter 的余弦相似度"""
        if not common_keys:
            return 0.0

        dot_product = sum(c1[k] * c2[k] for k in common_keys)
        norm1 = math.sqrt(sum(v * v for v in c1.values()))
        norm2 = math.sqrt(sum(v * v for v in c2.values()))

        if norm1 == 0.0 or norm2 == 0.0:
            return 0.0

        return dot_product / (norm1 * norm2)

    def calculate_similarity(self, norm_orig: str, norm_suspect: str) -> float:
        """
        计算两篇已归一化文本的综合重复率：
        - 双方完全一致（含双方皆空）：返回 1.00
        - 单方为空：返回 0.00
        - 无任何共有特征：返回 0.00
        - 常规文本：结合 SimHash 海明距离与 2-gram 余弦相似度加权得出
        """
        # 边界 1：文本完全相同
        if norm_orig == norm_suspect:
            return 1.0

        # 边界 2：其中一方为空
        if not norm_orig or not norm_suspect:
            return 0.0

        # 提取 n-gram 特征
        c_orig = self.extract_ngrams(norm_orig)
        c_suspect = self.extract_ngrams(norm_suspect)

        # 检查特征交集：无任何共同词/字符则完全无关
        common_keys = c_orig.keys() & c_suspect.keys()
        if not common_keys:
            return 0.0

        # 计算 SimHash 相似度
        h_orig = self.compute_simhash(c_orig)
        h_suspect = self.compute_simhash(c_suspect)
        dist = self.hamming_distance(h_orig, h_suspect)
        simhash_sim = 1.0 - (dist / float(self.hash_bits))

        # 计算余弦相似度
        cosine_sim = self.compute_cosine(c_orig, c_suspect, common_keys)

        # 融合加权：兼顾全局指纹分布与局部词汇匹配
        final_sim = 0.50 * simhash_sim + 0.50 * cosine_sim

        # 特征重合比例微调（防止特征重合度极低时 SimHash 偶合偏高）
        overlap_ratio = len(common_keys) / max(len(c_orig), len(c_suspect))
        if overlap_ratio < 0.15:
            final_sim *= (overlap_ratio / 0.15)

        return max(0.0, min(1.0, final_sim))
