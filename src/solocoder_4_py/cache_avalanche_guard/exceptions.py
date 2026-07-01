class CacheAvalancheGuardError(Exception):
    """缓存雪崩防护基础异常"""


class CacheRebuildError(CacheAvalancheGuardError):
    """缓存重建异常"""

    def __init__(self, key: str, original_error: Exception) -> None:
        self.key = key
        self.original_error = original_error
        super().__init__(
            f"重建缓存键 {key} 时发生错误: {type(original_error).__name__}: {original_error}"
        )


class CacheDegradedError(CacheAvalancheGuardError):
    """缓存降级异常"""

    def __init__(self, key: str) -> None:
        self.key = key
        super().__init__(f"缓存键 {key} 已降级，返回占位值")


class HotKeyDetectionError(CacheAvalancheGuardError):
    """热点键检测异常"""
