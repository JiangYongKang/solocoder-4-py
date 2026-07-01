import time
import pytest

from solocoder_4_py.request_snapshot_cache import (
    RequestSnapshotCache,
    CacheEntry,
)


class TestRequestSnapshotCache:
    def test_set_and_get(self):
        cache = RequestSnapshotCache()
        params = {"user_id": 123}
        result = {"name": "Alice", "age": 30}

        cache.set(params, result, data_entities=["users"])
        cached_result = cache.get(params, data_entities=["users"])

        assert cached_result == result

    def test_get_nonexistent(self):
        cache = RequestSnapshotCache()
        params = {"user_id": 123}

        assert cache.get(params) is None

    def test_get_miss_increments_miss_stat(self):
        cache = RequestSnapshotCache()
        params = {"user_id": 123}

        cache.get(params)
        stats = cache.get_stats()
        assert stats["misses"] == 1

    def test_get_hit_increments_hit_stat(self):
        cache = RequestSnapshotCache()
        params = {"user_id": 123}
        result = {"name": "Alice"}

        cache.set(params, result)
        cache.get(params)
        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 0

    def test_set_increments_set_stat(self):
        cache = RequestSnapshotCache()
        params = {"user_id": 123}

        cache.set(params, {"name": "Alice"})
        stats = cache.get_stats()
        assert stats["sets"] == 1

    def test_has(self):
        cache = RequestSnapshotCache()
        params = {"user_id": 123}

        assert cache.has(params) is False

        cache.set(params, {"name": "Alice"}, data_entities=["users"])
        assert cache.has(params, data_entities=["users"]) is True

    def test_contains_operator(self):
        cache = RequestSnapshotCache()
        params = {"user_id": 123}

        assert params not in cache
        cache.set(params, {"name": "Alice"})
        assert params in cache

    def test_len(self):
        cache = RequestSnapshotCache()
        assert len(cache) == 0

        cache.set({"user_id": 1}, {"name": "Alice"})
        cache.set({"user_id": 2}, {"name": "Bob"})
        assert len(cache) == 2

    def test_invalidate_by_entity(self):
        cache = RequestSnapshotCache()

        cache.set({"user_id": 1}, {"name": "Alice"}, data_entities=["users"])
        cache.set({"order_id": 1}, {"total": 100}, data_entities=["orders"])
        cache.set({"user_id": 1, "include_orders": True}, {"orders": []},
                  data_entities=["users", "orders"])

        invalidated = cache.invalidate_by_entity("users")
        assert invalidated == 2

        assert cache.get({"user_id": 1}, data_entities=["users"]) is None
        assert cache.get({"order_id": 1}, data_entities=["orders"]) is not None
        assert cache.get({"user_id": 1, "include_orders": True},
                         data_entities=["users", "orders"]) is None

    def test_invalidate_by_entities(self):
        cache = RequestSnapshotCache()

        cache.set({"user_id": 1}, {}, data_entities=["users"])
        cache.set({"order_id": 1}, {}, data_entities=["orders"])
        cache.set({"product_id": 1}, {}, data_entities=["products"])

        invalidated = cache.invalidate_by_entities(["users", "orders"])
        assert invalidated == 2

        assert cache.get({"user_id": 1}, data_entities=["users"]) is None
        assert cache.get({"order_id": 1}, data_entities=["orders"]) is None
        assert cache.get({"product_id": 1}, data_entities=["products"]) is not None

    def test_invalidate_all(self):
        cache = RequestSnapshotCache()

        cache.set({"user_id": 1}, {}, data_entities=["users"])
        cache.set({"order_id": 1}, {}, data_entities=["orders"])

        invalidated = cache.invalidate_all()
        assert invalidated == 2
        assert len(cache) == 0

    def test_invalidate_by_pattern(self):
        cache = RequestSnapshotCache()

        cache.set({"user_id": 1, "type": "admin"}, {"name": "Alice"})
        cache.set({"user_id": 2, "type": "user"}, {"name": "Bob"})
        cache.set({"user_id": 3, "type": "admin"}, {"name": "Charlie"})

        invalidated = cache.invalidate_by_pattern(
            lambda params: params.get("type") == "admin"
        )
        assert invalidated == 2

        assert cache.get({"user_id": 1, "type": "admin"}) is None
        assert cache.get({"user_id": 2, "type": "user"}) is not None
        assert cache.get({"user_id": 3, "type": "admin"}) is None

    def test_version_invalidation_on_get(self):
        cache = RequestSnapshotCache()
        params = {"user_id": 123}

        cache.set(params, {"name": "Alice"}, data_entities=["users"])
        cache.bump_entity_version("users")

        assert cache.get(params, data_entities=["users"]) is None
        assert cache.has(params, data_entities=["users"]) is False

    def test_get_or_compute(self):
        cache = RequestSnapshotCache()
        params = {"user_id": 123}
        call_count = [0]

        def compute_func():
            call_count[0] += 1
            return {"name": "Alice"}

        result1 = cache.get_or_compute(params, compute_func, data_entities=["users"])
        result2 = cache.get_or_compute(params, compute_func, data_entities=["users"])

        assert result1 == {"name": "Alice"}
        assert result2 == {"name": "Alice"}
        assert call_count[0] == 1

    def test_lru_eviction(self):
        cache = RequestSnapshotCache(max_size=3)

        cache.set({"key": 1}, "value1")
        time.sleep(0.01)
        cache.set({"key": 2}, "value2")
        time.sleep(0.01)
        cache.set({"key": 3}, "value3")

        cache.get({"key": 1})

        time.sleep(0.01)
        cache.set({"key": 4}, "value4")

        assert len(cache) == 3
        assert cache.get({"key": 1}) == "value1"
        assert cache.get({"key": 2}) is None
        assert cache.get({"key": 3}) == "value3"
        assert cache.get({"key": 4}) == "value4"

        stats = cache.get_stats()
        assert stats["evictions"] == 1

    def test_ttl_expiration(self):
        cache = RequestSnapshotCache(default_ttl=0.1)
        params = {"user_id": 123}

        cache.set(params, {"name": "Alice"})
        assert cache.get(params) == {"name": "Alice"}

        time.sleep(0.15)
        assert cache.get(params) is None

    def test_bump_entity_version(self):
        cache = RequestSnapshotCache()
        assert cache.bump_entity_version("users") == 1
        assert cache.bump_entity_version("users") == 2
        assert cache.get_entity_version("users") == 2

    def test_get_entity_version(self):
        cache = RequestSnapshotCache()
        assert cache.get_entity_version("nonexistent") == 0

    def test_get_entry(self):
        cache = RequestSnapshotCache()
        params = {"user_id": 123}
        result = {"name": "Alice"}

        cache.set(params, result, data_entities=["users"])
        entry = cache.get_entry(params, data_entities=["users"])

        assert isinstance(entry, CacheEntry)
        assert entry.result == result
        assert entry.request_params == params
        assert entry.data_entities == ["users"]
        assert "users" in entry.entity_versions
        assert entry.hit_count == 0

    def test_entry_touch(self):
        cache = RequestSnapshotCache()
        params = {"user_id": 123}

        cache.set(params, {"name": "Alice"})
        entry = cache.get_entry(params)
        initial_hit_count = entry.hit_count

        cache.get(params)
        entry = cache.get_entry(params)
        assert entry.hit_count == initial_hit_count + 1

    def test_reset_stats(self):
        cache = RequestSnapshotCache()
        cache.set({"a": 1}, "value")
        cache.get({"a": 1})
        cache.get({"b": 2})
        cache.invalidate_all()

        cache.reset_stats()
        stats = cache.get_stats()

        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["sets"] == 0
        assert stats["evictions"] == 0
        assert stats["invalidations"] == 0

    def test_clear(self):
        cache = RequestSnapshotCache()
        cache.set({"user_id": 1}, {}, data_entities=["users"])
        cache.bump_entity_version("users")

        cache.clear()

        assert len(cache) == 0
        assert cache.get_entity_version("users") == 0

    def test_stats_size(self):
        cache = RequestSnapshotCache()
        assert cache.get_stats()["size"] == 0

        cache.set({"a": 1}, "value")
        assert cache.get_stats()["size"] == 1

    def test_without_data_entities(self):
        cache = RequestSnapshotCache()
        params = {"query": "some query"}
        result = {"data": "result"}

        cache.set(params, result)
        assert cache.get(params) == result
        assert cache.has(params) is True

    def test_different_entities_same_params(self):
        cache = RequestSnapshotCache()
        params = {"id": 123}

        cache.set(params, "result1", data_entities=["users"])
        cache.set(params, "result2", data_entities=["orders"])

        assert cache.get(params, data_entities=["users"]) == "result1"
        assert cache.get(params, data_entities=["orders"]) == "result2"

    def test_invalidation_stat(self):
        cache = RequestSnapshotCache()
        cache.set({"user_id": 1}, {}, data_entities=["users"])
        cache.set({"user_id": 2}, {}, data_entities=["users"])

        cache.invalidate_by_entity("users")
        stats = cache.get_stats()
        assert stats["invalidations"] == 2

    def test_custom_key_generator(self):
        from solocoder_4_py.request_snapshot_cache import CacheKeyGenerator

        custom_gen = CacheKeyGenerator(prefix="custom")
        cache = RequestSnapshotCache(key_generator=custom_gen)

        params = {"a": 1}
        key = cache.set(params, "value")
        assert key.startswith("custom:")

    def test_custom_version_manager(self):
        from solocoder_4_py.request_snapshot_cache import VersionManager

        custom_vm = VersionManager()
        custom_vm.bump_entity_version("users")
        custom_vm.bump_entity_version("users")

        cache = RequestSnapshotCache(version_manager=custom_vm)
        assert cache.get_entity_version("users") == 2

    def test_set_overwrites_existing(self):
        cache = RequestSnapshotCache()
        params = {"user_id": 123}

        cache.set(params, {"name": "Alice"})
        cache.set(params, {"name": "Alice Updated"})

        assert cache.get(params) == {"name": "Alice Updated"}
        assert len(cache) == 1

    def test_same_key_different_entities(self):
        cache = RequestSnapshotCache()
        params = {"id": 1}

        key1 = cache.set(params, "value1", data_entities=["users"])
        key2 = cache.set(params, "value2", data_entities=["users", "orders"])

        assert key1 != key2
        assert len(cache) == 2

    def test_get_entry_nonexistent(self):
        cache = RequestSnapshotCache()
        assert cache.get_entry({"nonexistent": True}) is None

    def test_invalidate_by_pattern_no_match(self):
        cache = RequestSnapshotCache()
        cache.set({"type": "a"}, "value1")
        cache.set({"type": "b"}, "value2")

        invalidated = cache.invalidate_by_pattern(lambda p: p.get("type") == "c")
        assert invalidated == 0
        assert len(cache) == 2

    def test_lru_no_eviction_when_space_available(self):
        cache = RequestSnapshotCache(max_size=5)

        for i in range(3):
            cache.set({"key": i}, f"value{i}")

        stats = cache.get_stats()
        assert stats["evictions"] == 0
        assert len(cache) == 3

    def test_ttl_none_means_no_expiration(self):
        cache = RequestSnapshotCache(default_ttl=None)
        params = {"user_id": 123}

        cache.set(params, {"name": "Alice"})
        time.sleep(0.05)
        assert cache.get(params) == {"name": "Alice"}

    def test_get_or_compute_with_exception(self):
        cache = RequestSnapshotCache()
        params = {"user_id": 123}

        def failing_func():
            raise ValueError("Compute failed")

        with pytest.raises(ValueError, match="Compute failed"):
            cache.get_or_compute(params, failing_func)

        assert cache.get(params) is None

    def test_cache_entry_metadata(self):
        cache = RequestSnapshotCache()
        params = {"user_id": 123}
        result = {"name": "Alice"}

        before_set = time.time()
        cache.set(params, result, data_entities=["users"])
        after_set = time.time()

        entry = cache.get_entry(params, data_entities=["users"])

        assert before_set <= entry.created_at <= after_set
        assert before_set <= entry.accessed_at <= after_set
        assert entry.request_params == params
        assert entry.result == result
        assert entry.data_entities == ["users"]

    def test_multiple_entity_version_bumps(self):
        cache = RequestSnapshotCache()

        cache.set({"id": 1}, "result1", data_entities=["a", "b", "c"])

        cache.bump_entity_version("a")
        assert cache.get({"id": 1}, data_entities=["a", "b", "c"]) is None

        cache.set({"id": 1}, "result2", data_entities=["a", "b", "c"])
        cache.bump_entity_version("b")
        assert cache.get({"id": 1}, data_entities=["a", "b", "c"]) is None

        cache.set({"id": 1}, "result3", data_entities=["a", "b", "c"])
        cache.bump_entity_version("c")
        assert cache.get({"id": 1}, data_entities=["a", "b", "c"]) is None

    def test_thread_safety(self):
        import threading

        cache = RequestSnapshotCache(max_size=100)
        errors = []

        def write_operation(start, end):
            try:
                for i in range(start, end):
                    cache.set({"key": i}, f"value{i}", data_entities=["entity"])
            except Exception as e:
                errors.append(e)

        def read_operation(start, end):
            try:
                for i in range(start, end):
                    cache.get({"key": i}, data_entities=["entity"])
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(5):
            threads.append(threading.Thread(target=write_operation, args=(i * 20, (i + 1) * 20)))
            threads.append(threading.Thread(target=read_operation, args=(0, 100)))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    def test_complex_real_world_scenario(self):
        cache = RequestSnapshotCache()

        query1_params = {
            "query": "SELECT * FROM users WHERE status = ?",
            "params": ["active"],
            "limit": 10,
            "offset": 0,
        }
        result1 = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
        cache.set(query1_params, result1, data_entities=["users"])

        query2_params = {
            "query": "SELECT COUNT(*) FROM orders WHERE user_id = ?",
            "params": [1],
        }
        result2 = {"count": 5}
        cache.set(query2_params, result2, data_entities=["orders"])

        assert cache.get(query1_params, data_entities=["users"]) == result1
        assert cache.get(query2_params, data_entities=["orders"]) == result2

        invalidated = cache.invalidate_by_entity("users")
        assert invalidated == 1

        assert cache.get(query1_params, data_entities=["users"]) is None
        assert cache.get(query2_params, data_entities=["orders"]) == result2

    def test_invalidate_all_clears_versions(self):
        cache = RequestSnapshotCache()
        cache.bump_entity_version("users")
        cache.bump_entity_version("users")

        cache.set({"id": 1}, {}, data_entities=["users"])
        cache.invalidate_all()

        assert cache.get_entity_version("users") == 0

    def test_get_stats_includes_vm_stats(self):
        cache = RequestSnapshotCache()
        cache.set({"id": 1}, {}, data_entities=["users"])
        cache.set({"id": 2}, {}, data_entities=["orders"])

        stats = cache.get_stats()
        assert "vm_entity_count" in stats
        assert "vm_cache_count" in stats
        assert stats["vm_entity_count"] == 2
        assert stats["vm_cache_count"] == 2

    def test_none_result_stored(self):
        cache = RequestSnapshotCache()
        params = {"user_id": 999}

        cache.set(params, None)
        assert cache.get(params) is None

        entry = cache.get_entry(params)
        assert entry is not None
        assert entry.result is None

    def test_complex_nested_params(self):
        cache = RequestSnapshotCache()
        params = {
            "filters": {
                "status": ["active", "pending"],
                "date_range": {"start": "2024-01-01", "end": "2024-12-31"},
            },
            "sort": [{"field": "created_at", "order": "desc"}],
            "pagination": {"page": 1, "per_page": 20},
        }
        result = {"data": [1, 2, 3]}

        cache.set(params, result)

        params_reordered = {
            "pagination": {"per_page": 20, "page": 1},
            "sort": [{"field": "created_at", "order": "desc"}],
            "filters": {
                "date_range": {"end": "2024-12-31", "start": "2024-01-01"},
                "status": ["active", "pending"],
            },
        }

        assert cache.get(params_reordered) == result
