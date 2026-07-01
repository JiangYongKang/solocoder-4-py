import random
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple, TypeVar

from .cache_entry import CacheEntry
from .constants import (
    DEFAULT_BACKGROUND_RENEW_INTERVAL_SECONDS,
    DEFAULT_DEGRADED_TTL_SECONDS,
    DEFAULT_HOT_KEY_THRESHOLD,
    DEFAULT_HOT_KEY_WINDOW_SECONDS,
    DEFAULT_JITTER_RATIO,
    DEFAULT_MAX_CACHE_SIZE,
    DEFAULT_REBUILD_TIMEOUT_SECONDS,
    DEFAULT_TTL_SECONDS,
    REBUILD_LOCK_KEY_PREFIX,
    CacheEntryState,
    RebuildStrategy,
)
from .exceptions import CacheDegradedError, CacheRebuildError

T = TypeVar("T")


@dataclass
class CacheGuardStats:
    """缓存雪崩防护统计数据类"""

    accesses: int = 0
    hits: int = 0
    misses: int = 0
    sets: int = 0
    rebuilds: int = 0
    rebuild_failures: int = 0
    degraded_returns: int = 0
    hot_key_hits: int = 0
    background_renews: int = 0
    evictions: int = 0

    @property
    def hit_rate(self) -> float:
        """命中率"""
        if self.accesses == 0:
            return 0.0
        return self.hits / self.accesses

    def to_dict(self) -> Dict[str, Any]:
        return {
            "accesses": self.accesses,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": self.hit_rate,
            "sets": self.sets,
            "rebuilds": self.rebuilds,
            "rebuild_failures": self.rebuild_failures,
            "degraded_returns": self.degraded_returns,
            "hot_key_hits": self.hot_key_hits,
            "background_renews": self.background_renews,
            "evictions": self.evictions,
        }


