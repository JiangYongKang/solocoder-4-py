import pytest

from solocoder_4_py.transaction_log import (
    LogEntry,
    OperationType,
    StateStore,
    TransactionLogManager,
    _MISSING,
)


class TestTransactionLogManagerBasic:
    def test_initial_state(self):
        mgr = TransactionLogManager()
        assert mgr.log_length == 0
        assert mgr.checkpoint_lsn == -1
        assert mgr.next_lsn == 0
        assert len(mgr.state) == 0

    def test_set_without_transaction(self):
        mgr = TransactionLogManager()
        old = mgr.set("name", "Alice")
        assert old is _MISSING
        assert mgr.state["name"] == "Alice"
        assert mgr.log_length == 1
        entry = mgr.get_log_entry(0)
        assert entry is not None
        assert entry.operation == OperationType.SET
        assert entry.key == "name"
        assert entry.value == "Alice"

    def test_set_none_value_without_transaction(self):
        mgr = TransactionLogManager()
        old = mgr.set("nullable", None)
        assert old is _MISSING
        assert mgr.state["nullable"] is None
        assert "nullable" in mgr.state
        entry = mgr.get_log_entry(0)
        assert entry.operation == OperationType.SET
        assert entry.value is None
        assert entry.old_value is _MISSING

    def test_set_overwrite_with_none(self):
        mgr = TransactionLogManager()
        mgr.set("a", 1)
        old = mgr.set("a", None)
        assert old == 1
        assert mgr.state["a"] is None

    def test_set_overwrite_from_none(self):
        mgr = TransactionLogManager()
        mgr.set("a", None)
        old = mgr.set("a", 2)
        assert old is None
        assert old is not _MISSING
        assert mgr.state["a"] == 2

    def test_set_overwrite(self):
        mgr = TransactionLogManager()
        mgr.set("a", 1)
        old = mgr.set("a", 2)
        assert old == 1
        assert mgr.state["a"] == 2
        assert mgr.log_length == 2
        entry1 = mgr.get_log_entry(1)
        assert entry1.old_value == 1

    def test_delete_without_transaction(self):
        mgr = TransactionLogManager()
        mgr.set("x", "to_delete")
        existed, old = mgr.delete("x")
        assert existed is True
        assert old == "to_delete"
        assert "x" not in mgr.state
        entry = mgr.get_log_entry(1)
        assert entry.operation == OperationType.DELETE
        assert entry.key == "x"
        assert entry.old_value == "to_delete"

    def test_delete_none_value(self):
        mgr = TransactionLogManager()
        mgr.set("x", None)
        existed, old = mgr.delete("x")
        assert existed is True
        assert old is None
        assert old is not _MISSING
        assert "x" not in mgr.state

    def test_delete_missing(self):
        mgr = TransactionLogManager()
        existed, old = mgr.delete("missing")
        assert existed is False
        assert old is _MISSING
        assert mgr.log_length == 1
        entry = mgr.get_log_entry(0)
        assert entry.operation == OperationType.DELETE
        assert entry.old_value is _MISSING

    def test_get_log_entry_out_of_range(self):
        mgr = TransactionLogManager()
        assert mgr.get_log_entry(0) is None
        assert mgr.get_log_entry(-1) is None
        mgr.set("a", 1)
        assert mgr.get_log_entry(1) is None

    def test_get_log_entries(self):
        mgr = TransactionLogManager()
        mgr.set("a", 1)
        mgr.set("b", 2)
        mgr.set("c", 3)
        all_entries = mgr.get_log_entries()
        assert len(all_entries) == 3
        slice_entries = mgr.get_log_entries(start_lsn=1, end_lsn=3)
        assert len(slice_entries) == 2
        assert slice_entries[0].key == "b"
        assert slice_entries[1].key == "c"

    def test_next_lsn_matches_length(self):
        mgr = TransactionLogManager()
        assert mgr.next_lsn == 0
        mgr.set("a", 1)
        assert mgr.next_lsn == 1
        mgr.set("b", 2)
        assert mgr.next_lsn == 2

    def test_log_entries_have_no_lsn_attribute(self):
        mgr = TransactionLogManager()
        mgr.set("a", 1)
        entry = mgr.get_log_entry(0)
        assert not hasattr(entry, "lsn")

    def test_reset(self):
        mgr = TransactionLogManager()
        mgr.set("a", 1)
        mgr.set("b", 2)
        mgr.begin_transaction()
        mgr.reset()
        assert mgr.log_length == 0
        assert mgr.checkpoint_lsn == -1
        assert mgr.next_lsn == 0
        assert len(mgr.state) == 0


