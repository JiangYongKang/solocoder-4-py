import pytest

from solocoder_4_py.transaction_log import StateStore, _MISSING


class TestStateStoreBasic:
    def test_empty_store(self):
        store = StateStore()
        assert len(store) == 0
        assert list(store.keys()) == []
        assert list(store.values()) == []
        assert list(store.items()) == []

    def test_set_and_get(self):
        store = StateStore()
        old = store.set("name", "Alice")
        assert old is _MISSING
        assert store.get("name") == "Alice"
        assert store["name"] == "Alice"
        assert len(store) == 1

    def test_set_none_value(self):
        store = StateStore()
        old = store.set("nullable", None)
        assert old is _MISSING
        assert store.get("nullable") is None
        assert store["nullable"] is None
        assert "nullable" in store

    def test_set_overwrite_with_none(self):
        store = StateStore()
        store.set("a", 1)
        old = store.set("a", None)
        assert old == 1
        assert store["a"] is None

    def test_set_overwrite_from_none(self):
        store = StateStore()
        store.set("a", None)
        old = store.set("a", 2)
        assert old is None
        assert old is not _MISSING
        assert store["a"] == 2

    def test_set_overwrite_returns_old(self):
        store = StateStore()
        store.set("a", 1)
        old = store.set("a", 2)
        assert old == 1
        assert store["a"] == 2

    def test_get_default(self):
        store = StateStore()
        assert store.get("missing") is None
        assert store.get("missing", 42) == 42

    def test_exists(self):
        store = StateStore()
        store.set("x", 1)
        assert store.exists("x")
        assert not store.exists("y")
        assert "x" in store
        assert "y" not in store

    def test_exists_with_none_value(self):
        store = StateStore()
        store.set("x", None)
        assert store.exists("x")
        assert "x" in store

    def test_delete_existing(self):
        store = StateStore()
        store.set("z", "value")
        existed, old = store.delete("z")
        assert existed is True
        assert old == "value"
        assert "z" not in store
        assert len(store) == 0

    def test_delete_existing_none_value(self):
        store = StateStore()
        store.set("z", None)
        existed, old = store.delete("z")
        assert existed is True
        assert old is None
        assert old is not _MISSING
        assert "z" not in store

    def test_delete_missing(self):
        store = StateStore()
        existed, old = store.delete("nowhere")
        assert existed is False
        assert old is _MISSING

    def test_setitem_and_delitem(self):
        store = StateStore()
        store["a"] = 1
        store["b"] = 2
        assert store["a"] == 1
        assert store["b"] == 2
        del store["a"]
        assert "a" not in store
        assert len(store) == 1

    def test_setitem_none_value(self):
        store = StateStore()
        store["a"] = None
        assert store["a"] is None
        assert "a" in store
        assert len(store) == 1

    def test_getitem_missing_raises(self):
        store = StateStore()
        with pytest.raises(KeyError):
            _ = store["missing"]

    def test_delitem_missing_raises(self):
        store = StateStore()
        with pytest.raises(KeyError):
            del store["missing"]

    def test_iteration(self):
        store = StateStore()
        store["a"] = 1
        store["b"] = None
        store["c"] = 3
        keys = list(iter(store))
        assert sorted(keys) == ["a", "b", "c"]

    def test_clear(self):
        store = StateStore()
        store["a"] = 1
        store["b"] = None
        store.clear()
        assert len(store) == 0
        assert list(store.keys()) == []


class TestStateStoreSnapshots:
    def test_snapshot_basic(self):
        store = StateStore()
        store["a"] = 1
        idx = store.snapshot()
        assert idx == 0
        assert store.snapshot_count == 1

    def test_multiple_snapshots(self):
        store = StateStore()
        store["a"] = 1
        idx0 = store.snapshot()
        store["b"] = 2
        idx1 = store.snapshot()
        store["c"] = None
        idx2 = store.snapshot()
        assert idx0 == 0
        assert idx1 == 1
        assert idx2 == 2
        assert store.snapshot_count == 3

    def test_restore_latest_snapshot(self):
        store = StateStore()
        store["a"] = 1
        store["b"] = None
        store.snapshot()
        store["a"] = 999
        store["c"] = 3
        store.restore_snapshot()
        assert store["a"] == 1
        assert store["b"] is None
        assert "c" not in store

    def test_restore_specific_snapshot(self):
        store = StateStore()
        store["a"] = 1
        store.snapshot()
        store["b"] = None
        store.snapshot()
        store["c"] = 3
        store.restore_snapshot(0)
        assert store["a"] == 1
        assert "b" not in store
        assert "c" not in store

    def test_restore_snapshot_with_none_values(self):
        store = StateStore()
        store.set("nullable", None)
        store.set("normal", "value")
        store.snapshot()
        store.set("nullable", "changed")
        store.set("normal", None)
        store.restore_snapshot()
        assert store["nullable"] is None
        assert store["normal"] == "value"

    def test_restore_no_snapshots_raises(self):
        store = StateStore()
        with pytest.raises(ValueError, match="No snapshots available"):
            store.restore_snapshot()

    def test_restore_out_of_range_raises(self):
        store = StateStore()
        store.snapshot()
        with pytest.raises(IndexError):
            store.restore_snapshot(5)
        with pytest.raises(IndexError):
            store.restore_snapshot(-1)

    def test_clear_snapshots(self):
        store = StateStore()
        store.snapshot()
        store.snapshot()
        assert store.snapshot_count == 2
        store.clear_snapshots()
        assert store.snapshot_count == 0
        with pytest.raises(ValueError):
            store.restore_snapshot()

    def test_snapshot_is_deep_copy(self):
        store = StateStore()
        store["data"] = {"nested": [1, 2, 3]}
        store.snapshot()
        store["data"]["nested"].append(4)
        store.restore_snapshot()
        assert store["data"]["nested"] == [1, 2, 3]


class TestStateStoreSerialization:
    def test_to_dict(self):
        store = StateStore()
        store["x"] = 1
        store["y"] = "hi"
        store["z"] = None
        d = store.to_dict()
        assert d == {"x": 1, "y": "hi", "z": None}
        d["x"] = 999
        assert store["x"] == 1

    def test_load_dict_with_none_values(self):
        store = StateStore()
        store["existing"] = "keep"
        data = {"a": 1, "b": {"c": 2}, "nullable": None}
        store.load_dict(data)
        assert "existing" not in store
        assert store["a"] == 1
        assert store["b"] == {"c": 2}
        assert store["nullable"] is None
        data["a"] = 999
        assert store["a"] == 1

    def test_equality_with_none_values(self):
        s1 = StateStore()
        s2 = StateStore()
        assert s1 == s2
        s1["a"] = None
        assert s1 != s2
        s2["a"] = None
        assert s1 == s2
        s2["a"] = 1
        assert s1 != s2

    def test_equality_not_implemented_for_other(self):
        store = StateStore()
        assert store.__eq__({"a": 1}) is NotImplemented

    def test_repr(self):
        store = StateStore()
        store["x"] = 5
        store["y"] = None
        r = repr(store)
        assert "StateStore" in r
        assert "'x'" in r
        assert "5" in r
        assert "'y'" in r
