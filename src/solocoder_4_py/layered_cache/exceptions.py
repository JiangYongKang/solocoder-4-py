class LayeredCacheError(Exception):
    """分层缓存基础异常"""


class CacheLoaderError(LayeredCacheError):
    """数据加载函数执行异常"""

    def __init__(self, key: str, original_error: Exception) -> None:
        self.key = key
        self.original_error = original_error
        super().__init__(
            f"加载缓存键 {key} 时发生错误: {type(original_error).__name__}: {original_error}"
        )


class InvalidationError(LayeredCacheError):
    """缓存失效操作异常"""