class TestTransactions:
    def test_begin_transaction(self):
        mgr = TransactionLogManager()
        tx_id = mgr.begin_transaction()
        assert isinstance(tx_id, str) and len(tx_id) > 0
        assert mgr.log_length == 1
        entry = mgr.get_log_entry(0)
        assert entry.operation == OperationType.BEGIN
        assert entry.transaction_id == tx_id

    def test_transaction_set_and_commit(self):
        mgr = TransactionLogManager()
        tx_id = mgr.begin_transaction()
        mgr.set("balance", 100, transaction_id=tx_id)
        mgr.set("currency", "USD", transaction_id=tx_id)
        mgr.commit(tx_id)
        assert mgr.state["balance"] == 100
        assert mgr.state["currency"] == "USD"
        assert mgr.log_length == 4
        assert mgr.get_log_entry(3).operation == OperationType.COMMIT

    def test_transaction_set_none_and_commit(self):
        mgr = TransactionLogManager()
        mgr.set("a", 1)
        tx_id = mgr.begin_transaction()
        mgr.set("a", None, transaction_id=tx_id)
        mgr.commit(tx_id)
        assert mgr.state["a"] is None

    def test_transaction_set_new_none_and_rollback(self):
        mgr = TransactionLogManager()
        tx_id = mgr.begin_transaction()
        mgr.set("new_key", None, transaction_id=tx_id)
        assert mgr.state["new_key"] is None
        mgr.rollback(tx_id)
        assert "new_key" not in mgr.state

    def test_transaction_set_overwrite_none_and_rollback(self):
        mgr = TransactionLogManager()
        mgr.set("a", None)
        tx_id = mgr.begin_transaction()
        mgr.set("a", 100, transaction_id=tx_id)
        mgr.rollback(tx_id)
        assert mgr.state["a"] is None
        assert "a" in mgr.state

    def test_transaction_set_overwrite_to_none_and_rollback(self):
        mgr = TransactionLogManager()
        mgr.set("a", 100)
        tx_id = mgr.begin_transaction()
        mgr.set("a", None, transaction_id=tx_id)
        assert mgr.state["a"] is None
        mgr.rollback(tx_id)
        assert mgr.state["a"] == 100

    def test_transaction_rollback(self):
        mgr = TransactionLogManager()
        mgr.set("balance", 50)
        tx_id = mgr.begin_transaction()
        mgr.set("balance", 1000, transaction_id=tx_id)
        mgr.rollback(tx_id)
        assert mgr.state["balance"] == 50
        rollback_entry = mgr.get_log_entry(3)
        assert rollback_entry.operation == OperationType.ROLLBACK
        assert rollback_entry.transaction_id == tx_id

    def test_transaction_rollback_delete(self):
        mgr = TransactionLogManager()
        mgr.set("data", "important")
        tx_id = mgr.begin_transaction()
        mgr.delete("data", transaction_id=tx_id)
        assert "data" not in mgr.state
        mgr.rollback(tx_id)
        assert mgr.state["data"] == "important"

    def test_transaction_rollback_delete_none_value(self):
        mgr = TransactionLogManager()
        mgr.set("data", None)
        tx_id = mgr.begin_transaction()
        mgr.delete("data", transaction_id=tx_id)
        assert "data" not in mgr.state
        mgr.rollback(tx_id)
        assert "data" in mgr.state
        assert mgr.state["data"] is None

    def test_transaction_rollback_set_then_delete(self):
        mgr = TransactionLogManager()
        mgr.set("x", 1)
        tx_id = mgr.begin_transaction()
        mgr.set("x", 2, transaction_id=tx_id)
        mgr.delete("x", transaction_id=tx_id)
        mgr.rollback(tx_id)
        assert mgr.state["x"] == 1

    def test_transaction_rollback_new_key(self):
        mgr = TransactionLogManager()
        tx_id = mgr.begin_transaction()
        mgr.set("new_key", "value", transaction_id=tx_id)
        mgr.rollback(tx_id)
        assert "new_key" not in mgr.state

    def test_commit_unknown_transaction_raises(self):
        mgr = TransactionLogManager()
        with pytest.raises(ValueError, match="Unknown transaction"):
            mgr.commit("no-such-tx")

    def test_rollback_unknown_transaction_raises(self):
        mgr = TransactionLogManager()
        with pytest.raises(ValueError, match="Unknown transaction"):
            mgr.rollback("no-such-tx")

    def test_operation_unknown_transaction_raises(self):
        mgr = TransactionLogManager()
        with pytest.raises(ValueError):
            mgr.set("k", "v", transaction_id="fake")
        with pytest.raises(ValueError):
            mgr.delete("k", transaction_id="fake")

    def test_multiple_concurrent_transactions(self):
        mgr = TransactionLogManager()
        tx1 = mgr.begin_transaction()
        tx2 = mgr.begin_transaction()
        mgr.set("a", 1, transaction_id=tx1)
        mgr.set("b", 2, transaction_id=tx2)
        mgr.commit(tx1)
        mgr.rollback(tx2)
        assert mgr.state["a"] == 1
        assert "b" not in mgr.state

    def test_transaction_ordering(self):
        mgr = TransactionLogManager()
        mgr.set("counter", 0)
        tx1 = mgr.begin_transaction()
        mgr.set("counter", 1, transaction_id=tx1)
        tx2 = mgr.begin_transaction()
        mgr.set("counter", 100, transaction_id=tx2)
        mgr.commit(tx1)
        assert mgr.state["counter"] == 100
        mgr.rollback(tx2)
        assert mgr.state["counter"] == 1

    def test_transaction_with_multiple_none_operations(self):
        mgr = TransactionLogManager()
        mgr.set("x", "original")
        tx_id = mgr.begin_transaction()
        mgr.set("a", None, transaction_id=tx_id)
        mgr.set("x", None, transaction_id=tx_id)
        mgr.set("b", None, transaction_id=tx_id)
        mgr.commit(tx_id)
        assert mgr.state["a"] is None
        assert mgr.state["x"] is None
        assert mgr.state["b"] is None


