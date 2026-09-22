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

    Raised for header-level error responses, for per-item validation errors
    (ResponseCode 9001, ``info`` holds the JSON-encoded ``ItemMessages``), and
    for responses that fail validation (unknown line numbers, total-tax
    reconciliation mismatch). Always raised after the HTTP call has returned
    and outside any circuit breaker, so body errors never count as service
    failures.
    """

    def __init__(self, code: str, info: str):
        self.code = code
        self.info = info
        super().__init__(code, info)

    def __str__(self) -> str:
        return f"{self.__class__.__name__} {self.code}: {self.info}"


class SureTaxAddressError(SureTaxError):
    """
    A 9001 response whose every item failed only on ship-to address resolution.

    Bad shopper input rather than an integration fault, so the calculator logs
    it as a warning instead of an error.
    """


def build(severity: int, code: int, info: str) -> CCHError:
    types = {
        CCHSystemError.severity: CCHSystemError,
        CCHRequestError.severity: CCHRequestError,
    }
    Exc = types.get(severity, CCHError)
    return Exc(code, info)
