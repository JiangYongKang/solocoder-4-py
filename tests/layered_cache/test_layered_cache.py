import threading
import time
import pytest

from solocoder_4_py.layered_cache import (
    CacheEntry,
    CacheEntryStatus,
    CacheLevel,
    CacheLoaderError,
    CacheStats,
    LayeredCache,
    SingleLevelCache,
)


# =====================================================================
# CacheEntry 测试
# =====================================================================
class TestCacheEntry:
    def test_create_entry_defaults(self):
        entry = CacheEntry(key="k1", value="v1")
        assert entry.key == "k1"
        assert entry.value == "v1"
        assert entry.tags == []
        assert entry.status == CacheEntryStatus.VALID
        assert entry.expires_at is None
        assert entry.hit_count == 0

    def test_is_valid_no_expiry(self):
        entry = CacheEntry(key="k", value="v")
        assert entry.is_valid() is True

    def test_is_valid_not_expired(self):
        entry = CacheEntry(key="k", value="v", expires_at=time.time() + 3600)
        assert entry.is_valid() is True

    def test_is_valid_expired(self):
        entry = CacheEntry(key="k", value="v", expires_at=time.time() - 1)
        assert entry.is_valid() is False

    def test_is_valid_invalidated_status(self):
        entry = CacheEntry(key="k", value="v")
        entry.invalidate()
        assert entry.status == CacheEntryStatus.INVALIDATED
        assert entry.is_valid() is False

    def test_touch_updates_hit_count(self):
        entry = CacheEntry(key="k", value="v")
        initial_hit = entry.hit_count
        entry.touch()
        assert entry.hit_count == initial_hit + 1
        entry.touch()
        assert entry.hit_count == initial_hit + 2

    def test_invalidate_sets_status(self):
        entry = CacheEntry(key="k", value="v")
        entry.invalidate()
        assert entry.status == CacheEntryStatus.INVALIDATED

    def test_remaining_ttl_no_expiry(self):
        entry = CacheEntry(key="k", value="v")
        assert entry.remaining_ttl() is None

    def test_remaining_ttl_positive(self):
        future = time.time() + 100
        entry = CacheEntry(key="k", value="v", expires_at=future)
        ttl = entry.remaining_ttl()
        assert ttl is not None
        assert 99 <= ttl <= 101

    def test_remaining_ttl_negative(self):
        past = time.time() - 50
        entry = CacheEntry(key="k", value="v", expires_at=past)
        ttl = entry.remaining_ttl()
        assert ttl is not None
        assert ttl < 0

    def test_to_dict_and_from_dict(self):
        original = CacheEntry(
            key="k1",
            value={"nested": True},
            tags=["a", "b"],
            status=CacheEntryStatus.VALID,
            created_at=12345.0,
            expires_at=67890.0,
            accessed_at=54321.0,
            hit_count=10,
        )
        data = original.to_dict()
        restored = CacheEntry.from_dict(data)
        assert restored.key == original.key
        assert restored.value == original.value
        assert restored.tags == original.tags
        assert restored.status == original.status
        assert restored.created_at == original.created_at
        assert restored.expires_at == original.expires_at
        assert restored.accessed_at == original.accessed_at
        assert restored.hit_count == original.hit_count

    def test_tags_list_independence(self):
        tags = ["a", "b"]
        entry = CacheEntry(key="k", value="v", tags=tags)
        tags.append("c")
        assert entry.tags == ["a", "b"]


# =====================================================================
# CacheStats 测试
# =====================================================================
class TestCacheStats:
    def test_defaults(self):
        stats = CacheStats()
        assert stats.accesses == 0
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.hit_rate == 0.0

    def test_hit_rate_zero_accesses(self):
        stats = CacheStats(accesses=0, hits=0)
        assert stats.hit_rate == 0.0

    def test_hit_rate_all_hits(self):
        stats = CacheStats(accesses=100, hits=100, misses=0)
        assert stats.hit_rate == 1.0

    def test_hit_rate_partial(self):
        stats = CacheStats(accesses=100, hits=75, misses=25)
        assert stats.hit_rate == 0.75

    def test_to_dict_includes_hit_rate(self):
        stats = CacheStats(accesses=10, hits=7, misses=3, sets=5, invalidations=2, evictions=1, loader_calls=3)
        d = stats.to_dict()
        assert d["accesses"] == 10
        assert d["hits"] == 7
        assert d["misses"] == 3
        assert d["hit_rate"] == 0.7
        assert d["sets"] == 5
        assert d["invalidations"] == 2
        assert d["evictions"] == 1
        assert d["loader_calls"] == 3


