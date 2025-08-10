"""Custom exceptions for multiclaude."""


class MultiClaudeError(Exception):
    """Base exception for multiclaude errors."""

    pass


class NotInitializedError(MultiClaudeError):
    """Raised when multiclaude is not initialized."""

    pass
