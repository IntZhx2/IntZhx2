"""Expression tree representation and exact rational evaluation.
"""

from abc import ABC, abstractmethod
from fractions import Fraction
from typing import Any, Tuple, Union


def normalize_operator(op: str) -> str:
    """Normalize operator string to standard arithmetic symbols."""
    op = op.strip()
    if op in ("+",):
        return "+"
    if op in ("-", "−"):
        return "−"
    if op in ("*", "×", "x", "X"):
        return "×"
    if op in ("/", "÷"):
        return "÷"
    raise ValueError(f"Unsupported operator: {op}")


class Expression(ABC):
    """Abstract base class for all expression tree nodes."""

    @abstractmethod
    def evaluate(self) -> Fraction:
        """Evaluate the expression tree to an exact Fraction."""
        pass

    @abstractmethod
    def operator_count(self) -> int:
        """Count the total number of operators in this expression."""
        pass


class Number(Expression):
    """Leaf node representing a numeric constant (integer or fraction)."""

    def __init__(self, value: Union[Fraction, int, str]):
        if isinstance(value, int):
            self.value = Fraction(value, 1)
        elif isinstance(value, Fraction):
            self.value = value
        elif isinstance(value, str):
            self.value = Fraction(value)
        else:
            raise TypeError(f"Invalid value type for Number: {type(value)}")

    def evaluate(self) -> Fraction:
        return self.value

    def operator_count(self) -> int:
        return 0

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, Number):
            return self.value == other.value
        return False

    def __hash__(self) -> int:
        return hash(("Number", self.value))

    def __repr__(self) -> str:
        return f"Number({self.value})"


class BinaryExpression(Expression):
    """Internal node representing a binary arithmetic operation."""

    def __init__(self, operator: str, left: Expression, right: Expression):
        self.operator = normalize_operator(operator)
        self.left = left
        self.right = right

    def evaluate(self) -> Fraction:
        left_val = self.left.evaluate()
        right_val = self.right.evaluate()

        if self.operator == "+":
            return left_val + right_val
        if self.operator == "−":
            if left_val < right_val:
                raise ValueError("Subtraction produces negative number: "
                                 f"{left_val} - {right_val}")
            return left_val - right_val
        if self.operator == "×":
            return left_val * right_val
        if self.operator == "÷":
            if right_val == 0:
                raise ZeroDivisionError("Division by zero")
            return left_val / right_val

        raise ValueError(f"Unknown operator: {self.operator}")

    def operator_count(self) -> int:
        return 1 + self.left.operator_count() + self.right.operator_count()

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, BinaryExpression):
            return (
                self.operator == other.operator
                and self.left == other.left
                and self.right == other.right
            )
        return False

    def __hash__(self) -> int:
        return hash(("BinaryExpression", self.operator, self.left, self.right))

    def __repr__(self) -> str:
        return f"BinaryExpression({self.operator!r}, {self.left!r}, {self.right!r})"


def canonical_key(expression: Expression) -> Tuple[Any, ...]:
    """Generate a canonical key for expression deduplication under commutativity.

    Commutative operators '+' and '×' sort their operands, while
    non-commutative operators '−' and '÷' preserve operand order.
    The tree structure (associativity) is preserved.
    """
    if isinstance(expression, Number):
        return ("num", expression.value.numerator, expression.value.denominator)

    if isinstance(expression, BinaryExpression):
        left_k = canonical_key(expression.left)
        right_k = canonical_key(expression.right)

        if expression.operator in ("+", "×") and right_k < left_k:
            left_k, right_k = right_k, left_k

        return ("op", expression.operator, left_k, right_k)

    raise TypeError(f"Unknown expression node type: {type(expression)}")
