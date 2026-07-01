from __future__ import annotations

import threading
import time
import traceback
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from typing import Any, Callable, Deque, Dict, Iterable, List, Optional, Set, Tuple

from .constants import (
    DEFAULT_HISTORY_LIMIT,
    DEFAULT_TIMEOUT_SECONDS,
    TERMINAL_TASK_STATUSES,
    RunStatus,
    TaskStatus,
    TaskType,
)
from .exceptions import (
    InvalidScheduleError,
    TaskAlreadyRegisteredError,
    TaskExecutionError,
    TaskNotFoundError,
    TaskStateError,
    TaskTypeError,
)
from .task_definition import TaskDefinition, TaskRuntimeInfo
from .task_run_record import TaskRunRecord


@dataclass
class TaskRunnerStats:
    """任务运行器统计信息"""

    total_tasks: int = 0
    pending_tasks: int = 0
    active_tasks: int = 0
    paused_tasks: int = 0
    completed_tasks: int = 0
    cancelled_tasks: int = 0
    error_tasks: int = 0
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    skipped_runs: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_tasks": self.total_tasks,
            "pending_tasks": self.pending_tasks,
            "active_tasks": self.active_tasks,
            "paused_tasks": self.paused_tasks,
            "completed_tasks": self.completed_tasks,
            "cancelled_tasks": self.cancelled_tasks,
            "error_tasks": self.error_tasks,
            "total_runs": self.total_runs,
            "successful_runs": self.successful_runs,
            "failed_runs": self.failed_runs,
            "skipped_runs": self.skipped_runs,
        }


