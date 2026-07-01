import threading
import time
import pytest
from typing import List

from solocoder_4_py.cache_avalanche_guard import (
    CacheAvalancheGuard,
    CacheEntry,
    CacheEntryState,
    CacheGuardStats,
    CacheRebuildError,
    RebuildStrategy,
)


# =====================================================================
# CacheGuardStats 测试
# =====================================================================
class TestCacheGuardStats:
    def test_defaults(self):
        stats = CacheGuardStats()
        assert stats.accesses == 0
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.hit_rate == 0.0

    def test_hit_rate_zero_accesses(self):
        stats = CacheGuardStats(accesses=0, hits=0)
        assert stats.hit_rate == 0.0

    def test_hit_rate_all_hits(self):
        stats = CacheGuardStats(accesses=100, hits=100, misses=0)
        assert stats.hit_rate == 1.0

    def test_hit_rate_partial(self):
        stats = CacheGuardStats(accesses=100, hits=75, misses=25)
        assert stats.hit_rate == 0.75

    def test_to_dict_includes_all_fields(self):
        stats = CacheGuardStats(
            accesses=10,
            hits=7,
            misses=3,
            sets=5,
            rebuilds=2,
            rebuild_failures=1,
            degraded_returns=1,
            hot_key_hits=3,
            background_renews=4,
            evictions=2,
        )
        d = stats.to_dict()
        assert d["accesses"] == 10
        assert d["hits"] == 7
        assert d["misses"] == 3
        assert d["hit_rate"] == 0.7
        assert d["sets"] == 5
        assert d["rebuilds"] == 2
        assert d["rebuild_failures"] == 1
        assert d["degraded_returns"] == 1
        assert d["hot_key_hits"] == 3
        assert d["background_renews"] == 4
        assert d["evictions"] == 2