class CacheAvalancheGuard:
    """缓存雪崩防护核心类

    使用纯内存数据结构模拟缓存读写和热点键重建，提供以下防护策略：
    1. 过期时间随机抖动 - 避免大量缓存同时过期
    2. 热点键后台续期 - 自动识别热点键并在后台提前续期
    3. 单飞重建锁 - 避免多个调用方同时重建同一个缓存
    4. 降级占位值 - 重建失败或缓存不可用时返回降级值
    """

    def __init__(
        self,
        max_size: Optional[int] = DEFAULT_MAX_CACHE_SIZE,
        default_ttl: float = DEFAULT_TTL_SECONDS,
        jitter_ratio: float = DEFAULT_JITTER_RATIO,
        hot_key_threshold: int = DEFAULT_HOT_KEY_THRESHOLD,
        hot_key_window_seconds: int = DEFAULT_HOT_KEY_WINDOW_SECONDS,
        rebuild_timeout_seconds: float = DEFAULT_REBUILD_TIMEOUT_SECONDS,
        background_renew_interval_seconds: float = DEFAULT_BACKGROUND_RENEW_INTERVAL_SECONDS,
        degraded_ttl_seconds: float = DEFAULT_DEGRADED_TTL_SECONDS,
        enable_background_renew: bool = True,
    ) -> None:
        """
        Args:
            max_size: 缓存最大容量，None 表示无限制
            default_ttl: 默认 TTL（秒）
            jitter_ratio: 过期时间抖动比例，0~0.5 之间
            hot_key_threshold: 热点键判定阈值（窗口内命中次数）
            hot_key_window_seconds: 热点键检测时间窗口（秒）
            rebuild_timeout_seconds: 重建超时时间（秒）
            background_renew_interval_seconds: 后台续期检查间隔（秒）
            degraded_ttl_seconds: 降级值 TTL（秒）
            enable_background_renew: 是否启用后台续期
        """
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._jitter_ratio = max(0.0, min(jitter_ratio, 0.5))
        self._hot_key_threshold = hot_key_threshold
        self._hot_key_window_seconds = hot_key_window_seconds
        self._rebuild_timeout_seconds = rebuild_timeout_seconds
        self._background_renew_interval_seconds = background_renew_interval_seconds
        self._degraded_ttl_seconds = degraded_ttl_seconds
        self._enable_background_renew = enable_background_renew

        self._store: "OrderedDict[str, CacheEntry]" = OrderedDict()
        self._rebuild_locks: Dict[str, threading.Event] = {}
        self._tag_index: Dict[str, Set[str]] = {}
        self._lock = threading.RLock()
        self._rebuild_lock = threading.RLock()
        self._stats = CacheGuardStats()

        self._background_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        if self._enable_background_renew:
            self._start_background_renew()

    # ------------------------------------------------------------
    # 生命周期管理
    # ------------------------------------------------------------
    def _start_background_renew(self) -> None:
        """启动后台续期线程"""
        self._background_thread = threading.Thread(
            target=self._background_renew_worker,
            daemon=True,
            name="cache-avalanche-guard-renewer",
        )
        self._background_thread.start()

    def stop(self) -> None:
        """停止后台线程"""
        self._stop_event.set()
        if self._background_thread is not None:
            self._background_thread.join(timeout=5)

    def _background_renew_worker(self) -> None:
        """后台续期工作线程"""
        while not self._stop_event.is_set():
            try:
                self._renew_hot_keys()
            except Exception:
                pass
            self._stop_event.wait(self._background_renew_interval_seconds)

    def _renew_hot_keys(self) -> None:
        """续期所有热点键"""
        with self._lock:
            hot_keys = self._find_hot_keys_locked()

        for key, entry in hot_keys:
            try:
                self._renew_hot_key(key, entry)
            except Exception:
                continue

    def _find_hot_keys_locked(self) -> List[Tuple[str, CacheEntry]]:
        """查找所有热点键（必须在持有锁的情况下调用）

        续期阈值基于条目自身的 original_ttl 计算，而非全局默认值，
        避免短 TTL 条目在续期检查间隔内过期。
        """
        now = time.time()
        hot_keys: List[Tuple[str, CacheEntry]] = []
        for key, entry in self._store.items():
            if entry.state != CacheEntryState.VALID:
                continue
            recent_hits = entry.get_recent_hit_count(
                self._hot_key_window_seconds, now
            )
            if recent_hits >= self._hot_key_threshold:
                remaining_ttl = entry.remaining_ttl(now)
                entry_ttl = entry.original_ttl if entry.original_ttl is not None else self._default_ttl
                if remaining_ttl is not None and remaining_ttl < (
                    entry_ttl * 0.3
                ):
                    hot_keys.append((key, entry))
        return hot_keys

    def _renew_hot_key(self, key: str, entry: CacheEntry) -> None:
        """续期单个热点键

        续期时继承条目自身的 original_ttl，而非使用全局默认值，
        避免短 TTL 条目被意外延长。
        """
        if entry.state != CacheEntryState.VALID:
            return

        with self._lock:
            current_entry = self._store.get(key)
            if current_entry is None or current_entry is not entry:
                return
            now = time.time()
            entry_ttl = current_entry.original_ttl if current_entry.original_ttl is not None else self._default_ttl
            new_expires_at = self._apply_jitter(
                now + entry_ttl, entry_ttl, now
            )
            current_entry.expires_at = new_expires_at
            self._stats.background_renews += 1

    # ------------------------------------------------------------
    # 过期时间抖动
    # ------------------------------------------------------------
    def _apply_jitter(
        self, base_expires_at: float, ttl: float, now: Optional[float] = None
    ) -> float:
        """为过期时间添加随机抖动

        使用单一时间戳避免高并发场景下的时间偏差问题。

        Args:
            base_expires_at: 基础过期时间戳
            ttl: TTL 秒数，用于计算抖动范围
            now: 当前时间戳，可选，不提供则使用 time.time()

        Returns:
            添加抖动后的过期时间戳
        """
        current_time = now if now is not None else time.time()
        if self._jitter_ratio <= 0:
            return base_expires_at
        jitter_range = ttl * self._jitter_ratio
        jitter = random.uniform(-jitter_range, jitter_range)
        return max(current_time + 0.001, base_expires_at + jitter)

    # ------------------------------------------------------------
    # 核心读操作
    # ------------------------------------------------------------
    def get(
        self,
        key: str,
        loader: Optional[Callable[[], T]] = None,
        degraded_value: Optional[Any] = None,
        tags: Optional[Iterable[str]] = None,
        ttl: Optional[float] = None,
        rebuild_strategy: RebuildStrategy = RebuildStrategy.SYNC,
    ) -> Optional[T]:
        """获取缓存值，支持读穿透和雪崩防护

        Args:
            key: 缓存键
            loader: 数据加载函数，缓存未命中时调用
            degraded_value: 降级占位值，重建失败时返回
            tags: 缓存标签列表
            ttl: 自定义 TTL（秒）
            rebuild_strategy: 重建策略

        Returns:
            缓存值、加载值或降级值
        """
        with self._lock:
            self._stats.accesses += 1
            entry = self._store.get(key)

            if entry is not None:
                entry.touch(
                    now=time.time(), window_seconds=self._hot_key_window_seconds
                )

                if entry.is_valid():
                    self._stats.hits += 1
                    if self._is_hot_key(entry):
                        self._stats.hot_key_hits += 1
                    self._store.move_to_end(key)
                    if entry.state == CacheEntryState.DEGRADED:
                        self._stats.degraded_returns += 1
                        return entry.degraded_value
                    return entry.value

            self._stats.misses += 1

        if loader is None:
            return degraded_value

        return self._rebuild_cache(
            key=key,
            loader=loader,
            degraded_value=degraded_value,
            tags=tags,
            ttl=ttl,
            strategy=rebuild_strategy,
        )

    def get_or_load(
        self,
        key: str,
        loader: Callable[[], T],
        **kwargs: Any,
    ) -> T:
        """带强制 loader 的获取"""
        result = self.get(key=key, loader=loader, **kwargs)
        return result  # type: ignore[return-value]

    # ------------------------------------------------------------
    # 热点键检测
    # ------------------------------------------------------------
    def _is_hot_key(self, entry: CacheEntry) -> bool:
        """判断是否为热点键"""
        recent_hits = entry.get_recent_hit_count(self._hot_key_window_seconds)
        return recent_hits >= self._hot_key_threshold

    def get_hot_keys(self) -> List[str]:
        """获取当前所有热点键列表"""
        with self._lock:
            now = time.time()
            return [
                key
                for key, entry in self._store.items()
                if entry.is_valid(now)
                and entry.get_recent_hit_count(self._hot_key_window_seconds, now)
                >= self._hot_key_threshold
            ]

    # ------------------------------------------------------------
    # 缓存重建（单飞模式）
    # ------------------------------------------------------------
    def _rebuild_cache(
        self,
        key: str,
        loader: Callable[[], T],
        degraded_value: Optional[Any],
        tags: Optional[Iterable[str]],
        ttl: Optional[float],
        strategy: RebuildStrategy,
    ) -> Optional[T]:
        """重建缓存，使用单飞模式避免重复重建

        支持 SYNC（同步）和 ASYNC（异步）两种重建策略：
        - SYNC: 调用方同步等待重建完成，返回加载结果
        - ASYNC: 调用方立即返回降级值（或 None），重建在后台线程执行

        Args:
            key: 缓存键
            loader: 数据加载函数
            degraded_value: 降级占位值
            tags: 标签列表
            ttl: 自定义 TTL
            strategy: 重建策略

        Returns:
            重建后的值或降级值
        """
        lock_key = REBUILD_LOCK_KEY_PREFIX + key

        with self._rebuild_lock:
            event = self._rebuild_locks.get(lock_key)
            if event is None:
                event = threading.Event()
                self._rebuild_locks[lock_key] = event
                is_rebuilder = True
            else:
                is_rebuilder = False

        if is_rebuilder:
            if strategy == RebuildStrategy.ASYNC:
                rebuild_thread = threading.Thread(
                    target=self._do_rebuild_async,
                    kwargs={
                        "key": key,
                        "loader": loader,
                        "degraded_value": degraded_value,
                        "tags": tags,
                        "ttl": ttl,
                        "event": event,
                        "lock_key": lock_key,
                    },
                    daemon=True,
                    name=f"cache-rebuild-{key}",
                )
                rebuild_thread.start()

                if degraded_value is not None:
                    with self._lock:
                        entry = self._store.get(key)
                        if entry is None:
                            tag_list = list(tags) if tags is not None else []
                            entry = CacheEntry(
                                key=key,
                                value=None,
                                degraded_value=degraded_value,
                                tags=tag_list,
                            )
                            self._store[key] = entry
                            self._update_tag_index(key, [], tag_list)
                        entry.mark_degraded(
                            degraded_value=degraded_value,
                            degraded_ttl=self._degraded_ttl_seconds,
                        )
                        if tags is not None:
                            entry.tags = list(tags)
                    self._stats.degraded_returns += 1
                    return degraded_value
                return None

            try:
                return self._do_rebuild(
                    key=key,
                    loader=loader,
                    degraded_value=degraded_value,
                    tags=tags,
                    ttl=ttl,
                    event=event,
                    lock_key=lock_key,
                )
            finally:
                with self._rebuild_lock:
                    self._rebuild_locks.pop(lock_key, None)
        else:
            wait_result = event.wait(timeout=self._rebuild_timeout_seconds)
            if wait_result:
                with self._lock:
                    entry = self._store.get(key)
                    if entry is not None and entry.is_valid():
                        if entry.state == CacheEntryState.DEGRADED:
                            self._stats.degraded_returns += 1
                            return entry.degraded_value
                        return entry.value

            if not wait_result and degraded_value is not None:
                with self._lock:
                    entry = self._store.get(key)
                    tag_list = list(tags) if tags is not None else []
                    if entry is None:
                        entry = CacheEntry(
                            key=key,
                            value=None,
                            tags=tag_list,
                        )
                        self._store[key] = entry
                        self._update_tag_index(key, [], tag_list)
                    entry.mark_degraded(
                        degraded_value=degraded_value,
                        degraded_ttl=self._degraded_ttl_seconds,
                    )
                    if tags is not None:
                        entry.tags = tag_list
                        self._update_tag_index(key, [], tag_list)
                self._stats.degraded_returns += 1
                return degraded_value

            with self._lock:
                entry = self._store.get(key)
                if entry is not None and entry.state == CacheEntryState.DEGRADED:
                    self._stats.degraded_returns += 1
                    return entry.degraded_value

            return degraded_value

    def _do_rebuild_async(
        self,
        key: str,
        loader: Callable[[], T],
        degraded_value: Optional[Any],
        tags: Optional[Iterable[str]],
        ttl: Optional[float],
        event: threading.Event,
        lock_key: str,
    ) -> None:
        """异步重建缓存的后台线程方法

        Args:
            key: 缓存键
            loader: 数据加载函数
            degraded_value: 降级占位值
            tags: 标签列表
            ttl: 自定义 TTL
            event: 重建完成事件
            lock_key: 锁键
        """
        try:
            self._do_rebuild(
                key=key,
                loader=loader,
                degraded_value=degraded_value,
                tags=tags,
                ttl=ttl,
                event=event,
                lock_key=lock_key,
            )
        except Exception:
            pass
        finally:
            with self._rebuild_lock:
                self._rebuild_locks.pop(lock_key, None)

    def _do_rebuild(
        self,
        key: str,
        loader: Callable[[], T],
        degraded_value: Optional[Any],
        tags: Optional[Iterable[str]],
        ttl: Optional[float],
        event: threading.Event,
        lock_key: str,
    ) -> Optional[T]:
        """执行实际的缓存重建

        Args:
            key: 缓存键
            loader: 数据加载函数
            degraded_value: 降级占位值
            tags: 标签列表
            ttl: 自定义 TTL
            event: 重建完成事件
            lock_key: 锁键

        Returns:
            重建后的值或降级值
        """
        try:
            with self._lock:
                entry = self._store.get(key)
                if entry is not None:
                    entry.mark_rebuilding()
                else:
                    entry = CacheEntry(
                        key=key,
                        value=None,
                        state=CacheEntryState.REBUILDING,
                    )
                    entry.rebuild_attempts = 1
                    entry.last_rebuild_at = time.time()
                    self._store[key] = entry

            try:
                value = loader()
            except Exception as exc:
                self._stats.rebuild_failures += 1
                with self._lock:
                    entry = self._store.get(key)
                    if entry is not None:
                        if degraded_value is not None:
                            entry.mark_degraded(
                                degraded_value=degraded_value,
                                degraded_ttl=self._degraded_ttl_seconds,
                            )
                            if tags is not None:
                                entry.tags = list(tags)
                            self._update_tag_index(key, [], entry.tags)
                event.set()
                if degraded_value is not None:
                    self._stats.degraded_returns += 1
                    return degraded_value
                raise CacheRebuildError(key, exc) from exc

            with self._lock:
                now = time.time()
                effective_ttl = ttl if ttl is not None else self._default_ttl
                base_expires_at = now + effective_ttl
                expires_at = self._apply_jitter(base_expires_at, effective_ttl, now)

                tag_list = list(tags) if tags is not None else []

                entry = self._store.get(key)
                if entry is not None:
                    old_tags = entry.tags
                    entry.mark_rebuilt(
                        value=value, expires_at=expires_at, original_ttl=effective_ttl
                    )
                    entry.tags = tag_list
                    self._update_tag_index(key, old_tags, tag_list)
                else:
                    entry = CacheEntry(
                        key=key,
                        value=value,
                        expires_at=expires_at,
                        original_ttl=effective_ttl,
                        tags=tag_list,
                    )
                    self._store[key] = entry
                    self._update_tag_index(key, [], tag_list)

                if self._max_size is not None:
                    while len(self._store) > self._max_size:
                        self._evict_lru_locked()

                self._store.move_to_end(key)

            self._stats.rebuilds += 1
            self._stats.sets += 1
            event.set()
            return value

        except CacheRebuildError:
            event.set()
            raise

    # ------------------------------------------------------------
    # 核心写操作
    # ------------------------------------------------------------
    def set(
        self,
        key: str,
        value: Any,
        tags: Optional[Iterable[str]] = None,
        ttl: Optional[float] = None,
    ) -> CacheEntry:
        """设置缓存条目

        Args:
            key: 缓存键
            value: 缓存值
            tags: 标签列表
            ttl: 自定义 TTL（秒）

        Returns:
            创建的缓存条目
        """
        with self._lock:
            now = time.time()
            effective_ttl = ttl if ttl is not None else self._default_ttl
            base_expires_at = now + effective_ttl
            expires_at = self._apply_jitter(base_expires_at, effective_ttl, now)

            tag_list = list(tags) if tags is not None else []

            old_entry = self._store.get(key)
            old_tags = old_entry.tags if old_entry is not None else []

            entry = CacheEntry(
                key=key,
                value=value,
                expires_at=expires_at,
                original_ttl=effective_ttl,
                tags=tag_list,
            )
            self._store[key] = entry
            self._update_tag_index(key, old_tags, tag_list)

            if self._max_size is not None:
                while len(self._store) > self._max_size:
                    self._evict_lru_locked()

            self._store.move_to_end(key)
            self._stats.sets += 1
            return entry

    # ------------------------------------------------------------
    # 失效操作
    # ------------------------------------------------------------
    def invalidate(self, key: str) -> bool:
        """按 key 失效单个缓存"""
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return False
            self._remove_entry_locked(key, entry)
            return True

    def invalidate_by_tag(self, tag: str) -> int:
        """按标签批量失效"""
        with self._lock:
            keys_to_invalidate = set(self._tag_index.get(tag, []))
            count = 0
            for key in keys_to_invalidate:
                entry = self._store.get(key)
                if entry is not None:
                    self._remove_entry_locked(key, entry)
                    count += 1
            return count

    def invalidate_by_tags(self, tags: Iterable[str]) -> int:
        """按多个标签批量失效"""
        with self._lock:
            affected_keys: Set[str] = set()
            for tag in tags:
                affected_keys.update(self._tag_index.get(tag, []))
            count = 0
            for key in affected_keys:
                entry = self._store.get(key)
                if entry is not None:
                    self._remove_entry_locked(key, entry)
                    count += 1
            return count

    def invalidate_all(self) -> int:
        """清空所有缓存"""
        with self._lock:
            count = len(self._store)
            self._store.clear()
            self._tag_index.clear()
            return count

    def invalidate_expired(self) -> int:
        """清理所有过期条目"""
        with self._lock:
            now = time.time()
            expired_keys = [
                key
                for key, entry in self._store.items()
                if not entry.is_valid(now)
                and entry.state != CacheEntryState.REBUILDING
            ]
            count = 0
            for key in expired_keys:
                entry = self._store[key]
                self._remove_entry_locked(key, entry)
                count += 1
            return count

    # ------------------------------------------------------------
    # 查询辅助
    # ------------------------------------------------------------
    def has(self, key: str) -> bool:
        """检查缓存键是否存在且有效"""
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return False
            return entry.is_valid()

    def keys(self) -> List[str]:
        """返回所有有效缓存键列表"""
        with self._lock:
            now = time.time()
            return [key for key, entry in self._store.items() if entry.is_valid(now)]

    def get_entry(self, key: str) -> Optional[CacheEntry]:
        """获取原始缓存条目"""
        with self._lock:
            return self._store.get(key)

    def size(self) -> int:
        """返回当前缓存条目数量"""
        with self._lock:
            return len(self._store)

    def get_stats(self) -> CacheGuardStats:
        """获取统计信息"""
        with self._lock:
            return CacheGuardStats(
                accesses=self._stats.accesses,
                hits=self._stats.hits,
                misses=self._stats.misses,
                sets=self._stats.sets,
                rebuilds=self._stats.rebuilds,
                rebuild_failures=self._stats.rebuild_failures,
                degraded_returns=self._stats.degraded_returns,
                hot_key_hits=self._stats.hot_key_hits,
                background_renews=self._stats.background_renews,
                evictions=self._stats.evictions,
            )

    def reset_stats(self) -> None:
        """重置统计信息"""
        with self._lock:
            self._stats = CacheGuardStats()

    # ------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------
    def _remove_entry_locked(self, key: str, entry: CacheEntry) -> None:
        """移除缓存条目（必须在持有锁的情况下调用）"""
        if key in self._store:
            del self._store[key]
        self._update_tag_index(key, entry.tags, [])

    def _evict_lru_locked(self) -> None:
        """淘汰最久未使用的条目（必须在持有锁的情况下调用）"""
        if not self._store:
            return
        lru_key, lru_entry = self._store.popitem(last=False)
        self._update_tag_index(lru_key, lru_entry.tags, [])
        self._stats.evictions += 1

    def _update_tag_index(
        self, key: str, old_tags: List[str], new_tags: List[str]
    ) -> None:
        """更新标签索引"""
        for tag in old_tags:
            if tag in self._tag_index:
                self._tag_index[tag].discard(key)
                if not self._tag_index[tag]:
                    del self._tag_index[tag]

        for tag in new_tags:
            if tag not in self._tag_index:
                self._tag_index[tag] = set()
            self._tag_index[tag].add(key)

    def __len__(self) -> int:
        return self.size()

    def __contains__(self, key: str) -> bool:
        return self.has(key)

    def __del__(self) -> None:
        self.stop()
