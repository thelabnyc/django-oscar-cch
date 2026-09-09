from typing import Any


class CCHError(Exception):
    severity: int
    code: int
    info: str

    def __init__(self, code: int, info: str, *args: Any, **kwargs: Any):
        self.code = code
        self.info = info
        super().__init__(*args, **kwargs)

    @property
    def message(self) -> str:
        return f"CCHError {self.code}: {self.info}"

    def __str__(self) -> str:
        return self.message


class CCHSystemError(CCHError):
    severity = 1

    @property
    def message(self) -> str:
        return f"CCHSystemError {self.code}: {self.info}"


class CCHRequestError(CCHError):
    severity = 2

    @property
    def message(self) -> str:
        return f"CCHRequestError {self.code}: {self.info}"


class SureTaxError(Exception):
    """
    A SureTax response reported a failure.

    Raised for header-level error responses, and for responses that fail
    validation (unknown line numbers, total-tax reconciliation mismatch).
    """

    def __init__(self, code: str, info: str):
        self.code = code
        self.info = info
        super().__init__(code, info)

    def __str__(self) -> str:
        return f"{self.__class__.__name__} {self.code}: {self.info}"


class SureTaxItemError(SureTaxError):
    """
    A SureTax response reported per-item validation errors (ResponseCode 9001).

    ``info`` holds the JSON-encoded ``ItemMessages`` list, one entry per failed
    line with ``LineNumber``, ``ResponseCode``, and ``Message``. Like
    :class:`SureTaxError`, it is raised after the HTTP call has returned and
    outside any circuit breaker, so item errors never count as service failures.
    """


def build(severity: int, code: int, info: str) -> CCHError:
    types = {
        CCHSystemError.severity: CCHSystemError,
        CCHRequestError.severity: CCHRequestError,
    }
    Exc = types.get(severity, CCHError)
    return Exc(code, info)