# =====================================================================
# CacheAvalancheGuard 基础功能测试
# =====================================================================
class TestCacheAvalancheGuardBasic:
    def test_set_and_get(self):
        guard = CacheAvalancheGuard(enable_background_renew=False)
        guard.set("k1", "v1")
        assert guard.get("k1") == "v1"

    def test_get_nonexistent_returns_none(self):
        guard = CacheAvalancheGuard(enable_background_renew=False)
        assert guard.get("missing") is None

    def test_has(self):
        guard = CacheAvalancheGuard(enable_background_renew=False)
        assert guard.has("k1") is False
        guard.set("k1", "v1")
        assert guard.has("k1") is True
        assert "k1" in guard

    def test_len(self):
        guard = CacheAvalancheGuard(enable_background_renew=False)
        assert len(guard) == 0
        guard.set("a", 1)
        guard.set("b", 2)
        assert len(guard) == 2

    def test_overwrite_existing_key(self):
        guard = CacheAvalancheGuard(enable_background_renew=False)
        guard.set("k", "old")
        guard.set("k", "new")
        assert guard.get("k") == "new"
        assert len(guard) == 1

    def test_get_with_loader(self):
        guard = CacheAvalancheGuard(enable_background_renew=False)
        call_count = [0]

        def loader():
            call_count[0] += 1
            return "loaded_value"

        result = guard.get("key1", loader=loader)
        assert result == "loaded_value"
        assert call_count[0] == 1

        result2 = guard.get("key1", loader=loader)
        assert result2 == "loaded_value"
        assert call_count[0] == 1

    def test_get_or_load(self):
        guard = CacheAvalancheGuard(enable_background_renew=False)
        result = guard.get_or_load("k", lambda: "v")
        assert result == "v"

    def test_ttl_expiration(self):
        guard = CacheAvalancheGuard(default_ttl=0.1, enable_background_renew=False)
        guard.set("k", "v")
        assert guard.get("k") == "v"
        time.sleep(0.15)
        assert guard.get("k") is None
        assert guard.has("k") is False

    def test_per_key_ttl_overrides_default(self):
        guard = CacheAvalancheGuard(default_ttl=3600, enable_background_renew=False)
        guard.set("k_short", "v1", ttl=0.1)
        guard.set("k_long", "v2")
        time.sleep(0.15)
        assert guard.get("k_short") is None
        assert guard.get("k_long") == "v2"

    def test_invalidate_by_key(self):
        guard = CacheAvalancheGuard(enable_background_renew=False)
        guard.set("a", 1)
        guard.set("b", 2)
        assert guard.invalidate("a") is True
        assert guard.invalidate("nonexistent") is False
        assert guard.get("a") is None
        assert guard.get("b") == 2

    def test_invalidate_by_tag(self):
        guard = CacheAvalancheGuard(enable_background_renew=False)
        guard.set("u1", {"id": 1}, tags=["users"])
        guard.set("u2", {"id": 2}, tags=["users"])
        guard.set("o1", {"id": 1}, tags=["orders"])
        guard.set("mixed", {}, tags=["users", "orders"])

        count = guard.invalidate_by_tag("users")
        assert count == 3
        assert guard.get("u1") is None
        assert guard.get("u2") is None
        assert guard.get("mixed") is None
        assert guard.get("o1") is not None

    def test_invalidate_by_tags_multi(self):
        guard = CacheAvalancheGuard(enable_background_renew=False)
        guard.set("a", 1, tags=["t1"])
        guard.set("b", 2, tags=["t2"])
        guard.set("c", 3, tags=["t3"])

        count = guard.invalidate_by_tags(["t1", "t2"])
        assert count == 2
        assert guard.get("a") is None
        assert guard.get("b") is None
        assert guard.get("c") == 3

    def test_invalidate_all(self):
        guard = CacheAvalancheGuard(enable_background_renew=False)
        guard.set("a", 1)
        guard.set("b", 2)
        count = guard.invalidate_all()
        assert count == 2
        assert len(guard) == 0
        assert guard.get("a") is None

    def test_invalidate_expired(self):
        guard = CacheAvalancheGuard(enable_background_renew=False)
        guard.set("expired", "e1", ttl=0.05)
        guard.set("fresh", "f1")
        time.sleep(0.1)
        count = guard.invalidate_expired()
        assert count == 1
        assert guard.get("expired") is None
        assert guard.get("fresh") == "f1"

    def test_lru_eviction(self):
        guard = CacheAvalancheGuard(max_size=3, enable_background_renew=False)
        guard.set("a", 1)
        time.sleep(0.01)
        guard.set("b", 2)
        time.sleep(0.01)
        guard.set("c", 3)

        guard.get("a")

        time.sleep(0.01)
        guard.set("d", 4)

        assert len(guard) == 3
        assert guard.get("a") == 1
        assert guard.get("b") is None
        assert guard.get("c") == 3
        assert guard.get("d") == 4
        stats = guard.get_stats()
        assert stats.evictions == 1

    def test_keys(self):
        guard = CacheAvalancheGuard(enable_background_renew=False)
        guard.set("a", 1, tags=["t"])
        guard.set("b", 2, tags=["t"])
        keys = guard.keys()
        assert sorted(keys) == ["a", "b"]

    def test_get_entry(self):
        guard = CacheAvalancheGuard(enable_background_renew=False)
        guard.set("k", "v", tags=["t"])
        entry = guard.get_entry("k")
        assert isinstance(entry, CacheEntry)
        assert entry.key == "k"
        assert entry.value == "v"
        assert entry.tags == ["t"]

    def test_stats_tracking(self):
        guard = CacheAvalancheGuard(enable_background_renew=False)
        guard.set("a", 1)
        guard.set("b", 2)
        guard.get("a")
        guard.get("a")
        guard.get("missing")

        stats = guard.get_stats()
        assert stats.sets == 2
        assert stats.accesses == 3
        assert stats.hits == 2
        assert stats.misses == 1
        assert stats.hit_rate == 2 / 3

    def test_reset_stats(self):
        guard = CacheAvalancheGuard(enable_background_renew=False)
        guard.set("a", 1)
        guard.get("a")
        guard.invalidate("a")
        guard.reset_stats()
        stats = guard.get_stats()
        assert stats.accesses == 0
        assert stats.hits == 0
        assert stats.sets == 0


