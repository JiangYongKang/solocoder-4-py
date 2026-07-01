from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional
from uuid import uuid4

from .log_entry import LogEntry, OperationType, _MISSING
from .state_store import StateStore


@dataclass
class Transaction:
    transaction_id: str
    pending_entries: list[LogEntry] = field(default_factory=list)
    active: bool = True


class TransactionLogManager:
    def __init__(self) -> None:
        self._log: list[LogEntry] = []
        self._state: StateStore = StateStore()
        self._checkpoint_state: Optional[dict[str, Any]] = None
        self._checkpoint_index: int = -1
        self._active_transactions: dict[str, Transaction] = {}
        self._committed_indexes: set[int] = set()

    @property
    def state(self) -> StateStore:
        return self._state

    @property
    def log_length(self) -> int:
        return len(self._log)

    @property
    def checkpoint_lsn(self) -> int:
        return self._checkpoint_index

    @property
    def next_lsn(self) -> int:
        return len(self._log)

    def get_log_entry(self, lsn: int) -> Optional[LogEntry]:
        if 0 <= lsn < len(self._log):
            return self._log[lsn]
        return None

    def get_log_entries(self, start_lsn: int = 0, end_lsn: Optional[int] = None) -> list[LogEntry]:
        end = end_lsn if end_lsn is not None else len(self._log)
        return self._log[start_lsn:end]

    def begin_transaction(self) -> str:
        transaction_id = str(uuid4())
        entry = self._create_entry(
            operation=OperationType.BEGIN,
            transaction_id=transaction_id,
        )
        self._append_entry(entry)
        self._active_transactions[transaction_id] = Transaction(
            transaction_id=transaction_id,
            pending_entries=[entry],
        )
        return transaction_id

    def set(self, key: str, value: Any, transaction_id: Optional[str] = None) -> Any:
        if transaction_id is not None and transaction_id not in self._active_transactions:
            raise ValueError(f"Unknown transaction: {transaction_id}")

        old_value = self._state.set(key, value)

        entry = self._create_entry(
            operation=OperationType.SET,
            transaction_id=transaction_id,
            key=key,
            value=value,
            old_value=old_value,
        )
        self._append_entry(entry)

        if transaction_id is not None:
            self._active_transactions[transaction_id].pending_entries.append(entry)

        return old_value

    def delete(self, key: str, transaction_id: Optional[str] = None) -> tuple[bool, Any]:
        if transaction_id is not None and transaction_id not in self._active_transactions:
            raise ValueError(f"Unknown transaction: {transaction_id}")

        existed, old_value = self._state.delete(key)

        entry = self._create_entry(
            operation=OperationType.DELETE,
            transaction_id=transaction_id,
            key=key,
            old_value=old_value,
        )
        self._append_entry(entry)

        if transaction_id is not None:
            self._active_transactions[transaction_id].pending_entries.append(entry)

        return existed, old_value

    def commit(self, transaction_id: str) -> None:
        if transaction_id not in self._active_transactions:
            raise ValueError(f"Unknown transaction: {transaction_id}")

        tx = self._active_transactions[transaction_id]
        if not tx.active:
            raise ValueError(f"Transaction {transaction_id} is not active")

        entry = self._create_entry(
            operation=OperationType.COMMIT,
            transaction_id=transaction_id,
        )
        self._append_entry(entry)
        tx.pending_entries.append(entry)
        tx.active = False

        for e in tx.pending_entries:
            idx = self._log.index(e)
            self._committed_indexes.add(idx)

        del self._active_transactions[transaction_id]

    def rollback(self, transaction_id: str) -> None:
        if transaction_id not in self._active_transactions:
            raise ValueError(f"Unknown transaction: {transaction_id}")

        tx = self._active_transactions[transaction_id]
        if not tx.active:
            raise ValueError(f"Transaction {transaction_id} is not active")

        data_ops = [e for e in reversed(tx.pending_entries) if e.is_data_operation()]
        for entry in data_ops:
            if entry.operation == OperationType.SET:
                if entry.old_value is _MISSING:
                    self._state.delete(entry.key)
                else:
                    self._state.set(entry.key, entry.old_value)
            elif entry.operation == OperationType.DELETE:
                if entry.old_value is not _MISSING:
                    self._state.set(entry.key, entry.old_value)

        rollback_entry = self._create_entry(
            operation=OperationType.ROLLBACK,
            transaction_id=transaction_id,
        )
        self._append_entry(rollback_entry)
        tx.active = False
        del self._active_transactions[transaction_id]

    def checkpoint(self) -> int:
        for tx_id in list(self._active_transactions.keys()):
            self.rollback(tx_id)

        checkpoint_index = len(self._log)
        self._checkpoint_state = self._state.to_dict()
        self._checkpoint_index = checkpoint_index

        entry = self._create_entry(
            operation=OperationType.CHECKPOINT,
            value={"state": self._checkpoint_state, "index": checkpoint_index},
        )
        self._append_entry(entry)

        self._log = self._log[checkpoint_index:]
        self._checkpoint_index = 0
        self._committed_indexes = {
            i for i, e in enumerate(self._log)
            if e.operation == OperationType.COMMIT
        }

        return 0

    def simulate_crash_and_recover(self) -> tuple[StateStore, int, int]:
        recovered_state = StateStore()
        redo_entries: list[LogEntry] = []
        undo_transactions: dict[str, list[LogEntry]] = {}

        if self._checkpoint_state is not None:
            recovered_state.load_dict(self._checkpoint_state)

        for entry in self._log:
            if entry.operation == OperationType.BEGIN:
                if entry.transaction_id not in undo_transactions:
                    undo_transactions[entry.transaction_id] = []
                undo_transactions[entry.transaction_id].append(entry)
            elif entry.operation == OperationType.COMMIT:
                if entry.transaction_id in undo_transactions:
                    tx_entries = undo_transactions.pop(entry.transaction_id)
                    redo_entries.extend(tx_entries)
                    redo_entries.append(entry)
            elif entry.operation == OperationType.ROLLBACK:
                undo_transactions.pop(entry.transaction_id, None)
            elif entry.operation == OperationType.CHECKPOINT:
                continue
            elif entry.is_data_operation():
                if entry.transaction_id is not None:
                    if entry.transaction_id in undo_transactions:
                        undo_transactions[entry.transaction_id].append(entry)
                    else:
                        redo_entries.append(entry)
                else:
                    redo_entries.append(entry)

        for entry in redo_entries:
            if entry.operation == OperationType.SET:
                recovered_state.set(entry.key, entry.value)
            elif entry.operation == OperationType.DELETE:
                recovered_state.delete(entry.key)

        for tx_id, entries in list(undo_transactions.items()):
            data_ops = [e for e in reversed(entries) if e.is_data_operation()]
            for entry in data_ops:
                if entry.operation == OperationType.SET:
                    if entry.old_value is _MISSING:
                        recovered_state.delete(entry.key)
                    else:
                        recovered_state.set(entry.key, entry.old_value)
                elif entry.operation == OperationType.DELETE:
                    if entry.old_value is not _MISSING:
                        recovered_state.set(entry.key, entry.old_value)

        redo_count = len([e for e in redo_entries if e.is_data_operation()])
        undo_count = sum(
            len([e for e in entries if e.is_data_operation()])
            for entries in undo_transactions.values()
        )

        return recovered_state, redo_count, undo_count

    def truncate_log_before(self, lsn: int) -> int:
        if lsn <= 0:
            return 0
        if lsn > len(self._log):
            lsn = len(self._log)
        removed = lsn
        self._log = self._log[lsn:]
        if self._checkpoint_index >= 0:
            self._checkpoint_index = max(0, self._checkpoint_index - lsn)
        self._committed_indexes = {
            i - lsn for i in self._committed_indexes if i >= lsn
        }
        return removed

    def reset(self) -> None:
        self._log.clear()
        self._state.clear()
        self._checkpoint_state = None
        self._checkpoint_index = -1
        self._active_transactions.clear()
        self._committed_indexes.clear()

    def _create_entry(
        self,
        operation: OperationType,
        transaction_id: Optional[str] = None,
        key: Optional[str] = None,
        value: Any = None,
        old_value: Any = _MISSING,
    ) -> LogEntry:
        return LogEntry(
            operation=operation,
            transaction_id=transaction_id,
            key=key,
            value=value,
            old_value=old_value,
        )

    def _append_entry(self, entry: LogEntry) -> None:
        self._log.append(entry)
