"""Diagnostics and safe result handling for OPL parsing."""

from dataclasses import dataclass
from enum import Enum

from .model import Model, SourceLocation


class Severity(Enum):
    WARNING = "WARNING"
    ERROR = "ERROR"


@dataclass(frozen=True)
class Diagnostic:
    code: str
    severity: Severity
    message: str
    source: SourceLocation

    def __str__(self) -> str:
        return (f"{self.source.path}:{self.source.line}: "
                f"{self.severity.value} {self.code}: {self.message}")


@dataclass(frozen=True)
class ParseResult:
    """Errors suppress the model; warnings retain the supported subset."""

    model: Model | None
    diagnostics: tuple[Diagnostic, ...]

    @property
    def has_errors(self) -> bool:
        return any(d.severity is Severity.ERROR for d in self.diagnostics)

    @property
    def skipped_statements(self) -> int:
        return sum(d.code == "W001" for d in self.diagnostics)

    @property
    def incomplete(self) -> bool:
        return self.skipped_statements > 0

    @property
    def summary(self) -> str:
        if self.has_errors:
            errors = sum(d.severity is Severity.ERROR for d in self.diagnostics)
            return f"Cannot render: {errors} error(s); no model was produced."
        if self.incomplete:
            return (f"Diagram is incomplete: {self.skipped_statements} "
                    "unsupported statement(s) skipped.")
        return "Model is complete for the supported syntax."

    def require_model(self) -> Model:
        """Return a renderable model or raise with the collected diagnostics.

        Callers must also display diagnostics and summary, including warnings.
        """
        if self.model is None:
            raise ValueError("\n".join([self.summary, *(str(d) for d in self.diagnostics)]))
        return self.model
