"""Exercise generation engine, single-pass constraint validation, and deduplication.
"""

from fractions import Fraction
import random
from typing import List, Optional, Set, Tuple

from arithmetic.errors import GenerationExhaustedError
from arithmetic.expression import (
    BinaryExpression,
    Expression,
    Number,
    canonical_key,
)

OPERATORS = ["+", "−", "×", "÷"]


def random_operand(range_val: int, rng: random.Random) -> Number:
    """Generate a random number or fraction within the specified range [0, range_val).

    - If range_val == 1:
        Only natural number 0 (< 1). No valid fractions exist since denominator must be >= 2.
    - If range_val == 2:
        Only natural numbers 0 and 1 (< 2). No valid proper fractions exist since denominator
        must be >= 2 and < 2 (strict upper bound excludes 2).
    - If range_val >= 3:
        1. Natural numbers: 0 to range_val - 1
        2. Proper fractions: num / den where 2 <= den <= range_val - 1 and 1 <= num < den
        3. Mixed numbers: whole'num/den where whole in [1, max(1, range_val - 2)] and 2 <= den <= range_val - 1
    """
    if range_val < 1:
        raise ValueError(f"Range value must be >= 1, got {range_val}")

    if range_val == 1:
        return Number(0)

    if range_val == 2:
        return Number(rng.randint(0, 1))

    choice = rng.random()

    # 45% natural number in [0, range_val - 1]
    if choice < 0.45:
        val = rng.randint(0, range_val - 1)
        return Number(val)

    # 40% pure proper fraction: denominator strictly < range_val
    den = rng.randint(2, range_val - 1)
    num = rng.randint(1, den - 1)

    if choice < 0.85:
        return Number(Fraction(num, den))

    # 15% mixed number (< range_val)
    max_whole = max(1, range_val - 2)
    whole = rng.randint(1, max_whole)
    return Number(Fraction(whole * den + num, den))


def validate_node(node: Expression, max_operators: int = 3) -> Tuple[Fraction, int]:
    """Single-pass recursive validation of constraints.

    Returns:
        (exact_value, operator_count)

    Raises:
        ValueError: If any constraint is violated (negative subtraction,
                    integer division, division by zero, operator count > 3).
    """
    if isinstance(node, Number):
        return node.value, 0

    if isinstance(node, BinaryExpression):
        left_val, left_cnt = validate_node(node.left, max_operators)
        right_val, right_cnt = validate_node(node.right, max_operators)

        total_cnt = 1 + left_cnt + right_cnt
        if total_cnt > max_operators:
            raise ValueError(f"Operator count exceeds limit: {total_cnt} > {max_operators}")

        if node.operator == "+":
            return left_val + right_val, total_cnt

        if node.operator == "−":
            if left_val < right_val:
                raise ValueError(f"Negative subtraction: {left_val} − {right_val}")
            return left_val - right_val, total_cnt

        if node.operator == "×":
            return left_val * right_val, total_cnt

        if node.operator == "÷":
            if right_val == 0:
                raise ValueError("Division by zero")
            res = left_val / right_val
            # Rule: division result must be a positive non-integer rational number
            if res <= 0:
                raise ValueError(f"Division result must be positive: {res}")
            if res.denominator == 1:
                raise ValueError(f"Division result must be a non-integer fraction, got integer: {res}")
            return res, total_cnt

        raise ValueError(f"Unknown operator: {node.operator}")

    raise TypeError(f"Unknown node type: {type(node)}")


