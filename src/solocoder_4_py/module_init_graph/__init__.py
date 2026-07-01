"""模块初始化依赖图模块

使用纯内存数据结构描述模块和依赖关系，
支持依赖解析、启动顺序排序、循环依赖检测、失败隔离与局部重试。
"""

from .constants import (
    ModuleState,
    InitState,
    TERMINAL_MODULE_STATES,
    TERMINAL_INIT_STATES,
)
from .exceptions import (
    ModuleInitError,
    ModuleNotFoundError,
    ModuleAlreadyRegisteredError,
    CircularDependencyError,
    DependencyNotFoundError,
    InitStateError,
    ModuleInitFailureError,
    RetryLimitExceededError,
)
from .module import ModuleNode
from .topology import TopologyAnalyzer, CycleReport
from .initializer import InitProgress, ModuleProgress, ModuleInitializer

__all__ = [
    "ModuleState",
    "InitState",
    "TERMINAL_MODULE_STATES",
    "TERMINAL_INIT_STATES",
    "ModuleInitError",
    "ModuleNotFoundError",
    "ModuleAlreadyRegisteredError",
    "CircularDependencyError",
    "DependencyNotFoundError",
    "InitStateError",
    "ModuleInitFailureError",
    "RetryLimitExceededError",
    "ModuleNode",
    "TopologyAnalyzer",
    "CycleReport",
    "ModuleProgress",
    "InitProgress",
    "ModuleInitializer",
]
