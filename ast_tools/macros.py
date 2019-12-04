class unroll:
    def __init__(self, _iter):
        self._iter = _iter

    def __iter__(self):
        return iter(self._iter)
