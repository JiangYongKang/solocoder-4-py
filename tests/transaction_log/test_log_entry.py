import time

import pytest

from solocoder_4_py.transaction_log import LogEntry, OperationType, _MISSING


class TestOperationType:
    def test_operation_type_values(self):
        assert OperationType.BEGIN.value == "BEGIN"
        assert OperationType.COMMIT.value == "COMMIT"
        assert OperationType.ROLLBACK.value == "ROLLBACK"
        assert OperationType.SET.value == "SET"
        assert OperationType.DELETE.value == "DELETE"
        assert OperationType.CHECKPOINT.value == "CHECKPOINT"

    def test_operation_type_members(self):
        assert len(OperationType) == 6
        assert OperationType["BEGIN"] == OperationType.BEGIN


class TestMissingSentinel:
    def test_missing_is_unique_object(self):
        assert _MISSING is not None
        assert _MISSING is not False
        assert _MISSING is not 0
        assert _MISSING is not ""
        assert _MISSING is _MISSING

    def test_missing_identity(self):
        other = object()
        assert _MISSING is not other
        assert _MISSING is _MISSING


class TestLogEntry:
    def test_create_basic_entry(self):
        entry = LogEntry(operation=OperationType.SET, key="foo", value="bar")
        assert entry.operation == OperationType.SET
        assert entry.key == "foo"
        assert entry.value == "bar"
        assert entry.old_value is _MISSING
        assert entry.transaction_id is None
        assert isinstance(entry.log_id, str)
        assert len(entry.log_id) > 0
        assert isinstance(entry.timestamp, float)

    def test_create_full_entry(self):
        tx_id = "tx-123"
        entry = LogEntry(
            operation=OperationType.COMMIT,
            transaction_id=tx_id,
            key="k",
            value="v",
            old_value="old",
        )
        assert entry.operation == OperationType.COMMIT
        assert entry.transaction_id == tx_id
        assert entry.key == "k"
        assert entry.value == "v"
        assert entry.old_value == "old"

    def test_create_entry_with_none_value(self):
        entry = LogEntry(operation=OperationType.SET, key="nullable", value=None)
        assert entry.value is None
        assert entry.old_value is _MISSING

    def test_create_entry_with_none_old_value(self):
        entry = LogEntry(operation=OperationType.SET, key="k", value="new", old_value=None)
        assert entry.value == "new"
        assert entry.old_value is None
        assert entry.old_value is not _MISSING

    def test_log_entry_is_frozen(self):
        entry = LogEntry(operation=OperationType.SET, key="a", value=1)
        with pytest.raises(AttributeError):
            entry.key = "b"

    def test_is_transaction_boundary(self):
        assert LogEntry(operation=OperationType.BEGIN).is_transaction_boundary()
        assert LogEntry(operation=OperationType.COMMIT).is_transaction_boundary()
        assert LogEntry(operation=OperationType.ROLLBACK).is_transaction_boundary()
        assert LogEntry(operation=OperationType.CHECKPOINT).is_transaction_boundary()
        assert not LogEntry(operation=OperationType.SET).is_transaction_boundary()
        assert not LogEntry(operation=OperationType.DELETE).is_transaction_boundary()

    def test_is_data_operation(self):
        assert LogEntry(operation=OperationType.SET).is_data_operation()
        assert LogEntry(operation=OperationType.DELETE).is_data_operation()
        assert not LogEntry(operation=OperationType.BEGIN).is_data_operation()
        assert not LogEntry(operation=OperationType.COMMIT).is_data_operation()
        assert not LogEntry(operation=OperationType.ROLLBACK).is_data_operation()
        assert not LogEntry(operation=OperationType.CHECKPOINT).is_data_operation()

    def test_to_dict_with_missing_old_value(self):
        entry = LogEntry(
            operation=OperationType.SET,
            transaction_id="tx-1",
            key="name",
            value="Alice",
        )
        d = entry.to_dict()
        assert d["old_value"] is None
        assert d["old_value_is_missing"] is True

    def test_to_dict_with_none_old_value(self):
        entry = LogEntry(
            operation=OperationType.SET,
            key="nullable",
            value="new",
            old_value=None,
        )
        d = entry.to_dict()
        assert d["old_value"] is None
        assert d["old_value_is_missing"] is False

    def test_to_dict_and_from_dict_missing(self):
        original = LogEntry(
            operation=OperationType.SET,
            transaction_id="tx-1",
            key="name",
            value="Alice",
        )
        original_dict = original.to_dict()
        assert original_dict["operation"] == "SET"
        assert original_dict["transaction_id"] == "tx-1"
        assert original_dict["key"] == "name"
        assert original_dict["value"] == "Alice"
        assert original_dict["old_value_is_missing"] is True
        assert original_dict["log_id"] == original.log_id
        assert original_dict["timestamp"] == original.timestamp

        restored = LogEntry.from_dict(original_dict)
        assert restored.operation == original.operation
        assert restored.transaction_id == original.transaction_id
        assert restored.key == original.key
        assert restored.value == original.value
        assert restored.old_value is _MISSING
        assert restored.log_id == original.log_id
        assert restored.timestamp == original.timestamp

    def test_to_dict_and_from_dict_none_old_value(self):
        original = LogEntry(
            operation=OperationType.SET,
            key="nullable",
            value="new_val",
            old_value=None,
        )
        d = original.to_dict()
        assert d["old_value_is_missing"] is False

        restored = LogEntry.from_dict(d)
        assert restored.old_value is None
        assert restored.old_value is not _MISSING

    def test_to_dict_none_fields(self):
        entry = LogEntry(operation=OperationType.BEGIN)
        d = entry.to_dict()
        assert d["key"] is None
        assert d["value"] is None
        assert d["transaction_id"] is None

    def test_from_dict_with_defaults(self):
        d = {
            "log_id": "custom-id",
            "operation": "DELETE",
        }
        entry = LogEntry.from_dict(d)
        assert entry.log_id == "custom-id"
        assert entry.operation == OperationType.DELETE
        assert entry.timestamp == 0.0
        assert entry.old_value is _MISSING

    def test_unique_log_ids(self):
        entry1 = LogEntry(operation=OperationType.SET)
        entry2 = LogEntry(operation=OperationType.SET)
        assert entry1.log_id != entry2.log_id

    def test_timestamps_are_monotonic(self):
        entry1 = LogEntry(operation=OperationType.BEGIN)
        time.sleep(0.001)
        entry2 = LogEntry(operation=OperationType.BEGIN)
        assert entry2.timestamp >= entry1.timestamp

    def test_log_entry_equality(self):
        entry1 = LogEntry(operation=OperationType.SET, key="k", value="v")
        entry2 = LogEntry(operation=OperationType.SET, key="k", value="v")
        assert entry1 != entry2

    def test_log_entry_repr(self):
        entry = LogEntry(operation=OperationType.SET, key="k", value=42)
        r = repr(entry)
        assert "OperationType.SET" in r
        assert "key='k'" in r
        assert "value=42" in r

    def test_log_entry_no_lsn_attribute(self):
        entry = LogEntry(operation=OperationType.SET)
        assert not hasattr(entry, "lsn")
