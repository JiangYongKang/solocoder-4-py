from enum import Enum
from typing import Callable, Optional


class TaskType(Enum):
    """任务类型枚举"""

    ONE_SHOT = "ONE_SHOT"
    PERIODIC = "PERIODIC"
    MANUAL = "MANUAL"


class TaskStatus(Enum):
    """任务状态枚举"""

    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    ERROR = "ERROR"


class RunStatus(Enum):
    """运行结果状态枚举"""

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


TERMINAL_TASK_STATUSES = {TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.ERROR}
TERMINAL_RUN_STATUSES = {RunStatus.SUCCESS, RunStatus.FAILED, RunStatus.SKIPPED}

DEFAULT_HISTORY_LIMIT = 1000
DEFAULT_TIMEOUT_SECONDS = 300

TaskCallable = Callable[..., object]
