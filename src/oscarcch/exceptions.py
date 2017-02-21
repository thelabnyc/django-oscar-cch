
class CCHError(Exception):
    severity = None
    code = None
    info = None

    def __init__(self, code, info, *args, **kwargs):
        self.code = code
        self.info = info
        super().__init__(*args, **kwargs)

    def __str__(self):
        return self.message


class CCHSystemError(CCHError):
    severity = 1

    @property
    def message(self):
        return 'CCHSystemError %s: %s' % (self.code, self.info)


class CCHRequestError(CCHError):
    severity = 2

    @property
    def message(self):
        return 'CCHRequestError %s: %s' % (self.code, self.info)


def build(severity, code, info):
    types = {
        CCHSystemError.severity: CCHSystemError,
        CCHRequestError.severity: CCHRequestError,
    }
    Exc = types.get(severity, CCHError)
    return Exc(code, info)
