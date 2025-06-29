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


def build(severity: int, code: int, info: str) -> CCHError:
    types = {
        CCHSystemError.severity: CCHSystemError,
        CCHRequestError.severity: CCHRequestError,
    }
    Exc = types.get(severity, CCHError)
    return Exc(code, info)
