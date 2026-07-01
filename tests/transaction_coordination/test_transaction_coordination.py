from typing import Dict, List

import pytest

from solocoder_4_py.transaction_coordination import (
    CommitFailedError,
    ParticipantAlreadyRegisteredError,
    ParticipantState,
    PrepareFailedError,
    TERMINAL_PARTICIPANT_STATES,
    TERMINAL_TRANSACTION_STATES,
    TimeoutDecisionAbortedError,
    TransactionCoordinator,
    TransactionError,
    TransactionNotFoundError,
    TransactionParticipant,
    TransactionState,
    TransactionStateError,
)


class FakeClock:
    """可控的时钟，用于测试超时"""

    def __init__(self, start: float = 0.0) -> None:
        self._now = start

    def __call__(self) -> float:
        return self._now

    def advance(self, delta: float) -> None:
        self._now += delta


class CallTracker:
    """用于追踪回调被调用的次数，验证幂等性"""

    def __init__(self) -> None:
        self.prepare_calls: Dict[str, int] = {}
        self.commit_calls: Dict[str, int] = {}
        self.abort_calls: Dict[str, int] = {}
        self.commit_payloads: Dict[str, List[str]] = {}
        self.abort_payloads: Dict[str, List[str]] = {}

    def prepare(self, tx_id: str) -> bool:
        self.prepare_calls[tx_id] = self.prepare_calls.get(tx_id, 0) + 1
        return True

    def commit(self, tx_id: str) -> None:
        self.commit_calls[tx_id] = self.commit_calls.get(tx_id, 0) + 1
        self.commit_payloads.setdefault(tx_id, []).append(f"commit-{tx_id}")

    def abort(self, tx_id: str) -> None:
        self.abort_calls[tx_id] = self.abort_calls.get(tx_id, 0) + 1
        self.abort_payloads.setdefault(tx_id, []).append(f"abort-{tx_id}")


# ---------------------------------------------------------------------------
# Constants & enums
# ---------------------------------------------------------------------------
class TestConstants:
    def test_transaction_state_values(self) -> None:
        assert TransactionState.INIT.value == "INIT"
        assert TransactionState.PREPARING.value == "PREPARING"
        assert TransactionState.PREPARED.value == "PREPARED"
        assert TransactionState.COMMITTING.value == "COMMITTING"
        assert TransactionState.COMMITTED.value == "COMMITTED"
        assert TransactionState.ABORTING.value == "ABORTING"
        assert TransactionState.ABORTED.value == "ABORTED"
        assert TransactionState.TIMEOUT_ABORTED.value == "TIMEOUT_ABORTED"

    def test_participant_state_values(self) -> None:
        assert ParticipantState.INIT.value == "INIT"
        assert ParticipantState.PREPARING.value == "PREPARING"
        assert ParticipantState.PREPARED.value == "PREPARED"
        assert ParticipantState.COMMITTING.value == "COMMITTING"
        assert ParticipantState.COMMITTED.value == "COMMITTED"
        assert ParticipantState.ABORTING.value == "ABORTING"
        assert ParticipantState.ABORTED.value == "ABORTED"
        assert ParticipantState.PREPARE_FAILED.value == "PREPARE_FAILED"
        assert ParticipantState.COMMIT_FAILED.value == "COMMIT_FAILED"

    def test_terminal_sets(self) -> None:
        assert TransactionState.COMMITTED in TERMINAL_TRANSACTION_STATES
        assert TransactionState.ABORTED in TERMINAL_TRANSACTION_STATES
        assert TransactionState.TIMEOUT_ABORTED in TERMINAL_TRANSACTION_STATES
        assert TransactionState.PREPARED not in TERMINAL_TRANSACTION_STATES

        assert ParticipantState.COMMITTED in TERMINAL_PARTICIPANT_STATES
        assert ParticipantState.ABORTED in TERMINAL_PARTICIPANT_STATES
        assert ParticipantState.PREPARE_FAILED in TERMINAL_PARTICIPANT_STATES


