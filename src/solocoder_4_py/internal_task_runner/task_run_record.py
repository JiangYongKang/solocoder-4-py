from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from uuid import uuid4

from .constants import RunStatus


@dataclass
class TaskRunRecord:
    """任务运行记录"""

    task_id: str
    run_id: str = field(default_factory=lambda: str(uuid4()))
    status: RunStatus = RunStatus.SUCCESS
    started_at: float = 0.0
    finished_at: float = 0.0
    result: Optional[Any] = None
    error_message: Optional[str] = None
    error_type: Optional[str] = None
    attempt: int = 1
    trigger: str = "MANUAL"
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration_ms(self) -> float:
        """运行时长（毫秒）"""
        if self.started_at == 0.0 or self.finished_at == 0.0:
            return 0.0
        return (self.finished_at - self.started_at) * 1000.0

    @property
    def is_success(self) -> bool:
        return self.status == RunStatus.SUCCESS

    @property
    def is_failed(self) -> bool:
        return self.status == RunStatus.FAILED

    @property
    def is_skipped(self) -> bool:
        return self.status == RunStatus.SKIPPED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "task_id": self.task_id,
            "status": self.status.value,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_ms": self.duration_ms,
            "result": self.result,
            "error_message": self.error_message,
            "error_type": self.error_type,
            "attempt": self.attempt,
            "trigger": self.trigger,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskRunRecord":
        return cls(
            run_id=data["run_id"],
            task_id=data["task_id"],
            status=RunStatus(data["status"]),
            started_at=data.get("started_at", 0.0),
            finished_at=data.get("finished_at", 0.0),
            result=data.get("result"),
            error_message=data.get("error_message"),
            error_type=data.get("error_type"),
            attempt=data.get("attempt", 1),
            trigger=data.get("trigger", "MANUAL"),
            metadata=dict(data.get("metadata", {})),
        )
