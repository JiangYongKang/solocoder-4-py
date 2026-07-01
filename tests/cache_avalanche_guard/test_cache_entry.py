import time
import pytest

from solocoder_4_py.cache_avalanche_guard import (
    CacheEntry,
    CacheEntryState,
)


# =====================================================================
# CacheEntry 测试
# =====================================================================
class TestCacheEntry:
    def test_create_entry_defaults(self):
        entry = CacheEntry(key="k1", value="v1")
        assert entry.key == "k1"
        assert entry.value == "v1"
        assert entry.state == CacheEntryState.VALID
        assert entry.expires_at is None
        assert entry.hit_count == 0
        assert entry.tags == []
        assert entry.access_timestamps == []

    def test_is_valid_no_expiry(self):
        entry = CacheEntry(key="k", value="v")
        assert entry.is_valid() is True

    def test_is_valid_not_expired(self):
        entry = CacheEntry(key="k", value="v", expires_at=time.time() + 3600)
        assert entry.is_valid() is True

    def test_is_valid_expired(self):
        entry = CacheEntry(key="k", value="v", expires_at=time.time() - 1)
        assert entry.is_valid() is False

    def test_is_valid_rebuilding_state(self):
        entry = CacheEntry(key="k", value="v")
        entry.mark_rebuilding()
        assert entry.state == CacheEntryState.REBUILDING
        assert entry.is_valid() is False

    def test_is_valid_degraded_state(self):
        entry = CacheEntry(key="k", value="v")
        entry.mark_degraded(degraded_value="fallback", degraded_ttl=10)
        assert entry.state == CacheEntryState.DEGRADED
        assert entry.is_valid() is True

    def test_is_expired(self):
        entry = CacheEntry(key="k", value="v", expires_at=time.time() - 1)
        assert entry.is_expired() is True

    def test_is_expired_no_expiry(self):
        entry = CacheEntry(key="k", value="v")
        assert entry.is_expired() is False

    def test_touch_updates_hit_count(self):
        entry = CacheEntry(key="k", value="v")
        initial_hit = entry.hit_count
        entry.touch()
        assert entry.hit_count == initial_hit + 1
        entry.touch()
        assert entry.hit_count == initial_hit + 2

    def test_touch_updates_access_timestamps(self):
        entry = CacheEntry(key="k", value="v")
        assert len(entry.access_timestamps) == 0
        entry.touch()
        assert len(entry.access_timestamps) == 1
        entry.touch()
        assert len(entry.access_timestamps) == 2

    def test_touch_cleans_old_timestamps(self):
        entry = CacheEntry(key="k", value="v")
        now = time.time()
        old_time = now - 120
        entry.access_timestamps = [old_time, old_time + 1]

        entry.touch(now=now, window_seconds=60)

        assert len(entry.access_timestamps) == 1
        assert all(t >= now - 60 for t in entry.access_timestamps)

    def test_get_recent_hit_count(self):
        entry = CacheEntry(key="k", value="v")
        now = time.time()

        entry.access_timestamps = [
            now - 10,
            now - 20,
            now - 30,
            now - 70,
            now - 80,
        ]

        count = entry.get_recent_hit_count(window_seconds=60, now=now)
        assert count == 3

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

    def test_mark_rebuilding(self):
        entry = CacheEntry(key="k", value="v")
        initial_attempts = entry.rebuild_attempts

        entry.mark_rebuilding()

        assert entry.state == CacheEntryState.REBUILDING
        assert entry.rebuild_attempts == initial_attempts + 1
        assert entry.last_rebuild_at is not None

    def test_mark_rebuilt(self):
        entry = CacheEntry(key="k", value="old")
        entry.mark_degraded(degraded_value="fallback", degraded_ttl=10)
        new_expires_at = time.time() + 300

        entry.mark_rebuilt(value="new", expires_at=new_expires_at)

        assert entry.value == "new"
        assert entry.expires_at == new_expires_at
        assert entry.state == CacheEntryState.VALID
        assert entry.degraded_value is None
        assert entry.degraded_at is None

    def test_mark_degraded(self):
        entry = CacheEntry(key="k", value="v")

        entry.mark_degraded(degraded_value="fallback", degraded_ttl=10)

        assert entry.state == CacheEntryState.DEGRADED
        assert entry.degraded_value == "fallback"
        assert entry.degraded_at is not None
        assert entry.expires_at is not None
        assert entry.expires_at > time.time()

    def test_invalidate(self):
        entry = CacheEntry(key="k", value="v", expires_at=time.time() + 3600)
        assert entry.is_valid() is True

        entry.invalidate()

        assert entry.is_valid() is False
        assert entry.expires_at < time.time()

    def test_to_dict_and_from_dict(self):
        original = CacheEntry(
            key="k1",
            value={"nested": True},
            state=CacheEntryState.VALID,
            created_at=12345.0,
            expires_at=67890.0,
            accessed_at=54321.0,
            hit_count=10,
            access_timestamps=[1.0, 2.0, 3.0],
            degraded_value="fallback",
            degraded_at=4.0,
            rebuild_attempts=3,
            last_rebuild_at=5.0,
            tags=["a", "b"],
        )
        data = original.to_dict()
        restored = CacheEntry.from_dict(data)
        assert restored.key == original.key
        assert restored.value == original.value
        assert restored.state == original.state
        assert restored.created_at == original.created_at
        assert restored.expires_at == original.expires_at
        assert restored.accessed_at == original.accessed_at
        assert restored.hit_count == original.hit_count
        assert restored.access_timestamps == original.access_timestamps
        assert restored.degraded_value == original.degraded_value
        assert restored.degraded_at == original.degraded_at
        assert restored.rebuild_attempts == original.rebuild_attempts
        assert restored.last_rebuild_at == original.last_rebuild_at
        assert restored.tags == original.tags

    def test_tags_list_independence(self):
        tags = ["a", "b"]
        entry = CacheEntry(key="k", value="v", tags=tags)
        tags.append("c")
        assert entry.tags == ["a", "b"]

    def test_access_timestamps_independence(self):
        timestamps = [1.0, 2.0]
        entry = CacheEntry(key="k", value="v", access_timestamps=timestamps)
        timestamps.append(3.0)
        assert entry.access_timestamps == [1.0, 2.0]