class InternalTaskRunner:
    """内部任务运行器

    使用纯内存数据结构管理任务定义和运行记录，支持：
    - 一次性任务（ONE_SHOT）
    - 周期任务（PERIODIC），支持暂停/恢复与追赶补偿（catch_up）
    - 手动触发任务（MANUAL）
    - 完整运行历史记录与查询
    - 可注入 time_provider / sleep_provider，便于测试（不依赖真实等待）
    - handler 超时中断（ThreadPoolExecutor + Future.result(timeout)）
    - 重试间延迟（retry_delay_seconds + 可注入 sleep_provider）
    - 终态竞态防护：执行前再次校验终态 → 写入 SKIPPED 记录
    - 线程安全操作
    """

    def __init__(
        self,
        time_provider: Optional[Callable[[], float]] = None,
        sleep_provider: Optional[Callable[[float], None]] = None,
        history_limit: int = DEFAULT_HISTORY_LIMIT,
    ) -> None:
        """
        Args:
            time_provider: 可注入的时间提供者函数，默认使用 time.time()
            sleep_provider: 可注入的睡眠函数，默认使用 time.sleep()。
                           测试时可传入 no-op 或 FakeClock 的 advance 包装，
                           以避免真实等待。
            history_limit: 每个任务的运行历史最大保留条数
        """
        self._tasks: Dict[str, TaskRuntimeInfo] = {}
        self._history: Dict[str, Deque[TaskRunRecord]] = {}
        self._tag_index: Dict[str, Set[str]] = {}
        self._time_provider: Callable[[], float] = time_provider or time.time
        self._sleep_provider: Callable[[float], None] = sleep_provider or time.sleep
        self._history_limit = history_limit
        self._lock = threading.RLock()
        self._run_count_total = 0
        self._success_count_total = 0
        self._failure_count_total = 0
        self._skip_count_total = 0
        self._executor = ThreadPoolExecutor(thread_name_prefix="solo-task-runner")

    # ------------------------------------------------------------------
    # 时间/睡眠辅助
    # ------------------------------------------------------------------
    def _now(self) -> float:
        return self._time_provider()

    def _sleep(self, seconds: float) -> None:
        if seconds <= 0:
            return
        self._sleep_provider(seconds)

    def set_time_provider(self, time_provider: Callable[[], float]) -> None:
        """设置自定义时间提供者（用于测试）"""
        with self._lock:
            self._time_provider = time_provider

    def set_sleep_provider(self, sleep_provider: Callable[[float], None]) -> None:
        """设置自定义睡眠提供者（用于测试重试延迟）"""
        with self._lock:
            self._sleep_provider = sleep_provider

    def shutdown(self, wait: bool = True) -> None:
        """关闭内部线程池"""
        self._executor.shutdown(wait=wait)

    # ------------------------------------------------------------------
    # 任务注册与注销
    # ------------------------------------------------------------------
    def register(self, definition: TaskDefinition) -> TaskRuntimeInfo:
        """注册任务

        说明：PERIODIC 任务的 interval_seconds 校验已在 TaskDefinition.__post_init__
             中完成，此处不再重复检查。

        Args:
            definition: 任务定义

        Returns:
            任务运行时信息

        Raises:
            TaskAlreadyRegisteredError: 如果任务已存在
        """
        with self._lock:
            task_id = definition.task_id
            if task_id in self._tasks:
                raise TaskAlreadyRegisteredError(task_id)

            runtime_info = TaskRuntimeInfo(
                definition=definition,
                status=TaskStatus.PENDING,
                registered_at=self._now(),
            )

            self._tasks[task_id] = runtime_info
            self._history[task_id] = deque(maxlen=self._history_limit)
            self._build_tag_index(task_id, definition)

            return runtime_info

    def unregister(self, task_id: str) -> bool:
        """注销任务

        Args:
            task_id: 任务ID

        Returns:
            True 如果成功注销，False 如果任务不存在
        """
        with self._lock:
            if task_id not in self._tasks:
                return False

            definition = self._tasks[task_id].definition
            self._remove_tag_index(task_id, definition)
            del self._tasks[task_id]
            del self._history[task_id]
            return True

    def has_task(self, task_id: str) -> bool:
        """检查任务是否已注册"""
        with self._lock:
            return task_id in self._tasks

    def get_task(self, task_id: str) -> TaskRuntimeInfo:
        """获取任务运行时信息

        Raises:
            TaskNotFoundError: 如果任务不存在
        """
        with self._lock:
            return self._get_task_or_raise(task_id)

    def get_definition(self, task_id: str) -> TaskDefinition:
        """获取任务定义

        Raises:
            TaskNotFoundError: 如果任务不存在
        """
        with self._lock:
            return self._get_task_or_raise(task_id).definition

    # ------------------------------------------------------------------
    # 任务生命周期控制
    # ------------------------------------------------------------------
    def activate(self, task_id: str) -> TaskRuntimeInfo:
        """激活任务

        - ONE_SHOT: 标记为 ACTIVE，将在下次 tick 时执行
        - PERIODIC: 标记为 ACTIVE，设置下次运行时间
        - MANUAL: 标记为 ACTIVE，允许手动触发

        Args:
            task_id: 任务ID

        Returns:
            更新后的任务运行时信息

        Raises:
            TaskNotFoundError, TaskStateError
        """
        with self._lock:
            info = self._get_task_or_raise(task_id)
            if info.status in TERMINAL_TASK_STATUSES:
                raise TaskStateError(task_id, info.status.value, "activate")
            if info.status == TaskStatus.ACTIVE:
                raise TaskStateError(task_id, info.status.value, "activate")

            now = self._now()
            info.status = TaskStatus.ACTIVE
            info.activated_at = now
            info.paused_at = None
            info.catch_up = False

            definition = info.definition
            if definition.is_periodic():
                info.next_run_at = now + (definition.interval_seconds or 0)

            return info

    def pause(self, task_id: str) -> TaskRuntimeInfo:
        """暂停周期任务

        Args:
            task_id: 任务ID

        Returns:
            更新后的任务运行时信息

        Raises:
            TaskNotFoundError, TaskStateError, TaskTypeError
        """
        with self._lock:
            info = self._get_task_or_raise(task_id)
            if not info.definition.is_periodic():
                raise TaskTypeError(
                    task_id, TaskType.PERIODIC.value, info.definition.task_type.value
                )
            if info.status != TaskStatus.ACTIVE:
                raise TaskStateError(task_id, info.status.value, "pause")

            info.status = TaskStatus.PAUSED
            info.paused_at = self._now()
            return info

    def resume(self, task_id: str, catch_up: bool = False) -> TaskRuntimeInfo:
        """恢复暂停的周期任务

        Args:
            task_id: 任务ID
            catch_up: 是否启用追赶补偿。
                - False（默认）：next_run_at 重置为 ``now + interval_seconds``，
                  丢弃暂停期间应执行的所有周期。适合心跳、最新状态同步等任务。
                - True：保留原 next_run_at，后续 tick() 将按原调度逐周期补跑，
                  直到追上当前时间。适合每日结算、数据同步等不可遗漏的任务。
                  为避免一次 tick 执行过多，追赶采用逐次 tick 每次执行一周期
                  的方式，不会瞬间爆发大量运行。

        Returns:
            更新后的任务运行时信息

        Raises:
            TaskNotFoundError, TaskStateError, TaskTypeError
        """
        with self._lock:
            info = self._get_task_or_raise(task_id)
            if not info.definition.is_periodic():
                raise TaskTypeError(
                    task_id, TaskType.PERIODIC.value, info.definition.task_type.value
                )
            if info.status != TaskStatus.PAUSED:
                raise TaskStateError(task_id, info.status.value, "resume")

            now = self._now()
            info.status = TaskStatus.ACTIVE
            info.paused_at = None

            if catch_up:
                info.catch_up = True
                if info.next_run_at is None:
                    info.next_run_at = now + (info.definition.interval_seconds or 0)
            else:
                info.catch_up = False
                info.next_run_at = now + (info.definition.interval_seconds or 0)

            return info

    def cancel(self, task_id: str) -> TaskRuntimeInfo:
        """取消任务

        Args:
            task_id: 任务ID

        Returns:
            更新后的任务运行时信息

        Raises:
            TaskNotFoundError, TaskStateError
        """
        with self._lock:
            info = self._get_task_or_raise(task_id)
            if info.status in TERMINAL_TASK_STATUSES:
                raise TaskStateError(task_id, info.status.value, "cancel")

            info.status = TaskStatus.CANCELLED
            info.cancelled_at = self._now()
            return info

    def reset(self, task_id: str) -> TaskRuntimeInfo:
        """重置已完成/取消/出错的任务为 PENDING 状态

        Args:
            task_id: 任务ID

        Returns:
            更新后的任务运行时信息

        Raises:
            TaskNotFoundError, TaskStateError
        """
        with self._lock:
            info = self._get_task_or_raise(task_id)
            if info.status not in TERMINAL_TASK_STATUSES:
                raise TaskStateError(task_id, info.status.value, "reset")

            info.status = TaskStatus.PENDING
            info.activated_at = None
            info.paused_at = None
            info.completed_at = None
            info.cancelled_at = None
            info.next_run_at = None
            info.last_error = None
            info.catch_up = False
            return info

    # ------------------------------------------------------------------
    # 手动触发任务（MANUAL 类型）
    # ------------------------------------------------------------------
    def trigger(self, task_id: str, **kwargs: Any) -> TaskRunRecord:
        """手动触发一个任务执行

        说明：为避免「状态校验 → handler 执行」间的竞态（窗口期被 cancel），
             实际的终态二次校验在 ``_execute_single_run`` 入口处持锁完成。

        Args:
            task_id: 任务ID
            **kwargs: 传递给任务 handler 的参数

        Returns:
            本次运行记录（可能是 SUCCESS / FAILED / SKIPPED）

        Raises:
            TaskNotFoundError, TaskStateError
        """
        with self._lock:
            info = self._get_task_or_raise(task_id)

            definition = info.definition
            if definition.is_manual():
                if info.status in TERMINAL_TASK_STATUSES:
                    raise TaskStateError(task_id, info.status.value, "trigger")
            else:
                if info.status != TaskStatus.ACTIVE:
                    raise TaskStateError(task_id, info.status.value, "trigger")

        return self._execute_single_run(info, trigger="MANUAL", extra_kwargs=kwargs)

    # ------------------------------------------------------------------
    # Tick 调度（推进调度器，处理到期任务）
    # ------------------------------------------------------------------
    def tick(self) -> List[TaskRunRecord]:
        """推进调度器，处理到期的任务

        对所有 ACTIVE 状态的任务：
        - ONE_SHOT：首次 tick 时执行一次，执行后标记 COMPLETED（失败则 ERROR）
        - PERIODIC：到达 ``next_run_at`` 时执行
            - 默认模式：若落后多个周期，跳跃到 ``now + interval``，避免爆发式补跑
            - 追赶模式（``catch_up=True``）：每次 tick 补跑一个周期，直到追上 now

        Returns:
            本次 tick 中产生的运行记录列表

        注意：测试时配合时间注入，无需真实等待。
        """
        records: List[TaskRunRecord] = []
        with self._lock:
            task_ids = list(self._tasks.keys())

        for task_id in task_ids:
            with self._lock:
                if task_id not in self._tasks:
                    continue
                info = self._tasks[task_id]
                if info.status != TaskStatus.ACTIVE:
                    continue

                now = self._now()
                definition = info.definition
                should_run = False

                if definition.is_one_shot():
                    if info.last_run_at is None:
                        should_run = True
                elif definition.is_periodic():
                    if info.next_run_at is not None and now >= info.next_run_at:
                        should_run = True

                if not should_run:
                    continue

            record = self._execute_single_run(info, trigger="SCHEDULE")
            records.append(record)

            with self._lock:
                if task_id not in self._tasks:
                    continue
                info = self._tasks[task_id]
                now2 = self._now()
                if definition.is_one_shot() and info.status == TaskStatus.ACTIVE:
                    info.status = TaskStatus.COMPLETED
                    info.completed_at = now2
                elif definition.is_periodic() and info.status == TaskStatus.ACTIVE:
                    if info.next_run_at is not None:
                        interval = definition.interval_seconds or 0
                        info.next_run_at += interval
                        # 追赶模式（catch_up）：每次只前进一个 interval，
                        # 留给下一次 tick 继续补跑，避免单次 tick 爆发执行。
                        # 非追赶模式：若仍然落后，则直接跳到 now + interval。
                        if not info.catch_up and info.next_run_at <= now2:
                            info.next_run_at = now2 + interval
                        # 如果 catch_up 已追平（next_run_at > now），关闭标志
                        if info.catch_up and info.next_run_at > now2:
                            info.catch_up = False

        return records

    # ------------------------------------------------------------------
    # 运行历史查询
    # ------------------------------------------------------------------
    def get_run_history(
        self,
        task_id: str,
        limit: Optional[int] = None,
        status_filter: Optional[RunStatus] = None,
        since: Optional[float] = None,
        until: Optional[float] = None,
    ) -> List[TaskRunRecord]:
        """查询任务的运行历史

        Args:
            task_id: 任务ID
            limit: 最大返回条数（None 表示返回全部）
            status_filter: 按运行状态过滤
            since: 起始时间戳（包含）
            until: 结束时间戳（包含）

        Returns:
            运行记录列表（按时间倒序，最新在前）

        Raises:
            TaskNotFoundError
        """
        with self._lock:
            self._get_task_or_raise(task_id)
            records = list(self._history.get(task_id, []))

        filtered = []
        for r in records:
            if status_filter is not None and r.status != status_filter:
                continue
            if since is not None and r.started_at < since:
                continue
            if until is not None and r.started_at > until:
                continue
            filtered.append(r)

        filtered.sort(key=lambda r: r.started_at, reverse=True)

        if limit is not None:
            filtered = filtered[:limit]

        return filtered

    def get_latest_run(self, task_id: str) -> Optional[TaskRunRecord]:
        """获取任务的最近一次运行记录

        Raises:
            TaskNotFoundError
        """
        history = self.get_run_history(task_id, limit=1)
        return history[0] if history else None

    def get_run_by_id(self, task_id: str, run_id: str) -> Optional[TaskRunRecord]:
        """根据 run_id 查找指定任务的某次运行记录

        Raises:
            TaskNotFoundError
        """
        with self._lock:
            self._get_task_or_raise(task_id)
            for record in self._history.get(task_id, []):
                if record.run_id == run_id:
                    return record
        return None

    # ------------------------------------------------------------------
    # 任务列表与查询
    # ------------------------------------------------------------------
    def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        task_type: Optional[TaskType] = None,
        tag: Optional[str] = None,
    ) -> List[TaskRuntimeInfo]:
        """列出任务，支持按状态/类型/标签过滤"""
        with self._lock:
            task_ids: Optional[Set[str]] = None

            if tag is not None:
                task_ids = set(self._tag_index.get(tag, set()))

            if task_ids is None:
                task_ids = set(self._tasks.keys())

            result: List[TaskRuntimeInfo] = []
            for tid in task_ids:
                info = self._tasks.get(tid)
                if info is None:
                    continue
                if status is not None and info.status != status:
                    continue
                if task_type is not None and info.definition.task_type != task_type:
                    continue
                result.append(info)

            return sorted(result, key=lambda r: r.definition.task_id)

    def find_by_tag(self, tag: str) -> List[TaskRuntimeInfo]:
        """按标签查找任务"""
        return self.list_tasks(tag=tag)

    def find_by_tags(
        self, tags: Iterable[str], match_all: bool = True
    ) -> List[TaskRuntimeInfo]:
        """按多个标签查找任务

        Args:
            tags: 标签列表
            match_all: True 表示所有标签都要有，False 表示满足任意一个即可
        """
        tag_list = list(tags)
        if not tag_list:
            return []

        candidates = self.list_tasks()
        if match_all:
            return [t for t in candidates if t.definition.has_all_tags(tag_list)]
        else:
            return [t for t in candidates if t.definition.has_any_tag(tag_list)]

    def get_all_tags(self) -> List[str]:
        """获取所有已注册的标签"""
        with self._lock:
            return sorted(self._tag_index.keys())

    # ------------------------------------------------------------------
    # 统计信息
    # ------------------------------------------------------------------
    def get_stats(self) -> TaskRunnerStats:
        """获取任务运行器统计信息"""
        with self._lock:
            total = len(self._tasks)
            pending = active = paused = completed = cancelled = error = 0

            for info in self._tasks.values():
                s = info.status
                if s == TaskStatus.PENDING:
                    pending += 1
                elif s == TaskStatus.ACTIVE:
                    active += 1
                elif s == TaskStatus.PAUSED:
                    paused += 1
                elif s == TaskStatus.COMPLETED:
                    completed += 1
                elif s == TaskStatus.CANCELLED:
                    cancelled += 1
                elif s == TaskStatus.ERROR:
                    error += 1

            return TaskRunnerStats(
                total_tasks=total,
                pending_tasks=pending,
                active_tasks=active,
                paused_tasks=paused,
                completed_tasks=completed,
                cancelled_tasks=cancelled,
                error_tasks=error,
                total_runs=self._run_count_total,
                successful_runs=self._success_count_total,
                failed_runs=self._failure_count_total,
                skipped_runs=self._skip_count_total,
            )

    # ------------------------------------------------------------------
    # 批量操作
    # ------------------------------------------------------------------
    def activate_all(self) -> Dict[str, bool]:
        """激活所有 PENDING 状态的任务

        Returns:
            {task_id: 是否成功激活}
        """
        with self._lock:
            results: Dict[str, bool] = {}
            for task_id in list(self._tasks.keys()):
                try:
                    self.activate(task_id)
                    results[task_id] = True
                except Exception:
                    results[task_id] = False
            return results

    def cancel_all(self) -> Dict[str, bool]:
        """取消所有非终态任务

        Returns:
            {task_id: 是否成功取消}
        """
        with self._lock:
            results: Dict[str, bool] = {}
            for task_id in list(self._tasks.keys()):
                try:
                    self.cancel(task_id)
                    results[task_id] = True
                except Exception:
                    results[task_id] = False
            return results

    def clear(self) -> int:
        """清空所有任务

        Returns:
            清除的任务数量
        """
        with self._lock:
            count = len(self._tasks)
            self._tasks.clear()
            self._history.clear()
            self._tag_index.clear()
            self._run_count_total = 0
            self._success_count_total = 0
            self._failure_count_total = 0
            self._skip_count_total = 0
            return count

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------
    def _get_task_or_raise(self, task_id: str) -> TaskRuntimeInfo:
        info = self._tasks.get(task_id)
        if info is None:
            raise TaskNotFoundError(task_id)
        return info

    def _build_tag_index(self, task_id: str, definition: TaskDefinition) -> None:
        for tag in definition.tags:
            if tag not in self._tag_index:
                self._tag_index[tag] = set()
            self._tag_index[tag].add(task_id)

    def _remove_tag_index(self, task_id: str, definition: TaskDefinition) -> None:
        for tag in definition.tags:
            if tag in self._tag_index:
                self._tag_index[tag].discard(task_id)
                if not self._tag_index[tag]:
                    del self._tag_index[tag]

    def _append_history(self, task_id: str, record: TaskRunRecord) -> None:
        if task_id not in self._history:
            self._history[task_id] = deque(maxlen=self._history_limit)
        self._history[task_id].append(record)

    def _commit_run_record(self, task_id: str, record: TaskRunRecord) -> None:
        """将运行记录写入历史、更新计数（必须在锁内调用）"""
        self._append_history(task_id, record)
        task = self._tasks.get(task_id)
        if task is None:
            return

        task.last_run_at = record.started_at
        task.run_count += 1
        self._run_count_total += 1

        if record.is_success:
            task.success_count += 1
            self._success_count_total += 1
            task.last_error = None
        elif record.is_failed:
            task.failure_count += 1
            self._failure_count_total += 1
            task.last_error = record.error_message
            if task.definition.is_one_shot():
                task.status = TaskStatus.ERROR
        else:  # SKIPPED
            task.skip_count += 1
            self._skip_count_total += 1

    def _execute_single_run(
        self,
        info: TaskRuntimeInfo,
        trigger: str,
        extra_kwargs: Optional[Dict[str, Any]] = None,
    ) -> TaskRunRecord:
        """执行单次任务运行

        主要步骤：
        1. **入口终态二次校验**（锁内）：解决 trigger/tick 状态检查与 handler 执行
           之间的竞态窗口。若任务已为终态，直接写入 SKIPPED 记录并返回。
        2. 循环尝试（含重试）：
           a. 读取 handler、超时时间等配置（快照，避免动态替换期间产生不一致）
           b. 若 attempt > 1 且配置了 retry_delay_seconds，在重试前睡眠
           c. 使用 ThreadPoolExecutor.submit 执行 handler，
              future.result(timeout=timeout_seconds) 做超时控制
           d. 成功则构造 SUCCESS 记录并 break
           e. 失败（包括超时）则记录错误，未到 max_retries 则 continue
        3. 写入历史并更新计数（锁内）。

        Args:
            info: 任务运行时信息（传入时由调用方持锁读取，但本函数不依赖外部锁状态）
            trigger: SCHEDULE / MANUAL
            extra_kwargs: 传给 handler 的额外参数
        """
        task_id = info.definition.task_id
        kwargs = dict(extra_kwargs or {})

        # ================================================================
        # 步骤 1：入口终态二次校验 —— 修复竞态窗口（#4）
        # ================================================================
        with self._lock:
            now_entry = self._now()
            current = self._tasks.get(task_id)
            if current is None:
                # 任务在窗口期被注销，记录 SKIPPED（无 handler 可执行）
                record = TaskRunRecord(
                    task_id=task_id,
                    status=RunStatus.SKIPPED,
                    started_at=now_entry,
                    finished_at=now_entry,
                    error_message="任务已被注销，跳过执行",
                    attempt=1,
                    trigger=trigger,
                )
                return record

            if current.status in TERMINAL_TASK_STATUSES:
                # 任务在窗口期被取消/完成，记录 SKIPPED
                record = TaskRunRecord(
                    task_id=task_id,
                    status=RunStatus.SKIPPED,
                    started_at=now_entry,
                    finished_at=now_entry,
                    error_message=f"任务已为终态 {current.status.value}，跳过执行",
                    attempt=1,
                    trigger=trigger,
                )
                self._commit_run_record(task_id, record)
                return record

            definition_snapshot = current.definition

        # ================================================================
        # 步骤 2：循环尝试（含重试 / 超时 / 重试延迟）
        # ================================================================
        max_retries = definition_snapshot.max_retries
        retry_delay = max(0.0, definition_snapshot.retry_delay_seconds or 0.0)
        timeout = (
            definition_snapshot.timeout_seconds
            if definition_snapshot.timeout_seconds is not None
            and definition_snapshot.timeout_seconds > 0
            else None
        )

        attempt = 0
        last_record: Optional[TaskRunRecord] = None

        while True:
            attempt += 1

            # 重试前的延迟（不阻塞首次执行，修复 #1 后半）
            if attempt > 1 and retry_delay > 0:
                self._sleep(retry_delay)

            started_at = self._now()

            # —— 执行 handler（带超时控制，修复 #1 前半）——
            result: Any = None
            exc: Optional[BaseException] = None
            timed_out = False

            try:
                if timeout is not None:
                    future: Future = self._executor.submit(
                        definition_snapshot.handler, **kwargs
                    )
                    try:
                        result = future.result(timeout=timeout)
                    except FuturesTimeoutError:
                        # 尝试取消（Python 线程无法被强制 kill，但可以标记取消）
                        future.cancel()
                        timed_out = True
                        raise TimeoutError(
                            f"任务 handler 执行超时（>{timeout}s）"
                        )
                else:
                    result = definition_snapshot.handler(**kwargs)
            except BaseException as e:  # noqa: BLE001 —— 捕获所有异常，包括用户 handler 的 BaseException
                exc = e

            finished_at = self._now()

            if exc is None:
                last_record = TaskRunRecord(
                    task_id=task_id,
                    status=RunStatus.SUCCESS,
                    started_at=started_at,
                    finished_at=finished_at,
                    result=result,
                    attempt=attempt,
                    trigger=trigger,
                )
                break

            # —— 异常分支：判断是否重试 ——
            error_type = type(exc).__name__
            error_msg = str(exc)
            if timed_out:
                error_type = "TimeoutError"
                error_msg = error_msg or f"任务 handler 执行超时（>{timeout}s）"

            if attempt <= max_retries:
                # 继续重试
                continue

            last_record = TaskRunRecord(
                task_id=task_id,
                status=RunStatus.FAILED,
                started_at=started_at,
                finished_at=finished_at,
                error_message=error_msg,
                error_type=error_type,
                attempt=attempt,
                trigger=trigger,
            )
            break

        assert last_record is not None

        # ================================================================
        # 步骤 3：提交运行记录（锁内）
        # ================================================================
        with self._lock:
            # 再次确认任务仍存在（可能在执行期间被注销）
            if task_id in self._tasks:
                self._commit_run_record(task_id, last_record)
            else:
                self._append_history(task_id, last_record)

        return last_record

    # ------------------------------------------------------------------
    # 魔法方法
    # ------------------------------------------------------------------
    def __contains__(self, task_id: str) -> bool:
        return self.has_task(task_id)

    def __len__(self) -> int:
        with self._lock:
            return len(self._tasks)

    def __iter__(self):
        with self._lock:
            return iter(sorted(self._tasks.keys()))