# =====================================================================
# 过期时间抖动测试
# =====================================================================
class TestJitter:
    def test_jitter_applied_to_set(self):
        guard = CacheAvalancheGuard(
            default_ttl=100, jitter_ratio=0.1, enable_background_renew=False
        )
        entry = guard.set("k", "v")
        base_expiry = time.time() + 100
        jitter_range = 100 * 0.1
        assert (
            base_expiry - jitter_range - 1
            <= entry.expires_at
            <= base_expiry + jitter_range + 1
        )

    def test_jitter_applied_to_rebuild(self):
        guard = CacheAvalancheGuard(
            default_ttl=100, jitter_ratio=0.1, enable_background_renew=False
        )

        def loader():
            return "loaded"

        result = guard.get("k", loader=loader)
        assert result == "loaded"
        entry = guard.get_entry("k")
        base_expiry = time.time() + 100
        jitter_range = 100 * 0.1
        assert (
            base_expiry - jitter_range - 1
            <= entry.expires_at
            <= base_expiry + jitter_range + 1
        )

    def test_zero_jitter_no_variance(self):
        guard = CacheAvalancheGuard(
            default_ttl=100, jitter_ratio=0.0, enable_background_renew=False
        )
        entry = guard.set("k", "v")
        expected_expiry = time.time() + 100
        assert abs(entry.expires_at - expected_expiry) < 1

    def test_jitter_ratio_clamped(self):
        guard = CacheAvalancheGuard(
            default_ttl=100, jitter_ratio=1.0, enable_background_renew=False
        )
        entry = guard.set("k", "v")
        base_expiry = time.time() + 100
        jitter_range = 100 * 0.5
        assert (
            base_expiry - jitter_range - 1
            <= entry.expires_at
            <= base_expiry + jitter_range + 1
        )

    def test_jitter_prevents_simultaneous_expiry(self):
        guard = CacheAvalancheGuard(
            default_ttl=100, jitter_ratio=0.2, enable_background_renew=False
        )
        expiry_times: List[float] = []
        for i in range(100):
            entry = guard.set(f"k{i}", f"v{i}")
            expiry_times.append(entry.expires_at)

        unique_times = set(round(t, 1) for t in expiry_times)
        assert len(unique_times) > 50


# =====================================================================
# 热点键检测测试
# =====================================================================
class TestHotKeyDetection:
    def test_hot_key_detection(self):
        guard = CacheAvalancheGuard(
            hot_key_threshold=5, hot_key_window_seconds=60, enable_background_renew=False
        )
        guard.set("hot_key", "value")

        for _ in range(5):
            guard.get("hot_key")

        hot_keys = guard.get_hot_keys()
        assert "hot_key" in hot_keys

    def test_non_hot_key_not_detected(self):
        guard = CacheAvalancheGuard(
            hot_key_threshold=5, hot_key_window_seconds=60, enable_background_renew=False
        )
        guard.set("cold_key", "value")

        guard.get("cold_key")

        hot_keys = guard.get_hot_keys()
        assert "cold_key" not in hot_keys

    def test_hot_key_hit_tracking(self):
        guard = CacheAvalancheGuard(
            hot_key_threshold=3, hot_key_window_seconds=60, enable_background_renew=False
        )
        guard.set("hot", "value")

        for _ in range(5):
            guard.get("hot")

        stats = guard.get_stats()
        assert stats.hot_key_hits >= 2

    def test_hot_key_window_expiry(self):
        guard = CacheAvalancheGuard(
            hot_key_threshold=5, hot_key_window_seconds=1, enable_background_renew=False
        )
        guard.set("k", "v")

        for _ in range(5):
            guard.get("k")

        time.sleep(1.1)
        guard.invalidate_expired()

        hot_keys = guard.get_hot_keys()
        assert "k" not in hot_keys


# =====================================================================
# 单飞重建测试
# =====================================================================
class TestSingleFlightRebuild:
    def test_single_flight_prevents_duplicate_rebuilds(self):
        guard = CacheAvalancheGuard(
            enable_background_renew=False, rebuild_timeout_seconds=10
        )
        call_count = [0]
        results: List[str] = []
        errors: List[Exception] = []

        def slow_loader():
            call_count[0] += 1
            time.sleep(0.2)
            return "loaded_value"

        def worker():
            try:
                result = guard.get("key", loader=slow_loader)
                results.append(result)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert call_count[0] == 1
        assert len(errors) == 0
        assert all(r == "loaded_value" for r in results)
        assert len(results) == 10

    def test_single_flight_rebuild_timeout(self):
        guard = CacheAvalancheGuard(
            enable_background_renew=False, rebuild_timeout_seconds=0.1
        )

        def slow_loader():
            time.sleep(1.0)
            return "loaded"

        results: List[object] = []

        def worker():
            try:
                result = guard.get("key", loader=slow_loader, degraded_value="fallback")
                results.append(result)
            except Exception as e:
                results.append(e)

        t1 = threading.Thread(target=worker)
        t2 = threading.Thread(target=worker)
        t1.start()
        time.sleep(0.01)
        t2.start()
        t1.join()
        t2.join()

        assert len(results) == 2
        assert "fallback" in results

    def test_rebuild_state_transition(self):
        guard = CacheAvalancheGuard(enable_background_renew=False)

        rebuild_started = threading.Event()
        can_complete = threading.Event()

        def loader():
            rebuild_started.set()
            can_complete.wait()
            return "loaded"

        result_container: List[object] = []

        def worker():
            result = guard.get("k", loader=loader)
            result_container.append(result)

        t = threading.Thread(target=worker)
        t.start()

        rebuild_started.wait()

        entry = guard.get_entry("k")
        assert entry is not None
        assert entry.state == CacheEntryState.REBUILDING

        can_complete.set()
        t.join()

        entry = guard.get_entry("k")
        assert entry is not None
        assert entry.state == CacheEntryState.VALID
        assert result_container == ["loaded"]


