import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple, TypeVar

from .cache_entry import CacheEntry
from .constants import (
    DEFAULT_LOCAL_MAX_SIZE,
    DEFAULT_SHARED_MAX_SIZE,
    DEFAULT_TTL_SECONDS,
    LOCAL_CACHE_LABEL,
    SHARED_CACHE_LABEL,
    CacheEntryStatus,
    CacheLevel,
)
from .exceptions import CacheLoaderError

T = TypeVar("T")

_UNSET = object()


@dataclass
class CacheStats:
    """缓存统计数据类"""

    accesses: int = 0
    hits: int = 0
    misses: int = 0
    sets: int = 0
    invalidations: int = 0
    evictions: int = 0
    loader_calls: int = 0

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
            "invalidations": self.invalidations,
            "evictions": self.evictions,
            "loader_calls": self.loader_calls,
        }


class SingleLevelCache:
    """单层级缓存实现（支持 LRU 淘汰和 TTL 过期）"""

    def __init__(
        self,
        max_size: Optional[int] = None,
        default_ttl: Optional[float] = None,
        label: str = "cache",
    ) -> None:
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._label = label
        self._store: "OrderedDict[str, CacheEntry]" = OrderedDict()
        self._tag_index: Dict[str, Set[str]] = {}
        self._lock = threading.RLock()
        self._stats = CacheStats()

    # ------------------------------------------------------------
    # 基础读操作
    # ------------------------------------------------------------
    def get(self, key: str) -> Optional[CacheEntry]:
        """获取缓存条目（自动检查有效性，访问时移到末尾表示最近使用）"""
        with self._lock:
            self._stats.accesses += 1
            entry = self._store.get(key)
            if entry is None:
                self._stats.misses += 1
                return None

            if not entry.is_valid():
                self._remove_entry(key, entry)
                self._stats.misses += 1
                return None

            self._store.move_to_end(key)
            entry.touch()
            self._stats.hits += 1
            return entry

    def get_value(self, key: str) -> Optional[Any]:
        """仅获取缓存值"""
        entry = self.get(key)
        return entry.value if entry is not None else None

    def has(self, key: str) -> bool:
        """检查缓存键是否存在且有效"""
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return False
            if not entry.is_valid():
                self._remove_entry(key, entry)
                return False
            return True

    # ------------------------------------------------------------
    # 基础写操作
    # ------------------------------------------------------------
    def set(
        self,
        key: str,
        value: Any,
        tags: Optional[Iterable[str]] = None,
        ttl: Optional[float] = _UNSET,
    ) -> CacheEntry:
        """设置缓存条目

        Args:
            key: 缓存键
            value: 缓存值
            tags: 标签列表
            ttl: 过期时间（秒）。None 表示永不过期；不传则使用 default_ttl
        """
        with self._lock:
            if ttl is _UNSET:
                effective_ttl = self._default_ttl
            else:
                effective_ttl = ttl
            expires_at = None
            if effective_ttl is not None:
                expires_at = time.time() + effective_ttl

            tag_list = list(tags) if tags is not None else []

            if key in self._store:
                old_entry = self._store[key]
                self._remove_tag_index(key, old_entry.tags)

            if self._max_size is not None and key not in self._store:
                while len(self._store) >= self._max_size:
                    self._evict_lru()

            entry = CacheEntry(
                key=key,
                value=value,
                tags=tag_list,
                expires_at=expires_at,
            )
            self._store[key] = entry
            self._add_tag_index(key, tag_list)
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
            self._remove_entry(key, entry)
            self._stats.invalidations += 1
            return True

    def invalidate_by_tag(self, tag: str) -> int:
        """按标签批量失效"""
        with self._lock:
            keys_to_invalidate = set(self._tag_index.get(tag, []))
            count = 0
            for key in keys_to_invalidate:
                entry = self._store.get(key)
                if entry is not None:
                    self._remove_entry(key, entry)
                    count += 1
            self._stats.invalidations += count
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
                    self._remove_entry(key, entry)
                    count += 1
            self._stats.invalidations += count
            return count

    def invalidate_all(self) -> int:
        """清空所有缓存"""
        with self._lock:
            count = len(self._store)
            self._store.clear()
            self._tag_index.clear()
            self._stats.invalidations += count
            return count

    def invalidate_expired(self) -> int:
        """清理所有过期条目"""
        with self._lock:
            now = time.time()
            expired_keys = [
                key
                for key, entry in self._store.items()
                if not entry.is_valid(now)
            ]
            count = 0
            for key in expired_keys:
                entry = self._store[key]
                self._remove_entry(key, entry)
                count += 1
            self._stats.invalidations += count
            return count

    # ------------------------------------------------------------
    # 查询辅助
    # ------------------------------------------------------------
    def keys(self) -> List[str]:
        """返回所有有效缓存键列表"""
        with self._lock:
            now = time.time()
            return [
                key
                for key, entry in self._store.items()
                if entry.is_valid(now)
            ]

    def get_entry(self, key: str) -> Optional[CacheEntry]:
        """获取原始缓存条目（不统计访问，不检查有效性）"""
        with self._lock:
            return self._store.get(key)

    def size(self) -> int:
        """返回当前缓存条目数量（含可能过期的）"""
        with self._lock:
            return len(self._store)

    def get_stats(self) -> CacheStats:
        """获取统计信息"""
        with self._lock:
            return CacheStats(
                accesses=self._stats.accesses,
                hits=self._stats.hits,
                misses=self._stats.misses,
                sets=self._stats.sets,
                invalidations=self._stats.invalidations,
                evictions=self._stats.evictions,
                loader_calls=self._stats.loader_calls,
            )

    def reset_stats(self) -> None:
        """重置统计信息"""
        with self._lock:
            self._stats = CacheStats()

    # ------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------
    def _remove_entry(self, key: str, entry: CacheEntry) -> None:
        if key in self._store:
            del self._store[key]
        self._remove_tag_index(key, entry.tags)

    def _evict_lru(self) -> None:
        if not self._store:
            return
        lru_key, lru_entry = self._store.popitem(last=False)
        self._remove_tag_index(lru_key, lru_entry.tags)
        self._stats.evictions += 1

    def _add_tag_index(self, key: str, tags: List[str]) -> None:
        for tag in tags:
            if tag not in self._tag_index:
                self._tag_index[tag] = set()
            self._tag_index[tag].add(key)

    def _remove_tag_index(self, key: str, tags: List[str]) -> None:
        for tag in tags:
            if tag in self._tag_index:
                self._tag_index[tag].discard(key)
                if not self._tag_index[tag]:
                    del self._tag_index[tag]

    def __len__(self) -> int:
        return self.size()

    def __contains__(self, key: str) -> bool:
        return self.has(key)


