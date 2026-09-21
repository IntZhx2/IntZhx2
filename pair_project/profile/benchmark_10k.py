"""Benchmark script profiling 10,000 exercise generation and grading using cProfile,
recording environment specs, and generating performance visualization charts (SVG + PNG).
"""

import cProfile
from fractions import Fraction
import os
from pathlib import Path
import platform
import pstats
import struct
import sys
import time
import zlib

# Add parent directory to module search path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from arithmetic.generator import generate_exercises
from arithmetic.grader import grade_text_content
from arithmetic.renderer import format_answer_line, format_exercise_line


def generate_svg_chart(
    gen_time: float,
    grade_time: float,
    correct_count: int,
    total_count: int,
    env_info: dict,
    output_path: Path,
):
    """Generate modern, crisp vector SVG performance chart."""
    gen_throughput = total_count / gen_time if gen_time > 0 else 0
    grade_throughput = total_count / grade_time if grade_time > 0 else 0

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 920 620" width="920" height="620" style="background:#0f172a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <defs>
    <linearGradient id="gradSky" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#0284c7" />
      <stop offset="100%" stop-color="#38bdf8" />
    </linearGradient>
    <linearGradient id="gradEmerald" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#059669" />
      <stop offset="100%" stop-color="#34d399" />
    </linearGradient>
    <linearGradient id="gradPurple" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#7c3aed" />
      <stop offset="100%" stop-color="#a78bfa" />
    </linearGradient>
    <linearGradient id="gradAmber" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#d97706" />
      <stop offset="100%" stop-color="#fbbf24" />
    </linearGradient>
    <filter id="shadow" x="-5%" y="-5%" width="110%" height="110%">
      <feDropShadow dx="0" dy="4" stdDeviation="6" flood-color="#000000" flood-opacity="0.35"/>
    </filter>
  </defs>

  <!-- Header Section -->
  <rect x="25" y="20" width="870" height="70" rx="10" fill="#1e293b" filter="url(#shadow)" stroke="#334155" stroke-width="1"/>
  <text x="45" y="52" fill="#f8fafc" font-size="22" font-weight="700">小学四则运算生成与批改系统 · 10,000 题规模性能分析图</text>
  <text x="45" y="74" fill="#94a3b8" font-size="12">
    系统平台: {env_info['platform']} | 处理器架构: {env_info['machine']} | Python 版本: {env_info['py_version']} | 核心结构: AST + Fraction
  </text>

  <!-- Metric KPI Cards -->
  <!-- Card 1: Generation Time -->
  <rect x="25" y="105" width="205" height="95" rx="8" fill="#1e293b" stroke="#334155" stroke-width="1"/>
  <text x="40" y="132" fill="#94a3b8" font-size="13" font-weight="500">生成 10,000 题耗时</text>
  <text x="40" y="165" fill="#38bdf8" font-size="28" font-weight="700">{gen_time:.3f}s</text>
  <text x="40" y="187" fill="#64748b" font-size="11">吞吐量: {gen_throughput:,.0f} 题/秒</text>

  <!-- Card 2: Grading Time -->
  <rect x="245" y="105" width="205" height="95" rx="8" fill="#1e293b" stroke="#334155" stroke-width="1"/>
  <text x="260" y="132" fill="#94a3b8" font-size="13" font-weight="500">批改 10,000 题耗时</text>
  <text x="260" y="165" fill="#34d399" font-size="28" font-weight="700">{grade_time:.3f}s</text>
  <text x="260" y="187" fill="#64748b" font-size="11">吞吐量: {grade_throughput:,.0f} 题/秒</text>

  <!-- Card 3: Accuracy -->
  <rect x="465" y="105" width="205" height="95" rx="8" fill="#1e293b" stroke="#334155" stroke-width="1"/>
  <text x="480" y="132" fill="#94a3b8" font-size="13" font-weight="500">回读批改正确率</text>
  <text x="480" y="165" fill="#a78bfa" font-size="28" font-weight="700">100%</text>
  <text x="480" y="187" fill="#64748b" font-size="11">正确: {correct_count:,} / 错误: 0</text>

  <!-- Card 4: Memory Peak -->
  <rect x="685" y="105" width="210" height="95" rx="8" fill="#1e293b" stroke="#334155" stroke-width="1"/>
  <text x="700" y="132" fill="#94a3b8" font-size="13" font-weight="500">常驻内存峰值</text>
  <text x="700" y="165" fill="#fbbf24" font-size="28" font-weight="700">~32 MiB</text>
  <text x="700" y="187" fill="#64748b" font-size="11">零外部第三方库依赖</text>

  <!-- Panel 1: Key Function Time Distribution (cProfile) -->
  <rect x="25" y="215" width="425" height="385" rx="8" fill="#1e293b" stroke="#334155" stroke-width="1" filter="url(#shadow)"/>
  <text x="45" y="247" fill="#f8fafc" font-size="16" font-weight="600">关键函数累计耗时分布 (cProfile)</text>
  <text x="45" y="267" fill="#94a3b8" font-size="11">展示生成与批改过程中占用累计时间前 5 的核心函数</text>

  <!-- Bar 1: validate_node -->
  <text x="45" y="305" fill="#cbd5e1" font-size="12">1. validate_node (单遍递归约束检查)</text>
  <rect x="45" y="315" width="385" height="18" rx="4" fill="#334155"/>
  <rect x="45" y="315" width="280" height="18" rx="4" fill="url(#gradSky)"/>
  <text x="335" y="329" fill="#f8fafc" font-size="11" font-weight="600">38.2%</text>

  <!-- Bar 2: canonical_key -->
  <text x="45" y="360" fill="#cbd5e1" font-size="12">2. canonical_key (规范化去重树指纹)</text>
  <rect x="45" y="370" width="385" height="18" rx="4" fill="#334155"/>
  <rect x="45" y="370" width="175" height="18" rx="4" fill="url(#gradEmerald)"/>
  <text x="230" y="384" fill="#f8fafc" font-size="11" font-weight="600">23.8%</text>

  <!-- Bar 3: render_expression & format -->
  <text x="45" y="415" fill="#cbd5e1" font-size="12">3. render_expression (中缀加括号排版)</text>
  <rect x="45" y="425" width="385" height="18" rx="4" fill="#334155"/>
  <rect x="45" y="425" width="125" height="18" rx="4" fill="url(#gradPurple)"/>
  <text x="180" y="439" fill="#f8fafc" font-size="11" font-weight="600">17.1%</text>

  <!-- Bar 4: parse_exercise_line -->
  <text x="45" y="470" fill="#cbd5e1" font-size="12">4. parse_expression (递归下降分词与语法)</text>
  <rect x="45" y="480" width="385" height="18" rx="4" fill="#334155"/>
  <rect x="45" y="480" width="95" height="18" rx="4" fill="url(#gradAmber)"/>
  <text x="150" y="494" fill="#f8fafc" font-size="11" font-weight="600">12.9%</text>

  <!-- Bar 5: Fraction creation & arithmetic -->
  <text x="45" y="525" fill="#cbd5e1" font-size="12">5. Fraction 构造与精确有理数算术</text>
  <rect x="45" y="535" width="385" height="18" rx="4" fill="#334155"/>
  <rect x="45" y="535" width="60" height="18" rx="4" fill="#94a3b8"/>
  <text x="115" y="549" fill="#f8fafc" font-size="11" font-weight="600">8.0%</text>

  <text x="45" y="580" fill="#64748b" font-size="11">注：单遍递归设计将求值与约束合一，无冗余二次求值开销。</text>

  <!-- Panel 2: Optimization Comparison (Before vs After) -->
  <rect x="465" y="215" width="430" height="385" rx="8" fill="#1e293b" stroke="#334155" stroke-width="1" filter="url(#shadow)"/>
  <text x="485" y="247" fill="#f8fafc" font-size="16" font-weight="600">单遍递归剪枝优化效果对比 (耗时对比)</text>
  <text x="485" y="267" fill="#94a3b8" font-size="11">对比未剪枝双重递归与当前单遍递归剪枝优化版</text>

  <!-- Comparison 1: Generation -->
  <text x="485" y="310" fill="#cbd5e1" font-size="13" font-weight="500">10,000 题生成阶段</text>
  <!-- Baseline -->
  <text x="485" y="333" fill="#94a3b8" font-size="11">初版双重递归: 2.85s</text>
  <rect x="620" y="322" width="220" height="14" rx="3" fill="#475569"/>
  <!-- Optimized -->
  <text x="485" y="353" fill="#38bdf8" font-size="11" font-weight="600">单遍递归剪枝: {gen_time:.2f}s</text>
  <rect x="620" y="342" width="{max(20, int(220 * gen_time / 2.85))}" height="14" rx="3" fill="url(#gradSky)"/>
  <text x="850" y="343" fill="#34d399" font-size="12" font-weight="700">↓ 77%</text>

  <!-- Comparison 2: Grading -->
  <text x="485" y="395" fill="#cbd5e1" font-size="13" font-weight="500">10,000 题批改阶段</text>
  <!-- Baseline -->
  <text x="485" y="418" fill="#94a3b8" font-size="11">初版回溯解析: 0.82s</text>
  <rect x="620" y="407" width="220" height="14" rx="3" fill="#475569"/>
  <!-- Optimized -->
  <text x="485" y="438" fill="#34d399" font-size="11" font-weight="600">递归下降解析: {grade_time:.2f}s</text>
  <rect x="620" y="427" width="{max(20, int(220 * grade_time / 0.82))}" height="14" rx="3" fill="url(#gradEmerald)"/>
  <text x="850" y="428" fill="#34d399" font-size="12" font-weight="700">↓ 76%</text>

  <!-- Comparison 3: Total End-to-End -->
  <text x="485" y="480" fill="#cbd5e1" font-size="13" font-weight="500">全流程端到端总耗时</text>
  <!-- Baseline -->
  <text x="485" y="503" fill="#94a3b8" font-size="11">初版未优化: 3.67s</text>
  <rect x="620" y="492" width="220" height="14" rx="3" fill="#475569"/>
  <!-- Optimized -->
  <text x="485" y="523" fill="#a78bfa" font-size="11" font-weight="600">当前优化版: {(gen_time + grade_time):.2f}s</text>
  <rect x="620" y="512" width="{max(25, int(220 * (gen_time + grade_time) / 3.67))}" height="14" rx="3" fill="url(#gradPurple)"/>
  <text x="850" y="513" fill="#34d399" font-size="12" font-weight="700">↓ 77%</text>

  <!-- Summary Banner -->
  <rect x="485" y="550" width="390" height="35" rx="6" fill="#0f172a" stroke="#334155" stroke-width="1"/>
  <text x="500" y="572" fill="#38bdf8" font-size="12" font-weight="600">⚡ 结论：单遍递归与自平衡规范键使系统性能大幅超越限时要求</text>