# =====================================================================
# 降级占位值测试
# =====================================================================
class TestDegradedValue:
    def test_rebuild_failure_returns_degraded_value(self):
        guard = CacheAvalancheGuard(enable_background_renew=False)

        def bad_loader():
            raise ValueError("boom")

        result = guard.get(
            "k", loader=bad_loader, degraded_value="fallback"
        )
        assert result == "fallback"

        stats = guard.get_stats()
        assert stats.rebuild_failures == 1
        assert stats.degraded_returns == 1

    def test_rebuild_failure_raises_without_degraded_value(self):
        guard = CacheAvalancheGuard(enable_background_renew=False)

        def bad_loader():
            raise ValueError("boom")

        with pytest.raises(CacheRebuildError) as exc_info:
            guard.get("k", loader=bad_loader)

        assert exc_info.value.key == "k"
        assert isinstance(exc_info.value.original_error, ValueError)

    def test_degraded_state_persists(self):
        guard = CacheAvalancheGuard(
            enable_background_renew=False, degraded_ttl_seconds=1
        )

        def bad_loader():
            raise ValueError("boom")

        result1 = guard.get("k", loader=bad_loader, degraded_value="fallback")
        assert result1 == "fallback"

        result2 = guard.get("k")
        assert result2 == "fallback"

        entry = guard.get_entry("k")
        assert entry is not None
        assert entry.state == CacheEntryState.DEGRADED
        assert entry.degraded_value == "fallback"

    def test_degraded_value_expires(self):
        guard = CacheAvalancheGuard(
            enable_background_renew=False, degraded_ttl_seconds=0.1
        )

        def bad_loader():
            raise ValueError("boom")

        guard.get("k", loader=bad_loader, degraded_value="fallback")

        time.sleep(0.15)
        result = guard.get("k")
        assert result is None

    def test_degraded_value_tags(self):
        guard = CacheAvalancheGuard(enable_background_renew=False)

        def bad_loader():
            raise ValueError("boom")

        guard.get(
            "k",
            loader=bad_loader,
            degraded_value="fallback",
            tags=["test_tag"],
        )

        count = guard.invalidate_by_tag("test_tag")
        assert count == 1


# =====================================================================
# 后台续期测试
# =====================================================================
class TestBackgroundRenew:
    def test_background_renew_extends_hot_key_ttl(self):
        guard = CacheAvalancheGuard(
            default_ttl=100,
            jitter_ratio=0,
            hot_key_threshold=3,
            hot_key_window_seconds=60,
            background_renew_interval_seconds=0.1,
            enable_background_renew=True,
        )

        try:
            guard.set("hot_key", "value", ttl=5)

            for _ in range(5):
                guard.get("hot_key")

            entry_before = guard.get_entry("hot_key")
            assert entry_before is not None
            expiry_before = entry_before.expires_at

            time.sleep(4)

            entry_after = guard.get_entry("hot_key")
            assert entry_after is not None
            assert entry_after.expires_at > expiry_before

            stats = guard.get_stats()
            assert stats.background_renews >= 1
        finally:
            guard.stop()

    def test_background_renew_disabled(self):
        guard = CacheAvalancheGuard(
            enable_background_renew=False,
        )
        assert guard._background_thread is None

    def test_stop_background_thread(self):
        guard = CacheAvalancheGuard(
            background_renew_interval_seconds=0.1,
            enable_background_renew=True,
        )

        assert guard._background_thread is not None
        assert guard._background_thread.is_alive()

        guard.stop()

        time.sleep(0.3)
        assert not guard._background_thread.is_alive()


