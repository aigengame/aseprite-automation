"""Inner-owned runtime observation failures mapped by Application use cases."""

from spa.contracts import Diagnostics, FailureEnvelope


class RuntimeFailure(Exception):
    def __init__(self, code: str, category: str, message: str, details, diagnostics: Diagnostics | None = None):
        super().__init__(message)
        self.code = code
        self.category = category
        self.details = details
        self.diagnostics = diagnostics or Diagnostics()

    def to_envelope(self, operation: str) -> FailureEnvelope:
        return FailureEnvelope(
            operation=operation, code=self.code, category=self.category,
            message=str(self), details=self.details, diagnostics=self.diagnostics,
        )
