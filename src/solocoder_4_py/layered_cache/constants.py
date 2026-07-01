from enum import Enum


class CacheLevel(Enum):
    """缓存层级枚举"""

    LOCAL = "LOCAL"
    SHARED = "SHARED"
    SOURCE = "SOURCE"


class CacheEntryStatus(Enum):
    """缓存条目状态"""

    VALID = "VALID"
    EXPIRED = "EXPIRED"
    INVALIDATED = "INVALIDATED"


DEFAULT_LOCAL_MAX_SIZE = 1000
DEFAULT_SHARED_MAX_SIZE = 10000
DEFAULT_TTL_SECONDS = 300

LOCAL_CACHE_LABEL = "local"
SHARED_CACHE_LABEL = "shared"
