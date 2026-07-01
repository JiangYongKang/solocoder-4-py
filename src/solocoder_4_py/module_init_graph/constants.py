from enum import Enum


class ModuleState(Enum):
    """模块初始化状态枚举"""
    PENDING = "PENDING"
    INITIALIZING = "INITIALIZING"
    INITIALIZED = "INITIALIZED"
    FAILED = "FAILED"
    ISOLATED = "ISOLATED"


class InitState(Enum):
    """整体初始化流程状态枚举"""
    NOT_STARTED = "NOT_STARTED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PARTIAL_COMPLETED = "PARTIAL_COMPLETED"
    FAILED = "FAILED"


TERMINAL_MODULE_STATES = frozenset({
    ModuleState.INITIALIZED,
    ModuleState.FAILED,
    ModuleState.ISOLATED,
})

TERMINAL_INIT_STATES = frozenset({
    InitState.COMPLETED,
    InitState.PARTIAL_COMPLETED,
    InitState.FAILED,
})
