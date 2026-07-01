from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
from uuid import uuid4


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
    old_value: Any = None
    log_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: float = field(default_factory=lambda: __import__("time").time())
    lsn: int = 0

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
            "lsn": self.lsn,
            "timestamp": self.timestamp,
            "operation": self.operation.value,
            "transaction_id": self.transaction_id,
            "key": self.key,
            "value": self.value,
            "old_value": self.old_value,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LogEntry":
        return cls(
            log_id=data["log_id"],
            lsn=data.get("lsn", 0),
            timestamp=data.get("timestamp", 0.0),
            operation=OperationType(data["operation"]),
            transaction_id=data.get("transaction_id"),
            key=data.get("key"),
            value=data.get("value"),
            old_value=data.get("old_value"),
        )
