"""内存事务协调域模块

使用纯内存数据结构模拟两阶段提交（2PC）协议下的事务协调过程，
支持多参与者、超时决策、幂等操作等特性。
"""

from .constants import ParticipantState, TERMINAL_PARTICIPANT_STATES, \
    TERMINAL_TRANSACTION_STATES, TransactionState
from .coordinator import TransactionCoordinator, TransactionContext
from .exceptions import AbortFailedError, CommitFailedError, \
    ParticipantAlreadyRegisteredError, ParticipantNotFoundError, \
    PrepareFailedError, TimeoutDecisionAbortedError, TransactionError, \
    TransactionNotFoundError, TransactionStateError
from .participant import ParticipantTxContext, TransactionParticipant

__all__ = [
    "TransactionState",
    "ParticipantState",
    "TERMINAL_TRANSACTION_STATES",
    "TERMINAL_PARTICIPANT_STATES",
    "TransactionError",
    "TransactionNotFoundError",
    "TransactionStateError",
    "ParticipantAlreadyRegisteredError",
    "ParticipantNotFoundError",
    "TimeoutDecisionAbortedError",
    "PrepareFailedError",
    "CommitFailedError",
    "AbortFailedError",
    "ParticipantTxContext",
    "TransactionParticipant",
    "TransactionContext",
    "TransactionCoordinator",
]
