"""Recursive descent parser for arithmetic exercises and answers.

Parses text expressions safely without using eval().
"""

from fractions import Fraction
import re
from typing import List, Tuple

from arithmetic.errors import ExpressionParseError
from arithmetic.expression import (
    BinaryExpression,
    Expression,
    Number,
    normalize_operator,
)

# Regex matching tokens: mixed numbers (1'1/2 or 1’1/2), fractions (1/2), integers, operators, parens
TOKEN_PATTERN = re.compile(
    r"\d+['’]\d+/\d+"    # mixed numbers like 1'2/3 or 1’2/3
    r"|\d+/\d+"           # simple fractions like 2/3
    r"|\d+"               # integers like 42
    r"|[+−\-×*xX÷/]"      # operators
    r"|[()]"              # parentheses
)


def parse_number_token(token: str) -> Fraction:
    """Parse a numeric token into an exact Fraction."""
    token = token.strip()
    # Check mixed number: e.g. 1'1/2 or 1’1/2
    if "'" in token or "’" in token:
        parts = re.split(r"['’]", token)
        if len(parts) == 2 and "/" in parts[1]:
            whole = int(parts[0])
            num_str, den_str = parts[1].split("/")
            num = int(num_str)
            den = int(den_str)
            if den == 0:
                raise ExpressionParseError(f"Denominator cannot be zero in token: {token}")
            sign = -1 if whole < 0 else 1
            abs_whole = abs(whole)
            return Fraction(sign * (abs_whole * den + num), den)

    # Check fraction: e.g. 3/4
    if "/" in token:
        parts = token.split("/")
        if len(parts) == 2:
            num = int(parts[0])
            den = int(parts[1])
            if den == 0:
                raise ExpressionParseError(f"Denominator cannot be zero in token: {token}")
            return Fraction(num, den)

    # Integer
    return Fraction(int(token), 1)


class Parser:
    """Recursive descent parser for mathematical expressions."""

    def __init__(self, tokens: List[str]):
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> str:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return ""

    def consume(self) -> str:
        tok = self.peek()
        self.pos += 1
        return tok

    def parse(self) -> Expression:
        if not self.tokens:
            raise ExpressionParseError("Empty expression cannot be parsed")
        expr = self.parse_additive()
        if self.pos < len(self.tokens):
            unexpected = self.tokens[self.pos:]
            raise ExpressionParseError(f"Unexpected trailing tokens: {' '.join(unexpected)}")
        return expr

    def parse_additive(self) -> Expression:
        """parse_additive = parse_multiplicative (('+' | '−') parse_multiplicative)*"""
        left = self.parse_multiplicative()

        while self.peek() in ("+", "-", "−"):
            op = normalize_operator(self.consume())
            right = self.parse_multiplicative()
            left = BinaryExpression(op, left, right)

        return left

    def parse_multiplicative(self) -> Expression:
        """parse_multiplicative = parse_primary (('×' | '÷') parse_primary)*"""
        left = self.parse_primary()

        while self.peek() in ("*", "×", "x", "X", "/", "÷"):
            op = normalize_operator(self.consume())
            right = self.parse_primary()
            left = BinaryExpression(op, left, right)

        return left

    def parse_primary(self) -> Expression:
        """parse_primary = Number | '(' parse_additive ')'"""
        tok = self.peek()
        if not tok:
            raise ExpressionParseError("Unexpected end of expression, expected operand or '('")

        if tok == "(":
            self.consume()  # consume '('
            expr = self.parse_additive()
            if self.peek() != ")":
                raise ExpressionParseError("Mismatched parentheses: missing ')'")
            self.consume()  # consume ')'
            return expr

        if tok == ")":
            raise ExpressionParseError("Unexpected ')'")

        # It must be a number or fraction
        self.consume()
        try:
            val = parse_number_token(tok)
            return Number(val)
        except Exception as err:
            raise ExpressionParseError(f"Failed to parse number token '{tok}': {err}") from err


def parse_expression(text: str) -> Expression:
    """Parse raw expression text into an Expression tree."""
    tokens = TOKEN_PATTERN.findall(text)
    parser = Parser(tokens)
    return parser.parse()


def extract_line_index_and_body(line: str) -> Tuple[int, str]:
    """Extract line number index and clean body from formatted line.

    Matches formats like:
    '1.  3 + 4 ='
    '2. 1’1/2'
    '3、 5/6'
    """
    line = line.strip()
    match = re.match(r"^(\d+)[\.、\s]+(.*)$", line)
    if not match:
        raise ExpressionParseError(f"Line format invalid (missing question number): {line}")

    index = int(match.group(1))
    body = match.group(2).strip()
    return index, body


def parse_exercise_line(line: str) -> Tuple[int, Expression]:
    """Parse an exercise line from Exercises.txt.

    Returns:
        (index, expression_tree)
    """
    index, body = extract_line_index_and_body(line)
    # Remove trailing '='
    if body.endswith("="):
        body = body[:-1].strip()

    expr = parse_expression(body)
    return index, expr


def parse_answer_line(line: str) -> Tuple[int, Fraction]:
    """Parse an answer line from Answers.txt.

    Returns:
        (index, answer_fraction)
    """
    index, body = extract_line_index_and_body(line)
    val = parse_number_token(body)
    return index, val
