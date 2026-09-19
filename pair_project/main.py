#!/usr/bin/env python3
"""小学四则运算题目生成器与批改系统命令行主入口。

使用方法:
  生成题目:
    python main.py -n <题目数量> -r <数值范围>
  批改题目:
    python main.py -e <题目文件> -a <答案文件>
"""

import argparse
from pathlib import Path
import sys

from arithmetic.errors import (
    ArithmeticAppError,
    CommandLineArgumentError,
)
from arithmetic.generator import generate_exercises
from arithmetic.grader import grade_files
from arithmetic.renderer import format_answer_line, format_exercise_line


def build_arg_parser() -> argparse.ArgumentParser:
    """Construct command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="小学四则运算题目自动生成与批改程序",
        add_help=True,
    )
    parser.add_argument(
        "-n",
        dest="count",
        type=int,
        help="生成题目的数量（正整数，必须支持 10000 道题）",
    )
    parser.add_argument(
        "-r",
        dest="range_val",
        type=int,
        help="题目中数值（自然数、真分数和分母）的数值上限（必须 >= 2）",
    )
    parser.add_argument(
        "-e",
        dest="exercise_file",
        type=str,
        help="待批改的题目文件路径（如 Exercises.txt）",
    )
    parser.add_argument(
        "-a",
        dest="answer_file",
        type=str,
        help="待批改的答案文件路径（如 Answers.txt）",
    )
    return parser


def run_generation(count: int, range_val: int, output_dir: Path) -> None:
    """Execute exercise generation mode."""
    if count <= 0:
        raise CommandLineArgumentError(f"题目数量 -n 必须大于 0，当前为: {count}")
    if range_val < 2:
        raise CommandLineArgumentError(f"数值范围 -r 必须大于等于 2，当前为: {range_val}")

    exercises = generate_exercises(count=count, range_val=range_val)

    exercise_lines = [
        format_exercise_line(i, expr) for i, (expr, _) in enumerate(exercises, start=1)
    ]
    answer_lines = [
        format_answer_line(i, ans) for i, (_, ans) in enumerate(exercises, start=1)
    ]

    ex_file = output_dir / "Exercises.txt"
    ans_file = output_dir / "Answers.txt"

    ex_file.write_text("\n".join(exercise_lines) + "\n", encoding="utf-8")
    ans_file.write_text("\n".join(answer_lines) + "\n", encoding="utf-8")


def run_grading(exercise_path: str, answer_path: str, output_dir: Path) -> None:
    """Execute grading mode."""
    ex_file = Path(exercise_path).resolve()
    ans_file = Path(answer_path).resolve()
    grade_file = output_dir / "Grade.txt"

    grade_files(ex_file, ans_file, grade_file)


def main() -> int:
    """Main application entry point."""
    parser = build_arg_parser()

    # If no arguments provided at all, print help and exit 1
    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        return 1

    args = parser.parse_args()

    has_gen = (args.count is not None) or (args.range_val is not None)
    has_grade = (args.exercise_file is not None) or (args.answer_file is not None)

    # Check mutual exclusivity
    if has_gen and has_grade:
        sys.stderr.write("错误: 不能混用生成模式 (-n, -r) 和批改模式 (-e, -a)。\n")
        return 1

    current_dir = Path.cwd()

    try:
        if has_gen:
            if args.range_val is None:
                sys.stderr.write("错误: 生成模式必须通过 -r 参数指定数值范围。\n")
                parser.print_help(sys.stderr)
                return 1
            count = args.count if args.count is not None else 10
            run_generation(count, args.range_val, current_dir)
            return 0

        if has_grade:
            if args.exercise_file is None or args.answer_file is None:
                sys.stderr.write("错误: 批改模式必须同时通过 -e 指定题目文件和 -a 指定答案文件。\n")
                parser.print_help(sys.stderr)
                return 1
            run_grading(args.exercise_file, args.answer_file, current_dir)
            return 0

        parser.print_help(sys.stderr)
        return 1

    except ArithmeticAppError as err:
        sys.stderr.write(f"业务逻辑错误: {err}\n")
        return 1
    except Exception as err:
        sys.stderr.write(f"运行发生异常: {err}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
