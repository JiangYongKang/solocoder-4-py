class CacheWarmupError(Exception):
    """缓存预热基础异常"""
    pass


class TaskNotFoundError(CacheWarmupError):
    """预热任务不存在异常"""
    pass


class TaskAlreadyRegisteredError(CacheWarmupError):
    """预热任务重复注册异常"""
    pass


class CircularDependencyError(CacheWarmupError):
    """循环依赖异常"""
    pass


class DependencyNotFoundError(CacheWarmupError):
    """依赖任务不存在异常"""
    pass


class WarmupStateError(CacheWarmupError):
    """预热状态非法异常"""
    pass


class TaskExecutionError(CacheWarmupError):
    """任务执行失败异常"""
    pass


class OrchestratorNotConfiguredError(CacheWarmupError):
    """编排器未配置异常"""
    pass
