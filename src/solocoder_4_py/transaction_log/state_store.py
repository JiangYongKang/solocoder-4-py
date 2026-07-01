from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Iterator, Optional

from .log_entry import _MISSING


@dataclass
class StateStore:
    _data: dict[str, Any] = field(default_factory=dict)
    _snapshots: list[dict[str, Any]] = field(default_factory=list)

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> Any:
        if key in self._data:
            old_value = self._data[key]
        else:
            old_value = _MISSING
        self._data[key] = value
        return old_value

    def delete(self, key: str) -> tuple[bool, Any]:
        if key in self._data:
            old_value = self._data.pop(key)
            return True, old_value
        return False, _MISSING

    def exists(self, key: str) -> bool:
        return key in self._data

    def keys(self) -> Iterator[str]:
        return iter(self._data.keys())

    def values(self) -> Iterator[Any]:
        return iter(self._data.values())

    def items(self) -> Iterator[tuple[str, Any]]:
        return iter(self._data.items())

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._data[key] = value

    def __delitem__(self, key: str) -> None:
        del self._data[key]

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def __len__(self) -> int:
        return len(self._data)

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def snapshot(self) -> int:
        self._snapshots.append(deepcopy(self._data))
        return len(self._snapshots) - 1

    def restore_snapshot(self, index: Optional[int] = None) -> None:
        if not self._snapshots:
            raise ValueError("No snapshots available")
        target_index = index if index is not None else len(self._snapshots) - 1
        if target_index < 0 or target_index >= len(self._snapshots):
            raise IndexError(f"Snapshot index {target_index} out of range")
        self._data = deepcopy(self._snapshots[target_index])

    def clear_snapshots(self) -> None:
        self._snapshots.clear()

    @property
    def snapshot_count(self) -> int:
        return len(self._snapshots)

    def to_dict(self) -> dict[str, Any]:
        return deepcopy(self._data)

    def load_dict(self, data: dict[str, Any]) -> None:
        self._data = deepcopy(data)

    def clear(self) -> None:
        self._data.clear()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, StateStore):
            return NotImplemented
        return self._data == other._data

    def __repr__(self) -> str:
        return f"StateStore({self._data!r})"
