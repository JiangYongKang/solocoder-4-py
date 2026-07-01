from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Callable, Dict, Optional

from .constants import (
    ParticipantState,
    TERMINAL_PARTICIPANT_STATES,
)
from .exceptions import (
    AbortFailedError,
    CommitFailedError,
    ParticipantNotFoundError,
    PrepareFailedError,
    TransactionStateError,
)


ParticipantAction = Callable[[str], Any]
Predicate = Callable[[str], bool]


@dataclass
class ParticipantTxContext:
    """参与者针对单个事务的上下文"""
    tx_id: str
    state: ParticipantState = ParticipantState.INIT
    prepare_result: Optional[bool] = None
    commit_count: int = 0
    abort_count: int = 0
    prepare_count: int = 0


class TransactionParticipant:
    """事务参与者

    支持 prepare/commit/abort 操作，并保证幂等性。
    通过注入 on_prepare/on_commit/on_abort 回调来模拟业务逻辑。
    """

    def __init__(self, participant_id: str) -> None:
        self._id = participant_id
        self._tx_contexts: Dict[str, ParticipantTxContext] = {}
        self._on_prepare: Optional[Predicate] = None
        self._on_commit: Optional[ParticipantAction] = None
        self._on_abort: Optional[ParticipantAction] = None
        self._lock = Lock()

    @property
    def participant_id(self) -> str:
        return self._id

    def set_callbacks(
        self,
        on_prepare: Optional[Predicate] = None,
        on_commit: Optional[ParticipantAction] = None,
        on_abort: Optional[ParticipantAction] = None,
    ) -> None:
        """设置参与者的业务回调函数

        :param on_prepare: 准备阶段回调，返回 True 表示同意提交，False/抛异常表示拒绝
        :param on_commit: 提交阶段回调
        :param on_abort: 中止阶段回调
        """
        with self._lock:
            self._on_prepare = on_prepare
            self._on_commit = on_commit
            self._on_abort = on_abort

    def _get_or_create_context(self, tx_id: str) -> ParticipantTxContext:
        ctx = self._tx_contexts.get(tx_id)
        if ctx is None:
            ctx = ParticipantTxContext(tx_id=tx_id)
            self._tx_contexts[tx_id] = ctx
        return ctx

    def get_context(self, tx_id: str) -> ParticipantTxContext:
        with self._lock:
            ctx = self._tx_contexts.get(tx_id)
            if ctx is None:
                raise ParticipantNotFoundError(
                    f"参与者 {self._id} 未参与事务 {tx_id}"
                )
            return ctx

    def get_state(self, tx_id: str) -> ParticipantState:
        return self.get_context(tx_id).state

    # ------------------------------------------------------------
    # 幂等 prepare
    # ------------------------------------------------------------
    def prepare(self, tx_id: str) -> bool:
        """幂等的 prepare 操作

        返回规则：
        - PREPARED 或 之前成功：返回 True
        - PREPARE_FAILED 或 之前失败：返回 False 并抛出 PrepareFailedError
        - ABORTED: 返回 False 并抛出 PrepareFailedError（已中止事务不再准备）
        """
        with self._lock:
            ctx = self._get_or_create_context(tx_id)
            ctx.prepare_count += 1

            if ctx.state == ParticipantState.PREPARED:
                return True
            if ctx.state == ParticipantState.PREPARE_FAILED:
                raise PrepareFailedError(
                    f"参与者 {self._id} 对事务 {tx_id} 已准备失败，不可重复准备"
                )
            if ctx.state in TERMINAL_PARTICIPANT_STATES and ctx.state != ParticipantState.PREPARE_FAILED:
                raise TransactionStateError(
                    f"参与者 {self._id} 对事务 {tx_id} 处于终态 {ctx.state.value}，无法 prepare"
                )
            if ctx.state not in (ParticipantState.INIT, ParticipantState.PREPARING):
                raise TransactionStateError(
                    f"参与者 {self._id} 处于非法状态 {ctx.state.value} 进行 prepare"
                )

            ctx.state = ParticipantState.PREPARING

            try:
                if self._on_prepare is None:
                    result = True
                else:
                    result = bool(self._on_prepare(tx_id))
            except Exception as exc:
                ctx.state = ParticipantState.PREPARE_FAILED
                ctx.prepare_result = False
                raise PrepareFailedError(
                    f"参与者 {self._id} 对事务 {tx_id} 准备失败：{exc}"
                ) from exc

            if result:
                ctx.state = ParticipantState.PREPARED
                ctx.prepare_result = True
                return True
            else:
                ctx.state = ParticipantState.PREPARE_FAILED
                ctx.prepare_result = False
                raise PrepareFailedError(
                    f"参与者 {self._id} 拒绝对事务 {tx_id} 进行准备"
                )

    # ------------------------------------------------------------
    # 幂等 commit
    # ------------------------------------------------------------
    def commit(self, tx_id: str) -> None:
        """幂等的 commit 操作

        - COMMITTED: 直接返回（无副作用）
        - PREPARED: 执行 commit，转为 COMMITTED
        - COMMITTING: 等待（在本实现中直接重试执行）
        - INIT/PREPARING: 非法
        - ABORTED/PREPARE_FAILED: 非法（已中止不应再提交）
        """
        with self._lock:
            ctx = self._get_or_create_context(tx_id)

            if ctx.state == ParticipantState.COMMITTED:
                ctx.commit_count += 1
                return

            if ctx.state in (
                ParticipantState.ABORTED,
                ParticipantState.PREPARE_FAILED,
                ParticipantState.COMMIT_FAILED,
            ):
                raise TransactionStateError(
                    f"参与者 {self._id} 处于 {ctx.state.value}，对事务 {tx_id} 不能 commit"
                )
            if ctx.state not in (
                ParticipantState.PREPARED,
                ParticipantState.COMMITTING,
            ):
                raise TransactionStateError(
                    f"参与者 {self._id} 处于非法状态 {ctx.state.value} 进行 commit，需要先 prepare"
                )

            previous_state = ctx.state
            ctx.state = ParticipantState.COMMITTING
            ctx.commit_count += 1

            try:
                if self._on_commit is not None:
                    self._on_commit(tx_id)
                ctx.state = ParticipantState.COMMITTED
            except Exception as exc:
                if previous_state == ParticipantState.COMMITTING:
                    ctx.state = ParticipantState.COMMIT_FAILED
                else:
                    ctx.state = previous_state
                raise CommitFailedError(
                    f"参与者 {self._id} 提交事务 {tx_id} 失败：{exc}"
                ) from exc

    # ------------------------------------------------------------
    # 幂等 abort
    # ------------------------------------------------------------
    def abort(self, tx_id: str) -> None:
        """幂等的 abort 操作

        - ABORTED: 直接返回（无副作用）
        - PREPARED/INIT/PREPARING/PREPARE_FAILED: 执行 abort，转为 ABORTED
        - COMMITTED: 非法（已提交不应再中止）
        """
        with self._lock:
            ctx = self._get_or_create_context(tx_id)

            if ctx.state == ParticipantState.ABORTED:
                ctx.abort_count += 1
                return

            if ctx.state == ParticipantState.COMMITTED:
                raise TransactionStateError(
                    f"参与者 {self._id} 对事务 {tx_id} 已提交，不能 abort"
                )

            valid_states = (
                ParticipantState.INIT,
                ParticipantState.PREPARING,
                ParticipantState.PREPARED,
                ParticipantState.PREPARE_FAILED,
                ParticipantState.ABORTING,
                ParticipantState.COMMIT_FAILED,
            )
            if ctx.state not in valid_states:
                raise TransactionStateError(
                    f"参与者 {self._id} 处于非法状态 {ctx.state.value} 进行 abort"
                )

            previous_state = ctx.state
            ctx.state = ParticipantState.ABORTING
            ctx.abort_count += 1

            try:
                if self._on_abort is not None:
                    self._on_abort(tx_id)
                ctx.state = ParticipantState.ABORTED
            except Exception as exc:
                ctx.state = previous_state
                raise AbortFailedError(
                    f"参与者 {self._id} 中止事务 {tx_id} 失败：{exc}"
                ) from exc

    # ------------------------------------------------------------
    # 统计 & 调试
    # ------------------------------------------------------------
    def get_call_count(self, tx_id: str) -> Dict[str, int]:
        ctx = self.get_context(tx_id)
        return {
            "prepare": ctx.prepare_count,
            "commit": ctx.commit_count,
            "abort": ctx.abort_count,
        }