class TestCheckpoint:
    def test_checkpoint_creates_entry(self):
        mgr = TransactionLogManager()
        mgr.set("a", 1)
        mgr.set("b", 2)
        cp_lsn = mgr.checkpoint()
        assert cp_lsn == 0
        entries = mgr.get_log_entries()
        checkpoint_entries = [e for e in entries if e.operation == OperationType.CHECKPOINT]
        assert len(checkpoint_entries) == 1

    def test_checkpoint_truncates_log(self):
        mgr = TransactionLogManager()
        for i in range(10):
            mgr.set(f"k{i}", i)
        log_before = mgr.log_length
        mgr.checkpoint()
        assert mgr.log_length <= log_before
        assert mgr.log_length == 1

    def test_checkpoint_rolls_back_active_transactions(self):
        mgr = TransactionLogManager()
        mgr.set("persistent", "value")
        tx_id = mgr.begin_transaction()
        mgr.set("temp", "data", transaction_id=tx_id)
        mgr.checkpoint()
        assert mgr.state["persistent"] == "value"
        assert "temp" not in mgr.state

    def test_checkpoint_state_preserved(self):
        mgr = TransactionLogManager()
        mgr.set("x", 100)
        mgr.set("y", 200)
        mgr.checkpoint()
        assert mgr.checkpoint_lsn >= 0
        mgr.set("x", 999)
        mgr.set("z", 300)
        assert mgr.checkpoint_lsn == 0

    def test_checkpoint_preserves_none_values(self):
        mgr = TransactionLogManager()
        mgr.set("nullable", None)
        mgr.set("normal", 42)
        mgr.checkpoint()
        assert mgr.state["nullable"] is None
        assert mgr.state["normal"] == 42

    def test_multiple_checkpoints(self):
        mgr = TransactionLogManager()
        mgr.set("a", 1)
        cp1 = mgr.checkpoint()
        mgr.set("b", 2)
        cp2 = mgr.checkpoint()
        assert cp2 == 0
        assert mgr.state["a"] == 1
        assert mgr.state["b"] == 2
        entries = mgr.get_log_entries()
        cps = [e for e in entries if e.operation == OperationType.CHECKPOINT]
        assert len(cps) == 1

    def test_checkpoint_lsn_updated(self):
        mgr = TransactionLogManager()
        assert mgr.checkpoint_lsn == -1
        mgr.set("a", 1)
        mgr.checkpoint()
        assert mgr.checkpoint_lsn == 0


