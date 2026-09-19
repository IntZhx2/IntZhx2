"""Custom exception classes for arithmetic generator and grader.
"""


class ArithmeticAppError(Exception):
    """Base exception class for arithmetic package."""

    pass


class CommandLineArgumentError(ArithmeticAppError):
    """Raised when command-line parameters are invalid or missing."""

    pass


class ExpressionParseError(ArithmeticAppError):
    """Raised when an expression or answer text cannot be parsed."""

    pass


class GenerationExhaustedError(ArithmeticAppError):
    """Raised when unable to generate the requested number of unique exercises."""

    pass


class FileOperationError(ArithmeticAppError):
    """Raised when reading or writing exercises/answers/grades fails."""

    pass