def generate_tree_shape(
    operands: List[Number],
    rng: random.Random,
    allowed_ops: Optional[List[str]] = None,
) -> Expression:
    """Combine a list of operands into a valid binary expression tree."""
    ops_pool = allowed_ops or OPERATORS
    if len(operands) == 1:
        return operands[0]

    if len(operands) == 2:
        op = rng.choice(ops_pool)
        return BinaryExpression(op, operands[0], operands[1])

    if len(operands) == 3:
        # Two possible binary tree structures
        op1 = rng.choice(ops_pool)
        op2 = rng.choice(ops_pool)
        if rng.random() < 0.5:
            # (A op B) op C
            left = BinaryExpression(op1, operands[0], operands[1])
            return BinaryExpression(op2, left, operands[2])
        else:
            # A op (B op C)
            right = BinaryExpression(op2, operands[1], operands[2])
            return BinaryExpression(op1, operands[0], right)

    if len(operands) == 4:
        # 5 possible binary tree structures
        shape_type = rng.randint(0, 4)
        op1, op2, op3 = [rng.choice(ops_pool) for _ in range(3)]
        if shape_type == 0:
            # ((A op B) op C) op D
            t1 = BinaryExpression(op1, operands[0], operands[1])
            t2 = BinaryExpression(op2, t1, operands[2])
            return BinaryExpression(op3, t2, operands[3])
        elif shape_type == 1:
            # (A op (B op C)) op D
            t1 = BinaryExpression(op2, operands[1], operands[2])
            t2 = BinaryExpression(op1, operands[0], t1)
            return BinaryExpression(op3, t2, operands[3])
        elif shape_type == 2:
            # (A op B) op (C op D)
            left = BinaryExpression(op1, operands[0], operands[1])
            right = BinaryExpression(op3, operands[2], operands[3])
            return BinaryExpression(op2, left, right)
        elif shape_type == 3:
            # A op ((B op C) op D)
            t1 = BinaryExpression(op2, operands[1], operands[2])
            t2 = BinaryExpression(op3, t1, operands[3])
            return BinaryExpression(op1, operands[0], t2)
        else:
            # A op (B op (C op D))
            t1 = BinaryExpression(op3, operands[2], operands[3])
            t2 = BinaryExpression(op2, operands[1], t1)
            return BinaryExpression(op1, operands[0], t2)

    raise ValueError(f"Unsupported number of operands: {len(operands)}")


def generate_single_candidate(range_val: int, rng: random.Random) -> Expression:
    """Generate a single random candidate expression with 1 to 3 operators."""
    op_count = rng.randint(1, 3)
    num_operands = op_count + 1
    operands = [random_operand(range_val, rng) for _ in range(num_operands)]
    # For range_val <= 2, division cannot yield positive non-integer fractions without
    # exceeding bounds (e.g. denominator >= 2), so restrict operators to +, −, ×.
    allowed_ops = ["+", "−", "×"] if range_val <= 2 else OPERATORS
    return generate_tree_shape(operands, rng, allowed_ops=allowed_ops)


def generate_exercises(
    count: int,
    range_val: int,
    seed: Optional[int] = None,
    max_attempts_per_item: int = 500,
) -> List[Tuple[Expression, Fraction]]:
    """Generate requested number of unique exercises satisfying all constraints.

    Args:
        count: Number of exercises to generate.
        range_val: Maximum numeric range for numbers and denominators (must be >= 1).
        seed: Optional random seed for reproducible generation.
        max_attempts_per_item: Max retry limit per item before raising error.

    Returns:
        List of (expression_tree, exact_answer_fraction) tuples.

    Raises:
        GenerationExhaustedError: If not enough unique valid exercises can be generated.
    """
    if count <= 0:
        return []
    if range_val < 1:
        raise ValueError(f"Range value -r must be >= 1, got {range_val}")

    rng = random.Random(seed)
    seen_keys: Set[Tuple] = set()
    results: List[Tuple[Expression, Fraction]] = []

    total_attempts = 0
    max_total_attempts = max(count * max_attempts_per_item, 50000)

    while len(results) < count:
        total_attempts += 1
        if total_attempts > max_total_attempts:
            raise GenerationExhaustedError(
                f"Exhausted attempts: could only generate {len(results)}/{count} "
                f"unique exercises with -r {range_val}. Increase -r or reduce -n."
            )

        candidate = generate_single_candidate(range_val, rng)

        try:
            val, _ = validate_node(candidate, max_operators=3)
        except (ValueError, ZeroDivisionError):
            continue

        key = canonical_key(candidate)
        if key in seen_keys:
            continue

        seen_keys.add(key)
        results.append((candidate, val))

    return results
