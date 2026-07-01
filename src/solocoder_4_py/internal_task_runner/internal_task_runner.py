from __future__ import annotations

import threading
import time
import traceback
from collections import deque
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
    - 周期任务（PERIODIC）
    - 手动触发任务（MANUAL）
    - 完整运行历史记录与查询
    - 可注入时间提供者，便于测试（不依赖真实等待）
    - 线程安全操作
    """

    def __init__(
        self,
        time_provider: Optional[Callable[[], float]] = None,
        history_limit: int = DEFAULT_HISTORY_LIMIT,
    ) -> None:
        """
        Args:
            time_provider: 可注入的时间提供者函数，默认使用 time.time()
                          测试时可传入自定义函数以模拟时间流逝
            history_limit: 每个任务的运行历史最大保留条数
        """
        self._tasks: Dict[str, TaskRuntimeInfo] = {}
        self._history: Dict[str, Deque[TaskRunRecord]] = {}
        self._tag_index: Dict[str, Set[str]] = {}
        self._time_provider: Callable[[], float] = time_provider or time.time
        self._history_limit = history_limit
        self._lock = threading.RLock()
        self._run_count_total = 0
        self._success_count_total = 0
        self._failure_count_total = 0
        self._skip_count_total = 0

    # ------------------------------------------------------------------
    # 时间辅助方法
    # ------------------------------------------------------------------
    def _now(self) -> float:
        return self._time_provider()

    def set_time_provider(self, time_provider: Callable[[], float]) -> None:
        """设置自定义时间提供者（用于测试）"""
        with self._lock:
            self._time_provider = time_provider

    # ------------------------------------------------------------------
    # 任务注册与注销
    # ------------------------------------------------------------------
    def register(self, definition: TaskDefinition) -> TaskRuntimeInfo:
        """注册任务

        Args:
            definition: 任务定义

        Returns:
            任务运行时信息

        Raises:
            TaskAlreadyRegisteredError: 如果任务已存在
            InvalidScheduleError: 如果调度参数非法
        """
        with self._lock:
            task_id = definition.task_id
            if task_id in self._tasks:
                raise TaskAlreadyRegisteredError(task_id)

            if definition.is_periodic() and definition.interval_seconds is None:
                raise InvalidScheduleError("周期任务必须指定 interval_seconds")

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

    def resume(self, task_id: str) -> TaskRuntimeInfo:
        """恢复暂停的周期任务

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
            if info.status != TaskStatus.PAUSED:
                raise TaskStateError(task_id, info.status.value, "resume")

            now = self._now()
            info.status = TaskStatus.ACTIVE
            info.next_run_at = now + (info.definition.interval_seconds or 0)
            info.paused_at = None
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
            return info

    # ------------------------------------------------------------------
    # 手动触发任务（MANUAL 类型）
    # ------------------------------------------------------------------
    def trigger(self, task_id: str, **kwargs: Any) -> TaskRunRecord:
        """手动触发一个任务执行

        - MANUAL 类型：任何状态下（非终态）都可以手动触发
        - ONE_SHOT / PERIODIC：也允许手动触发，但必须在 ACTIVE 状态

        Args:
            task_id: 任务ID
            **kwargs: 传递给任务 handler 的参数

        Returns:
            本次运行记录

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

        此方法检查所有 ACTIVE 状态的任务：
        - ONE_SHOT: 首次 tick 时执行一次，执行后标记 COMPLETED
        - PERIODIC: 到达 next_run_at 时执行，更新 next_run_at

        Returns:
            本次 tick 中产生的运行记录列表

        注意：测试时配合时间注入，无需真实等待。
        """
        records: List[TaskRunRecord] = []
        with self._lock:
            now = self._now()
            task_ids = list(self._tasks.keys())

        for task_id in task_ids:
            with self._lock:
                if task_id not in self._tasks:
                    continue
                info = self._tasks[task_id]
                if info.status != TaskStatus.ACTIVE:
                    continue

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
                        info.next_run_at += definition.interval_seconds or 0
                        if info.next_run_at <= now2:
                            info.next_run_at = now2 + (definition.interval_seconds or 0)

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

    def _execute_single_run(
        self,
        info: TaskRuntimeInfo,
        trigger: str,
        extra_kwargs: Optional[Dict[str, Any]] = None,
    ) -> TaskRunRecord:
        """执行单次任务运行（含重试逻辑）

        注意：此方法内部对 info 的更新需要持有锁的调用方保证外部一致性，
        但 handler 调用期间锁会被释放以避免阻塞。
        """
        definition = info.definition
        task_id = definition.task_id
        kwargs = dict(extra_kwargs or {})

        max_retries = definition.max_retries
        attempt = 0
        last_error: Optional[Exception] = None
        last_record: Optional[TaskRunRecord] = None

        while True:
            attempt += 1
            started_at = self._now()

            try:
                result = definition.handler(**kwargs)
                finished_at = self._now()
                record = TaskRunRecord(
                    task_id=task_id,
                    status=RunStatus.SUCCESS,
                    started_at=started_at,
                    finished_at=finished_at,
                    result=result,
                    attempt=attempt,
                    trigger=trigger,
                )
                last_record = record
                last_error = None
                break
            except Exception as e:
                finished_at = self._now()
                last_error = e

                if attempt <= max_retries:
                    continue

                record = TaskRunRecord(
                    task_id=task_id,
                    status=RunStatus.FAILED,
                    started_at=started_at,
                    finished_at=finished_at,
                    error_message=str(e),
                    error_type=type(e).__name__,
                    attempt=attempt,
                    trigger=trigger,
                )
                last_record = record
                break

        assert last_record is not None

        with self._lock:
            self._append_history(task_id, last_record)

            if task_id in self._tasks:
                info = self._tasks[task_id]
                info.last_run_at = last_record.started_at
                info.run_count += 1
                self._run_count_total += 1

                if last_record.is_success:
                    info.success_count += 1
                    self._success_count_total += 1
                    info.last_error = None
                elif last_record.is_failed:
                    info.failure_count += 1
                    self._failure_count_total += 1
                    info.last_error = last_record.error_message
                    if definition.is_one_shot():
                        info.status = TaskStatus.ERROR
                else:
                    info.skip_count += 1
                    self._skip_count_total += 1

        if last_record.is_failed and last_error is not None:
            info.last_error = last_record.error_message

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
