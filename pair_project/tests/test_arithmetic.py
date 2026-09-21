"""Comprehensive test suite for arithmetic generator and grader.
"""

from fractions import Fraction
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

# Ensure pair_project is in sys.path when running from any working directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from arithmetic.errors import (
    CommandLineArgumentError,
    ExpressionParseError,
    FileOperationError,
    GenerationExhaustedError,
)
from arithmetic.expression import (
    BinaryExpression,
    Number,
    canonical_key,
    normalize_operator,
)
from arithmetic.generator import (
    generate_exercises,
    random_operand,
    validate_node,
)
from arithmetic.grader import (
    format_grade_report,
    grade_files,
    grade_text_content,
)
from arithmetic.parser import (
    extract_line_index_and_body,
    parse_answer_line,
    parse_exercise_line,
    parse_expression,
    parse_number_token,
)
from arithmetic.renderer import (
    format_answer_line,
    format_exercise_line,
    format_value,
    render_expression,
)


class TestNumberAndEvaluation(unittest.TestCase):
    """Test Number node, Fraction precision, and basic evaluation."""

    def test_integer_number(self):
        n = Number(5)
        self.assertEqual(n.evaluate(), Fraction(5, 1))
        self.assertEqual(n.operator_count(), 0)

    def test_fraction_number(self):
        n = Number(Fraction(3, 4))
        self.assertEqual(n.evaluate(), Fraction(3, 4))
        self.assertEqual(n.operator_count(), 0)

    def test_fraction_reduction(self):
        n = Number(Fraction(4, 8))
        self.assertEqual(n.evaluate(), Fraction(1, 2))


class TestBinaryExpression(unittest.TestCase):
    """Test BinaryExpression operators and constraint boundaries."""

    def test_addition(self):
        expr = BinaryExpression("+", Number(Fraction(1, 6)), Number(Fraction(1, 8)))
        self.assertEqual(expr.evaluate(), Fraction(7, 24))

    def test_subtraction_positive(self):
        expr = BinaryExpression("−", Number(3), Number(1))
        self.assertEqual(expr.evaluate(), Fraction(2, 1))

    def test_subtraction_negative_raises(self):
        expr = BinaryExpression("−", Number(1), Number(3))
        with self.assertRaises(ValueError):
            expr.evaluate()

    def test_multiplication(self):
        expr = BinaryExpression("×", Number(Fraction(2, 3)), Number(Fraction(9, 4)))
        self.assertEqual(expr.evaluate(), Fraction(3, 2))

    def test_division_valid(self):
        expr = BinaryExpression("÷", Number(3), Number(2))
        self.assertEqual(expr.evaluate(), Fraction(3, 2))

    def test_division_by_zero_raises(self):
        expr = BinaryExpression("÷", Number(3), Number(0))
        with self.assertRaises(ZeroDivisionError):
            expr.evaluate()

    def test_operator_count(self):
        inner = BinaryExpression("+", Number(1), Number(2))
        outer = BinaryExpression("×", inner, Number(3))
        self.assertEqual(outer.operator_count(), 2)


class TestCanonicalKeyAndDeduplication(unittest.TestCase):
    """Test equivalence detection under commutativity and structure preservation."""

    def test_simple_addition_commutativity(self):
        a = BinaryExpression("+", Number(2), Number(3))
        b = BinaryExpression("+", Number(3), Number(2))
        self.assertEqual(canonical_key(a), canonical_key(b))

    def test_simple_multiplication_commutativity(self):
        a = BinaryExpression("×", Number(Fraction(1, 2)), Number(4))
        b = BinaryExpression("×", Number(4), Number(Fraction(1, 2)))
        self.assertEqual(canonical_key(a), canonical_key(b))

    def test_subtraction_non_commutativity(self):
        a = BinaryExpression("−", Number(3), Number(1))
        b = BinaryExpression("−", Number(1), Number(3))
        self.assertNotEqual(canonical_key(a), canonical_key(b))

    def test_associative_tree_structure_preserved(self):
        # (1 + 2) + 3 vs 3 + (2 + 1) -> equivalent by tree rotation / child swapping
        e1 = BinaryExpression("+", BinaryExpression("+", Number(1), Number(2)), Number(3))
        e2 = BinaryExpression("+", Number(3), BinaryExpression("+", Number(2), Number(1)))
        self.assertEqual(canonical_key(e1), canonical_key(e2))

        # (1 + 2) + 3 vs (3 + 2) + 1 -> different grouping, should not match
        e3 = BinaryExpression("+", BinaryExpression("+", Number(3), Number(2)), Number(1))
        self.assertNotEqual(canonical_key(e1), canonical_key(e3))