# ---------------------------------------------------------------------------
# TransactionParticipant
# ---------------------------------------------------------------------------
class TestTransactionParticipant:
    def test_prepare_success_default_callback(self) -> None:
        p = TransactionParticipant("p1")
        tx_id = "tx-1"
        assert p.prepare(tx_id) is True
        assert p.get_state(tx_id) == ParticipantState.PREPARED

    def test_prepare_with_callback(self) -> None:
        tracker = CallTracker()
        p = TransactionParticipant("p1")
        p.set_callbacks(on_prepare=tracker.prepare)
        tx_id = "tx-1"
        assert p.prepare(tx_id) is True
        assert tracker.prepare_calls[tx_id] == 1

    def test_prepare_rejected(self) -> None:
        p = TransactionParticipant("p1")
        p.set_callbacks(on_prepare=lambda tx: False)
        with pytest.raises(PrepareFailedError):
            p.prepare("tx-1")
        assert p.get_state("tx-1") == ParticipantState.PREPARE_FAILED

    def test_prepare_callback_raises(self) -> None:
        p = TransactionParticipant("p1")
        p.set_callbacks(on_prepare=lambda tx: (_ for _ in ()).throw(RuntimeError("boom")))
        with pytest.raises(PrepareFailedError) as excinfo:
            p.prepare("tx-1")
        assert "boom" in str(excinfo.value)
        assert p.get_state("tx-1") == ParticipantState.PREPARE_FAILED

    def test_prepare_idempotent_success(self) -> None:
        tracker = CallTracker()
        p = TransactionParticipant("p1")
        p.set_callbacks(on_prepare=tracker.prepare)
        tx_id = "tx-1"
        assert p.prepare(tx_id) is True
        assert p.prepare(tx_id) is True
        assert p.prepare(tx_id) is True
        # 回调应只调用一次
        assert tracker.prepare_calls[tx_id] == 1
        assert p.get_call_count(tx_id)["prepare"] == 3

    def test_prepare_idempotent_failed(self) -> None:
        p = TransactionParticipant("p1")
        p.set_callbacks(on_prepare=lambda tx: False)
        with pytest.raises(PrepareFailedError):
            p.prepare("tx-1")
        with pytest.raises(PrepareFailedError):
            p.prepare("tx-1")

    def test_commit_without_prepare_is_error(self) -> None:
        p = TransactionParticipant("p1")
        with pytest.raises(TransactionStateError):
            p.commit("tx-1")

    def test_commit_success(self) -> None:
        tracker = CallTracker()
        p = TransactionParticipant("p1")
        p.set_callbacks(on_prepare=tracker.prepare, on_commit=tracker.commit)
        tx_id = "tx-1"
        p.prepare(tx_id)
        p.commit(tx_id)
        assert p.get_state(tx_id) == ParticipantState.COMMITTED
        assert tracker.commit_calls[tx_id] == 1

    def test_commit_idempotent(self) -> None:
        tracker = CallTracker()
        p = TransactionParticipant("p1")
        p.set_callbacks(on_prepare=tracker.prepare, on_commit=tracker.commit)
        tx_id = "tx-1"
        p.prepare(tx_id)
        p.commit(tx_id)
        p.commit(tx_id)
        p.commit(tx_id)
        assert p.get_state(tx_id) == ParticipantState.COMMITTED
        # 业务回调只执行一次，无重复副作用
        assert tracker.commit_calls[tx_id] == 1
        # commit 调用计数递增但业务副作用稳定
        assert p.get_call_count(tx_id)["commit"] == 3
        assert tracker.commit_payloads[tx_id] == [f"commit-{tx_id}"]

    def test_commit_callback_raises(self) -> None:
        p = TransactionParticipant("p1")
        p.set_callbacks(
            on_prepare=lambda tx: True,
            on_commit=lambda tx: (_ for _ in ()).throw(RuntimeError("db crash")),
        )
        tx_id = "tx-1"
        p.prepare(tx_id)
        with pytest.raises(CommitFailedError) as excinfo:
            p.commit(tx_id)
        assert "db crash" in str(excinfo.value)

    def test_abort_after_init(self) -> None:
        tracker = CallTracker()
        p = TransactionParticipant("p1")
        p.set_callbacks(on_abort=tracker.abort)
        tx_id = "tx-1"
        p.abort(tx_id)
        assert p.get_state(tx_id) == ParticipantState.ABORTED
        assert tracker.abort_calls[tx_id] == 1

    def test_abort_after_prepare(self) -> None:
        tracker = CallTracker()
        p = TransactionParticipant("p1")
        p.set_callbacks(
            on_prepare=tracker.prepare,
            on_commit=tracker.commit,
            on_abort=tracker.abort,
        )
        tx_id = "tx-1"
        p.prepare(tx_id)
        p.abort(tx_id)
        assert p.get_state(tx_id) == ParticipantState.ABORTED
        assert tracker.commit_calls.get(tx_id, 0) == 0
        assert tracker.abort_calls[tx_id] == 1

    def test_abort_after_prepare_failed(self) -> None:
        tracker = CallTracker()
        p = TransactionParticipant("p1")
        p.set_callbacks(on_prepare=lambda tx: False, on_abort=tracker.abort)
        tx_id = "tx-1"
        with pytest.raises(PrepareFailedError):
            p.prepare(tx_id)
        p.abort(tx_id)
        assert p.get_state(tx_id) == ParticipantState.ABORTED
        assert tracker.abort_calls[tx_id] == 1

    def test_abort_idempotent(self) -> None:
        tracker = CallTracker()
        p = TransactionParticipant("p1")
        p.set_callbacks(on_abort=tracker.abort)
        tx_id = "tx-1"
        p.abort(tx_id)
        p.abort(tx_id)
        p.abort(tx_id)
        assert p.get_state(tx_id) == ParticipantState.ABORTED
        assert tracker.abort_calls[tx_id] == 1
        assert tracker.abort_payloads[tx_id] == [f"abort-{tx_id}"]

    def test_commit_after_abort_is_error(self) -> None:
        p = TransactionParticipant("p1")
        tx_id = "tx-1"
        p.abort(tx_id)
        with pytest.raises(TransactionStateError):
            p.commit(tx_id)

    def test_abort_after_commit_is_error(self) -> None:
        tracker = CallTracker()
        p = TransactionParticipant("p1")
        p.set_callbacks(on_prepare=tracker.prepare, on_commit=tracker.commit)
        tx_id = "tx-1"
        p.prepare(tx_id)
        p.commit(tx_id)
        with pytest.raises(TransactionStateError):
            p.abort(tx_id)

    def test_participant_id_property(self) -> None:
        p = TransactionParticipant("my-service")
        assert p.participant_id == "my-service"


