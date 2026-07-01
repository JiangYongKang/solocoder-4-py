from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .constants import TaskStatus, TaskType


@dataclass
class TaskDefinition:
    """任务定义"""

    task_id: str
    task_type: TaskType
    handler: Callable[..., Any]
    name: str = ""
    description: str = ""
    interval_seconds: Optional[float] = None
    max_retries: int = 0
    retry_delay_seconds: float = 0.0
    timeout_seconds: Optional[float] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name:
            self.name = self.task_id
        if self.task_type == TaskType.PERIODIC:
            if self.interval_seconds is None or self.interval_seconds <= 0:
                raise ValueError(
                    "PERIODIC 任务必须指定正的 interval_seconds"
                )

    def is_one_shot(self) -> bool:
        return self.task_type == TaskType.ONE_SHOT

    def is_periodic(self) -> bool:
        return self.task_type == TaskType.PERIODIC

    def is_manual(self) -> bool:
        return self.task_type == TaskType.MANUAL

    def has_tag(self, tag: str) -> bool:
        return tag in self.tags

    def has_any_tag(self, tags: List[str]) -> bool:
        return any(t in self.tags for t in tags)

    def has_all_tags(self, tags: List[str]) -> bool:
        return all(t in self.tags for t in tags)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type.value,
            "name": self.name,
            "description": self.description,
            "interval_seconds": self.interval_seconds,
            "max_retries": self.max_retries,
            "retry_delay_seconds": self.retry_delay_seconds,
            "timeout_seconds": self.timeout_seconds,
            "tags": list(self.tags),
            "metadata": dict(self.metadata),
        }


@dataclass
class TaskRuntimeInfo:
    """任务运行时信息"""

    definition: TaskDefinition
    status: TaskStatus = TaskStatus.PENDING
    registered_at: float = 0.0
    activated_at: Optional[float] = None
    paused_at: Optional[float] = None
    completed_at: Optional[float] = None
    cancelled_at: Optional[float] = None
    last_run_at: Optional[float] = None
    next_run_at: Optional[float] = None
    run_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    skip_count: int = 0
    last_error: Optional[str] = None
    catch_up: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.definition.task_id,
            "definition": self.definition.to_dict(),
            "status": self.status.value,
            "registered_at": self.registered_at,
            "activated_at": self.activated_at,
            "paused_at": self.paused_at,
            "completed_at": self.completed_at,
            "cancelled_at": self.cancelled_at,
            "last_run_at": self.last_run_at,
            "next_run_at": self.next_run_at,
            "run_count": self.run_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "skip_count": self.skip_count,
            "last_error": self.last_error,
            "catch_up": self.catch_up,
        }
