from enum import Enum


class TransactionState(Enum):
    """事务全局状态枚举"""
    INIT = "INIT"
    PREPARING = "PREPARING"
    PREPARED = "PREPARED"
    COMMITTING = "COMMITTING"
    COMMITTED = "COMMITTED"
    ABORTING = "ABORTING"
    ABORTED = "ABORTED"
    TIMEOUT_ABORTED = "TIMEOUT_ABORTED"


class ParticipantState(Enum):
    """参与者本地状态枚举"""
    INIT = "INIT"
    PREPARING = "PREPARING"
    PREPARED = "PREPARED"
    COMMITTING = "COMMITTING"
    COMMITTED = "COMMITTED"
    ABORTING = "ABORTING"
    ABORTED = "ABORTED"
    PREPARE_FAILED = "PREPARE_FAILED"
    COMMIT_FAILED = "COMMIT_FAILED"


TERMINAL_TRANSACTION_STATES = frozenset({
    TransactionState.COMMITTED,
    TransactionState.ABORTED,
    TransactionState.TIMEOUT_ABORTED,
})

TERMINAL_PARTICIPANT_STATES = frozenset({
    ParticipantState.COMMITTED,
    ParticipantState.ABORTED,
    ParticipantState.PREPARE_FAILED,
    ParticipantState.COMMIT_FAILED,
})
