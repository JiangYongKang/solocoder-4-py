"""缓存雪崩防护模块

使用纯内存数据结构模拟缓存读写和热点键重建，提供以下防护策略：
1. 过期时间随机抖动 - 避免大量缓存同时过期引发雪崩
2. 热点键后台续期 - 自动识别热点键并在后台提前续期
3. 单飞重建锁 - 避免多个调用方同时重建同一个缓存
4. 降级占位值 - 重建失败或缓存不可用时返回降级值
"""

from .cache_entry import CacheEntry
from .cache_avalanche_guard import CacheAvalancheGuard, CacheGuardStats
from .constants import (
    CacheEntryState,
    RebuildStrategy,
    DEFAULT_MAX_CACHE_SIZE,
    DEFAULT_TTL_SECONDS,
    DEFAULT_JITTER_RATIO,
    DEFAULT_HOT_KEY_THRESHOLD,
    DEFAULT_HOT_KEY_WINDOW_SECONDS,
    DEFAULT_REBUILD_TIMEOUT_SECONDS,
    DEFAULT_BACKGROUND_RENEW_INTERVAL_SECONDS,
    DEFAULT_DEGRADED_TTL_SECONDS,
)
from .exceptions import (
    CacheAvalancheGuardError,
    CacheRebuildError,
    CacheDegradedError,
    HotKeyDetectionError,
)

__all__ = [
    "CacheAvalancheGuard",
    "CacheEntry",
    "CacheGuardStats",
    "CacheEntryState",
    "RebuildStrategy",
    "DEFAULT_MAX_CACHE_SIZE",
    "DEFAULT_TTL_SECONDS",
    "DEFAULT_JITTER_RATIO",
    "DEFAULT_HOT_KEY_THRESHOLD",
    "DEFAULT_HOT_KEY_WINDOW_SECONDS",
    "DEFAULT_REBUILD_TIMEOUT_SECONDS",
    "DEFAULT_BACKGROUND_RENEW_INTERVAL_SECONDS",
    "DEFAULT_DEGRADED_TTL_SECONDS",
    "CacheAvalancheGuardError",
    "CacheRebuildError",
    "CacheDegradedError",
    "HotKeyDetectionError",
]