# =====================================================================
# 线程安全测试
# =====================================================================
class TestThreadSafety:
    def test_concurrent_read_write(self):
        guard = CacheAvalancheGuard(max_size=100, enable_background_renew=False)
        errors: List[Exception] = []

        def writer(start, end):
            try:
                for i in range(start, end):
                    guard.set(f"k{i}", i, tags=[f"tag{i % 5}"])
            except Exception as e:
                errors.append(e)

        def reader(start, end):
            try:
                for i in range(start, end):
                    guard.get(f"k{i}")
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

    def test_concurrent_rebuild_with_degraded_value(self):
        guard = CacheAvalancheGuard(
            enable_background_renew=False,
            rebuild_timeout_seconds=5,
            degraded_ttl_seconds=0.1,
        )
        errors: List[Exception] = []
        results: List[object] = []

        call_count = [0]

        def flaky_loader():
            call_count[0] += 1
            if call_count[0] == 1:
                raise ValueError("first call fails")
            time.sleep(0.05)
            return "success"

        def worker():
            try:
                result = guard.get(
                    "key", loader=flaky_loader, degraded_value="fallback"
                )
                results.append(result)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert all(r in ("fallback", "success") for r in results)
        assert "fallback" in results

        time.sleep(0.15)
        result_after_expiry = guard.get(
            "key", loader=flaky_loader, degraded_value="fallback"
        )
        assert result_after_expiry == "success"


# =====================================================================
# 综合场景测试
# =====================================================================
class TestIntegration:
    def test_full_avalanche_protection_scenario(self):
        guard = CacheAvalancheGuard(
            max_size=1000,
            default_ttl=300,
            jitter_ratio=0.1,
            hot_key_threshold=10,
            hot_key_window_seconds=60,
            rebuild_timeout_seconds=5,
            enable_background_renew=True,
        )

        try:
            load_count = {"user": 0, "product": 0}

            def load_user(uid):
                load_count["user"] += 1
                return {"id": uid, "name": f"User{uid}"}

            def load_product(pid):
                load_count["product"] += 1
                return {"id": pid, "name": f"Product{pid}", "price": 100}

            for _ in range(20):
                result = guard.get(
                    "user:1",
                    loader=lambda: load_user(1),
                    degraded_value={"id": 1, "name": "Guest"},
                    tags=["users"],
                )
                assert result["id"] == 1

            for _ in range(5):
                result = guard.get(
                    "product:123",
                    loader=lambda: load_product(123),
                    tags=["products"],
                )
                assert result["id"] == 123

            hot_keys = guard.get_hot_keys()
            assert "user:1" in hot_keys

            assert load_count["user"] == 1
            assert load_count["product"] == 1

            guard.invalidate_by_tag("users")

            result = guard.get(
                "user:1",
                loader=lambda: load_user(1),
                degraded_value={"id": 1, "name": "Guest"},
            )
            assert result["id"] == 1
            assert load_count["user"] == 2

            stats = guard.get_stats()
            assert stats.accesses >= 26
            assert stats.hits >= 23
            assert stats.rebuilds == 3
            assert stats.hot_key_hits >= 10
        finally:
            guard.stop()

    def test_massive_concurrent_access_scenario(self):
        guard = CacheAvalancheGuard(
            max_size=10000,
            default_ttl=10,
            jitter_ratio=0.2,
            hot_key_threshold=100,
            rebuild_timeout_seconds=10,
            enable_background_renew=True,
        )

        try:
            call_count = {"hot": 0, "cold": 0}
            errors: List[Exception] = []

            def load_hot():
                call_count["hot"] += 1
                time.sleep(0.01)
                return "hot_data"

            def load_cold():
                call_count["cold"] += 1
                time.sleep(0.01)
                return "cold_data"

            def access_hot():
                try:
                    for _ in range(100):
                        guard.get(
                            "hot_key",
                            loader=load_hot,
                            degraded_value="hot_fallback",
                        )
                except Exception as e:
                    errors.append(e)

            def access_cold():
                try:
                    for i in range(10):
                        guard.get(
                            f"cold_key_{i}",
                            loader=load_cold,
                            degraded_value="cold_fallback",
                        )
                except Exception as e:
                    errors.append(e)

            threads = []
            for _ in range(20):
                threads.append(threading.Thread(target=access_hot))
                threads.append(threading.Thread(target=access_cold))

            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert len(errors) == 0
            assert call_count["hot"] == 1
            assert call_count["cold"] == 10

            stats = guard.get_stats()
            assert stats.accesses == 20 * 100 + 20 * 10
            assert stats.hit_rate > 0.85
        finally:
            guard.stop()