# ---------------------------------------------------------------------------
# TransactionCoordinator - Basics
# ---------------------------------------------------------------------------
class TestCoordinatorBasics:
    def test_begin_transaction_auto_id(self) -> None:
        coord = TransactionCoordinator()
        tx_id = coord.begin_transaction()
        assert tx_id.startswith("tx-")
        assert coord.get_transaction_state(tx_id) == TransactionState.INIT

    def test_begin_transaction_custom_id(self) -> None:
        coord = TransactionCoordinator()
        tx_id = coord.begin_transaction("order-42")
        assert tx_id == "order-42"

    def test_begin_duplicate_id_raises(self) -> None:
        coord = TransactionCoordinator()
        coord.begin_transaction("tx-1")
        with pytest.raises(ValueError):
            coord.begin_transaction("tx-1")

    def test_unknown_transaction_raises(self) -> None:
        coord = TransactionCoordinator()
        with pytest.raises(TransactionNotFoundError):
            coord.get_transaction_state("ghost")

    def test_register_and_list_participants(self) -> None:
        coord = TransactionCoordinator()
        tx_id = coord.begin_transaction()
        p1 = TransactionParticipant("p1")
        p2 = TransactionParticipant("p2")
        coord.register_participant(tx_id, p1)
        coord.register_participant(tx_id, p2)
        assert coord.get_participants(tx_id) == ["p1", "p2"]

    def test_register_duplicate_participant_raises(self) -> None:
        coord = TransactionCoordinator()
        tx_id = coord.begin_transaction()
        p1 = TransactionParticipant("p1")
        coord.register_participant(tx_id, p1)
        with pytest.raises(ParticipantAlreadyRegisteredError):
            coord.register_participant(tx_id, p1)

    def test_register_after_prepared_raises(self) -> None:
        coord = TransactionCoordinator()
        tx_id = coord.begin_transaction()
        coord.prepare_transaction(tx_id)
        p1 = TransactionParticipant("p1")
        with pytest.raises(TransactionStateError):
            coord.register_participant(tx_id, p1)

    def test_invalid_timeout_value(self) -> None:
        with pytest.raises(ValueError):
            TransactionCoordinator(prepare_timeout_seconds=-1)


# ---------------------------------------------------------------------------
# TransactionCoordinator - 2PC happy path
# ---------------------------------------------------------------------------
class TestCoordinatorHappyPath:
    def test_single_participant_commit(self) -> None:
        tracker = CallTracker()
        coord = TransactionCoordinator()
        p = TransactionParticipant("p1")
        p.set_callbacks(
            on_prepare=tracker.prepare,
            on_commit=tracker.commit,
            on_abort=tracker.abort,
        )
        tx_id = coord.begin_transaction()
        coord.register_participant(tx_id, p)

        assert coord.prepare_transaction(tx_id) is True
        assert coord.get_transaction_state(tx_id) == TransactionState.PREPARED

        coord.commit_transaction(tx_id)
        assert coord.get_transaction_state(tx_id) == TransactionState.COMMITTED
        assert p.get_state(tx_id) == ParticipantState.COMMITTED
        assert tracker.commit_calls[tx_id] == 1
        assert tracker.abort_calls.get(tx_id, 0) == 0

    def test_multi_participants_commit(self) -> None:
        coord = TransactionCoordinator()
        trackers: Dict[str, CallTracker] = {}
        tx_id = coord.begin_transaction()
        for name in ("payment", "inventory", "shipping"):
            t = CallTracker()
            trackers[name] = t
            p = TransactionParticipant(name)
            p.set_callbacks(on_prepare=t.prepare, on_commit=t.commit, on_abort=t.abort)
            coord.register_participant(tx_id, p)

        assert coord.prepare_transaction(tx_id) is True
        coord.commit_transaction(tx_id)

        assert coord.get_transaction_state(tx_id) == TransactionState.COMMITTED
        for name, t in trackers.items():
            assert t.prepare_calls[tx_id] == 1
            assert t.commit_calls[tx_id] == 1
            assert t.abort_calls.get(tx_id, 0) == 0

    def test_no_participant_tx(self) -> None:
        coord = TransactionCoordinator()
        tx_id = coord.begin_transaction()
        assert coord.prepare_transaction(tx_id) is True
        coord.commit_transaction(tx_id)
        assert coord.get_transaction_state(tx_id) == TransactionState.COMMITTED

    def test_execute_transaction_commit(self) -> None:
        tracker = CallTracker()
        coord = TransactionCoordinator()
        p = TransactionParticipant("p1")
        p.set_callbacks(on_prepare=tracker.prepare, on_commit=tracker.commit)
        tx_id = coord.begin_transaction()
        coord.register_participant(tx_id, p)

        state = coord.execute_transaction(tx_id)
        assert state == TransactionState.COMMITTED
        assert tracker.commit_calls[tx_id] == 1