class TestRenderer(unittest.TestCase):
    """Test numeric formatting and expression infix rendering with parentheses."""

    def test_format_integer(self):
        self.assertEqual(format_value(Fraction(5, 1)), "5")

    def test_format_proper_fraction(self):
        self.assertEqual(format_value(Fraction(3, 7)), "3/7")

    def test_format_mixed_number_curly_quote(self):
        self.assertEqual(format_value(Fraction(7, 4), use_curly_quote=True), "1’3/4")

    def test_format_mixed_number_straight_quote(self):
        self.assertEqual(format_value(Fraction(7, 4), use_curly_quote=False), "1'3/4")

    def test_render_parentheses_for_precedence(self):
        # (1 + 2) × 3 requires parentheses around (1 + 2)
        inner = BinaryExpression("+", Number(1), Number(2))
        outer = BinaryExpression("×", inner, Number(3))
        self.assertEqual(render_expression(outer), "(1 + 2) × 3")

    def test_render_parentheses_for_right_subtraction(self):
        # 5 − (3 − 1) requires parentheses on the right child
        inner = BinaryExpression("−", Number(3), Number(1))
        outer = BinaryExpression("−", Number(5), inner)
        self.assertEqual(render_expression(outer), "5 − (3 − 1)")

    def test_render_parentheses_for_right_division(self):
        # 12 ÷ (6 ÷ 2) requires parentheses on the right child
        inner = BinaryExpression("÷", Number(6), Number(2))
        outer = BinaryExpression("÷", Number(12), inner)
        self.assertEqual(render_expression(outer), "12 ÷ (6 ÷ 2)")


class TestParser(unittest.TestCase):
    """Test custom recursive descent parser for expressions and answers."""

    def test_parse_integer_token(self):
        self.assertEqual(parse_number_token("42"), Fraction(42, 1))

    def test_parse_fraction_token(self):
        self.assertEqual(parse_number_token("3/8"), Fraction(3, 8))

    def test_parse_mixed_number_token(self):
        self.assertEqual(parse_number_token("2'3/8"), Fraction(19, 8))
        self.assertEqual(parse_number_token("2’3/8"), Fraction(19, 8))

    def test_parse_simple_expression(self):
        expr = parse_expression("3 + 4 × 2")
        self.assertEqual(expr.evaluate(), Fraction(11, 1))

    def test_parse_expression_with_parentheses(self):
        expr = parse_expression("(3 + 4) × 2")
        self.assertEqual(expr.evaluate(), Fraction(14, 1))

    def test_parse_complex_with_fractions(self):
        expr = parse_expression("1’1/2 + 2/3 ÷ 4")
        expected = Fraction(3, 2) + (Fraction(2, 3) / Fraction(4, 1))
        self.assertEqual(expr.evaluate(), expected)

    def test_parse_invalid_syntax_raises(self):
        with self.assertRaises(ExpressionParseError):
            parse_expression("(3 + 4")
        with self.assertRaises(ExpressionParseError):
            parse_expression("3 + + 4")


class TestGeneratorAndConstraints(unittest.TestCase):
    """Test exercise generator and constraint satisfaction."""

    def test_validate_node_rejection_negative(self):
        bad = BinaryExpression("−", Number(2), Number(5))
        with self.assertRaises(ValueError):
            validate_node(bad)

    def test_validate_node_rejection_integer_division(self):
        # 4 ÷ 2 produces integer 2, which must be rejected per curriculum rules
        bad = BinaryExpression("÷", Number(4), Number(2))
        with self.assertRaises(ValueError):
            validate_node(bad)

    def test_validate_node_rejection_division_by_zero(self):
        bad = BinaryExpression("÷", Number(4), Number(0))
        with self.assertRaises(ValueError):
            validate_node(bad)

    def test_generate_exercises_count_and_uniqueness(self):
        exercises = generate_exercises(count=50, range_val=10, seed=42)
        self.assertEqual(len(exercises), 50)

        keys = set()
        for expr, ans in exercises:
            self.assertLessEqual(expr.operator_count(), 3)
            key = canonical_key(expr)
            self.assertNotIn(key, keys)
            keys.add(key)
            # Verify exact calculation matches
            self.assertEqual(expr.evaluate(), ans)

    def test_random_operand_bounds_r1(self):
        rng = random.Random(42)
        op = random_operand(1, rng)
        self.assertEqual(op.value, Fraction(0, 1))

    def test_random_operand_bounds_r2_strict(self):
        rng = random.Random(42)
        # Verify that for -r 2, all operands are strictly in {0, 1}, and never any fraction (e.g. 1/2)
        for _ in range(100):
            op = random_operand(2, rng)
            self.assertIn(op.value, [Fraction(0, 1), Fraction(1, 1)])
            self.assertEqual(op.value.denominator, 1)

    def test_random_operand_bounds_r3_strict(self):
        rng = random.Random(42)
        # Verify that for -r 3, proper fraction denominators are strictly < 3 (only 2 allowed)
        for _ in range(100):
            op = random_operand(3, rng)
            self.assertLess(op.value.denominator, 3)

    def test_generate_exercises_r1_minimal(self):
        # -r 1 is explicitly allowed by homework specification
        exercises = generate_exercises(count=3, range_val=1, seed=42)
        self.assertEqual(len(exercises), 3)
        for expr, ans in exercises:
            self.assertEqual(ans, Fraction(0, 1))

    def test_generate_exercises_r2_strict_bound(self):
        def get_leaf_numbers(node):
            if isinstance(node, Number):
                return [node.value]
            return get_leaf_numbers(node.left) + get_leaf_numbers(node.right)

        exercises = generate_exercises(count=20, range_val=2, seed=42)
        self.assertEqual(len(exercises), 20)
        for expr, ans in exercises:
            for val in get_leaf_numbers(expr):
                self.assertIn(val, [Fraction(0, 1), Fraction(1, 1)])
                self.assertEqual(val.denominator, 1)


