import functools as ft
import typing as tp
import sys

# PEP 585
if sys.version_info < (3, 9):
    from typing import MutableMapping, Mapping, MutableSet, AbstractSet as Set, Iterator, Iterable
    from typing import MappingView, ItemsView, KeysView, ValuesView
else:
    from collections.abc import MutableMapping, Mapping, MutableSet, Set, Iterator, Iterable
    from collections.abc import MappingView, ItemsView, KeysView, ValuesView


T = tp.TypeVar('T')
S = tp.TypeVar('S')

# Because the setitem signature does not match mutable mapping 
# we inherit from mapping. We lose MutableMapping mixin methods
# for correct typing but we don't use them anyway 
class BiMap(Mapping[T, Set[S]]):
    _d: MutableMapping[T, MutableSet[S]]
    _r: MutableMapping[S, MutableSet[T]]

    def __init__(self, d: tp.Optional['BiMap[T, S]'] = None) -> None:
        self._d = {}
        self._r = {}
        if d is not None:
            for k, v in d.items():
                for vv in v:
                    self[k] = vv

    def __getitem__(self, idx: T) -> Set[S]:
        return frozenset(self._d[idx])

    def __setitem__(self, idx: T, val: S) -> None:
        self._d.setdefault(idx, set()).add(val)
        self._r.setdefault(val, set()).add(idx)

    def __delitem__(self, idx: T) -> None:
        for val in self._d[idx]:
            self._r[val].remove(idx)
            if not self._r[val]:
                del self._r[val]
        del self._d[idx]

    def __iter__(self) -> Iterator[T]:
        return iter(self._d)

    def __len__(self) -> int:
        return len(self._d)

    def __eq__(self, other) -> bool:
        if isinstance(other, type(self)):
            if self._d == other._d:
                assert self._r == other._r
                return True
            else:
                assert self._r != other._r
                return False
        else:
            return NotImplemented

    def __ne__(self, other) -> bool:
        if isinstance(other, type(self)):
            return not self == other
        else:
            return NotImplemented

    @property
    def i(self) -> 'BiMap[S, T]':
        i: BiMap[S, T] = BiMap()
        i._d = self._r
        i._r = self._d
        return i

    def __repr__(self) -> str:
        kv = map(': '.join, (map(repr, items) for items in self.items()))
        return f'{type(self).__name__}(' + ', '.join(kv) + ')'


def _attest(self: BiMap[T, S]) -> None:
    for dk, dvals in self._d.items():
        for dv in dvals:
            assert dk in self._r[dv]

    for rk, rvals in self._r.items():
        for rv in rvals:
            assert rk in self._d[rv]

F = tp.TypeVar('F', bound=tp.Callable[..., tp.Any])

def _with_attestation(f: F) -> F:
    @ft.wraps(f)
    def wrapper(self: BiMap[T, S], *args, **kwargs):
        _attest(self)
        r_val = f(self, *args, **kwargs)
        _attest(self)
        return r_val
    return tp.cast(F, wrapper)

class _BiMapDebug(BiMap[T, S]):
    def __init__(self, d: tp.Optional[BiMap[T, S]] = None) -> None:
        super().__init__(d)
        _attest(self)

    @property
    def i(self) -> '_BiMapDebug[S, T]':
        _attest(self)
        i: _BiMapDebug[S, T] = _BiMapDebug()
        i._d = self._r
        i._r = self._d
        _attest(i)
        return i

    __getitem__ = _with_attestation(BiMap.__getitem__)
    __setitem__ = _with_attestation(BiMap.__setitem__)
    __delitem__ = _with_attestation(BiMap.__delitem__)
    __iter__ = _with_attestation(BiMap.__iter__)
    __len__ = _with_attestation(BiMap.__len__)
    __eq__ = _with_attestation(BiMap.__eq__)
    __ne__ = _with_attestation(BiMap.__ne__)
