import time
import uuid
from dataclasses import dataclass, field
from threading import Lock
from typing import Callable, Dict, List, Optional, Set

from .constants import (
    ParticipantState,
    TERMINAL_TRANSACTION_STATES,
    TransactionState,
)
from .exceptions import (
    CommitFailedError,
    ParticipantAlreadyRegisteredError,
    PrepareFailedError,
    TimeoutDecisionAbortedError,
    TransactionNotFoundError,
    TransactionStateError,
)
from .participant import TransactionParticipant


@dataclass
class TransactionContext:
    """协调器视角下的事务上下文"""
    tx_id: str
    state: TransactionState = TransactionState.INIT
    participants: Dict[str, TransactionParticipant] = field(default_factory=dict)
    participants_order: List[str] = field(default_factory=list)
    prepared_participants: Set[str] = field(default_factory=set)
    failed_participants: Set[str] = field(default_factory=set)
    committed_participants: Set[str] = field(default_factory=set)
    aborted_participants: Set[str] = field(default_factory=set)
    abort_failed_participants: Set[str] = field(default_factory=set)
    prepare_started_at: Optional[float] = None
    final_decision_made: bool = False
    decision: Optional[TransactionState] = None
    errors: List[str] = field(default_factory=list)


class TransactionCoordinator:
    """事务协调器

    实现两阶段提交（2PC）：
      阶段一 Prepare: 要求所有参与者锁定资源并应答 YES/NO
      阶段二 Commit/Abort: 基于阶段一结果统一决策

    特性：
      * prepare 阶段超时（未在限定时间内收到所有 YES）→ 决策 Abort
      * 终态事务重复调用稳定返回（幂等）
      * 参与者重复 prepare/commit/abort 由参与者自身保证幂等
    """

    def __init__(
        self,
        prepare_timeout_seconds: float = 30.0,
        clock: Optional[Callable[[], float]] = None,
    ) -> None:
        if prepare_timeout_seconds <= 0:
            raise ValueError("prepare_timeout_seconds 必须为正数")
        self._prepare_timeout = prepare_timeout_seconds
        self._clock = clock if clock is not None else time.monotonic
        self._transactions: Dict[str, TransactionContext] = {}
        self._lock = Lock()

    # ------------------------------------------------------------
    # 基础 API
    # ------------------------------------------------------------
    def begin_transaction(self, tx_id: Optional[str] = None) -> str:
        """开启一个新事务并返回事务 ID"""
        if tx_id is None:
            tx_id = f"tx-{uuid.uuid4().hex}"
        with self._lock:
            if tx_id in self._transactions:
                raise ValueError(f"事务 {tx_id} 已存在")
            ctx = TransactionContext(tx_id=tx_id)
            self._transactions[tx_id] = ctx
            return tx_id

    def register_participant(
        self,
        tx_id: str,
        participant: TransactionParticipant,
    ) -> None:
        """向事务注册参与者

        仅允许在 INIT / PREPARING 阶段注册（prepare 开始前）。
        """
        with self._lock:
            ctx = self._require_transaction(tx_id)
            if ctx.state not in (TransactionState.INIT, TransactionState.PREPARING):
                raise TransactionStateError(
                    f"事务 {tx_id} 已处于 {ctx.state.value}，不能再注册参与者"
                )
            pid = participant.participant_id
            if pid in ctx.participants:
                raise ParticipantAlreadyRegisteredError(
                    f"参与者 {pid} 已在事务 {tx_id} 中注册"
                )
            ctx.participants[pid] = participant
            ctx.participants_order.append(pid)

    def get_transaction_state(self, tx_id: str) -> TransactionState:
        with self._lock:
            return self._require_transaction(tx_id).state

    def get_participants(self, tx_id: str) -> List[str]:
        with self._lock:
            return list(self._require_transaction(tx_id).participants_order)

    # ------------------------------------------------------------
    # 阶段一：Prepare
    # ------------------------------------------------------------
    def prepare_transaction(self, tx_id: str) -> bool:
        """执行阶段一：准备所有参与者

        :returns: True 表示所有参与者均成功准备；False 表示存在失败/超时
        """
        with self._lock:
            ctx = self._require_transaction(tx_id)

            if ctx.final_decision_made:
                if ctx.decision == TransactionState.PREPARED:
                    return True
                if ctx.decision in (
                    TransactionState.ABORTED,
                    TransactionState.TIMEOUT_ABORTED,
                ):
                    return False
                raise TransactionStateError(
                    f"事务 {tx_id} 已决策为 {ctx.decision.value}，不能再执行 prepare"
                )

            if ctx.state not in (
                TransactionState.INIT,
                TransactionState.PREPARING,
                TransactionState.PREPARED,
            ):
                raise TransactionStateError(
                    f"事务 {tx_id} 处于 {ctx.state.value}，不能执行 prepare"
                )

            if not ctx.participants:
                ctx.state = TransactionState.PREPARED
                return True

            ctx.state = TransactionState.PREPARING
            if ctx.prepare_started_at is None:
                ctx.prepare_started_at = self._clock()

        all_prepared = True
        timed_out = False
        for pid in list(ctx.participants_order):
            with self._lock:
                ctx = self._transactions[tx_id]
                if ctx.final_decision_made:
                    if ctx.decision == TransactionState.TIMEOUT_ABORTED:
                        timed_out = True
                    break
                if self._check_prepare_timeout_locked(ctx):
                    timed_out = True
                    all_prepared = False
                    break
                participant = ctx.participants[pid]
                if pid in ctx.prepared_participants:
                    continue
                if pid in ctx.failed_participants:
                    all_prepared = False
                    continue

            try:
                ok = participant.prepare(tx_id)
            except PrepareFailedError as exc:
                with self._lock:
                    ctx = self._transactions[tx_id]
                    ctx.failed_participants.add(pid)
                    ctx.errors.append(str(exc))
                    if self._check_prepare_timeout_locked(ctx):
                        timed_out = True
                        all_prepared = False
                        break
                all_prepared = False
                continue

            with self._lock:
                ctx = self._transactions[tx_id]
                if ok:
                    ctx.prepared_participants.add(pid)
                else:
                    ctx.failed_participants.add(pid)
                    all_prepared = False

                # 每次参与者 prepare 结束后再次检查超时
                if self._check_prepare_timeout_locked(ctx):
                    timed_out = True
                    all_prepared = False
                    break

        with self._lock:
            ctx = self._transactions[tx_id]
            if timed_out:
                raise TimeoutDecisionAbortedError(
                    f"事务 {tx_id} prepare 阶段超时，已决策中止：{'; '.join(ctx.errors)}"
                )
            if ctx.final_decision_made:
                if ctx.decision == TransactionState.PREPARED:
                    return True
                if ctx.decision in (
                    TransactionState.ABORTED,
                    TransactionState.TIMEOUT_ABORTED,
                ):
                    return False
                raise TransactionStateError(
                    f"事务 {tx_id} 已决策为 {ctx.decision.value}，不能再执行 prepare"
                )

            if all_prepared and len(ctx.prepared_participants) == len(
                ctx.participants
            ):
                ctx.state = TransactionState.PREPARED
                return True
            else:
                ctx.final_decision_made = True
                ctx.decision = TransactionState.ABORTED
                ctx.state = TransactionState.ABORTING
                return False

    # ------------------------------------------------------------
    # 阶段二：Commit
    # ------------------------------------------------------------
    def commit_transaction(self, tx_id: str) -> None:
        """执行阶段二：提交事务

        必须所有参与者均 PREPARED 才能提交（或已经 COMMITTED 幂等返回）。
        """
        with self._lock:
            ctx = self._require_transaction(tx_id)

            if ctx.state == TransactionState.COMMITTED:
                return

            if ctx.final_decision_made and ctx.decision != TransactionState.COMMITTED:
                raise TransactionStateError(
                    f"事务 {tx_id} 已决策为 {ctx.decision.value}，不能 commit"
                )

            if ctx.state not in (TransactionState.PREPARED, TransactionState.COMMITTING):
                raise TransactionStateError(
                    f"事务 {tx_id} 处于 {ctx.state.value}，需要先 prepare 成功才能 commit"
                )

            # 额外安全校验：必须所有参与者均 PREPARED
            missing_prepare = set(ctx.participants.keys()) - ctx.prepared_participants
            if missing_prepare:
                raise TransactionStateError(
                    f"事务 {tx_id} 存在未 PREPARED 参与者 {missing_prepare}，不能 commit"
                )

            ctx.state = TransactionState.COMMITTING

        errors = []
        for pid in list(ctx.participants_order):
            with self._lock:
                ctx = self._transactions[tx_id]
                participant = ctx.participants[pid]
                if pid in ctx.committed_participants:
                    continue
            try:
                participant.commit(tx_id)
                with self._lock:
                    ctx = self._transactions[tx_id]
                    ctx.committed_participants.add(pid)
            except Exception as exc:
                errors.append(f"参与者 {pid} commit 失败：{exc}")
                with self._lock:
                    ctx = self._transactions[tx_id]
                    ctx.errors.append(str(exc))

        with self._lock:
            ctx = self._transactions[tx_id]
            if errors:
                # 一旦进入 COMMITTING 即视为最终决策为 COMMITTED
                ctx.final_decision_made = True
                ctx.decision = TransactionState.COMMITTED
                ctx.state = TransactionState.COMMITTED
                raise CommitFailedError(
                    f"事务 {tx_id} 部分参与者 commit 失败：{'; '.join(errors)}"
                )
            ctx.final_decision_made = True
            ctx.decision = TransactionState.COMMITTED
            ctx.state = TransactionState.COMMITTED

    # ------------------------------------------------------------
    # 阶段二：Abort
    # ------------------------------------------------------------
    def abort_transaction(self, tx_id: str) -> None:
        """执行阶段二：中止事务

        幂等：已经 ABORTED/TIMEOUT_ABORTED 的事务直接返回。

        注意：若某参与者 abort 回调失败，该参与者会被标记到 abort_failed_participants，
        协调器保持 ABORTING 状态。调用者需通过 retry_abort() 重试，直到所有参与者
        成功 abort（协调器转为 ABORTED）。
        """
        with self._lock:
            ctx = self._require_transaction(tx_id)

            if ctx.state in (
                TransactionState.ABORTED,
                TransactionState.TIMEOUT_ABORTED,
            ):
                return

            if ctx.final_decision_made and ctx.decision == TransactionState.COMMITTED:
                raise TransactionStateError(
                    f"事务 {tx_id} 已决策为 COMMITTED，不能 abort"
                )

            if ctx.state not in (
                TransactionState.INIT,
                TransactionState.PREPARING,
                TransactionState.PREPARED,
                TransactionState.ABORTING,
            ):
                raise TransactionStateError(
                    f"事务 {tx_id} 处于 {ctx.state.value}，不能 abort"
                )

            ctx.state = TransactionState.ABORTING
            if not ctx.final_decision_made:
                ctx.final_decision_made = True
                ctx.decision = TransactionState.ABORTED

        self._do_abort_participants(tx_id, list(ctx.participants_order))

    def _do_abort_participants(self, tx_id: str, pids_to_abort: List[str]) -> bool:
        """执行具体的参与者 abort 操作

        :returns: True 表示所有指定参与者均 abort 成功；False 表示存在失败
        """
        all_success = True
        for pid in pids_to_abort:
            with self._lock:
                ctx = self._transactions[tx_id]
                participant = ctx.participants[pid]
                if pid in ctx.aborted_participants:
                    ctx.abort_failed_participants.discard(pid)
                    continue
            try:
                participant.abort(tx_id)
                with self._lock:
                    ctx = self._transactions[tx_id]
                    ctx.aborted_participants.add(pid)
                    ctx.abort_failed_participants.discard(pid)
            except Exception as exc:
                all_success = False
                with self._lock:
                    ctx = self._transactions[tx_id]
                    ctx.abort_failed_participants.add(pid)
                    ctx.errors.append(f"参与者 {pid} abort 失败：{exc}")

        with self._lock:
            ctx = self._transactions[tx_id]
            if ctx.state == TransactionState.ABORTING and not ctx.abort_failed_participants:
                if ctx.decision == TransactionState.TIMEOUT_ABORTED:
                    ctx.state = TransactionState.TIMEOUT_ABORTED
                else:
                    ctx.state = TransactionState.ABORTED

        return all_success

    def retry_abort(self, tx_id: str) -> bool:
        """重试 abort 那些之前失败的参与者

        :returns: True 表示所有参与者均已成功 abort（事务进入 ABORTED）
                   False 表示仍有参与者 abort 失败（保持 ABORTING）
        """
        with self._lock:
            ctx = self._require_transaction(tx_id)

            if ctx.state in (
                TransactionState.ABORTED,
                TransactionState.TIMEOUT_ABORTED,
            ):
                return True

            if ctx.state != TransactionState.ABORTING:
                raise TransactionStateError(
                    f"事务 {tx_id} 处于 {ctx.state.value}，不在 ABORTING 阶段，不能 retry_abort"
                )

            failed_pids = list(ctx.abort_failed_participants)
            if not failed_pids:
                if ctx.state == TransactionState.ABORTING:
                    ctx.state = TransactionState.ABORTED
                return True

        return self._do_abort_participants(tx_id, failed_pids)

    def has_incomplete_abort(self, tx_id: str) -> bool:
        """查询是否存在未成功 abort 的参与者"""
        with self._lock:
            ctx = self._require_transaction(tx_id)
            return bool(ctx.abort_failed_participants)

    def get_abort_failed_participants(self, tx_id: str) -> List[str]:
        """查询 abort 失败、需要重试的参与者 ID 列表"""
        with self._lock:
            ctx = self._require_transaction(tx_id)
            return sorted(ctx.abort_failed_participants)

    # ------------------------------------------------------------
    # 一键执行
    # ------------------------------------------------------------
    def execute_transaction(self, tx_id: str) -> TransactionState:
        """完整执行 2PC 流程（prepare → commit/abort）

        :returns: 最终事务状态
        :raises TimeoutDecisionAbortedError: prepare 阶段超时，决策中止
        :raises CommitFailedError: commit 阶段部分参与者提交失败（事务仍标记为 COMMITTED）
        :raises TransactionStateError: 状态机非法转换等错误
        """
        # 已处于终态的事务直接返回（幂等）
        with self._lock:
            ctx = self._require_transaction(tx_id)
            if ctx.state in TERMINAL_TRANSACTION_STATES:
                return ctx.state

        try:
            prepared = self.prepare_transaction(tx_id)
        except TimeoutDecisionAbortedError:
            self.abort_transaction(tx_id)
            with self._lock:
                ctx = self._transactions.get(tx_id)
                return ctx.state if ctx else TransactionState.ABORTED

        if prepared:
            # commit_transaction 内部已处理 COMMITTED 幂等返回，
            # 若抛出 CommitFailedError 或 TransactionStateError 则由调用者处理
            self.commit_transaction(tx_id)
        else:
            self.abort_transaction(tx_id)

        return self.get_transaction_state(tx_id)

    # ------------------------------------------------------------
    # 超时判定
    # ------------------------------------------------------------
    def _check_prepare_timeout_locked(self, ctx: TransactionContext) -> bool:
        if ctx.prepare_started_at is None:
            return False
        if self._clock() - ctx.prepare_started_at > self._prepare_timeout:
            if not ctx.final_decision_made:
                ctx.final_decision_made = True
                ctx.decision = TransactionState.TIMEOUT_ABORTED
                ctx.state = TransactionState.ABORTING
                ctx.errors.append(
                    f"prepare 阶段超时（>{self._prepare_timeout}s），决策中止"
                )
            return True
        return False

    def _require_transaction(self, tx_id: str) -> TransactionContext:
        ctx = self._transactions.get(tx_id)
        if ctx is None:
            raise TransactionNotFoundError(f"事务 {tx_id} 不存在")
        return ctx
