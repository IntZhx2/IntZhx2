"""
benchmark_profile.py
性能测试基准：构造 10 万~50 万字的大规模长文本，使用 cProfile 进行深度 CPU 性能采样
"""
import os
import sys
import cProfile
import pstats

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from text_processor import TextProcessor
from similarity_checker import SimilarityChecker

def generate_large_text(base_text: str, repeat_count: int = 40) -> tuple:
    """构造大规模长文本，包含增删改扰动"""
    text1 = (base_text + "，" + "这是一段用于压测论文查重系统性能的大规模段落数据。") * repeat_count
    # 模拟抄袭改写：每隔一定长度替换字符
    chars = list(text1)
    for i in range(0, len(chars), 15):
        chars[i] = '改'
    text2 = "".join(chars)
    return text1, text2

def run_benchmark():
    samples_dir = os.path.join(parent_dir, 'samples')
    orig_file = os.path.join(samples_dir, 'orig.txt')
    if os.path.exists(orig_file):
        base_text = TextProcessor.read_file(orig_file)
    else:
        base_text = "软件工程是一门研究用工程化方法构建和维护有效、实用和高质量的软件的学科。"

    print("正在构造大规模压测文本...")
    t1, t2 = generate_large_text(base_text, repeat_count=35)
    print(f"文本构造完毕：原文 {len(t1)} 字符，疑似文本 {len(t2)} 字符。")

    checker = SimilarityChecker()

    print("开始执行性能采样...")
    norm1 = TextProcessor.normalize(t1)
    norm2 = TextProcessor.normalize(t2)

    score = checker.calculate_similarity(norm1, norm2)
    print(f"计算完成！重复率: {score:.4f}")

if __name__ == '__main__':
    prof_file = os.path.join(current_dir, 'simhash_profile.prof')
    cProfile.run('run_benchmark()', prof_file)

    p = pstats.Stats(prof_file)
    p.strip_dirs().sort_stats('cumtime').print_stats(15)
