"""Expression and numeric formatting module.
"""

from fractions import Fraction
from typing import Optional

from arithmetic.expression import BinaryExpression, Expression, Number

PRECEDENCE = {
    "+": 1,
    "−": 1,
    "×": 2,
    "÷": 2,
}


def format_value(value: Fraction, use_curly_quote: bool = True) -> str:
    """Format an exact Fraction according to curriculum requirements.

    - Integers: '0', '4', '12'
    - Proper fractions: '1/2', '3/8'
    - Mixed numbers: '1’1/2' or '1\'1/2'
    """
    value = Fraction(value)
    if value.denominator == 1:
        return str(value.numerator)

    if abs(value.numerator) < value.denominator:
        return f"{value.numerator}/{value.denominator}"

    whole, rem = divmod(abs(value.numerator), value.denominator)
    quote = "’" if use_curly_quote else "'"
    sign = "-" if value.numerator < 0 else ""
    return f"{sign}{whole}{quote}{rem}/{value.denominator}"


def render_expression(expression: Expression, parent_op: Optional[str] = None, is_right: bool = False) -> str:
    """Render an expression tree to an infix string with necessary parentheses.

    Parentheses are preserved where mathematically required or where needed
    to preserve tree associativity.
    """
    if isinstance(expression, Number):
        return format_value(expression.value)

    if isinstance(expression, BinaryExpression):
        my_prec = PRECEDENCE[expression.operator]
        left_str = render_expression(expression.left, expression.operator, is_right=False)
        right_str = render_expression(expression.right, expression.operator, is_right=True)

        current_str = f"{left_str} {expression.operator} {right_str}"

        if parent_op is not None:
            parent_prec = PRECEDENCE[parent_op]
            need_parens = False

            # Lower precedence than parent always needs parens: e.g. A × (B + C)
            if my_prec < parent_prec:
                need_parens = True
            # Same precedence on the right:
            # For non-commutative '−' and '÷': A − (B − C), A ÷ (B ÷ C)
            # For commutative '+' and '×': A + (B + C), A × (B × C) to preserve AST grouping
            elif my_prec == parent_prec and is_right:
                need_parens = True

            if need_parens:
                return f"({current_str})"

        return current_str

    raise TypeError(f"Unknown expression type: {type(expression)}")


def format_exercise_line(index: int, expression: Expression) -> str:
    """Format a single exercise line for Exercises.txt."""
    return f"{index}.  {render_expression(expression)} ="


def format_answer_line(index: int, value: Fraction) -> str:
    """Format a single answer line for Answers.txt."""
    return f"{index}.  {format_value(value)}"
