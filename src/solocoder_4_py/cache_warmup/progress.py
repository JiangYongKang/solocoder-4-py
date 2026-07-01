from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .constants import TaskState, WarmupState


@dataclass
class TaskProgress:
    """单个任务的进度信息"""
    task_id: str
    state: TaskState = TaskState.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: str = ""
    loaded_data_preview: str = ""
    attempts: int = 0
    duration_seconds: float = 0.0
    extra: Dict[str, Any] = field(default_factory=dict)

    def mark_running(self) -> None:
        self.state = TaskState.RUNNING
        self.started_at = datetime.now()
        self.attempts += 1

    def mark_completed(self, duration: float, data_preview: str = "") -> None:
        self.state = TaskState.COMPLETED
        self.completed_at = datetime.now()
        self.duration_seconds = duration
        self.loaded_data_preview = data_preview

    def mark_failed(self, duration: float, error: str = "") -> None:
        self.state = TaskState.FAILED
        self.completed_at = datetime.now()
        self.duration_seconds = duration
        self.error_message = error

    def mark_skipped(self, reason: str = "") -> None:
        self.state = TaskState.SKIPPED
        self.completed_at = datetime.now()
        self.error_message = reason

    def is_terminal(self) -> bool:
        return self.state in (
            TaskState.COMPLETED,
            TaskState.FAILED,
            TaskState.SKIPPED,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "state": self.state.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
            "loaded_data_preview": self.loaded_data_preview,
            "attempts": self.attempts,
            "duration_seconds": round(self.duration_seconds, 4),
        }


@dataclass
class WarmupProgress:
    """整体预热流程的进度信息"""
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    skipped_tasks: int = 0
    running_tasks: int = 0
    pending_tasks: int = 0
    state: WarmupState = WarmupState.NOT_STARTED
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    task_progress: Dict[str, TaskProgress] = field(default_factory=dict)

    @property
    def progress_percentage(self) -> float:
        if self.total_tasks == 0:
            return 100.0
        done = self.completed_tasks + self.failed_tasks + self.skipped_tasks
        return round((done / self.total_tasks) * 100, 2)

    def recalculate_counts(self) -> None:
        self.completed_tasks = 0
        self.failed_tasks = 0
        self.skipped_tasks = 0
        self.running_tasks = 0
        self.pending_tasks = 0
        for tp in self.task_progress.values():
            if tp.state == TaskState.COMPLETED:
                self.completed_tasks += 1
            elif tp.state == TaskState.FAILED:
                self.failed_tasks += 1
            elif tp.state == TaskState.SKIPPED:
                self.skipped_tasks += 1
            elif tp.state == TaskState.RUNNING:
                self.running_tasks += 1
            else:
                self.pending_tasks += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_tasks": self.total_tasks,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "skipped_tasks": self.skipped_tasks,
            "running_tasks": self.running_tasks,
            "pending_tasks": self.pending_tasks,
            "progress_percentage": self.progress_percentage,
            "state": self.state.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "tasks": {tid: tp.to_dict() for tid, tp in self.task_progress.items()},
        }
