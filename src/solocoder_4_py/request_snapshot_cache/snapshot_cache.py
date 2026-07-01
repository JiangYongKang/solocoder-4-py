import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple, TypeVar, Set

from .cache_key import CacheKeyGenerator, generate_cache_key
from .version_manager import VersionManager

T = TypeVar("T")


@dataclass
class CacheEntry:
    cache_key: str
    result: Any
    request_params: Dict[str, Any]
    data_entities: List[str]
    entity_versions: Dict[str, int]
    created_at: float
    accessed_at: float = field(default_factory=time.time)
    hit_count: int = 0

    def touch(self) -> None:
        self.accessed_at = time.time()
        self.hit_count += 1


class RequestSnapshotCache:
    def __init__(self,
                 key_generator: Optional[CacheKeyGenerator] = None,
                 version_manager: Optional[VersionManager] = None,
                 max_size: Optional[int] = None,
                 default_ttl: Optional[float] = None):
        self._key_generator = key_generator or CacheKeyGenerator()
        self._version_manager = version_manager or VersionManager()
        self._cache: Dict[str, CacheEntry] = {}
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._lock = threading.RLock()
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "evictions": 0,
            "invalidations": 0,
            "ttl_cleanups": 0,
            "version_race_detected": 0,
        }

    def _cleanup_expired(self) -> int:
        if self._default_ttl is None:
            return 0

        now = time.time()
        expired_keys: List[str] = []

        for cache_key, entry in self._cache.items():
            if now - entry.created_at > self._default_ttl:
                expired_keys.append(cache_key)

        for cache_key in expired_keys:
            self._evict_internal(cache_key)

        cleaned_count = len(expired_keys)
        if cleaned_count > 0:
            self._stats["ttl_cleanups"] += cleaned_count

        return cleaned_count

    def _evict_internal(self, cache_key: str) -> None:
        if cache_key in self._cache:
            del self._cache[cache_key]
        self._version_manager.unregister_cache(cache_key)

    def get(self,
            request_params: Dict[str, Any],
            data_entities: Optional[List[str]] = None) -> Optional[Any]:
        cache_key = self._key_generator.generate(request_params, data_entities)

        with self._lock:
            self._cleanup_expired()

            entry = self._cache.get(cache_key)
            if entry is None:
                self._stats["misses"] += 1
                return None

            if not self._version_manager.check_versions_valid(
                cache_key, entry.entity_versions
            ):
                self._evict_internal(cache_key)
                self._stats["misses"] += 1
                return None

            if self._default_ttl is not None:
                if time.time() - entry.created_at > self._default_ttl:
                    self._evict_internal(cache_key)
                    self._stats["misses"] += 1
                    return None

            entry.touch()
            self._stats["hits"] += 1
            return entry.result

    def get_or_compute(self,
                       request_params: Dict[str, Any],
                       compute_func: Callable[[], T],
                       data_entities: Optional[List[str]] = None) -> T:
        cached_result = self.get(request_params, data_entities)
        if cached_result is not None:
            return cached_result

        entities = data_entities or []

        with self._lock:
            versions_before = self._version_manager.get_entities_version(entities)

        result = compute_func()

        with self._lock:
            versions_after = self._version_manager.get_entities_version(entities)
            if versions_before != versions_after:
                self._stats["version_race_detected"] += 1
                return result

            self._set_internal(request_params, result, data_entities, cache_versions=versions_after)
            return result

    def set(self,
            request_params: Dict[str, Any],
            result: Any,
            data_entities: Optional[List[str]] = None,
            ttl: Optional[float] = None) -> str:
        with self._lock:
            self._cleanup_expired()
            return self._set_internal(request_params, result, data_entities, ttl)

    def _set_internal(self,
                      request_params: Dict[str, Any],
                      result: Any,
                      data_entities: Optional[List[str]] = None,
                      ttl: Optional[float] = None,
                      cache_versions: Optional[Dict[str, int]] = None) -> str:
        cache_key = self._key_generator.generate(request_params, data_entities)
        entities = data_entities or []

        if self._max_size is not None and len(self._cache) >= self._max_size:
            if cache_key not in self._cache:
                self._evict_lru()

        entity_versions = cache_versions or self._version_manager.get_entities_version(entities)

        entry = CacheEntry(
            cache_key=cache_key,
            result=result,
            request_params=request_params,
            data_entities=entities,
            entity_versions=entity_versions,
            created_at=time.time(),
        )

        self._cache[cache_key] = entry
        self._version_manager.register_cache_dependency(cache_key, entities)

        self._stats["sets"] += 1
        return cache_key

    def invalidate_by_entity(self, entity_name: str) -> int:
        with self._lock:
            self._cleanup_expired()
            invalidated_keys = self._version_manager.invalidate_entity(entity_name)
            for cache_key in invalidated_keys:
                if cache_key in self._cache:
                    del self._cache[cache_key]
            self._stats["invalidations"] += len(invalidated_keys)
            return len(invalidated_keys)

    def invalidate_by_entities(self, entity_names: Iterable[str]) -> int:
        with self._lock:
            self._cleanup_expired()
            invalidated_keys = self._version_manager.invalidate_entities(entity_names)
            for cache_key in invalidated_keys:
                if cache_key in self._cache:
                    del self._cache[cache_key]
            self._stats["invalidations"] += len(invalidated_keys)
            return len(invalidated_keys)

    def invalidate_all(self) -> int:
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._version_manager.clear()
            self._stats["invalidations"] += count
            return count

    def invalidate_by_pattern(self, pattern_func: Callable[[Dict[str, Any]], bool]) -> int:
        with self._lock:
            self._cleanup_expired()

            to_remove = [
                cache_key
                for cache_key, entry in self._cache.items()
                if pattern_func(entry.request_params)
            ]

            affected_entities: Set[str] = set()
            for cache_key in to_remove:
                entry = self._cache.get(cache_key)
                if entry:
                    affected_entities.update(entry.data_entities)

            for entity in affected_entities:
                self._version_manager.bump_entity_version(entity)

            for cache_key in to_remove:
                self._evict_internal(cache_key)

            self._stats["invalidations"] += len(to_remove)
            return len(to_remove)

    def has(self, request_params: Dict[str, Any],
            data_entities: Optional[List[str]] = None) -> bool:
        cache_key = self._key_generator.generate(request_params, data_entities)
        with self._lock:
            self._cleanup_expired()
            if cache_key not in self._cache:
                return False
            entry = self._cache[cache_key]
            return self._version_manager.check_versions_valid(
                cache_key, entry.entity_versions
            )

    def get_entry(self, request_params: Dict[str, Any],
                  data_entities: Optional[List[str]] = None) -> Optional[CacheEntry]:
        cache_key = self._key_generator.generate(request_params, data_entities)
        with self._lock:
            self._cleanup_expired()
            return self._cache.get(cache_key)

    def _evict(self, cache_key: str) -> None:
        self._evict_internal(cache_key)

    def _evict_lru(self) -> None:
        if not self._cache:
            return

        lru_key = min(
            self._cache.keys(),
            key=lambda k: self._cache[k].accessed_at
        )
        self._evict_internal(lru_key)
        self._stats["evictions"] += 1

    def bump_entity_version(self, entity_name: str) -> int:
        return self._version_manager.bump_entity_version(entity_name)

    def get_entity_version(self, entity_name: str) -> int:
        return self._version_manager.get_entity_version(entity_name)

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            self._cleanup_expired()
            stats = self._stats.copy()
            stats.update({
                "size": len(self._cache),
                "max_size": self._max_size,
                "default_ttl": self._default_ttl,
            })
            vm_stats = self._version_manager.get_stats()
            stats.update({f"vm_{k}": v for k, v in vm_stats.items()})
            return stats

    def reset_stats(self) -> None:
        with self._lock:
            self._stats = {
                "hits": 0,
                "misses": 0,
                "sets": 0,
                "evictions": 0,
                "invalidations": 0,
                "ttl_cleanups": 0,
                "version_race_detected": 0,
            }

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self._version_manager.clear()

    def __len__(self) -> int:
        with self._lock:
            self._cleanup_expired()
            return len(self._cache)

    def __contains__(self, request_params: Dict[str, Any]) -> bool:
        return self.has(request_params)