# ---------------------------------------------------------------------------
# TransactionCoordinator - Abort paths
# ---------------------------------------------------------------------------
class TestCoordinatorAbortPaths:
    def test_one_participant_rejects_prepare(self) -> None:
        coord = TransactionCoordinator()
        trackers: Dict[str, CallTracker] = {}
        tx_id = coord.begin_transaction()
        for idx, name in enumerate(("p-good", "p-bad", "p-other")):
            t = CallTracker()
            trackers[name] = t
            p = TransactionParticipant(name)
            if idx == 1:
                p.set_callbacks(
                    on_prepare=lambda tx: False,
                    on_abort=t.abort,
                )
            else:
                p.set_callbacks(on_prepare=t.prepare, on_commit=t.commit, on_abort=t.abort)
            coord.register_participant(tx_id, p)

        assert coord.prepare_transaction(tx_id) is False
        coord.abort_transaction(tx_id)

        assert coord.get_transaction_state(tx_id) == TransactionState.ABORTED
        for name, t in trackers.items():
            assert t.commit_calls.get(tx_id, 0) == 0
            assert t.abort_calls.get(tx_id, 0) == 1

    def test_participant_prepare_exception(self) -> None:
        coord = TransactionCoordinator()
        t1 = CallTracker()
        p_good = TransactionParticipant("p-good")
        p_good.set_callbacks(on_prepare=t1.prepare, on_commit=t1.commit, on_abort=t1.abort)

        p_bad = TransactionParticipant("p-bad")
        p_bad.set_callbacks(
            on_prepare=lambda tx: (_ for _ in ()).throw(RuntimeError("DB down"))
        )

        tx_id = coord.begin_transaction()
        coord.register_participant(tx_id, p_good)
        coord.register_participant(tx_id, p_bad)

        assert coord.prepare_transaction(tx_id) is False
        state = coord.execute_transaction(tx_id)
        assert state == TransactionState.ABORTED

    def test_execute_transaction_aborts_on_prepare_fail(self) -> None:
        coord = TransactionCoordinator()
        p = TransactionParticipant("p1")
        p.set_callbacks(on_prepare=lambda tx: False)
        tx_id = coord.begin_transaction()
        coord.register_participant(tx_id, p)
        state = coord.execute_transaction(tx_id)
        assert state == TransactionState.ABORTED

    def test_manual_abort(self) -> None:
        tracker = CallTracker()
        coord = TransactionCoordinator()
        p = TransactionParticipant("p1")
        p.set_callbacks(on_prepare=tracker.prepare, on_abort=tracker.abort)
        tx_id = coord.begin_transaction()
        coord.register_participant(tx_id, p)
        coord.prepare_transaction(tx_id)
        coord.abort_transaction(tx_id)
        assert coord.get_transaction_state(tx_id) == TransactionState.ABORTED
        assert tracker.abort_calls[tx_id] == 1

    def test_abort_then_commit_raises(self) -> None:
        coord = TransactionCoordinator()
        tx_id = coord.begin_transaction()
        coord.abort_transaction(tx_id)
        with pytest.raises(TransactionStateError):
            coord.commit_transaction(tx_id)

    def test_commit_then_abort_raises(self) -> None:
        coord = TransactionCoordinator()
        tx_id = coord.begin_transaction()
        coord.prepare_transaction(tx_id)
        coord.commit_transaction(tx_id)
        with pytest.raises(TransactionStateError):
            coord.abort_transaction(tx_id)


# ---------------------------------------------------------------------------
# TransactionCoordinator - Timeout
# ---------------------------------------------------------------------------
class TestCoordinatorTimeout:
    def test_prepare_timeout_triggers_abort(self) -> None:
        clock = FakeClock()
        coord = TransactionCoordinator(prepare_timeout_seconds=5.0, clock=clock)
        tracker = CallTracker()

        def slow_prepare(tx_id: str) -> bool:
            clock.advance(10.0)
            return True

        p = TransactionParticipant("slow")
        p.set_callbacks(on_prepare=slow_prepare, on_abort=tracker.abort)

        tx_id = coord.begin_transaction()
        coord.register_participant(tx_id, p)

        with pytest.raises(TimeoutDecisionAbortedError):
            coord.prepare_transaction(tx_id)
        final = coord.execute_transaction(tx_id)
        assert final == TransactionState.TIMEOUT_ABORTED
        assert tracker.abort_calls[tx_id] == 1

    def test_prepare_before_timeout_succeeds(self) -> None:
        clock = FakeClock()
        coord = TransactionCoordinator(prepare_timeout_seconds=5.0, clock=clock)
        tracker = CallTracker()
        p = TransactionParticipant("fast")
        p.set_callbacks(on_prepare=tracker.prepare, on_commit=tracker.commit)
        tx_id = coord.begin_transaction()
        coord.register_participant(tx_id, p)
        clock.advance(2.0)
        assert coord.prepare_transaction(tx_id) is True
        clock.advance(100.0)
        coord.commit_transaction(tx_id)
        assert coord.get_transaction_state(tx_id) == TransactionState.COMMITTED


# ---------------------------------------------------------------------------
# TransactionCoordinator - Idempotency
# ---------------------------------------------------------------------------
class TestCoordinatorIdempotency:
    def test_prepare_idempotent_on_success(self) -> None:
        tracker = CallTracker()
        coord = TransactionCoordinator()
        p = TransactionParticipant("p1")
        p.set_callbacks(on_prepare=tracker.prepare, on_commit=tracker.commit)
        tx_id = coord.begin_transaction()
        coord.register_participant(tx_id, p)
        r1 = coord.prepare_transaction(tx_id)
        r2 = coord.prepare_transaction(tx_id)
        r3 = coord.prepare_transaction(tx_id)
        assert r1 is r2 is r3 is True
        assert tracker.prepare_calls[tx_id] == 1

    def test_prepare_idempotent_on_failure(self) -> None:
        coord = TransactionCoordinator()
        p = TransactionParticipant("p1")
        p.set_callbacks(on_prepare=lambda tx: False)
        tx_id = coord.begin_transaction()
        coord.register_participant(tx_id, p)
        r1 = coord.prepare_transaction(tx_id)
        r2 = coord.prepare_transaction(tx_id)
        assert r1 is r2 is False

    def test_commit_idempotent(self) -> None:
        tracker = CallTracker()
        coord = TransactionCoordinator()
        p = TransactionParticipant("p1")
        p.set_callbacks(on_prepare=tracker.prepare, on_commit=tracker.commit)
        tx_id = coord.begin_transaction()
        coord.register_participant(tx_id, p)
        coord.prepare_transaction(tx_id)
        coord.commit_transaction(tx_id)
        coord.commit_transaction(tx_id)
        coord.commit_transaction(tx_id)
        assert coord.get_transaction_state(tx_id) == TransactionState.COMMITTED
        assert tracker.commit_calls[tx_id] == 1

    def test_abort_idempotent(self) -> None:
        tracker = CallTracker()
        coord = TransactionCoordinator()
        p = TransactionParticipant("p1")
        p.set_callbacks(on_prepare=tracker.prepare, on_abort=tracker.abort)
        tx_id = coord.begin_transaction()
        coord.register_participant(tx_id, p)
        coord.prepare_transaction(tx_id)
        coord.abort_transaction(tx_id)
        coord.abort_transaction(tx_id)
        coord.abort_transaction(tx_id)
        assert coord.get_transaction_state(tx_id) == TransactionState.ABORTED
        assert tracker.abort_calls[tx_id] == 1

    def test_execute_transaction_idempotent(self) -> None:
        tracker = CallTracker()
        coord = TransactionCoordinator()
        p = TransactionParticipant("p1")
        p.set_callbacks(on_prepare=tracker.prepare, on_commit=tracker.commit)
        tx_id = coord.begin_transaction()
        coord.register_participant(tx_id, p)
        s1 = coord.execute_transaction(tx_id)
        s2 = coord.execute_transaction(tx_id)
        s3 = coord.execute_transaction(tx_id)
        assert s1 == s2 == s3 == TransactionState.COMMITTED
        assert tracker.prepare_calls[tx_id] == 1
        assert tracker.commit_calls[tx_id] == 1


