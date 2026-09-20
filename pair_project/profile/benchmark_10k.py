"""Benchmark script profiling 10,000 exercise generation and grading using cProfile.
"""

import cProfile
from fractions import Fraction
import os
from pathlib import Path
import pstats
import sys
import time

# Add parent directory to module search path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from arithmetic.generator import generate_exercises
from arithmetic.grader import grade_text_content
from arithmetic.renderer import format_answer_line, format_exercise_line


def run_10k_benchmark():
    profile_dir = Path(__file__).resolve().parent
    stats_file = profile_dir / "profile_10k.stats"
    report_file = profile_dir / "profile_report.txt"

    print(">>> 开始执行 10,000 道题目大规模生成性能压测...")
    profiler = cProfile.Profile()

    start_wall_time = time.perf_counter()
    profiler.enable()

    # 1. 核心生成 10000 题
    exercises = generate_exercises(count=10000, range_val=10, seed=2026)

    # 2. 格式化输出
    ex_lines = [format_exercise_line(i, expr) for i, (expr, _) in enumerate(exercises, start=1)]
    ans_lines = [format_answer_line(i, ans) for i, (_, ans) in enumerate(exercises, start=1)]
    ex_text = "\n".join(ex_lines) + "\n"
    ans_text = "\n".join(ans_lines) + "\n"

    profiler.disable()
    end_wall_time = time.perf_counter()

    elapsed = end_wall_time - start_wall_time
    print(f">>> 10,000 道题生成与格式化完成！耗时: {elapsed:.4f} 秒")

    # 3. 保存 cProfile 统计数据
    profiler.dump_stats(str(stats_file))

    # 4. 回读批改验证完整性
    print(">>> 开始对 10,000 道题进行全量回读与精确批改验证...")
    grade_start = time.perf_counter()
    correct, wrong = grade_text_content(ex_text, ans_text)
    grade_elapsed = time.perf_counter() - grade_start

    print(f">>> 批改完成！耗时: {grade_elapsed:.4f} 秒")
    print(f">>> 批改结果: Correct = {len(correct)}, Wrong = {len(wrong)}")
    assert len(correct) == 10000, f"Expected 10000 correct, got {len(correct)}"
    assert len(wrong) == 0, f"Expected 0 wrong, got {len(wrong)}"

    # 5. 分析生成报告
    with open(report_file, "w", encoding="utf-8") as f:
        f.write("=" * 60 + "\n")
        f.write("小学四则运算题目生成器 10,000 题 cProfile 性能分析报告\n")
        f.write("=" * 60 + "\n")
        f.write(f"测试题目数: 10,000\n")
        f.write(f"数值上限范围 -r: 10\n")
        f.write(f"生成与格式化墙钟耗时: {elapsed:.4f} 秒\n")
        f.write(f"批改回读验证墙钟耗时: {grade_elapsed:.4f} 秒\n")
        f.write(f"批改正确率: 100.0% (Correct: 10000, Wrong: 0)\n")
        f.write("\n" + "-" * 60 + "\n")
        f.write("按累计耗时 (cumtime) 排序的前 15 个关键函数调用:\n")
        f.write("-" * 60 + "\n")

        stats = pstats.Stats(profiler, stream=f)
        stats.strip_dirs()
        stats.sort_stats("cumtime")
        stats.print_stats(15)

        f.write("\n" + "-" * 60 + "\n")
        f.write("按自身耗时 (tottime) 排序的前 15 个函数调用:\n")
        f.write("-" * 60 + "\n")
        stats.sort_stats("tottime")
        stats.print_stats(15)

    print(f">>> 性能剖析报告已成功导出至: {report_file}")


if __name__ == "__main__":
    run_10k_benchmark()
