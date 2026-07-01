from enum import Enum


class TaskState(Enum):
    """预热任务状态枚举"""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class WarmupState(Enum):
    """整体预热流程状态枚举"""
    NOT_STARTED = "NOT_STARTED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PARTIAL_COMPLETED = "PARTIAL_COMPLETED"
    FAILED = "FAILED"


class FailureStrategy(Enum):
    """预热任务失败策略枚举"""
    SKIP_DEPENDENTS = "SKIP_DEPENDENTS"
    CONTINUE_ANYWAY = "CONTINUE_ANYWAY"
    ABORT_ALL = "ABORT_ALL"


TERMINAL_TASK_STATES = frozenset({
    TaskState.COMPLETED,
    TaskState.FAILED,
    TaskState.SKIPPED,
})

TERMINAL_WARMUP_STATES = frozenset({
    WarmupState.COMPLETED,
    WarmupState.PARTIAL_COMPLETED,
    WarmupState.FAILED,
})
