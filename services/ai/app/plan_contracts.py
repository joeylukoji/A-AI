"""Explicit domain failures shared by generation and adaptation."""

from __future__ import annotations


class PlanConstraintError(ValueError):
    """An input constraint cannot be represented by the current layout engine."""

    def __init__(self, code: str, fields: tuple[str, ...], message: str) -> None:
        self.code = code
        self.fields = fields
        super().__init__(f"{code} ({', '.join(fields)}): {message}")


class PlanDocumentError(ValueError):
    """A document violates the shared structure-and-intervals profile."""

    def __init__(self, code: str, path: str) -> None:
        self.code = code
        self.path = path
        super().__init__(f"{code}: {path}")


class GeneratedDocumentError(RuntimeError):
    """An internal stage returned an invalid document, not invalid user input."""

    def __init__(self, cause: PlanDocumentError) -> None:
        self.code = cause.code
        self.path = cause.path
        super().__init__(str(cause))
