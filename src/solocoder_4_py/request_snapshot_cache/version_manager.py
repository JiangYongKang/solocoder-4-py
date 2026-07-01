import threading
from typing import Dict, Iterable, List, Optional, Set


class VersionManager:
    def __init__(self):
        self._entity_versions: Dict[str, int] = {}
        self._cache_to_entities: Dict[str, Set[str]] = {}
        self._entity_to_caches: Dict[str, Set[str]] = {}
        self._lock = threading.RLock()

    def get_entity_version(self, entity_name: str) -> int:
        with self._lock:
            return self._entity_versions.get(entity_name, 0)

    def get_entities_version(self, entity_names: Iterable[str]) -> Dict[str, int]:
        with self._lock:
            return {
                entity: self._entity_versions.get(entity, 0)
                for entity in entity_names
            }

    def bump_entity_version(self, entity_name: str) -> int:
        with self._lock:
            new_version = self._entity_versions.get(entity_name, 0) + 1
            self._entity_versions[entity_name] = new_version
            return new_version

    def bump_entities_version(self, entity_names: Iterable[str]) -> Dict[str, int]:
        with self._lock:
            return {
                entity: self.bump_entity_version(entity)
                for entity in entity_names
            }

    def register_cache_dependency(self, cache_key: str, entity_names: Iterable[str]) -> None:
        with self._lock:
            self.unregister_cache(cache_key)

            entity_set = set(entity_names)
            self._cache_to_entities[cache_key] = entity_set

            for entity in entity_set:
                if entity not in self._entity_versions:
                    self._entity_versions[entity] = 0
                if entity not in self._entity_to_caches:
                    self._entity_to_caches[entity] = set()
                self._entity_to_caches[entity].add(cache_key)

    def unregister_cache(self, cache_key: str) -> None:
        with self._lock:
            entities = self._cache_to_entities.pop(cache_key, set())
            for entity in entities:
                if entity in self._entity_to_caches:
                    self._entity_to_caches[entity].discard(cache_key)
                    if not self._entity_to_caches[entity]:
                        del self._entity_to_caches[entity]

    def get_invalidated_caches(self, entity_names: Iterable[str]) -> Set[str]:
        with self._lock:
            invalidated: Set[str] = set()
            for entity in entity_names:
                invalidated.update(self._entity_to_caches.get(entity, set()))
            return invalidated

    def get_cache_dependencies(self, cache_key: str) -> Set[str]:
        with self._lock:
            return self._cache_to_entities.get(cache_key, set()).copy()

    def get_version_signature(self, entity_names: Iterable[str]) -> str:
        with self._lock:
            versions = self.get_entities_version(entity_names)
            sorted_versions = sorted(versions.items())
            return "|".join(f"{entity}:{version}" for entity, version in sorted_versions)

    def check_versions_valid(self, cache_key: str,
                             expected_versions: Dict[str, int]) -> bool:
        with self._lock:
            for entity, expected_version in expected_versions.items():
                current_version = self._entity_versions.get(entity, 0)
                if current_version != expected_version:
                    return False
            return True

    def invalidate_entity(self, entity_name: str) -> Set[str]:
        with self._lock:
            invalidated = self._entity_to_caches.get(entity_name, set()).copy()
            self.bump_entity_version(entity_name)
            for cache_key in invalidated:
                self.unregister_cache(cache_key)
            return invalidated

    def invalidate_entities(self, entity_names: Iterable[str]) -> Set[str]:
        with self._lock:
            all_invalidated: Set[str] = set()
            for entity in entity_names:
                all_invalidated.update(self.invalidate_entity(entity))
            return all_invalidated

    def get_all_entities(self) -> List[str]:
        with self._lock:
            return sorted(self._entity_versions.keys())

    def get_all_cache_keys(self) -> List[str]:
        with self._lock:
            return sorted(self._cache_to_entities.keys())

    def clear(self) -> None:
        with self._lock:
            self._entity_versions.clear()
            self._cache_to_entities.clear()
            self._entity_to_caches.clear()

    def get_stats(self) -> Dict[str, int]:
        with self._lock:
            return {
                "entity_count": len(self._entity_versions),
                "cache_count": len(self._cache_to_entities),
                "entity_to_cache_count": len(self._entity_to_caches),
            }
