"""缓存预热编排模块

使用纯内存数据结构模拟热点数据加载的预热编排过程，
支持任务依赖关系声明、按序执行、失败策略和进度追踪。
"""

from .constants import (
    FailureStrategy,
    TaskState,
    TERMINAL_TASK_STATES,
    TERMINAL_WARMUP_STATES,
    WarmupState,
)
from .exceptions import (
    CacheWarmupError,
    CircularDependencyError,
    DependencyNotFoundError,
    OrchestratorNotConfiguredError,
    TaskAlreadyRegisteredError,
    TaskExecutionError,
    TaskNotFoundError,
    WarmupStateError,
)
from .orchestrator import WarmupContext, WarmupOrchestrator
from .progress import TaskProgress, WarmupProgress
from .task import WarmupTask
from .topology import TopologySorter

__all__ = [
    "TaskState",
    "WarmupState",
    "FailureStrategy",
    "TERMINAL_TASK_STATES",
    "TERMINAL_WARMUP_STATES",
    "CacheWarmupError",
    "TaskNotFoundError",
    "TaskAlreadyRegisteredError",
    "CircularDependencyError",
    "DependencyNotFoundError",
    "WarmupStateError",
    "TaskExecutionError",
    "OrchestratorNotConfiguredError",
    "WarmupTask",
    "TaskProgress",
    "WarmupProgress",
    "TopologySorter",
    "WarmupContext",
    "WarmupOrchestrator",
]