# =====================================================================
# SingleLevelCache 测试
# =====================================================================
class TestSingleLevelCache:
    def test_set_and_get(self):
        cache = SingleLevelCache()
        cache.set("k1", "v1")
        assert cache.get_value("k1") == "v1"

    def test_get_nonexistent_returns_none(self):
        cache = SingleLevelCache()
        assert cache.get_value("missing") is None
        assert cache.get("missing") is None

    def test_has(self):
        cache = SingleLevelCache()
        assert cache.has("k1") is False
        cache.set("k1", "v1")
        assert cache.has("k1") is True
        assert "k1" in cache

    def test_len(self):
        cache = SingleLevelCache()
        assert len(cache) == 0
        cache.set("a", 1)
        cache.set("b", 2)
        assert len(cache) == 2

    def test_overwrite_existing_key(self):
        cache = SingleLevelCache()
        cache.set("k", "old")
        cache.set("k", "new")
        assert cache.get_value("k") == "new"
        assert len(cache) == 1

    def test_ttl_expiration(self):
        cache = SingleLevelCache(default_ttl=0.1)
        cache.set("k", "v")
        assert cache.get_value("k") == "v"
        time.sleep(0.15)
        assert cache.get_value("k") is None
        assert cache.has("k") is False

    def test_per_key_ttl_overrides_default(self):
        cache = SingleLevelCache(default_ttl=3600)
        cache.set("k_short", "v1", ttl=0.1)
        cache.set("k_long", "v2")
        time.sleep(0.15)
        assert cache.get_value("k_short") is None
        assert cache.get_value("k_long") == "v2"

    def test_lru_eviction(self):
        cache = SingleLevelCache(max_size=3)
        cache.set("a", 1)
        time.sleep(0.01)
        cache.set("b", 2)
        time.sleep(0.01)
        cache.set("c", 3)

        cache.get_value("a")

        time.sleep(0.01)
        cache.set("d", 4)

        assert len(cache) == 3
        assert cache.get_value("a") == 1
        assert cache.get_value("b") is None
        assert cache.get_value("c") == 3
        assert cache.get_value("d") == 4
        stats = cache.get_stats()
        assert stats.evictions == 1

    def test_no_eviction_when_space(self):
        cache = SingleLevelCache(max_size=5)
        for i in range(3):
            cache.set(f"k{i}", i)
        stats = cache.get_stats()
        assert stats.evictions == 0
        assert len(cache) == 3

    def test_invalidate_by_key(self):
        cache = SingleLevelCache()
        cache.set("a", 1)
        cache.set("b", 2)
        assert cache.invalidate("a") is True
        assert cache.invalidate("nonexistent") is False
        assert cache.get_value("a") is None
        assert cache.get_value("b") == 2

    def test_invalidate_by_tag(self):
        cache = SingleLevelCache()
        cache.set("u1", {"id": 1}, tags=["users"])
        cache.set("u2", {"id": 2}, tags=["users"])
        cache.set("o1", {"id": 1}, tags=["orders"])
        cache.set("mixed", {}, tags=["users", "orders"])

        count = cache.invalidate_by_tag("users")
        assert count == 3
        assert cache.get_value("u1") is None
        assert cache.get_value("u2") is None
        assert cache.get_value("mixed") is None
        assert cache.get_value("o1") is not None

    def test_invalidate_by_tags_multi(self):
        cache = SingleLevelCache()
        cache.set("a", 1, tags=["t1"])
        cache.set("b", 2, tags=["t2"])
        cache.set("c", 3, tags=["t3"])

        count = cache.invalidate_by_tags(["t1", "t2"])
        assert count == 2
        assert cache.get_value("a") is None
        assert cache.get_value("b") is None
        assert cache.get_value("c") == 3

    def test_invalidate_all(self):
        cache = SingleLevelCache()
        cache.set("a", 1)
        cache.set("b", 2)
        count = cache.invalidate_all()
        assert count == 2
        assert len(cache) == 0
        assert cache.get_value("a") is None

    def test_invalidate_expired(self):
        cache = SingleLevelCache()
        cache.set("expired", "e1", ttl=0.05)
        cache.set("fresh", "f1")
        time.sleep(0.1)
        count = cache.invalidate_expired()
        assert count == 1
        assert cache.get_value("expired") is None
        assert cache.get_value("fresh") == "f1"

    def test_stats_tracking(self):
        cache = SingleLevelCache()
        cache.set("a", 1)
        cache.set("b", 2)
        cache.get_value("a")
        cache.get_value("a")
        cache.get_value("missing")

        stats = cache.get_stats()
        assert stats.sets == 2
        assert stats.accesses == 3
        assert stats.hits == 2
        assert stats.misses == 1
        assert stats.hit_rate == 2 / 3

    def test_reset_stats(self):
        cache = SingleLevelCache()
        cache.set("a", 1)
        cache.get_value("a")
        cache.invalidate("a")
        cache.reset_stats()
        stats = cache.get_stats()
        assert stats.accesses == 0
        assert stats.hits == 0
        assert stats.sets == 0
        assert stats.invalidations == 0

    def test_keys(self):
        cache = SingleLevelCache()
        cache.set("a", 1, tags=["t"])
        cache.set("b", 2, tags=["t"])
        keys = cache.keys()
        assert sorted(keys) == ["a", "b"]

    def test_get_entry_returns_none_for_missing(self):
        cache = SingleLevelCache()
        assert cache.get_entry("missing") is None

    def test_get_entry_returns_entry_object(self):
        cache = SingleLevelCache()
        cache.set("k", "v", tags=["t"])
        entry = cache.get_entry("k")
        assert isinstance(entry, CacheEntry)
        assert entry.key == "k"
        assert entry.value == "v"
        assert entry.tags == ["t"]

    def test_tag_index_cleanup_on_overwrite(self):
        cache = SingleLevelCache()
        cache.set("k", "v1", tags=["old_tag"])
        cache.set("k", "v2", tags=["new_tag"])

        assert cache.invalidate_by_tag("old_tag") == 0
        assert cache.invalidate_by_tag("new_tag") == 1

    def test_thread_safety(self):
        cache = SingleLevelCache(max_size=100)
        errors = []

        def writer(start, end):
            try:
                for i in range(start, end):
                    cache.set(f"k{i}", i, tags=[f"tag{i % 5}"])
            except Exception as e:
                errors.append(e)

        def reader(start, end):
            try:
                for i in range(start, end):
                    cache.get_value(f"k{i}")
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(4):
            threads.append(threading.Thread(target=writer, args=(i * 25, (i + 1) * 25)))
            threads.append(threading.Thread(target=reader, args=(0, 100)))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