# =====================================================================
# ASYNC 异步重建策略测试
# =====================================================================
class TestAsyncRebuildStrategy:
    def test_async_rebuild_returns_degraded_value_immediately(self):
        guard = CacheAvalancheGuard(enable_background_renew=False)
        rebuild_started = threading.Event()
        can_complete = threading.Event()

        def slow_loader():
            rebuild_started.set()
            can_complete.wait()
            return "loaded_value"

        result = guard.get(
            "async_key",
            loader=slow_loader,
            degraded_value="fallback",
            rebuild_strategy=RebuildStrategy.ASYNC,
        )
        assert result == "fallback"
        assert rebuild_started.wait(timeout=1)

        entry = guard.get_entry("async_key")
        assert entry is not None
        assert entry.state == CacheEntryState.DEGRADED
        assert entry.degraded_value == "fallback"

        can_complete.set()
        time.sleep(0.2)

        entry_after = guard.get_entry("async_key")
        assert entry_after is not None
        assert entry_after.state == CacheEntryState.VALID
        assert entry_after.value == "loaded_value"

        result_after = guard.get("async_key")
        assert result_after == "loaded_value"
        guard.stop()

    def test_async_rebuild_without_degraded_value_returns_none(self):
        guard = CacheAvalancheGuard(enable_background_renew=False)
        rebuild_completed = threading.Event()

        def loader():
            try:
                return "loaded"
            finally:
                rebuild_completed.set()

        result = guard.get(
            "async_key2",
            loader=loader,
            rebuild_strategy=RebuildStrategy.ASYNC,
        )
        assert result is None
        assert rebuild_completed.wait(timeout=2)
        time.sleep(0.1)

        result_after = guard.get("async_key2")
        assert result_after == "loaded"
        guard.stop()

    def test_async_rebuild_failure_persists_degraded_state(self):
        guard = CacheAvalancheGuard(enable_background_renew=False)
        rebuild_completed = threading.Event()

        def bad_loader():
            try:
                raise ValueError("rebuild failed")
            finally:
                rebuild_completed.set()

        result = guard.get(
            "async_key3",
            loader=bad_loader,
            degraded_value="fallback",
            rebuild_strategy=RebuildStrategy.ASYNC,
        )
        assert result == "fallback"
        assert rebuild_completed.wait(timeout=2)
        time.sleep(0.1)

        entry = guard.get_entry("async_key3")
        assert entry is not None
        assert entry.state == CacheEntryState.DEGRADED
        assert entry.degraded_value == "fallback"

        result_after = guard.get("async_key3")
        assert result_after == "fallback"
        guard.stop()

    def test_sync_rebuild_still_works(self):
        guard = CacheAvalancheGuard(enable_background_renew=False)
        call_count = [0]

        def loader():
            call_count[0] += 1
            return "sync_value"

        result = guard.get(
            "sync_key",
            loader=loader,
            rebuild_strategy=RebuildStrategy.SYNC,
        )
        assert result == "sync_value"
        assert call_count[0] == 1

        result2 = guard.get("sync_key")
        assert result2 == "sync_value"
        assert call_count[0] == 1