class TestCrashRecovery:
    def test_recover_empty(self):
        mgr = TransactionLogManager()
        recovered, redo, undo = mgr.simulate_crash_and_recover()
        assert len(recovered) == 0
        assert redo == 0
        assert undo == 0

    def test_recover_without_checkpoint(self):
        mgr = TransactionLogManager()
        mgr.set("a", 1)
        mgr.set("b", 2)
        mgr.delete("a")
        recovered, redo, undo = mgr.simulate_crash_and_recover()
        assert "a" not in recovered
        assert recovered["b"] == 2
        assert redo == 3
        assert undo == 0

    def test_recover_with_checkpoint(self):
        mgr = TransactionLogManager()
        mgr.set("base1", "v1")
        mgr.set("base2", "v2")
        mgr.checkpoint()
        mgr.set("after1", "a1")
        mgr.set("after2", "a2")
        recovered, redo, undo = mgr.simulate_crash_and_recover()
        assert recovered["base1"] == "v1"
        assert recovered["base2"] == "v2"
        assert recovered["after1"] == "a1"
        assert recovered["after2"] == "a2"
        assert redo == 2
        assert undo == 0

    def test_recover_none_value_without_checkpoint(self):
        mgr = TransactionLogManager()
        mgr.set("nullable", None)
        mgr.set("normal", "value")
        recovered, redo, undo = mgr.simulate_crash_and_recover()
        assert recovered["nullable"] is None
        assert recovered["normal"] == "value"
        assert redo == 2
        assert undo == 0

    def test_recover_none_value_with_checkpoint(self):
        mgr = TransactionLogManager()
        mgr.set("cp_null", None)
        mgr.set("cp_normal", 100)
        mgr.checkpoint()
        mgr.set("after_null", None)
        mgr.set("after_normal", 200)
        recovered, redo, undo = mgr.simulate_crash_and_recover()
        assert recovered["cp_null"] is None
        assert recovered["cp_normal"] == 100
        assert recovered["after_null"] is None
        assert recovered["after_normal"] == 200
        assert redo == 2
        assert undo == 0

    def test_recover_committed_transaction(self):
        mgr = TransactionLogManager()
        mgr.set("x", 0)
        tx_id = mgr.begin_transaction()
        mgr.set("x", 42, transaction_id=tx_id)
        mgr.commit(tx_id)
        recovered, redo, undo = mgr.simulate_crash_and_recover()
        assert recovered["x"] == 42
        assert redo == 2
        assert undo == 0

    def test_recover_committed_none_value(self):
        mgr = TransactionLogManager()
        mgr.set("x", 0)
        tx_id = mgr.begin_transaction()
        mgr.set("x", None, transaction_id=tx_id)
        mgr.commit(tx_id)
        recovered, redo, undo = mgr.simulate_crash_and_recover()
        assert recovered["x"] is None
        assert redo == 2
        assert undo == 0

    def test_recover_uncommitted_transaction_is_undone(self):
        mgr = TransactionLogManager()
        mgr.set("x", 0)
        tx_id = mgr.begin_transaction()
        mgr.set("x", 999, transaction_id=tx_id)
        recovered, redo, undo = mgr.simulate_crash_and_recover()
        assert recovered["x"] == 0
        assert redo == 1
        assert undo == 1

    def test_recover_uncommitted_none_value(self):
        mgr = TransactionLogManager()
        mgr.set("x", 0)
        tx_id = mgr.begin_transaction()
        mgr.set("x", None, transaction_id=tx_id)
        recovered, redo, undo = mgr.simulate_crash_and_recover()
        assert recovered["x"] == 0
        assert "x" in recovered
        assert redo == 1
        assert undo == 1

    def test_recover_uncommitted_new_none_value(self):
        mgr = TransactionLogManager()
        tx_id = mgr.begin_transaction()
        mgr.set("new_key", None, transaction_id=tx_id)
        recovered, redo, undo = mgr.simulate_crash_and_recover()
        assert "new_key" not in recovered
        assert redo == 0
        assert undo == 1

    def test_recover_uncommitted_overwrite_from_none(self):
        mgr = TransactionLogManager()
        mgr.set("x", None)
        tx_id = mgr.begin_transaction()
        mgr.set("x", 999, transaction_id=tx_id)
        recovered, redo, undo = mgr.simulate_crash_and_recover()
        assert recovered["x"] is None
        assert "x" in recovered
        assert redo == 1
        assert undo == 1

    def test_recover_rolled_back_transaction(self):
        mgr = TransactionLogManager()
        mgr.set("x", 0)
        tx_id = mgr.begin_transaction()
        mgr.set("x", 500, transaction_id=tx_id)
        mgr.rollback(tx_id)
        recovered, redo, undo = mgr.simulate_crash_and_recover()
        assert recovered["x"] == 0
        assert redo == 1
        assert undo == 0

    def test_recover_rolled_back_none_value(self):
        mgr = TransactionLogManager()
        mgr.set("x", 0)
        tx_id = mgr.begin_transaction()
        mgr.set("x", None, transaction_id=tx_id)
        mgr.rollback(tx_id)
        recovered, redo, undo = mgr.simulate_crash_and_recover()
        assert recovered["x"] == 0
        assert redo == 1
        assert undo == 0

    def test_recover_with_checkpoint_and_transactions(self):
        mgr = TransactionLogManager()
        mgr.set("checkpointed", "yes")
        mgr.set("cp_null", None)
        mgr.checkpoint()
        tx1 = mgr.begin_transaction()
        mgr.set("committed_later", "true", transaction_id=tx1)
        mgr.set("committed_null", None, transaction_id=tx1)
        mgr.commit(tx1)
        tx2 = mgr.begin_transaction()
        mgr.set("never_committed", "oops", transaction_id=tx2)
        mgr.set("never_committed_null", None, transaction_id=tx2)
        recovered, redo, undo = mgr.simulate_crash_and_recover()
        assert recovered["checkpointed"] == "yes"
        assert recovered["cp_null"] is None
        assert recovered["committed_later"] == "true"
        assert recovered["committed_null"] is None
        assert "never_committed" not in recovered
        assert "never_committed_null" not in recovered
        assert redo == 2
        assert undo == 2

    def test_recover_mixed_operations(self):
        mgr = TransactionLogManager()
        mgr.set("a", 1)
        tx = mgr.begin_transaction()
        mgr.set("b", 2, transaction_id=tx)
        mgr.set("a", 10, transaction_id=tx)
        mgr.commit(tx)
        mgr.delete("a")
        recovered, redo, undo = mgr.simulate_crash_and_recover()
        assert "a" not in recovered
        assert recovered["b"] == 2
        assert redo == 4
        assert undo == 0

    def test_recover_uncommitted_delete(self):
        mgr = TransactionLogManager()
        mgr.set("saved", "data")
        tx = mgr.begin_transaction()
        mgr.delete("saved", transaction_id=tx)
        recovered, redo, undo = mgr.simulate_crash_and_recover()
        assert recovered["saved"] == "data"
        assert undo == 1

    def test_recover_uncommitted_delete_none_value(self):
        mgr = TransactionLogManager()
        mgr.set("saved", None)
        tx = mgr.begin_transaction()
        mgr.delete("saved", transaction_id=tx)
        recovered, redo, undo = mgr.simulate_crash_and_recover()
        assert "saved" in recovered
        assert recovered["saved"] is None
        assert undo == 1

    def test_recover_does_not_affect_original(self):
        mgr = TransactionLogManager()
        mgr.set("orig", 1)
        recovered, _, _ = mgr.simulate_crash_and_recover()
        recovered["orig"] = 999
        recovered["new"] = "x"
        assert mgr.state["orig"] == 1
        assert "new" not in mgr.state

    def test_recover_complex_none_scenario(self):
        mgr = TransactionLogManager()
        mgr.set("config:version", "1.0")
        mgr.set("config:debug", None)
        mgr.checkpoint()
        tx = mgr.begin_transaction()
        mgr.set("config:version", "2.0", transaction_id=tx)
        mgr.set("config:debug", True, transaction_id=tx)
        mgr.set("config:new_feature", None, transaction_id=tx)
        mgr.commit(tx)
        tx2 = mgr.begin_transaction()
        mgr.set("config:version", "3.0-beta", transaction_id=tx2)
        mgr.delete("config:debug", transaction_id=tx2)
        recovered, redo, undo = mgr.simulate_crash_and_recover()
        assert recovered["config:version"] == "2.0"
        assert recovered["config:debug"] is True
        assert recovered["config:new_feature"] is None
        assert redo == 3
        assert undo == 2