class TestGrader(unittest.TestCase):
    """Test answer grading and report formatting."""

    def test_grade_text_all_correct(self):
        ex_text = "1.  3 + 4 =\n2.  5 × 2 =\n"
        ans_text = "1.  7\n2.  10\n"
        correct, wrong = grade_text_content(ex_text, ans_text)
        self.assertEqual(correct, [1, 2])
        self.assertEqual(wrong, [])

    def test_grade_text_with_wrong_answers(self):
        ex_text = "1.  3 + 4 =\n2.  5 × 2 =\n3.  1/2 + 1/2 =\n"
        ans_text = "1.  7\n2.  99\n3.  1\n"
        correct, wrong = grade_text_content(ex_text, ans_text)
        self.assertEqual(correct, [1, 3])
        self.assertEqual(wrong, [2])

        report = format_grade_report(correct, wrong)
        self.assertIn("Correct: 2 (1, 3)", report)
        self.assertIn("Wrong: 1 (2)", report)

    def test_grade_text_mismatched_count(self):
        ex_text = "1.  3 + 4 =\n"
        ans_text = "1.  7\n2.  10\n"
        with self.assertRaises(FileOperationError):
            grade_text_content(ex_text, ans_text)


class TestCommandLineEndToEnd(unittest.TestCase):
    """End-to-end CLI execution tests."""

    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.work_dir = Path(self.test_dir.name)
        self.main_py = (Path(__file__).resolve().parent.parent / "main.py").resolve()

    def tearDown(self):
        self.test_dir.cleanup()

    def test_cli_generate_and_grade(self):
        # 1. Run generation
        res = subprocess.run(
            [sys.executable, str(self.main_py), "-n", "10", "-r", "10"],
            cwd=self.work_dir,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0)
        ex_file = self.work_dir / "Exercises.txt"
        ans_file = self.work_dir / "Answers.txt"
        self.assertTrue(ex_file.is_file())
        self.assertTrue(ans_file.is_file())

        # 2. Run grading
        res_grade = subprocess.run(
            [sys.executable, str(self.main_py), "-e", "Exercises.txt", "-a", "Answers.txt"],
            cwd=self.work_dir,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res_grade.returncode, 0)
        grade_file = self.work_dir / "Grade.txt"
        self.assertTrue(grade_file.is_file())
        content = grade_file.read_text(encoding="utf-8")
        self.assertIn("Correct: 10", content)
        self.assertIn("Wrong: 0", content)

    def test_cli_missing_range_fails(self):
        res = subprocess.run(
            [sys.executable, str(self.main_py), "-n", "10"],
            cwd=self.work_dir,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("错误", res.stderr)

    def test_cli_mixed_mode_fails(self):
        res = subprocess.run(
            [sys.executable, str(self.main_py), "-n", "10", "-r", "10", "-e", "Ex.txt"],
            cwd=self.work_dir,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("不能混用", res.stderr)

    def test_cli_minimal_range_r1(self):
        res = subprocess.run(
            [sys.executable, str(self.main_py), "-n", "1", "-r", "1"],
            cwd=self.work_dir,
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0)
        ex_file = self.work_dir / "Exercises.txt"
        ans_file = self.work_dir / "Answers.txt"
        self.assertTrue(ex_file.is_file())
        self.assertTrue(ans_file.is_file())
        self.assertIn("0", ans_file.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