# =====================================================================
# 降级值持久化测试
# =====================================================================
class TestDegradedValuePersistence:
    def test_timeout_persists_degraded_value(self):
        guard = CacheAvalancheGuard(
            enable_background_renew=False,
            rebuild_timeout_seconds=0.1,
            degraded_ttl_seconds=1,
        )
        rebuild_started = threading.Event()
        can_complete = threading.Event()

        def slow_loader():
            rebuild_started.set()
            can_complete.wait()
            return "loaded"

        results: List[object] = []

        def worker1():
            try:
                result = guard.get(
                    "key",
                    loader=slow_loader,
                    degraded_value="fallback",
                    tags=["persist_test"],
                )
                results.append(result)
            except Exception as e:
                results.append(e)

        def worker2():
            time.sleep(0.01)
            try:
                result = guard.get(
                    "key",
                    loader=slow_loader,
                    degraded_value="fallback",
                    tags=["persist_test"],
                )
                results.append(result)
            except Exception as e:
                results.append(e)

        t1 = threading.Thread(target=worker1)
        t2 = threading.Thread(target=worker2)
        t1.start()
        t2.start()
        rebuild_started.wait(timeout=1)
        t1.join(timeout=1)
        t2.join(timeout=1)

        assert "fallback" in results

        entry = guard.get_entry("key")
        assert entry is not None
        assert entry.state == CacheEntryState.DEGRADED
        assert entry.degraded_value == "fallback"

        result_without_degraded = guard.get("key")
        assert result_without_degraded == "fallback"

        count = guard.invalidate_by_tag("persist_test")
        assert count == 1

        can_complete.set()

    def test_degraded_value_persists_without_reloader(self):
        guard = CacheAvalancheGuard(
            enable_background_renew=False,
            degraded_ttl_seconds=2,
        )

        def bad_loader():
            raise ValueError("boom")

        result1 = guard.get(
            "persist_key",
            loader=bad_loader,
            degraded_value="fallback",
        )
        assert result1 == "fallback"

        result2 = guard.get("persist_key")
        assert result2 == "fallback"

        result3 = guard.get("persist_key", loader=bad_loader)
        assert result3 == "fallback"

        entry = guard.get_entry("persist_key")
        assert entry is not None
        assert entry.state == CacheEntryState.DEGRADED

    def test_timeout_degraded_value_has_independent_ttl(self):
        guard = CacheAvalancheGuard(
            enable_background_renew=False,
            rebuild_timeout_seconds=0.1,
            degraded_ttl_seconds=0.4,
        )
        can_complete = threading.Event()
        rebuild_started = threading.Event()

        def slow_loader():
            rebuild_started.set()
            can_complete.wait()
            return "loaded"

        def worker_rebuilder():
            return guard.get(
                "ttl_key",
                loader=slow_loader,
                degraded_value="fallback",
            )

        def worker_waiter():
            time.sleep(0.01)
            return guard.get(
                "ttl_key",
                loader=slow_loader,
                degraded_value="fallback",
            )

        t_rebuilder = threading.Thread(target=worker_rebuilder)
        t_waiter = threading.Thread(target=worker_waiter)

        t_rebuilder.start()
        rebuild_started.wait(timeout=1)
        t_waiter.start()

        t_waiter.join(timeout=2)
        assert t_waiter.is_alive() is False

        entry = guard.get_entry("ttl_key")
        assert entry is not None
        assert entry.state == CacheEntryState.DEGRADED

        result = guard.get("ttl_key")
        assert result == "fallback"

        time.sleep(0.2)
        result2 = guard.get("ttl_key")
        assert result2 == "fallback"

        time.sleep(0.3)
        result3 = guard.get("ttl_key")
        assert result3 is None

        can_complete.set()
        t_rebuilder.join(timeout=1)


# =====================================================================
# 自定义 TTL 续期测试
# =====================================================================
class TestCustomTTLRenewal:
    def test_set_preserves_original_ttl(self):
        guard = CacheAvalancheGuard(
            default_ttl=300,
            enable_background_renew=False,
        )
        entry = guard.set("short_ttl_key", "value", ttl=60)
        assert entry.original_ttl == 60

        entry2 = guard.set("default_ttl_key", "value")
        assert entry2.original_ttl == 300

    def test_rebuild_preserves_original_ttl(self):
        guard = CacheAvalancheGuard(
            default_ttl=300,
            enable_background_renew=False,
        )

        def loader():
            return "loaded"

        guard.get("custom_ttl_rebuild", loader=loader, ttl=120)
        entry = guard.get_entry("custom_ttl_rebuild")
        assert entry is not None
        assert entry.original_ttl == 120

    def test_renew_hot_key_uses_entry_ttl(self):
        guard = CacheAvalancheGuard(
            default_ttl=300,
            jitter_ratio=0,
            hot_key_threshold=3,
            hot_key_window_seconds=60,
            enable_background_renew=False,
        )

        guard.set("short_ttl_hot", "value", ttl=10)

        for _ in range(5):
            guard.get("short_ttl_hot")

        entry = guard.get_entry("short_ttl_hot")
        assert entry is not None
        original_expires_at = entry.expires_at
        original_ttl = entry.original_ttl
        assert original_ttl == 10

        time.sleep(9)

        now_before = time.time()
        guard._renew_hot_key("short_ttl_hot", entry)

        entry_after = guard.get_entry("short_ttl_hot")
        assert entry_after is not None
        assert entry_after.expires_at > original_expires_at

        expected_min = now_before + 10 - 1
        expected_max = now_before + 10 + 1
        assert expected_min <= entry_after.expires_at <= expected_max

    def test_renew_hot_key_default_ttl_fallback(self):
        guard = CacheAvalancheGuard(
            default_ttl=300,
            jitter_ratio=0,
            hot_key_threshold=3,
            hot_key_window_seconds=60,
            enable_background_renew=False,
        )

        entry = CacheEntry(
            key="no_original_ttl",
            value="value",
            expires_at=time.time() + 10,
            original_ttl=None,
        )
        guard._store["no_original_ttl"] = entry

        for _ in range(5):
            guard.get("no_original_ttl")

        original_expires_at = entry.expires_at

        time.sleep(9)

        now_before = time.time()
        guard._renew_hot_key("no_original_ttl", entry)

        entry_after = guard.get_entry("no_original_ttl")
        assert entry_after is not None
        assert entry_after.expires_at > original_expires_at

        expected_min = now_before + 300 - 1
        expected_max = now_before + 300 + 1
        assert expected_min <= entry_after.expires_at <= expected_max


