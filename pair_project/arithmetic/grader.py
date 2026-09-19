"""Grading engine for comparing student answers against exercise calculations.
"""

from fractions import Fraction
from pathlib import Path
from typing import List, Tuple

from arithmetic.errors import FileOperationError
from arithmetic.parser import (
    extract_line_index_and_body,
    parse_expression,
    parse_number_token,
)


def format_grade_report(correct: List[int], wrong: List[int]) -> str:
    """Format the grading result for Grade.txt.

    Example format:
        Correct: 5 (1, 3, 5, 7, 9)
        Wrong: 5 (2, 4, 6, 8, 10)
    """
    correct_nums = ", ".join(str(x) for x in correct)
    wrong_nums = ", ".join(str(x) for x in wrong)

    correct_line = f"Correct: {len(correct)} ({correct_nums})"
    wrong_line = f"Wrong: {len(wrong)} ({wrong_nums})"

    return f"{correct_line}\n{wrong_line}\n"


def grade_text_content(exercises_content: str, answers_content: str) -> Tuple[List[int], List[int]]:
    """Grade exercises and answers from string content.

    Returns:
        (correct_indices, wrong_indices)
    """
    ex_lines = [line.strip() for line in exercises_content.strip().splitlines() if line.strip()]
    ans_lines = [line.strip() for line in answers_content.strip().splitlines() if line.strip()]

    if len(ex_lines) != len(ans_lines):
        raise FileOperationError(
            f"Exercise count ({len(ex_lines)}) does not match answer count ({len(ans_lines)})"
        )

    correct: List[int] = []
    wrong: List[int] = []

    for ex_line, ans_line in zip(ex_lines, ans_lines):
        idx_ex, body_ex = extract_line_index_and_body(ex_line)
        idx_ans, body_ans = extract_line_index_and_body(ans_line)

        if idx_ex != idx_ans:
            raise FileOperationError(
                f"Question index mismatch between exercises ({idx_ex}) and answers ({idx_ans})"
            )

        # Remove trailing '=' from exercise if present
        if body_ex.endswith("="):
            body_ex = body_ex[:-1].strip()

        expr = parse_expression(body_ex)
        true_val = expr.evaluate()
        given_val = parse_number_token(body_ans)

        if true_val == given_val:
            correct.append(idx_ex)
        else:
            wrong.append(idx_ex)

    return correct, wrong


def grade_files(
    exercise_file: Path,
    answer_file: Path,
    grade_file: Path,
) -> Tuple[List[int], List[int]]:
    """Read exercises and answers from disk, grade them, and write Grade.txt."""
    if not exercise_file.is_file():
        raise FileOperationError(f"Exercise file not found: {exercise_file}")
    if not answer_file.is_file():
        raise FileOperationError(f"Answer file not found: {answer_file}")

    try:
        ex_content = exercise_file.read_text(encoding="utf-8")
    except Exception as err:
        raise FileOperationError(f"Failed to read exercise file: {err}") from err

    try:
        ans_content = answer_file.read_text(encoding="utf-8")
    except Exception as err:
        raise FileOperationError(f"Failed to read answer file: {err}") from err

    correct, wrong = grade_text_content(ex_content, ans_content)
    report = format_grade_report(correct, wrong)

    try:
        grade_file.write_text(report, encoding="utf-8")
    except Exception as err:
        raise FileOperationError(f"Failed to write grade file: {err}") from err

    return correct, wrong
