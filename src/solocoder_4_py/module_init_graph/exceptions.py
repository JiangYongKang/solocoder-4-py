from typing import List


class ModuleInitError(Exception):
    """模块初始化基础异常"""
    pass


class ModuleNotFoundError(ModuleInitError):
    """模块不存在异常"""
    pass


class ModuleAlreadyRegisteredError(ModuleInitError):
    """模块重复注册异常"""
    pass


class CircularDependencyError(ModuleInitError):
    """循环依赖异常"""

    def __init__(self, message: str, cycles: List[List[str]] | None = None) -> None:
        super().__init__(message)
        self.cycles = cycles or []


class DependencyNotFoundError(ModuleInitError):
    """依赖模块不存在异常"""
    pass


class InitStateError(ModuleInitError):
    """初始化状态非法异常"""
    pass


class ModuleInitFailureError(ModuleInitError):
    """模块初始化失败异常"""
    pass


class RetryLimitExceededError(ModuleInitError):
    """重试次数超过限制异常"""
    pass
