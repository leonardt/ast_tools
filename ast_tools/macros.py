class unroll:
    def __init__(self, _iter):
        self._iter = _iter

    def __iter__(self):
        return iter(self._iter)

class inline:
    def __init__(self, cond):
        self._cond = cond

    def __bool__(self):
        return self._cond