# ---------------------------------------------------------------------------
# TransactionCoordinator - State machine errors
# ---------------------------------------------------------------------------
class TestCoordinatorStateMachine:
    def test_commit_without_prepare(self) -> None:
        coord = TransactionCoordinator()
        tx_id = coord.begin_transaction()
        p = TransactionParticipant("p1")
        coord.register_participant(tx_id, p)
        with pytest.raises(TransactionStateError):
            coord.commit_transaction(tx_id)

    def test_commit_after_one_rejected_prepare(self) -> None:
        coord = TransactionCoordinator()
        p1 = TransactionParticipant("p1")
        p1.set_callbacks(on_prepare=lambda tx: True)
        p2 = TransactionParticipant("p2")
        p2.set_callbacks(on_prepare=lambda tx: False)
        tx_id = coord.begin_transaction()
        coord.register_participant(tx_id, p1)
        coord.register_participant(tx_id, p2)
        coord.prepare_transaction(tx_id)
        with pytest.raises(TransactionStateError):
            coord.commit_transaction(tx_id)

    def test_prepare_after_committed_raises(self) -> None:
        coord = TransactionCoordinator()
        tx_id = coord.begin_transaction()
        coord.prepare_transaction(tx_id)
        coord.commit_transaction(tx_id)
        with pytest.raises(TransactionStateError):
            coord.prepare_transaction(tx_id)


# ---------------------------------------------------------------------------
# Integration
# ---------------------------------------------------------------------------
class TestIntegrationScenarios:
    def test_order_checkout_success(self) -> None:
        """模拟电商下单：库存+支付+积分全部成功"""
        inventory_data = {"sku-1": 10}
        wallet = {"alice": 100}
        points = {"alice": 0}

        def inv_prep(tx_id: str) -> bool:
            return inventory_data["sku-1"] >= 1

        def inv_commit(tx_id: str) -> None:
            inventory_data["sku-1"] -= 1

        def inv_abort(tx_id: str) -> None:
            pass

        def pay_prep(tx_id: str) -> bool:
            return wallet["alice"] >= 50

        def pay_commit(tx_id: str) -> None:
            wallet["alice"] -= 50

        def pay_abort(tx_id: str) -> None:
            pass

        def pts_prep(tx_id: str) -> bool:
            return True

        def pts_commit(tx_id: str) -> None:
            points["alice"] += 50

        inventory = TransactionParticipant("inventory")
        inventory.set_callbacks(inv_prep, inv_commit, inv_abort)
        payment = TransactionParticipant("payment")
        payment.set_callbacks(pay_prep, pay_commit, pay_abort)
        loyalty = TransactionParticipant("loyalty")
        loyalty.set_callbacks(pts_prep, pts_commit, lambda tx: None)

        coord = TransactionCoordinator()
        tx_id = coord.begin_transaction("order-123")
        coord.register_participant(tx_id, inventory)
        coord.register_participant(tx_id, payment)
        coord.register_participant(tx_id, loyalty)

        state = coord.execute_transaction(tx_id)
        assert state == TransactionState.COMMITTED
        assert inventory_data["sku-1"] == 9
        assert wallet["alice"] == 50
        assert points["alice"] == 50

    def test_order_checkout_payment_insufficient_funds(self) -> None:
        """模拟支付余额不足，所有参与者回滚"""
        inventory_data = {"sku-1": 10}
        inventory_prepared: Dict[str, bool] = {}

        def inv_prep(tx_id: str) -> bool:
            inventory_prepared[tx_id] = True
            return inventory_data["sku-1"] >= 1

        def inv_commit(tx_id: str) -> None:
            inventory_data["sku-1"] -= 1

        def inv_abort(tx_id: str) -> None:
            inventory_prepared.pop(tx_id, None)

        def pay_prep(tx_id: str) -> bool:
            return False  # 余额不足

        inventory = TransactionParticipant("inventory")
        inventory.set_callbacks(inv_prep, inv_commit, inv_abort)
        payment = TransactionParticipant("payment")
        payment.set_callbacks(pay_prep)

        coord = TransactionCoordinator()
        tx_id = coord.begin_transaction("order-456")
        coord.register_participant(tx_id, inventory)
        coord.register_participant(tx_id, payment)

        state = coord.execute_transaction(tx_id)
        assert state == TransactionState.ABORTED
        # 库存未扣减
        assert inventory_data["sku-1"] == 10
        # 幂等再次调用仍保持 ABORTED
        assert coord.execute_transaction(tx_id) == TransactionState.ABORTED

    def test_exception_hierarchy(self) -> None:
        assert issubclass(TransactionNotFoundError, TransactionError)
        assert issubclass(TransactionStateError, TransactionError)
        assert issubclass(PrepareFailedError, TransactionError)
        assert issubclass(CommitFailedError, TransactionError)


