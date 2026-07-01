"""内部任务运行器模块

使用纯内存数据结构管理任务定义和运行记录，
支持一次性任务、周期任务和手动触发任务，
并提供完整的运行历史查询功能。
"""

from .constants import (
    DEFAULT_HISTORY_LIMIT,
    DEFAULT_TIMEOUT_SECONDS,
    TERMINAL_RUN_STATUSES,
    TERMINAL_TASK_STATUSES,
    RunStatus,
    TaskStatus,
    TaskType,
)
from .exceptions import (
    InvalidScheduleError,
    TaskAlreadyRegisteredError,
    TaskExecutionError,
    TaskNotFoundError,
    TaskRunnerError,
    TaskStateError,
    TaskTypeError,
)
from .internal_task_runner import InternalTaskRunner, TaskRunnerStats
from .task_definition import TaskDefinition, TaskRuntimeInfo
from .task_run_record import TaskRunRecord

__all__ = [
    "DEFAULT_HISTORY_LIMIT",
    "DEFAULT_TIMEOUT_SECONDS",
    "TERMINAL_RUN_STATUSES",
    "TERMINAL_TASK_STATUSES",
    "RunStatus",
    "TaskStatus",
    "TaskType",
    "InvalidScheduleError",
    "TaskAlreadyRegisteredError",
    "TaskExecutionError",
    "TaskNotFoundError",
    "TaskRunnerError",
    "TaskStateError",
    "TaskTypeError",
    "InternalTaskRunner",
    "TaskRunnerStats",
    "TaskDefinition",
    "TaskRuntimeInfo",
    "TaskRunRecord",
]