class TestTruncate:
    def test_truncate_zero(self):
        mgr = TransactionLogManager()
        mgr.set("a", 1)
        removed = mgr.truncate_log_before(0)
        assert removed == 0
        assert mgr.log_length == 1

    def test_truncate_all(self):
        mgr = TransactionLogManager()
        mgr.set("a", 1)
        mgr.set("b", 2)
        mgr.set("c", 3)
        removed = mgr.truncate_log_before(3)
        assert removed == 3
        assert mgr.log_length == 0
        assert mgr.next_lsn == 0

    def test_truncate_partial(self):
        mgr = TransactionLogManager()
        for i in range(5):
            mgr.set(f"k{i}", i)
        removed = mgr.truncate_log_before(2)
        assert removed == 2
        assert mgr.log_length == 3
        entry0 = mgr.get_log_entry(0)
        assert entry0.key == "k2"

    def test_truncate_beyond_length(self):
        mgr = TransactionLogManager()
        mgr.set("a", 1)
        removed = mgr.truncate_log_before(100)
        assert removed == 1
        assert mgr.log_length == 0


class TestComprehensiveScenarios:
    def test_banking_scenario(self):
        mgr = TransactionLogManager()
        mgr.set("alice_balance", 1000)
        mgr.set("bob_balance", 1000)
        mgr.checkpoint()
        transfer_amount = 200
        tx = mgr.begin_transaction()
        alice_before = mgr.state["alice_balance"]
        mgr.set("alice_balance", alice_before - transfer_amount, transaction_id=tx)
        bob_before = mgr.state["bob_balance"]
        mgr.set("bob_balance", bob_before + transfer_amount, transaction_id=tx)
        mgr.commit(tx)
        assert mgr.state["alice_balance"] == 800
        assert mgr.state["bob_balance"] == 1200
        recovered, redo, undo = mgr.simulate_crash_and_recover()
        assert recovered["alice_balance"] == 800
        assert recovered["bob_balance"] == 1200
        assert redo == 2
        assert undo == 0

    def test_session_scenario_with_rollback(self):
        mgr = TransactionLogManager()
        mgr.set("user_count", 0)
        mgr.checkpoint()
        session_tx = mgr.begin_transaction()
        mgr.set("user_count", 1, transaction_id=session_tx)
        mgr.set("session_id", "abc123", transaction_id=session_tx)
        mgr.set("last_login", None, transaction_id=session_tx)
        mgr.rollback(session_tx)
        assert mgr.state["user_count"] == 0
        assert "session_id" not in mgr.state
        assert "last_login" not in mgr.state
        recovered, redo, undo = mgr.simulate_crash_and_recover()
        assert recovered["user_count"] == 0
        assert "session_id" not in recovered
        assert redo == 0
        assert undo == 0

    def test_ecommerce_inventory_scenario(self):
        mgr = TransactionLogManager()
        mgr.set("inventory:sku-001", 100)
        mgr.set("inventory:sku-002", 50)
        mgr.set("product:sku-003:description", None)
        mgr.checkpoint()
        order_tx = mgr.begin_transaction()
        mgr.set("inventory:sku-001", 95, transaction_id=order_tx)
        mgr.set("inventory:sku-002", 48, transaction_id=order_tx)
        mgr.set("order:ORD-001", {"items": ["sku-001", "sku-002"], "total": 5}, transaction_id=order_tx)
        mgr.commit(order_tx)
        mgr.checkpoint()
        assert mgr.state["inventory:sku-001"] == 95
        assert mgr.state["inventory:sku-002"] == 48
        assert "order:ORD-001" in mgr.state
        assert mgr.state["product:sku-003:description"] is None
        recovered, redo, undo = mgr.simulate_crash_and_recover()
        assert recovered["inventory:sku-001"] == 95
        assert recovered["order:ORD-001"]["total"] == 5
        assert recovered["product:sku-003:description"] is None
        assert redo == 0
        assert undo == 0

    def test_incomplete_transaction_during_checkpoint_and_recovery(self):
        mgr = TransactionLogManager()
        mgr.set("config:version", "1.0")
        mgr.set("config:beta_features", None)
        mgr.checkpoint()
        mgr.set("config:debug", "true")
        deploy_tx = mgr.begin_transaction()
        mgr.set("config:version", "2.0-beta", transaction_id=deploy_tx)
        mgr.set("config:features", "v2-only", transaction_id=deploy_tx)
        mgr.set("config:beta_features", True, transaction_id=deploy_tx)
        recovered, redo, undo = mgr.simulate_crash_and_recover()
        assert recovered["config:version"] == "1.0"
        assert recovered["config:debug"] == "true"
        assert recovered["config:beta_features"] is None
        assert "config:features" not in recovered
        assert redo == 1
        assert undo == 3

    def test_crash_recovery_with_mixed_none_and_transactions_precise_counts(self):
        mgr = TransactionLogManager()
        mgr.set("base:v1", 100)
        mgr.set("base:v2", None)
        cp_lsn = mgr.checkpoint()
        assert cp_lsn == 0
        assert mgr.checkpoint_lsn == 0

        mgr.set("direct:v1", 200)
        mgr.set("direct:v2", None)

        tx1 = mgr.begin_transaction()
        mgr.set("tx1:set1", "a", transaction_id=tx1)
        mgr.set("tx1:set2", None, transaction_id=tx1)
        mgr.delete("base:v1", transaction_id=tx1)
        mgr.commit(tx1)

        tx2 = mgr.begin_transaction()
        mgr.set("tx2:set1", "b", transaction_id=tx2)
        mgr.set("base:v2", "not-none-anymore", transaction_id=tx2)

        mgr.set("direct:v3", 300)

        recovered, redo, undo = mgr.simulate_crash_and_recover()

        assert "base:v1" not in recovered
        assert recovered["base:v2"] is None
        assert recovered["direct:v1"] == 200
        assert recovered["direct:v2"] is None
        assert recovered["direct:v3"] == 300
        assert recovered["tx1:set1"] == "a"
        assert recovered["tx1:set2"] is None
        assert "tx2:set1" not in recovered

        assert redo == 6
        assert undo == 2