# ---------------------------------------------------------------------------
# Bug fixes & new features (part of the fix for reported issues)
# ---------------------------------------------------------------------------
class TestTimeoutExceptionRaised:
    """问题1修复：prepare_transaction 应真正抛出 TimeoutDecisionAbortedError"""

    def test_prepare_transaction_throws_timeout_exception(self) -> None:
        clock = FakeClock()
        coord = TransactionCoordinator(prepare_timeout_seconds=5.0, clock=clock)
        tracker = CallTracker()

        def slow_prepare(tx_id: str) -> bool:
            clock.advance(10.0)
            return True

        p = TransactionParticipant("slow")
        p.set_callbacks(on_prepare=slow_prepare, on_abort=tracker.abort)

        tx_id = coord.begin_transaction()
        coord.register_participant(tx_id, p)

        with pytest.raises(TimeoutDecisionAbortedError) as excinfo:
            coord.prepare_transaction(tx_id)

        assert "超时" in str(excinfo.value)
        assert coord.get_transaction_state(tx_id) == TransactionState.ABORTING
        # 执行 abort
        coord.abort_transaction(tx_id)
        # 由于超时分支设置了 decision = TIMEOUT_ABORTED，需要用 retry_abort 确保完成
        if coord.has_incomplete_abort(tx_id):
            coord.retry_abort(tx_id)
        final_state = coord.get_transaction_state(tx_id)
        assert final_state in (
            TransactionState.ABORTED,
            TransactionState.TIMEOUT_ABORTED,
        )

    def test_execute_transaction_handles_timeout(self) -> None:
        """execute_transaction 能正确捕获 TimeoutDecisionAbortedError 并执行 abort"""
        clock = FakeClock()
        coord = TransactionCoordinator(prepare_timeout_seconds=5.0, clock=clock)

        def slow_prepare(tx_id: str) -> bool:
            clock.advance(100.0)
            return True

        p = TransactionParticipant("slow-svc")
        p.set_callbacks(on_prepare=slow_prepare)

        tx_id = coord.begin_transaction()
        coord.register_participant(tx_id, p)

        with pytest.raises(TimeoutDecisionAbortedError):
            coord.execute_transaction(tx_id)
        # 异常抛出前已完成 abort，状态应为 TIMEOUT_ABORTED
        assert coord.get_transaction_state(tx_id) == TransactionState.TIMEOUT_ABORTED