# =====================================================================
# 短 TTL 续期阈值测试
# =====================================================================
class TestShortTTLRenewalThreshold:
    def test_short_ttl_entry_triggers_renewal(self):
        guard = CacheAvalancheGuard(
            default_ttl=300,
            hot_key_threshold=3,
            hot_key_window_seconds=60,
            enable_background_renew=False,
        )

        now = time.time()
        guard._store["short_ttl"] = CacheEntry(
            key="short_ttl",
            value="value",
            state=CacheEntryState.VALID,
            created_at=now - 5,
            expires_at=now + 2,
            original_ttl=10,
            access_timestamps=[now - 1, now - 0.5, now],
        )

        hot_keys = guard._find_hot_keys_locked()
        assert any(k == "short_ttl" for k, _ in hot_keys)

    def test_long_ttl_entry_not_triggered_with_low_remaining(self):
        guard = CacheAvalancheGuard(
            default_ttl=300,
            hot_key_threshold=3,
            hot_key_window_seconds=60,
            enable_background_renew=False,
        )

        now = time.time()
        guard._store["long_ttl"] = CacheEntry(
            key="long_ttl",
            value="value",
            state=CacheEntryState.VALID,
            created_at=now - 5,
            expires_at=now + 200,
            original_ttl=300,
            access_timestamps=[now - 1, now - 0.5, now],
        )

        hot_keys = guard._find_hot_keys_locked()
        assert not any(k == "long_ttl" for k, _ in hot_keys)

    def test_short_ttl_with_high_remaining_not_triggered(self):
        guard = CacheAvalancheGuard(
            default_ttl=300,
            hot_key_threshold=3,
            hot_key_window_seconds=60,
            enable_background_renew=False,
        )

        now = time.time()
        guard._store["short_ttl_high_remaining"] = CacheEntry(
            key="short_ttl_high_remaining",
            value="value",
            state=CacheEntryState.VALID,
            created_at=now - 1,
            expires_at=now + 9,
            original_ttl=10,
            access_timestamps=[now - 0.5, now - 0.25, now],
        )

        hot_keys = guard._find_hot_keys_locked()
        assert not any(k == "short_ttl_high_remaining" for k, _ in hot_keys)

    def test_find_hot_keys_uses_entry_ttl_not_default(self):
        guard = CacheAvalancheGuard(
            default_ttl=300,
            hot_key_threshold=2,
            hot_key_window_seconds=60,
            enable_background_renew=False,
        )

        now = time.time()
        guard._store["short"] = CacheEntry(
            key="short",
            value="v",
            state=CacheEntryState.VALID,
            expires_at=now + 2,
            original_ttl=10,
            access_timestamps=[now, now - 0.1],
        )
        guard._store["long"] = CacheEntry(
            key="long",
            value="v",
            state=CacheEntryState.VALID,
            expires_at=now + 200,
            original_ttl=300,
            access_timestamps=[now, now - 0.1],
        )

        hot_keys = guard._find_hot_keys_locked()
        hot_key_names = [k for k, _ in hot_keys]

        assert "short" in hot_key_names
        assert "long" not in hot_key_names