class LayeredCache:
    """分层缓存核心类

    缓存层级：
      L1 LOCAL  -> 本地内存缓存，速度快，容量小
      L2 SHARED -> 共享内存缓存，模拟分布式/进程间缓存，容量较大
      SOURCE    -> 数据源，通过 loader 函数加载

    读穿透流程：
      get(key) -> 查 L1 -> 命中返回
                    -> 未命中 -> 查 L2 -> 命中回填 L1 并返回
                                    -> 未命中 -> 调 loader -> 回填 L2 + L1 -> 返回

    写后失效：
      写入数据后通过 invalidate/invalidate_by_tag 让相关缓存失效
    """

    def __init__(
        self,
        local_max_size: Optional[int] = DEFAULT_LOCAL_MAX_SIZE,
        shared_max_size: Optional[int] = DEFAULT_SHARED_MAX_SIZE,
        local_ttl: Optional[float] = DEFAULT_TTL_SECONDS,
        shared_ttl: Optional[float] = DEFAULT_TTL_SECONDS * 2,
        shared_cache_instance: Optional[SingleLevelCache] = None,
    ) -> None:
        self._local = SingleLevelCache(
            max_size=local_max_size,
            default_ttl=local_ttl,
            label=LOCAL_CACHE_LABEL,
        )
        if shared_cache_instance is not None:
            self._shared = shared_cache_instance
        else:
            self._shared = SingleLevelCache(
                max_size=shared_max_size,
                default_ttl=shared_ttl,
                label=SHARED_CACHE_LABEL,
            )
        self._lock = threading.RLock()
        self._request_stats = CacheStats()

    # ------------------------------------------------------------
    # 内部辅助方法
    # ------------------------------------------------------------
    def _resolve_shared_hit_backfill_ttl(
        self,
        shared_entry: CacheEntry,
        ttl: Optional[float],
        local_ttl: Optional[float],
    ) -> Optional[float]:
        """解析共享缓存命中回填本地时的 TTL

        优先级：local_ttl > 统一 ttl > 共享条目 remaining_ttl > 共享永不过期
        """
        if local_ttl is not _UNSET:
            return local_ttl
        elif ttl is not _UNSET:
            return ttl
        elif shared_entry.expires_at is not None:
            return max(0.0, shared_entry.remaining_ttl())
        else:
            return None

    def _resolve_loader_backfill_ttls(
        self,
        ttl: Optional[float],
        local_ttl: Optional[float],
        shared_ttl: Optional[float],
    ) -> Tuple[object, object]:
        """解析 loader 回填时的 TTL，返回 (effective_local_ttl, effective_shared_ttl)

        优先级：local_ttl/shared_ttl > 统一 ttl > _UNSET（使用各层 default_ttl）
        """
        if shared_ttl is not _UNSET:
            effective_shared_ttl = shared_ttl
        elif ttl is not _UNSET:
            effective_shared_ttl = ttl
        else:
            effective_shared_ttl = _UNSET

        if local_ttl is not _UNSET:
            effective_local_ttl = local_ttl
        elif ttl is not _UNSET:
            effective_local_ttl = ttl
        else:
            effective_local_ttl = _UNSET

        return effective_local_ttl, effective_shared_ttl

    def _set_both_levels(
        self,
        key: str,
        value: Any,
        tags: Iterable[str],
        effective_local_ttl: object,
        effective_shared_ttl: object,
    ) -> None:
        """同时写入本地和共享缓存"""
        if effective_shared_ttl is _UNSET:
            self._shared.set(key=key, value=value, tags=tags)
        else:
            self._shared.set(key=key, value=value, tags=tags, ttl=effective_shared_ttl)
        if effective_local_ttl is _UNSET:
            self._local.set(key=key, value=value, tags=tags)
        else:
            self._local.set(key=key, value=value, tags=tags, ttl=effective_local_ttl)

    # ------------------------------------------------------------
    # 核心：读穿透访问
    # ------------------------------------------------------------
    def get(
        self,
        key: str,
        loader: Optional[Callable[[], T]] = None,
        tags: Optional[Iterable[str]] = None,
        ttl: Optional[float] = _UNSET,
        local_ttl: Optional[float] = _UNSET,
        shared_ttl: Optional[float] = _UNSET,
    ) -> Optional[T]:
        """分层读取缓存，支持读穿透

        Args:
            key: 缓存键
            loader: 数据加载函数，所有层级都未命中时调用
            tags: 加载时回填到缓存的标签列表
            ttl: 统一的 TTL（秒）。None 表示永不过期；不传则使用各层默认 TTL
            local_ttl: 本地缓存 TTL（秒）。None 表示永不过期；不传则使用 ttl 或默认
            shared_ttl: 共享缓存 TTL（秒）。None 表示永不过期；不传则使用 ttl 或默认

        Returns:
            缓存值，未命中且无 loader 时返回 None
        """
        with self._lock:
            self._request_stats.accesses += 1

            local_entry = self._local.get(key)
            if local_entry is not None:
                self._request_stats.hits += 1
                return local_entry.value

            shared_entry = self._shared.get(key)
            if shared_entry is not None:
                self._request_stats.hits += 1

                effective_local_ttl = self._resolve_shared_hit_backfill_ttl(
                    shared_entry, ttl, local_ttl
                )
                self._local.set(
                    key=key,
                    value=shared_entry.value,
                    tags=shared_entry.tags,
                    ttl=effective_local_ttl,
                )
                return shared_entry.value

            self._request_stats.misses += 1

            if loader is None:
                return None

            try:
                loaded_value = loader()
            except Exception as exc:
                raise CacheLoaderError(key, exc) from exc

            if loaded_value is None:
                return None

            self._request_stats.loader_calls += 1
            effective_tags = list(tags) if tags is not None else []

            effective_local_ttl, effective_shared_ttl = self._resolve_loader_backfill_ttls(
                ttl, local_ttl, shared_ttl
            )
            self._set_both_levels(
                key=key,
                value=loaded_value,
                tags=effective_tags,
                effective_local_ttl=effective_local_ttl,
                effective_shared_ttl=effective_shared_ttl,
            )
            return loaded_value

    def get_or_load(
        self,
        key: str,
        loader: Callable[[], T],
        tags: Optional[Iterable[str]] = None,
        **kwargs: Any,
    ) -> Optional[T]:
        """带强制 loader 的获取，loader 必传

        Returns:
            加载后的缓存值；当 loader 返回 None 时返回 None
        """
        result = self.get(key=key, loader=loader, tags=tags, **kwargs)
        return result

    # ------------------------------------------------------------
    # 单独查询某一层
    # ------------------------------------------------------------
    def get_local(self, key: str) -> Optional[Any]:
        """仅查询本地缓存"""
        return self._local.get_value(key)

    def get_shared(self, key: str) -> Optional[Any]:
        """仅查询共享缓存"""
        return self._shared.get_value(key)

    def get_with_level(
        self,
        key: str,
        loader: Optional[Callable[[], T]] = None,
        tags: Optional[Iterable[str]] = None,
        ttl: Optional[float] = _UNSET,
        local_ttl: Optional[float] = _UNSET,
        shared_ttl: Optional[float] = _UNSET,
    ) -> Tuple[Optional[T], Optional[CacheLevel]]:
        """获取值并返回命中的层级，支持读穿透

        Args:
            key: 缓存键
            loader: 数据加载函数，所有层级都未命中时调用
            tags: 加载时回填到缓存的标签列表
            ttl: 统一的 TTL（秒）。None 表示永不过期；不传则使用各层默认 TTL
            local_ttl: 本地缓存 TTL（秒）。None 表示永不过期；不传则使用 ttl 或默认
            shared_ttl: 共享缓存 TTL（秒）。None 表示永不过期；不传则使用 ttl 或默认

        Returns:
            (value, level) 元组，level 为 None 表示未命中且无 loader 或 loader 返回 None
        """
        with self._lock:
            self._request_stats.accesses += 1

            local_entry = self._local.get(key)
            if local_entry is not None:
                self._request_stats.hits += 1
                return local_entry.value, CacheLevel.LOCAL

            shared_entry = self._shared.get(key)
            if shared_entry is not None:
                self._request_stats.hits += 1

                effective_local_ttl = self._resolve_shared_hit_backfill_ttl(
                    shared_entry, ttl, local_ttl
                )
                self._local.set(
                    key=key,
                    value=shared_entry.value,
                    tags=shared_entry.tags,
                    ttl=effective_local_ttl,
                )
                return shared_entry.value, CacheLevel.SHARED

            self._request_stats.misses += 1

            if loader is None:
                return None, None

            try:
                loaded_value = loader()
            except Exception as exc:
                raise CacheLoaderError(key, exc) from exc

            if loaded_value is None:
                return None, CacheLevel.SOURCE

            self._request_stats.loader_calls += 1
            effective_tags = list(tags) if tags is not None else []

            effective_local_ttl, effective_shared_ttl = self._resolve_loader_backfill_ttls(
                ttl, local_ttl, shared_ttl
            )
            self._set_both_levels(
                key=key,
                value=loaded_value,
                tags=effective_tags,
                effective_local_ttl=effective_local_ttl,
                effective_shared_ttl=effective_shared_ttl,
            )
            return loaded_value, CacheLevel.SOURCE

    # ------------------------------------------------------------
    # 写入缓存（主动写入，非读穿透）
    # ------------------------------------------------------------
    def set(
        self,
        key: str,
        value: Any,
        tags: Optional[Iterable[str]] = None,
        ttl: Optional[float] = _UNSET,
        local_ttl: Optional[float] = _UNSET,
        shared_ttl: Optional[float] = _UNSET,
        write_local: bool = True,
        write_shared: bool = True,
    ) -> None:
        """主动写入缓存

        Args:
            key: 缓存键
            value: 缓存值
            tags: 标签列表
            ttl: 统一 TTL。None 表示永不过期；不传则使用各层默认 TTL
            local_ttl: 本地缓存 TTL。None 表示永不过期；不传则使用 ttl 或默认
            shared_ttl: 共享缓存 TTL。None 表示永不过期；不传则使用 ttl 或默认
            write_local: 是否写入本地缓存
            write_shared: 是否写入共享缓存
        """
        with self._lock:
            tag_list = list(tags) if tags is not None else []

            if shared_ttl is not _UNSET:
                effective_shared_ttl = shared_ttl
            elif ttl is not _UNSET:
                effective_shared_ttl = ttl
            else:
                effective_shared_ttl = _UNSET

            if local_ttl is not _UNSET:
                effective_local_ttl = local_ttl
            elif ttl is not _UNSET:
                effective_local_ttl = ttl
            else:
                effective_local_ttl = _UNSET

            if write_shared:
                if effective_shared_ttl is _UNSET:
                    self._shared.set(
                        key=key,
                        value=value,
                        tags=tag_list,
                    )
                else:
                    self._shared.set(
                        key=key,
                        value=value,
                        tags=tag_list,
                        ttl=effective_shared_ttl,
                    )
            if write_local:
                if effective_local_ttl is _UNSET:
                    self._local.set(
                        key=key,
                        value=value,
                        tags=tag_list,
                    )
                else:
                    self._local.set(
                        key=key,
                        value=value,
                        tags=tag_list,
                        ttl=effective_local_ttl,
                    )

    def set_local(
        self,
        key: str,
        value: Any,
        tags: Optional[Iterable[str]] = None,
        ttl: Optional[float] = _UNSET,
    ) -> None:
        """仅写入本地缓存

        Args:
            key: 缓存键
            value: 缓存值
            tags: 标签列表
            ttl: 过期时间（秒）。None 表示永不过期；不传则使用本地默认 TTL
        """
        if ttl is _UNSET:
            self._local.set(key=key, value=value, tags=tags)
        else:
            self._local.set(key=key, value=value, tags=tags, ttl=ttl)

    def set_shared(
        self,
        key: str,
        value: Any,
        tags: Optional[Iterable[str]] = None,
        ttl: Optional[float] = _UNSET,
    ) -> None:
        """仅写入共享缓存

        Args:
            key: 缓存键
            value: 缓存值
            tags: 标签列表
            ttl: 过期时间（秒）。None 表示永不过期；不传则使用共享默认 TTL
        """
        if ttl is _UNSET:
            self._shared.set(key=key, value=value, tags=tags)
        else:
            self._shared.set(key=key, value=value, tags=tags, ttl=ttl)

    # ------------------------------------------------------------
    # 失效操作（写后失效核心）
    # ------------------------------------------------------------
    def invalidate(self, key: str) -> Dict[str, bool]:
        """按 key 失效所有层级的缓存

        Returns:
            {"local": bool, "shared": bool} 表示各层是否执行了失效
        """
        with self._lock:
            return {
                "local": self._local.invalidate(key),
                "shared": self._shared.invalidate(key),
            }

    def invalidate_by_tag(self, tag: str) -> Dict[str, int]:
        """按标签失效所有层级

        Returns:
            {"local": count, "shared": count}
        """
        with self._lock:
            return {
                "local": self._local.invalidate_by_tag(tag),
                "shared": self._shared.invalidate_by_tag(tag),
            }

    def invalidate_by_tags(self, tags: Iterable[str]) -> Dict[str, int]:
        """按多个标签失效所有层级"""
        with self._lock:
            return {
                "local": self._local.invalidate_by_tags(tags),
                "shared": self._shared.invalidate_by_tags(tags),
            }

    def invalidate_local(self, key: str) -> bool:
        """仅失效本地缓存"""
        return self._local.invalidate(key)

    def invalidate_shared(self, key: str) -> bool:
        """仅失效共享缓存"""
        return self._shared.invalidate(key)

    def invalidate_all_local(self) -> int:
        """清空本地缓存"""
        return self._local.invalidate_all()

    def invalidate_all_shared(self) -> int:
        """清空共享缓存"""
        return self._shared.invalidate_all()

    def invalidate_all(self) -> Dict[str, int]:
        """清空所有层级缓存"""
        with self._lock:
            return {
                "local": self._local.invalidate_all(),
                "shared": self._shared.invalidate_all(),
            }

    def invalidate_expired(self) -> Dict[str, int]:
        """清理所有过期条目"""
        with self._lock:
            return {
                "local": self._local.invalidate_expired(),
                "shared": self._shared.invalidate_expired(),
            }

    # ------------------------------------------------------------
    # 存在性检查
    # ------------------------------------------------------------
    def has(self, key: str) -> bool:
        """任意层存在有效缓存则返回 True"""
        return self._local.has(key) or self._shared.has(key)

    def has_local(self, key: str) -> bool:
        return self._local.has(key)

    def has_shared(self, key: str) -> bool:
        return self._shared.has(key)

    # ------------------------------------------------------------
    # 统计信息
    # ------------------------------------------------------------
    def get_stats(self) -> Dict[str, Any]:
        """获取完整统计信息

        注意：overall 统计为请求级计数，即每次 get / get_with_level 调用计为一次访问，
        即使触发了多层缓存查询也不会重复计数，确保命中率准确反映用户视角。
        """
        with self._lock:
            local_stats = self._local.get_stats()
            shared_stats = self._shared.get_stats()

            return {
                "overall": {
                    "accesses": self._request_stats.accesses,
                    "hits": self._request_stats.hits,
                    "misses": self._request_stats.misses,
                    "hit_rate": self._request_stats.hit_rate,
                    "sets": local_stats.sets + shared_stats.sets,
                    "invalidations": local_stats.invalidations + shared_stats.invalidations,
                    "evictions": local_stats.evictions + shared_stats.evictions,
                    "loader_calls": self._request_stats.loader_calls,
                },
                "local": local_stats.to_dict(),
                "shared": shared_stats.to_dict(),
                "sizes": {
                    "local": self._local.size(),
                    "shared": self._shared.size(),
                },
            }

    def reset_stats(self) -> None:
        """重置所有统计信息"""
        with self._lock:
            self._local.reset_stats()
            self._shared.reset_stats()
            self._request_stats = CacheStats()

    # ------------------------------------------------------------
    # 其他辅助
    # ------------------------------------------------------------
    def get_entry_local(self, key: str) -> Optional[CacheEntry]:
        return self._local.get_entry(key)

    def get_entry_shared(self, key: str) -> Optional[CacheEntry]:
        return self._shared.get_entry(key)

    def __contains__(self, key: str) -> bool:
        return self.has(key)

    def __len__(self) -> int:
        return self._local.size() + self._shared.size()