class TestCommitPartialFailure:
    """问题2修复：commit 部分失败应抛 CommitFailedError，execute_transaction 不静默吞掉"""

    def test_commit_partial_failure_throws_commit_failed_error(self) -> None:
        coord = TransactionCoordinator()
        t1 = CallTracker()
        t2 = CallTracker()

        p_good = TransactionParticipant("good")
        p_good.set_callbacks(
            on_prepare=t1.prepare,
            on_commit=t1.commit,
            on_abort=t1.abort,
        )

        p_bad = TransactionParticipant("bad")
        p_bad.set_callbacks(
            on_prepare=lambda tx: True,
            on_commit=lambda tx: (_ for _ in ()).throw(RuntimeError("db crashed")),
            on_abort=t2.abort,
        )

        tx_id = coord.begin_transaction()
        coord.register_participant(tx_id, p_good)
        coord.register_participant(tx_id, p_bad)

        assert coord.prepare_transaction(tx_id) is True

        with pytest.raises(CommitFailedError) as excinfo:
            coord.commit_transaction(tx_id)

        # 现在状态是 COMMIT_PARTIALLY_FAILED（中间状态），不是 COMMITTED
        assert "db crashed" in str(excinfo.value)
        assert coord.get_transaction_state(tx_id) == TransactionState.COMMIT_PARTIALLY_FAILED
        # good 参与者已提交
        assert p_good.get_state(tx_id) == ParticipantState.COMMITTED
        # bad 参与者仍为 PREPARED 或 COMMIT_FAILED
        assert p_bad.get_state(tx_id) in (
            ParticipantState.PREPARED,
            ParticipantState.COMMIT_FAILED,
        )
        # 异常对象附带失败参与者列表
        assert excinfo.value.failed_participants == ["bad"]
        assert excinfo.value.committed_participants == ["good"]
        # 查询方法可用
        assert coord.has_incomplete_commit(tx_id) is True
        assert coord.get_commit_failed_participants(tx_id) == ["bad"]

    def test_retry_commit_succeeds_after_fix(self) -> None:
        """retry_commit 可以成功完成之前失败的参与者"""
        coord = TransactionCoordinator()
        bad_state = {"should_fail": True}

        def flaky_commit(tx_id: str) -> None:
            if bad_state["should_fail"]:
                raise RuntimeError("network partition")

        p = TransactionParticipant("flaky")
        p.set_callbacks(on_prepare=lambda tx: True, on_commit=flaky_commit)

        tx_id = coord.begin_transaction()
        coord.register_participant(tx_id, p)

        coord.prepare_transaction(tx_id)
        with pytest.raises(CommitFailedError):
            coord.commit_transaction(tx_id)

        # 第一次失败
        assert coord.has_incomplete_commit(tx_id) is True
        assert coord.retry_commit(tx_id) is False
        assert coord.get_transaction_state(tx_id) == TransactionState.COMMIT_PARTIALLY_FAILED

        # 修复后重试
        bad_state["should_fail"] = False
        assert coord.retry_commit(tx_id) is True
        assert coord.get_transaction_state(tx_id) == TransactionState.COMMITTED
        assert p.get_state(tx_id) == ParticipantState.COMMITTED
        assert coord.has_incomplete_commit(tx_id) is False
        assert coord.get_commit_failed_participants(tx_id) == []

    def test_execute_transaction_propagates_commit_failure(self) -> None:
        """execute_transaction 不应静默吞掉 CommitFailedError（重试后仍失败）"""
        # 设置 max_retry_attempts=1 以快速失败
        coord = TransactionCoordinator(max_retry_attempts=1)
        p_good = TransactionParticipant("good")
        p_good.set_callbacks(on_prepare=lambda tx: True, on_commit=lambda tx: None)
        p_bad = TransactionParticipant("bad")
        p_bad.set_callbacks(
            on_prepare=lambda tx: True,
            on_commit=lambda tx: (_ for _ in ()).throw(RuntimeError("boom")),
        )

        tx_id = coord.begin_transaction()
        coord.register_participant(tx_id, p_good)
        coord.register_participant(tx_id, p_bad)

        with pytest.raises(CommitFailedError) as excinfo:
            coord.execute_transaction(tx_id)

        # 异常对象包含失败详情
        assert "重试" in str(excinfo.value)
        assert excinfo.value.failed_participants == ["bad"]
        assert excinfo.value.committed_participants == ["good"]
        # 事务保持 COMMIT_PARTIALLY_FAILED
        assert coord.get_transaction_state(tx_id) == TransactionState.COMMIT_PARTIALLY_FAILED

    def test_execute_transaction_commit_retries_until_success(self) -> None:
        """execute_transaction 会自动重试 commit，直到成功或达到最大重试次数"""
        coord = TransactionCoordinator(max_retry_attempts=3)
        fail_count = {"n": 0}

        def commit_with_failures(tx_id: str) -> None:
            if fail_count["n"] < 2:
                fail_count["n"] += 1
                raise RuntimeError(f"fail #{fail_count['n']}")
            # 第三次成功

        p = TransactionParticipant("eventually-consistent")
        p.set_callbacks(on_prepare=lambda tx: True, on_commit=commit_with_failures)

        tx_id = coord.begin_transaction()
        coord.register_participant(tx_id, p)

        # 应该自动重试并最终成功
        final_state = coord.execute_transaction(tx_id)
        assert final_state == TransactionState.COMMITTED
        assert fail_count["n"] == 2  # 失败了 2 次，第 3 次成功

    def test_commit_idempotent_after_partial_failure(self) -> None:
        """对 COMMIT_PARTIALLY_FAILED 的事务再次调用 commit_transaction 会继续执行"""
        coord = TransactionCoordinator()
        fail_once = {"failed": False}

        def commit_fail_once(tx_id: str) -> None:
            if not fail_once["failed"]:
                fail_once["failed"] = True
                raise RuntimeError("fail-once")
            # 第二次成功

        p1 = TransactionParticipant("p1")
        p1.set_callbacks(
            on_prepare=lambda tx: True,
            on_commit=commit_fail_once,
        )

        tx_id = coord.begin_transaction()
        coord.register_participant(tx_id, p1)

        coord.prepare_transaction(tx_id)
        with pytest.raises(CommitFailedError):
            coord.commit_transaction(tx_id)

        assert coord.get_transaction_state(tx_id) == TransactionState.COMMIT_PARTIALLY_FAILED
        # 第二次调用 commit_transaction 会继续执行（或用 retry_commit）
        coord.commit_transaction(tx_id)  # 这次应该成功
        assert coord.get_transaction_state(tx_id) == TransactionState.COMMITTED

    def test_retry_commit_on_committed_is_noop(self) -> None:
        """对已 COMMITTED 的事务调用 retry_commit 返回 True，无副作用"""
        tracker = CallTracker()
        coord = TransactionCoordinator()
        p = TransactionParticipant("p1")
        p.set_callbacks(on_prepare=tracker.prepare, on_commit=tracker.commit)

        tx_id = coord.begin_transaction()
        coord.register_participant(tx_id, p)
        coord.prepare_transaction(tx_id)
        coord.commit_transaction(tx_id)

        assert coord.get_transaction_state(tx_id) == TransactionState.COMMITTED
        commit_count_before = tracker.commit_calls.get(tx_id, 0)
        assert coord.retry_commit(tx_id) is True
        # 不产生额外副作用
        assert tracker.commit_calls.get(tx_id, 0) == commit_count_before

    def test_retry_commit_on_non_committing_state_raises(self) -> None:
        """对非 commit 阶段的事务调用 retry_commit 应抛错"""
        coord = TransactionCoordinator()
        tx_id = coord.begin_transaction()
        coord.prepare_transaction(tx_id)
        coord.abort_transaction(tx_id)

        with pytest.raises(TransactionStateError):
            coord.retry_commit(tx_id)

    def test_commit_failed_error_contains_details(self) -> None:
        """CommitFailedError 异常应包含失败和成功参与者列表"""
        coord = TransactionCoordinator()
        p1 = TransactionParticipant("p1")
        p1.set_callbacks(
            on_prepare=lambda tx: True,
            on_commit=lambda tx: (_ for _ in ()).throw(RuntimeError("err1")),
        )
        p2 = TransactionParticipant("p2")
        p2.set_callbacks(on_prepare=lambda tx: True, on_commit=lambda tx: None)
        p3 = TransactionParticipant("p3")
        p3.set_callbacks(
            on_prepare=lambda tx: True,
            on_commit=lambda tx: (_ for _ in ()).throw(RuntimeError("err3")),
        )

        tx_id = coord.begin_transaction()
        coord.register_participant(tx_id, p1)
        coord.register_participant(tx_id, p2)
        coord.register_participant(tx_id, p3)

        coord.prepare_transaction(tx_id)
        with pytest.raises(CommitFailedError) as excinfo:
            coord.commit_transaction(tx_id)

        assert excinfo.value.failed_participants == ["p1", "p3"]
        assert excinfo.value.committed_participants == ["p2"]


