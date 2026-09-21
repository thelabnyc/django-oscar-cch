from collections.abc import Mapping, Sequence
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

    def __init__(
        self,
        code: str,
        info: str,
        item_messages: Sequence[Mapping[str, Any]] = (),
    ):
        self.code = code
        self.info = info
        #: The ``ItemMessages`` of a 9001 response; empty for every other error.
        self.item_messages = tuple(item_messages)
        super().__init__(code, info)

    def __str__(self) -> str:
        return f"{self.__class__.__name__} {self.code}: {self.info}"


def build(severity: int, code: int, info: str) -> CCHError:
    types = {
        CCHSystemError.severity: CCHSystemError,
        CCHRequestError.severity: CCHRequestError,
    }
    Exc = types.get(severity, CCHError)
    return Exc(code, info)
