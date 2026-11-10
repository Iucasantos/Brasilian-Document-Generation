MAX_INVALID_INPUT_ATTEMPTS = 20


class InputRetryLimitError(RuntimeError):
    """Raised when an interactive input remains invalid past the retry limit."""