class TestAbortCallbackFailure:
    """问题3修复：参与者 abort 回调失败的处置策略"""

    def test_abort_callback_failure_keeps_coordinator_in_aborting(self) -> None:
        """某参与者 abort 回调失败时，协调器保持 ABORTING 状态"""
        coord = TransactionCoordinator()
        t1 = CallTracker()
        t2 = CallTracker()

        p_good = TransactionParticipant("good")
        p_good.set_callbacks(
            on_prepare=t1.prepare,
            on_abort=t1.abort,
        )

        p_bad = TransactionParticipant("bad")
        p_bad.set_callbacks(
            on_prepare=lambda tx: True,
            on_abort=lambda tx: (_ for _ in ()).throw(RuntimeError("unreliable network")),
        )

        tx_id = coord.begin_transaction()
        coord.register_participant(tx_id, p_good)
        coord.register_participant(tx_id, p_bad)

        coord.prepare_transaction(tx_id)
        coord.abort_transaction(tx_id)

        # 协调器保持 ABORTING
        assert coord.get_transaction_state(tx_id) == TransactionState.ABORTING
        # good 参与者已 ABORTED
        assert p_good.get_state(tx_id) == ParticipantState.ABORTED
        # bad 参与者状态回退（未到 ABORTED）
        assert p_bad.get_state(tx_id) == ParticipantState.PREPARED

        # 查询方法返回正确结果
        assert coord.has_incomplete_abort(tx_id) is True
        assert coord.get_abort_failed_participants(tx_id) == ["bad"]

    def test_retry_abort_succeeds_after_fix(self) -> None:
        """retry_abort 可以成功完成之前失败的参与者"""
        coord = TransactionCoordinator()
        bad_state = {"should_fail": True}

        def flaky_abort(tx_id: str) -> None:
            if bad_state["should_fail"]:
                raise RuntimeError("network partition")
            # 否则成功

        p = TransactionParticipant("flaky")
        p.set_callbacks(on_prepare=lambda tx: True, on_abort=flaky_abort)

        tx_id = coord.begin_transaction()
        coord.register_participant(tx_id, p)

        coord.prepare_transaction(tx_id)
        coord.abort_transaction(tx_id)

        # 第一次失败
        assert coord.has_incomplete_abort(tx_id) is True
        assert coord.retry_abort(tx_id) is False
        assert coord.get_transaction_state(tx_id) == TransactionState.ABORTING

        # 修复后重试
        bad_state["should_fail"] = False
        assert coord.retry_abort(tx_id) is True
        assert coord.get_transaction_state(tx_id) == TransactionState.ABORTED
        assert p.get_state(tx_id) == ParticipantState.ABORTED
        assert coord.has_incomplete_abort(tx_id) is False
        assert coord.get_abort_failed_participants(tx_id) == []

    def test_retry_abort_on_non_aborting_raises(self) -> None:
        """对非 ABORTING 状态的事务调用 retry_abort 应抛错"""
        coord = TransactionCoordinator()
        tx_id = coord.begin_transaction()
        coord.prepare_transaction(tx_id)
        coord.commit_transaction(tx_id)

        with pytest.raises(TransactionStateError):
            coord.retry_abort(tx_id)

    def test_retry_abort_on_aborted_is_noop(self) -> None:
        """对已 ABORTED 的事务调用 retry_abort 返回 True，无副作用"""
        tracker = CallTracker()
        coord = TransactionCoordinator()
        p = TransactionParticipant("p1")
        p.set_callbacks(on_prepare=tracker.prepare, on_abort=tracker.abort)

        tx_id = coord.begin_transaction()
        coord.register_participant(tx_id, p)
        coord.prepare_transaction(tx_id)
        coord.abort_transaction(tx_id)

        assert coord.get_transaction_state(tx_id) == TransactionState.ABORTED
        abort_count_before = tracker.abort_calls.get(tx_id, 0)
        assert coord.retry_abort(tx_id) is True
        # 不产生额外副作用
        assert tracker.abort_calls.get(tx_id, 0) == abort_count_before

    def test_multiple_participants_abort_failure(self) -> None:
        """多个参与者 abort 失败的场景"""
        coord = TransactionCoordinator()

        def always_fail(tx: str) -> None:
            raise RuntimeError("always fail")

        p1 = TransactionParticipant("p1")
        p1.set_callbacks(on_prepare=lambda tx: True, on_abort=always_fail)
        p2 = TransactionParticipant("p2")
        p2.set_callbacks(on_prepare=lambda tx: True, on_abort=always_fail)
        p3 = TransactionParticipant("p3")
        p3.set_callbacks(on_prepare=lambda tx: True, on_abort=lambda tx: None)

        tx_id = coord.begin_transaction()
        coord.register_participant(tx_id, p1)
        coord.register_participant(tx_id, p2)
        coord.register_participant(tx_id, p3)

        coord.prepare_transaction(tx_id)
        coord.abort_transaction(tx_id)

        assert coord.get_transaction_state(tx_id) == TransactionState.ABORTING
        assert coord.has_incomplete_abort(tx_id) is True
        failed = coord.get_abort_failed_participants(tx_id)
        assert "p1" in failed
        assert "p2" in failed
        assert "p3" not in failed
        assert p3.get_state(tx_id) == ParticipantState.ABORTED


# ---------------------------------------------------------------------------
# Test for AbortFailedError exception class
# ---------------------------------------------------------------------------
class TestAbortFailedError:
    def test_abort_failed_error_is_transaction_error(self) -> None:
        from solocoder_4_py.transaction_coordination import AbortFailedError
        assert issubclass(AbortFailedError, TransactionError)

