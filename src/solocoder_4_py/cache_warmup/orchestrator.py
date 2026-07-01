import time
from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock
from typing import Any, Callable, Dict, List, Optional, Set

from .constants import (
    FailureStrategy,
    TaskState,
    TERMINAL_TASK_STATES,
    TERMINAL_WARMUP_STATES,
    WarmupState,
)
from .exceptions import (
    CircularDependencyError,
    DependencyNotFoundError,
    TaskAlreadyRegisteredError,
    TaskExecutionError,
    TaskNotFoundError,
    WarmupStateError,
)
from .progress import TaskProgress, WarmupProgress
from .task import WarmupTask
from .topology import TopologySorter


@dataclass
class WarmupContext:
    """编排器视角下的预热上下文"""
    run_id: str
    tasks: Dict[str, WarmupTask] = field(default_factory=dict)
    task_order: List[str] = field(default_factory=list)
    cache_store: Dict[str, Any] = field(default_factory=dict)
    progress: WarmupProgress = field(default_factory=WarmupProgress)
    failure_strategy: FailureStrategy = FailureStrategy.SKIP_DEPENDENTS
    aborted: bool = False
    errors: List[str] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class WarmupOrchestrator:
    """缓存预热编排器

    负责编排多个预热任务的执行顺序，处理依赖关系、失败策略和进度追踪。
    使用内存字典模拟缓存存储。
    """

    def __init__(
        self,
        failure_strategy: FailureStrategy = FailureStrategy.SKIP_DEPENDENTS,
        clock: Optional[Callable[[], float]] = None,
    ) -> None:
        self._default_failure_strategy = failure_strategy
        self._clock = clock if clock is not None else time.monotonic
        self._contexts: Dict[str, WarmupContext] = {}
        self._lock = Lock()

    # ------------------------------------------------------------
    # 基础 API：任务注册
    # ------------------------------------------------------------
    def create_warmup_run(
        self,
        run_id: Optional[str] = None,
        failure_strategy: Optional[FailureStrategy] = None,
    ) -> str:
        """创建一个预热流程实例

        :param run_id: 可选的自定义流程 ID
        :param failure_strategy: 可选的失败策略，覆盖默认值
        :returns: 预热 run_id
        """
        if run_id is None:
            import uuid
            run_id = f"warmup-{uuid.uuid4().hex[:12]}"

        with self._lock:
            if run_id in self._contexts:
                raise ValueError(f"预热流程 {run_id} 已存在")

            strategy = (
                failure_strategy
                if failure_strategy is not None
                else self._default_failure_strategy
            )
            ctx = WarmupContext(run_id=run_id, failure_strategy=strategy)
            self._contexts[run_id] = ctx
            return run_id

    def register_task(self, run_id: str, task: WarmupTask) -> None:
        """向预热流程注册一个任务

        :raises TaskAlreadyRegisteredError: 任务 ID 重复
        :raises WarmupStateError: 流程已启动，不能再注册
        """
        with self._lock:
            ctx = self._require_context(run_id)
            if ctx.progress.state != WarmupState.NOT_STARTED:
                raise WarmupStateError(
                    f"预热流程 {run_id} 已处于 {ctx.progress.state.value} 状态，"
                    f"不能再注册任务"
                )
            if task.task_id in ctx.tasks:
                raise TaskAlreadyRegisteredError(
                    f"任务 {task.task_id} 已在预热流程 {run_id} 中注册"
                )
            ctx.tasks[task.task_id] = task
            ctx.progress.task_progress[task.task_id] = TaskProgress(task_id=task.task_id)

    def register_tasks(self, run_id: str, tasks: List[WarmupTask]) -> None:
        """批量注册任务"""
        for task in tasks:
            self.register_task(run_id, task)

    def get_cached_data(self, run_id: str, task_id: str) -> Any:
        """获取已加载到缓存中的数据"""
        with self._lock:
            ctx = self._require_context(run_id)
            return ctx.cache_store.get(task_id)

    def get_all_cached_data(self, run_id: str) -> Dict[str, Any]:
        """获取所有缓存数据的副本"""
        with self._lock:
            ctx = self._require_context(run_id)
            return dict(ctx.cache_store)

    # ------------------------------------------------------------
    # 查询 API
    # ------------------------------------------------------------
    def get_warmup_state(self, run_id: str) -> WarmupState:
        with self._lock:
            return self._require_context(run_id).progress.state

    def get_progress(self, run_id: str) -> WarmupProgress:
        with self._lock:
            ctx = self._require_context(run_id)
            return self._snapshot_progress(ctx)

    def get_task_progress(self, run_id: str, task_id: str) -> TaskProgress:
        with self._lock:
            ctx = self._require_context(run_id)
            if task_id not in ctx.progress.task_progress:
                raise TaskNotFoundError(
                    f"任务 {task_id} 不存在于预热流程 {run_id}"
                )
            tp = ctx.progress.task_progress[task_id]
            return TaskProgress(**{
                "task_id": tp.task_id,
                "state": tp.state,
                "started_at": tp.started_at,
                "completed_at": tp.completed_at,
                "error_message": tp.error_message,
                "loaded_data_preview": tp.loaded_data_preview,
                "attempts": tp.attempts,
                "duration_seconds": tp.duration_seconds,
                "extra": dict(tp.extra),
            })

    def get_registered_tasks(self, run_id: str) -> List[str]:
        with self._lock:
            ctx = self._require_context(run_id)
            return list(ctx.tasks.keys())

    # ------------------------------------------------------------
    # 核心：执行预热
    # ------------------------------------------------------------
    def execute_warmup(self, run_id: str) -> WarmupProgress:
        """执行完整的预热流程

        1. 校验依赖并做拓扑排序
        2. 按序执行每个任务
        3. 处理失败策略
        4. 更新进度和最终状态

        :returns: 最终的预热进度快照
        """
        ctx = self._prepare_execution(run_id)

        if ctx.progress.state in TERMINAL_WARMUP_STATES:
            return self._snapshot_progress(ctx)

        skip_set: Set[str] = set()
        fail_set: Set[str] = set()

        for task_id in ctx.task_order:
            if ctx.aborted:
                break

            task = ctx.tasks[task_id]
            tp = ctx.progress.task_progress[task_id]

            if task_id in skip_set:
                with self._lock:
                    reason = self._build_skip_reason(ctx, task, fail_set)
                    tp.mark_skipped(reason)
                    ctx.progress.skipped_tasks += 1
                continue

            if not self._dependencies_ready(task, fail_set, skip_set):
                with self._lock:
                    reason = self._build_skip_reason(ctx, task, fail_set)
                    tp.mark_skipped(reason)
                    ctx.progress.skipped_tasks += 1
                    skip_set.add(task_id)
                continue

            self._run_single_task(ctx, task_id, task, tp, fail_set, skip_set)

        return self._finalize_warmup(run_id)

    # ------------------------------------------------------------
    # 内部实现
    # ------------------------------------------------------------
    def _prepare_execution(self, run_id: str) -> WarmupContext:
        with self._lock:
            ctx = self._require_context(run_id)

            if ctx.progress.state in TERMINAL_WARMUP_STATES:
                return ctx

            if ctx.progress.state == WarmupState.RUNNING:
                raise WarmupStateError(
                    f"预热流程 {run_id} 正在运行中"
                )

            try:
                ctx.task_order = TopologySorter.sort(ctx.tasks)
            except (CircularDependencyError, DependencyNotFoundError) as e:
                ctx.progress.state = WarmupState.FAILED
                ctx.errors.append(str(e))
                raise

            ctx.progress.total_tasks = len(ctx.tasks)
            ctx.progress.state = WarmupState.RUNNING
            ctx.progress.pending_tasks = len(ctx.tasks)
            ctx.progress.started_at = datetime.now()
            ctx.started_at = ctx.progress.started_at
            return ctx

    def _run_single_task(
        self,
        ctx: WarmupContext,
        task_id: str,
        task: WarmupTask,
        tp: TaskProgress,
        fail_set: Set[str],
        skip_set: Set[str],
    ) -> None:
        with self._lock:
            tp.mark_running()
            ctx.progress.pending_tasks -= 1
            ctx.progress.running_tasks += 1

        start_ts = self._clock()
        try:
            loaded_data = task.execute_load()
            duration = self._clock() - start_ts

            preview = self._make_preview(loaded_data)

            with self._lock:
                ctx.cache_store[task_id] = loaded_data
                tp.mark_completed(duration, preview)
                ctx.progress.running_tasks -= 1
                ctx.progress.completed_tasks += 1
        except Exception as exc:
            duration = self._clock() - start_ts
            error_msg = f"{type(exc).__name__}: {exc}"

            with self._lock:
                tp.mark_failed(duration, error_msg)
                ctx.progress.running_tasks -= 1
                ctx.progress.failed_tasks += 1
                fail_set.add(task_id)
                ctx.errors.append(f"任务 {task_id} 失败: {error_msg}")

            self._handle_failure(ctx, task_id, fail_set, skip_set)

    def _handle_failure(
        self,
        ctx: WarmupContext,
        failed_task_id: str,
        fail_set: Set[str],
        skip_set: Set[str],
    ) -> None:
        strategy = ctx.failure_strategy

        if strategy == FailureStrategy.ABORT_ALL:
            with self._lock:
                ctx.aborted = True
            return

        if strategy == FailureStrategy.SKIP_DEPENDENTS:
            downstream = TopologySorter.get_all_downstream(ctx.tasks, failed_task_id)
            with self._lock:
                for ds_id in downstream:
                    if ds_id not in skip_set and ds_id not in fail_set:
                        skip_set.add(ds_id)

    def _dependencies_ready(
        self,
        task: WarmupTask,
        fail_set: Set[str],
        skip_set: Set[str],
    ) -> bool:
        for dep in task.dependencies:
            if dep in fail_set or dep in skip_set:
                return False
        return True

    def _build_skip_reason(
        self,
        ctx: WarmupContext,
        task: WarmupTask,
        fail_set: Set[str],
    ) -> str:
        failed_deps = [d for d in task.dependencies if d in fail_set]
        if failed_deps:
            return f"依赖任务失败: {', '.join(failed_deps)}"
        skipped_deps = [
            d for d in task.dependencies
            if ctx.progress.task_progress[d].state == TaskState.SKIPPED
        ]
        if skipped_deps:
            return f"依赖任务被跳过: {', '.join(skipped_deps)}"
        return "失败策略导致跳过"

    @staticmethod
    def _make_preview(data: Any, max_len: int = 100) -> str:
        if data is None:
            return "None"
        try:
            s = repr(data)
        except Exception:
            s = f"<{type(data).__name__}>"
        if len(s) > max_len:
            s = s[:max_len] + "..."
        return s

    def _finalize_warmup(self, run_id: str) -> WarmupProgress:
        with self._lock:
            ctx = self._require_context(run_id)

            if ctx.progress.state in TERMINAL_WARMUP_STATES:
                return self._snapshot_progress(ctx)

            if ctx.aborted:
                for task_id, tp in ctx.progress.task_progress.items():
                    if tp.state == TaskState.PENDING:
                        tp.mark_skipped("流程中止，任务未执行")
                        ctx.progress.skipped_tasks += 1

            ctx.progress.recalculate_counts()
            ctx.progress.completed_at = datetime.now()
            ctx.completed_at = ctx.progress.completed_at

            total = ctx.progress.total_tasks
            completed = ctx.progress.completed_tasks
            failed = ctx.progress.failed_tasks
            skipped = ctx.progress.skipped_tasks

            if ctx.aborted:
                ctx.progress.state = WarmupState.FAILED
            elif failed == 0 and skipped == 0 and completed == total:
                ctx.progress.state = WarmupState.COMPLETED
            elif completed > 0 and (failed > 0 or skipped > 0):
                ctx.progress.state = WarmupState.PARTIAL_COMPLETED
            else:
                ctx.progress.state = WarmupState.FAILED

            return self._snapshot_progress(ctx)

    @staticmethod
    def _snapshot_progress(ctx: WarmupContext) -> WarmupProgress:
        tasks_snapshot = {
            tid: TaskProgress(**{
                "task_id": tp.task_id,
                "state": tp.state,
                "started_at": tp.started_at,
                "completed_at": tp.completed_at,
                "error_message": tp.error_message,
                "loaded_data_preview": tp.loaded_data_preview,
                "attempts": tp.attempts,
                "duration_seconds": tp.duration_seconds,
                "extra": dict(tp.extra),
            })
            for tid, tp in ctx.progress.task_progress.items()
        }
        return WarmupProgress(
            total_tasks=ctx.progress.total_tasks,
            completed_tasks=ctx.progress.completed_tasks,
            failed_tasks=ctx.progress.failed_tasks,
            skipped_tasks=ctx.progress.skipped_tasks,
            running_tasks=ctx.progress.running_tasks,
            pending_tasks=ctx.progress.pending_tasks,
            state=ctx.progress.state,
            started_at=ctx.progress.started_at,
            completed_at=ctx.progress.completed_at,
            task_progress=tasks_snapshot,
        )

    def _require_context(self, run_id: str) -> WarmupContext:
        ctx = self._contexts.get(run_id)
        if ctx is None:
            raise TaskNotFoundError(f"预热流程 {run_id} 不存在")
        return ctx