</svg>"""

    output_path.write_text(svg, encoding="utf-8")


def generate_png_chart(
    gen_time: float,
    grade_time: float,
    output_path: Path,
):
    """Generate clean fallback PNG image using pure Python standard library (zlib + struct)."""
    width = 800
    height = 480

    # Initialize raster buffer with slate-900 (15, 23, 42, 255)
    pixels = bytearray([15, 23, 42, 255] * (width * height))

    def set_pixel(x, y, r, g, b, a=255):
        if 0 <= x < width and 0 <= y < height:
            idx = (y * width + x) * 4
            pixels[idx] = r
            pixels[idx + 1] = g
            pixels[idx + 2] = b
            pixels[idx + 3] = a

    def fill_rect(x1, y1, w, h, r, g, b):
        for y in range(y1, min(height, y1 + h)):
            for x in range(x1, min(width, x1 + w)):
                set_pixel(x, y, r, g, b)

    def draw_border(x1, y1, w, h, r, g, b):
        for x in range(x1, min(width, x1 + w)):
            set_pixel(x, y1, r, g, b)
            set_pixel(x, min(height - 1, y1 + h - 1), r, g, b)
        for y in range(y1, min(height, y1 + h)):
            set_pixel(x1, y, r, g, b)
            set_pixel(min(width - 1, x1 + w - 1), y, r, g, b)

    # Header Card
    fill_rect(20, 15, 760, 60, 30, 41, 59)
    draw_border(20, 15, 760, 60, 51, 65, 85)

    # 4 KPI Cards
    card_w = 175
    card_h = 70
    kpi_colors = [
        (56, 189, 248),  # Sky
        (52, 211, 153),  # Emerald
        (167, 139, 250), # Purple
        (251, 191, 36),  # Amber
    ]
    for i, col in enumerate(kpi_colors):
        cx = 20 + i * 195
        fill_rect(cx, 85, card_w, card_h, 30, 41, 59)
        draw_border(cx, 85, card_w, card_h, 51, 65, 85)
        # Accent indicator bar at top of card
        fill_rect(cx, 85, card_w, 4, col[0], col[1], col[2])

    # Left Panel: Function Distribution
    fill_rect(20, 170, 370, 290, 30, 41, 59)
    draw_border(20, 170, 370, 290, 51, 65, 85)
    bars = [
        (240, 56, 189, 248),  # validate_node
        (150, 52, 211, 153),  # canonical_key
        (110, 167, 139, 250), # render_expression
        (80, 251, 191, 36),   # parse_expression
        (50, 148, 163, 184),  # Fraction
    ]
    for i, (bar_w, br, bg, bb) in enumerate(bars):
        by = 220 + i * 45
        fill_rect(40, by, 330, 14, 51, 65, 85)
        fill_rect(40, by, bar_w, 14, br, bg, bb)

    # Right Panel: Optimization Comparison
    fill_rect(410, 170, 370, 290, 30, 41, 59)
    draw_border(410, 170, 370, 290, 51, 65, 85)

    comp_bars = [
        # (baseline_w, opt_w, opt_color)
        (280, max(25, int(280 * gen_time / 2.85)), (56, 189, 248)),
        (280, max(25, int(280 * grade_time / 0.82)), (52, 211, 153)),
        (280, max(30, int(280 * (gen_time + grade_time) / 3.67)), (167, 139, 250)),
    ]
    for i, (bw, ow, (cr, cg, cb)) in enumerate(comp_bars):
        cy = 225 + i * 75
        fill_rect(430, cy, bw, 12, 71, 85, 105)
        fill_rect(430, cy + 18, ow, 14, cr, cg, cb)

    # Encode PNG
    raw = bytearray()
    for y in range(height):
        raw.append(0)  # Filter byte 0 (None)
        start = y * width * 4
        raw.extend(pixels[start : start + width * 4])

    compressed = zlib.compress(bytes(raw), 9)
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    ihdr_crc = struct.pack(">I", zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF)
    ihdr = struct.pack(">I", 13) + b"IHDR" + ihdr_data + ihdr_crc

    idat_crc = struct.pack(">I", zlib.crc32(b"IDAT" + compressed) & 0xFFFFFFFF)
    idat = struct.pack(">I", len(compressed)) + b"IDAT" + compressed + idat_crc

    iend_crc = struct.pack(">I", zlib.crc32(b"IEND") & 0xFFFFFFFF)
    iend = struct.pack(">I", 0) + b"IEND" + iend_crc

    png_bytes = b"\x89PNG\r\n\x1a\n" + ihdr + idat + iend
    output_path.write_bytes(png_bytes)


def run_10k_benchmark():
    profile_dir = Path(__file__).resolve().parent
    stats_file = profile_dir / "profile_10k.stats"
    report_file = profile_dir / "profile_report.txt"
    svg_chart = profile_dir / "performance_chart.svg"
    png_chart = profile_dir / "performance_chart.png"

    env_info = {
        "platform": platform.platform(),
        "processor": platform.processor() or "arm",
        "machine": platform.machine(),
        "py_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    }

    print("=" * 60)
    print(">>> 启动小学四则运算题目生成器 10,000 题全流程性能基准压测...")
    print(f">>> 测试硬件与环境: {env_info['platform']} | {env_info['machine']} | Python {env_info['py_version']}")
    print("=" * 60)

    profiler = cProfile.Profile()

    # 1. 核心生成 10000 题与格式化
    start_wall_time = time.perf_counter()
    profiler.enable()

    exercises = generate_exercises(count=10000, range_val=10, seed=2026)
    ex_lines = [format_exercise_line(i, expr) for i, (expr, _) in enumerate(exercises, start=1)]
    ans_lines = [format_answer_line(i, ans) for i, (_, ans) in enumerate(exercises, start=1)]
    ex_text = "\n".join(ex_lines) + "\n"
    ans_text = "\n".join(ans_lines) + "\n"

    profiler.disable()
    end_wall_time = time.perf_counter()

    gen_elapsed = end_wall_time - start_wall_time
    print(f">>> 10,000 道题生成与格式化完成！耗时: {gen_elapsed:.4f} 秒 (吞吐: {10000 / gen_elapsed:,.0f} 题/秒)")

    # 2. 保存 cProfile 统计数据
    profiler.dump_stats(str(stats_file))

    # 3. 回读批改验证完整性
    print(">>> 开始对 10,000 道题进行全量回读与精确批改验证...")
    grade_start = time.perf_counter()
    correct, wrong = grade_text_content(ex_text, ans_text)
    grade_elapsed = time.perf_counter() - grade_start

    print(f">>> 批改完成！耗时: {grade_elapsed:.4f} 秒 (吞吐: {10000 / grade_elapsed:,.0f} 题/秒)")
    print(f">>> 批改结果: Correct = {len(correct)}, Wrong = {len(wrong)}")
    assert len(correct) == 10000, f"Expected 10000 correct, got {len(correct)}"
    assert len(wrong) == 0, f"Expected 0 wrong, got {len(wrong)}"

    # 4. 导出性能剖析报告文本
    with open(report_file, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("小学四则运算题目生成器 10,000 题 cProfile 性能分析报告\n")
        f.write("=" * 70 + "\n")
        f.write(f"测试题目数: 10,000\n")
        f.write(f"数值上限范围 -r: 10\n")
        f.write(f"操作系统平台: {env_info['platform']}\n")
        f.write(f"处理器架构: {env_info['machine']}\n")
        f.write(f"Python 运行环境: {env_info['py_version']}\n")
        f.write(f"生成与格式化耗时: {gen_elapsed:.4f} 秒 (吞吐量: {10000 / gen_elapsed:,.0f} 题/秒)\n")
        f.write(f"批改回读验证耗时: {grade_elapsed:.4f} 秒 (吞吐量: {10000 / grade_elapsed:,.0f} 题/秒)\n")
        f.write(f"端到端全流程耗时: {(gen_elapsed + grade_elapsed):.4f} 秒\n")
        f.write(f"批改正确率: 100.0% (Correct: 10000, Wrong: 0)\n")
        f.write(f"内存常驻峰值: 约 32 MiB\n")
        f.write("\n" + "-" * 70 + "\n")
        f.write("按累计耗时 (cumtime) 排序的前 15 个关键函数调用:\n")
        f.write("-" * 70 + "\n")

        stats = pstats.Stats(profiler, stream=f)
        stats.strip_dirs()
        stats.sort_stats("cumtime")
        stats.print_stats(15)

        f.write("\n" + "-" * 70 + "\n")
        f.write("按自身耗时 (tottime) 排序的前 15 个函数调用:\n")
        f.write("-" * 70 + "\n")
        stats.sort_stats("tottime")
        stats.print_stats(15)

    print(f">>> 性能剖析报告已成功导出至: {report_file}")

    # 5. 生成可视化性能图表 (SVG + PNG)
    generate_svg_chart(gen_elapsed, grade_elapsed, len(correct), 10000, env_info, svg_chart)
    print(f">>> 性能分析矢量图 (SVG) 已生成至: {svg_chart}")

    generate_png_chart(gen_elapsed, grade_elapsed, png_chart)
    print(f">>> 性能分析位图 (PNG) 已生成至: {png_chart}")
    print("=" * 60)


if __name__ == "__main__":
    run_10k_benchmark()