# =====================================================================
# LayeredCache 测试
# =====================================================================
class TestLayeredCache:
    # ------------------------------------------------------------
    # 基础读穿透
    # ------------------------------------------------------------
    def test_read_through_from_loader(self):
        cache = LayeredCache()
        call_count = [0]

        def loader():
            call_count[0] += 1
            return "loaded_value"

        result = cache.get("key1", loader=loader)
        assert result == "loaded_value"
        assert call_count[0] == 1

        result2 = cache.get("key1", loader=loader)
        assert result2 == "loaded_value"
        assert call_count[0] == 1

    def test_get_without_loader_returns_none(self):
        cache = LayeredCache()
        assert cache.get("missing") is None

    def test_get_or_load_requires_loader(self):
        cache = LayeredCache()
        assert cache.get_or_load("k", lambda: "v") == "v"

    def test_local_hit_does_not_check_shared(self):
        cache = LayeredCache()
        cache.set_local("k", "local_v")
        cache.set_shared("k", "shared_v")

        result = cache.get("k")
        assert result == "local_v"

        local_stats = cache.get_stats()["local"]
        shared_stats = cache.get_stats()["shared"]
        assert local_stats["hits"] == 1
        assert shared_stats["accesses"] == 0

    def test_shared_hit_backfills_local(self):
        cache = LayeredCache()
        cache.set_shared("k", "shared_v", tags=["t1"])

        assert cache.has_local("k") is False
        result = cache.get("k")
        assert result == "shared_v"
        assert cache.has_local("k") is True
        assert cache.get_local("k") == "shared_v"

    def test_get_with_level_local(self):
        cache = LayeredCache()
        cache.set_local("k", "v")
        value, level = cache.get_with_level("k")
        assert value == "v"
        assert level == CacheLevel.LOCAL

    def test_get_with_level_shared(self):
        cache = LayeredCache()
        cache.set_shared("k", "v")
        value, level = cache.get_with_level("k")
        assert value == "v"
        assert level == CacheLevel.SHARED

    def test_get_with_level_miss(self):
        cache = LayeredCache()
        value, level = cache.get_with_level("missing")
        assert value is None
        assert level is None

    def test_loader_backfills_both_layers(self):
        cache = LayeredCache()

        def loader():
            return "loaded"

        cache.get("k", loader=loader, tags=["tag1", "tag2"])

        assert cache.get_local("k") == "loaded"
        assert cache.get_shared("k") == "loaded"

        local_entry = cache.get_entry_local("k")
        shared_entry = cache.get_entry_shared("k")
        assert local_entry.tags == ["tag1", "tag2"]
        assert shared_entry.tags == ["tag1", "tag2"]

    def test_loader_propagates_tags_on_shared_hit(self):
        cache = LayeredCache()
        cache.set_shared("k", "sv", tags=["shared_tag"])

        cache.get("k")

        local_entry = cache.get_entry_local("k")
        assert local_entry is not None
        assert local_entry.tags == ["shared_tag"]

    # ------------------------------------------------------------
    # 写操作
    # ------------------------------------------------------------
    def test_set_writes_both_layers(self):
        cache = LayeredCache()
        cache.set("k", "v", tags=["t"])
        assert cache.get_local("k") == "v"
        assert cache.get_shared("k") == "v"

    def test_set_local_only(self):
        cache = LayeredCache()
        cache.set("k", "v", write_local=True, write_shared=False)
        assert cache.get_local("k") == "v"
        assert cache.get_shared("k") is None

    def test_set_shared_only(self):
        cache = LayeredCache()
        cache.set("k", "v", write_local=False, write_shared=True)
        assert cache.get_local("k") is None
        assert cache.get_shared("k") == "v"

    def test_set_local_method(self):
        cache = LayeredCache()
        cache.set_local("k", "v", tags=["t"])
        assert cache.get_local("k") == "v"
        assert cache.get_shared("k") is None

    def test_set_shared_method(self):
        cache = LayeredCache()
        cache.set_shared("k", "v", tags=["t"])
        assert cache.get_shared("k") == "v"
        assert cache.get_local("k") is None

    def test_set_with_custom_ttl(self):
        cache = LayeredCache()
        cache.set("k_short", "v1", ttl=0.1)
        cache.set("k_long", "v2")
        time.sleep(0.15)
        assert cache.get("k_short") is None
        assert cache.get("k_long") == "v2"

    def test_set_with_different_local_shared_ttl(self):
        cache = LayeredCache()
        cache.set("k", "v", local_ttl=0.1, shared_ttl=3600)
        time.sleep(0.15)
        assert cache.get_local("k") is None
        assert cache.get_shared("k") == "v"

    # ------------------------------------------------------------
    # 失效操作
    # ------------------------------------------------------------
    def test_invalidate_key_both_layers(self):
        cache = LayeredCache()
        cache.set("k", "v")
        result = cache.invalidate("k")
        assert result == {"local": True, "shared": True}
        assert cache.has("k") is False

    def test_invalidate_key_partial(self):
        cache = LayeredCache()
        cache.set_local("k", "local_v")
        result = cache.invalidate("k")
        assert result == {"local": True, "shared": False}

    def test_invalidate_key_missing(self):
        cache = LayeredCache()
        result = cache.invalidate("missing")
        assert result == {"local": False, "shared": False}

    def test_invalidate_by_tag(self):
        cache = LayeredCache()
        cache.set("u1", {}, tags=["users"])
        cache.set("u2", {}, tags=["users"])
        cache.set("o1", {}, tags=["orders"])
        cache.set("both", {}, tags=["users", "orders"])

        result = cache.invalidate_by_tag("users")
        assert result["local"] == 3
        assert result["shared"] == 3
        assert cache.get("u1") is None
        assert cache.get("u2") is None
        assert cache.get("both") is None
        assert cache.get("o1") is not None

    def test_invalidate_by_tags(self):
        cache = LayeredCache()
        cache.set("a", 1, tags=["t1"])
        cache.set("b", 2, tags=["t2"])
        cache.set("c", 3, tags=["t3"])

        result = cache.invalidate_by_tags(["t1", "t2"])
        assert result["local"] == 2
        assert result["shared"] == 2
        assert cache.get("c") == 3

    def test_invalidate_local_only(self):
        cache = LayeredCache()
        cache.set("k", "v")
        assert cache.invalidate_local("k") is True
        assert cache.get_local("k") is None
        assert cache.get_shared("k") == "v"

    def test_invalidate_shared_only(self):
        cache = LayeredCache()
        cache.set("k", "v")
        assert cache.invalidate_shared("k") is True
        assert cache.get_shared("k") is None
        assert cache.get_local("k") == "v"

    def test_invalidate_all(self):
        cache = LayeredCache()
        cache.set("a", 1)
        cache.set("b", 2)
        result = cache.invalidate_all()
        assert result["local"] == 2
        assert result["shared"] == 2
        assert len(cache) == 0

    def test_invalidate_all_local(self):
        cache = LayeredCache()
        cache.set("k", "v")
        count = cache.invalidate_all_local()
        assert count == 1
        assert cache.get_local("k") is None
        assert cache.get_shared("k") == "v"

    def test_invalidate_all_shared(self):
        cache = LayeredCache()
        cache.set("k", "v")
        count = cache.invalidate_all_shared()
        assert count == 1
        assert cache.get_shared("k") is None
        assert cache.get_local("k") == "v"

    def test_invalidate_expired(self):
        cache = LayeredCache(local_ttl=0.1, shared_ttl=0.1)
        cache.set("k1", "v1")
        cache.set("k2", "v2", local_ttl=3600, shared_ttl=3600)
        time.sleep(0.15)
        result = cache.invalidate_expired()
        assert result["local"] == 1
        assert result["shared"] == 1

    # ------------------------------------------------------------
    # has 检查
    # ------------------------------------------------------------
    def test_has_checks_both_layers(self):
        cache = LayeredCache()
        assert cache.has("k") is False
        cache.set_local("a", 1)
        cache.set_shared("b", 2)
        assert cache.has("a") is True
        assert cache.has("b") is True
        assert "a" in cache
        assert "b" in cache

    def test_has_local_and_has_shared(self):
        cache = LayeredCache()
        cache.set_shared("only_shared", 1)
        assert cache.has_local("only_shared") is False
        assert cache.has_shared("only_shared") is True

    # ------------------------------------------------------------
    # 统计
    # ------------------------------------------------------------
    def test_overall_stats_aggregation(self):
        cache = LayeredCache()
        cache.set("a", 1)
        cache.set("b", 2)
        cache.get("a")
        cache.get("b")
        cache.get("missing", loader=lambda: "loaded")
        cache.get("missing")

        stats = cache.get_stats()
        overall = stats["overall"]

        assert overall["accesses"] > 0
        assert overall["hits"] >= 3
        assert overall["loader_calls"] == 1
        assert 0 <= overall["hit_rate"] <= 1.0

    def test_loader_calls_counter(self):
        cache = LayeredCache()
        cache.get("a", loader=lambda: 1)
        cache.get("b", loader=lambda: 2)
        cache.get("a", loader=lambda: 999)
        stats = cache.get_stats()
        assert stats["overall"]["loader_calls"] == 2

    def test_reset_stats(self):
        cache = LayeredCache()
        cache.set("a", 1)
        cache.get("a")
        cache.invalidate("a")
        cache.reset_stats()
        stats = cache.get_stats()
        assert stats["local"]["sets"] == 0
        assert stats["shared"]["sets"] == 0
        assert stats["local"]["hits"] == 0
        assert stats["overall"]["invalidations"] == 0
        assert stats["overall"]["loader_calls"] == 0

    def test_sizes_in_stats(self):
        cache = LayeredCache()
        cache.set_local("a", 1)
        cache.set_shared("b", 2)
        stats = cache.get_stats()
        assert stats["sizes"]["local"] == 1
        assert stats["sizes"]["shared"] == 1

    def test_invalidation_stats(self):
        cache = LayeredCache()
        cache.set("a", 1, tags=["t"])
        cache.set("b", 2, tags=["t"])
        cache.invalidate_by_tag("t")
        stats = cache.get_stats()
        assert stats["overall"]["invalidations"] >= 4

    # ------------------------------------------------------------
    # 异常处理
    # ------------------------------------------------------------
    def test_loader_exception_wrapped(self):
        cache = LayeredCache()

        def bad_loader():
            raise ValueError("boom")

        with pytest.raises(CacheLoaderError) as exc_info:
            cache.get("k", loader=bad_loader)

        assert exc_info.value.key == "k"
        assert isinstance(exc_info.value.original_error, ValueError)
        assert "boom" in str(exc_info.value.original_error)

    def test_loader_exception_no_cache_pollution(self):
        cache = LayeredCache()

        def bad_loader():
            raise RuntimeError("fail")

        with pytest.raises(CacheLoaderError):
            cache.get("k", loader=bad_loader)

        assert cache.has("k") is False
        assert cache.get_local("k") is None
        assert cache.get_shared("k") is None

    # ------------------------------------------------------------
    # 共享缓存共享（模拟多个客户端共享同一个 shared cache）
    # ------------------------------------------------------------
    def test_shared_cache_instance_reuse(self):
        shared = SingleLevelCache(max_size=100, default_ttl=None)

        client1 = LayeredCache(shared_cache_instance=shared)
        client2 = LayeredCache(shared_cache_instance=shared)

        client1.set("shared_key", "shared_value", write_local=True, write_shared=True)

        assert client2.get_shared("shared_key") == "shared_value"
        result = client2.get("shared_key")
        assert result == "shared_value"
        assert client2.get_local("shared_key") == "shared_value"

    def test_shared_invalidation_affects_all_clients(self):
        shared = SingleLevelCache()
        client1 = LayeredCache(shared_cache_instance=shared)
        client2 = LayeredCache(shared_cache_instance=shared)

        client1.set("k", "v", tags=["t"], write_local=False, write_shared=True)
        client2.get("k")

        shared.invalidate_by_tag("t")

        assert client1.get_shared("k") is None
        assert client2.get_shared("k") is None

    # ------------------------------------------------------------
    # LRU 分层独立
    # ------------------------------------------------------------
    def test_local_lru_independent_of_shared(self):
        cache = LayeredCache(local_max_size=2, shared_max_size=100)
        cache.set("a", 1)
        cache.set("b", 2)

        cache.get("a")
        cache.set("c", 3)

        assert cache.get_local("a") == 1
        assert cache.get_local("b") is None
        assert cache.get_local("c") == 3
        assert cache.get_shared("a") == 1
        assert cache.get_shared("b") == 2
        assert cache.get_shared("c") == 3

    # ------------------------------------------------------------
    # __len__ 聚合
    # ------------------------------------------------------------
    def test_len_sums_both_layers(self):
        cache = LayeredCache()
        cache.set_local("a", 1)
        cache.set_shared("b", 2)
        cache.set("c", 3)
        assert len(cache) == 4  # a(local) + b(shared) + c(local+shared)

    # ------------------------------------------------------------
    # 线程安全
    # ------------------------------------------------------------
    def test_layered_thread_safety(self):
        cache = LayeredCache(local_max_size=100, shared_max_size=100)
        errors = []

        def worker(start, end):
            try:
                for i in range(start, end):
                    key = f"k{i}"
                    cache.set(key, i, tags=[f"tag{i % 3}"])
                    cache.get(key, loader=lambda idx=i: idx * 2)
                    if i % 5 == 0:
                        cache.invalidate(key)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i * 25, (i + 1) * 25)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    # ------------------------------------------------------------
    # 综合场景
    # ------------------------------------------------------------
    def test_real_world_scenario(self):
        shared_cache = SingleLevelCache()
        app_cache = LayeredCache(shared_cache_instance=shared_cache)

        load_count = {"user": 0, "order": 0}

        def load_user(uid):
            load_count["user"] += 1
            return {"id": uid, "name": f"User{uid}"}

        def load_order(oid):
            load_count["order"] += 1
            return {"id": oid, "user_id": 1, "total": 100}

        u1 = app_cache.get("user:1", loader=lambda: load_user(1), tags=["users"])
        u1_again = app_cache.get("user:1", loader=lambda: load_user(1), tags=["users"])
        assert u1 == u1_again
        assert load_count["user"] == 1

        o1 = app_cache.get("order:1", loader=lambda: load_order(1), tags=["orders", "users"])
        o1_again = app_cache.get("order:1", loader=lambda: load_order(1), tags=["orders", "users"])
        assert o1 == o1_again
        assert load_count["order"] == 1

        result = app_cache.invalidate_by_tag("users")
        assert result["local"] == 2
        assert result["shared"] == 2

        app_cache.get("user:1", loader=lambda: load_user(1), tags=["users"])
        app_cache.get("order:1", loader=lambda: load_order(1), tags=["orders", "users"])
        assert load_count["user"] == 2
        assert load_count["order"] == 2

        stats = app_cache.get_stats()
        assert stats["overall"]["loader_calls"] == 4
