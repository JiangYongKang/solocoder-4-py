from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

_MISSING = object()


class OperationType(Enum):
    BEGIN = "BEGIN"
    COMMIT = "COMMIT"
    ROLLBACK = "ROLLBACK"
    SET = "SET"
    DELETE = "DELETE"
    CHECKPOINT = "CHECKPOINT"


@dataclass(frozen=True)
class LogEntry:
    operation: OperationType
    transaction_id: Optional[str] = None
    key: Optional[str] = None
    value: Any = None
    old_value: Any = _MISSING
    log_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: float = field(default_factory=lambda: __import__("time").time())

    def is_transaction_boundary(self) -> bool:
        return self.operation in {
            OperationType.BEGIN,
            OperationType.COMMIT,
            OperationType.ROLLBACK,
            OperationType.CHECKPOINT,
        }

    def is_data_operation(self) -> bool:
        return self.operation in {OperationType.SET, OperationType.DELETE}

    def to_dict(self) -> dict[str, Any]:
        return {
            "log_id": self.log_id,
            "timestamp": self.timestamp,
            "operation": self.operation.value,
            "transaction_id": self.transaction_id,
            "key": self.key,
            "value": None if self.value is _MISSING else self.value,
            "old_value": None if self.old_value is _MISSING else self.old_value,
            "old_value_is_missing": self.old_value is _MISSING,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LogEntry":
        if data.get("old_value_is_missing", False) or "old_value" not in data:
            old_value = _MISSING
        else:
            old_value = data["old_value"]
        return cls(
            log_id=data["log_id"],
            timestamp=data.get("timestamp", 0.0),
            operation=OperationType(data["operation"]),
            transaction_id=data.get("transaction_id"),
            key=data.get("key"),
            value=data.get("value"),
            old_value=old_value,
        )
