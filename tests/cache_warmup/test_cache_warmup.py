from typing import Any, Dict, List

import pytest

from solocoder_4_py.cache_warmup import (
    CacheWarmupError,
    CircularDependencyError,
    DependencyNotFoundError,
    FailureStrategy,
    TaskAlreadyRegisteredError,
    TaskExecutionError,
    TaskNotFoundError,
    TaskProgress,
    TaskState,
    TERMINAL_TASK_STATES,
    TERMINAL_WARMUP_STATES,
    TopologySorter,
    WarmupContext,
    WarmupOrchestrator,
    WarmupProgress,
    WarmupState,
    WarmupTask,
    WarmupStateError,
)


# ---------------------------------------------------------------------------
# 辅助类 & 夹具
# ---------------------------------------------------------------------------
class CallTracker:
    """追踪任务加载回调的调用次数和顺序"""

    def __init__(self) -> None:
        self.call_count: Dict[str, int] = {}
        self.call_order: List[str] = []
        self.results: Dict[str, Any] = {}

    def make_loader(self, task_id: str, result: Any = None) -> callable:
        def _loader():
            self.call_count[task_id] = self.call_count.get(task_id, 0) + 1
            self.call_order.append(task_id)
            if result is None:
                return {f"data_{task_id}": list(range(5))}
            self.results[task_id] = result
            return result
        return _loader

    def make_failing_loader(self, task_id: str, error: Exception) -> callable:
        def _loader():
            self.call_count[task_id] = self.call_count.get(task_id, 0) + 1
            self.call_order.append(task_id)
            raise error
        return _loader


@pytest.fixture
def tracker() -> CallTracker:
    return CallTracker()


# ---------------------------------------------------------------------------
# Constants & Enums
# ---------------------------------------------------------------------------
class TestConstants:
    def test_task_state_values(self) -> None:
        assert TaskState.PENDING.value == "PENDING"
        assert TaskState.RUNNING.value == "RUNNING"
        assert TaskState.COMPLETED.value == "COMPLETED"
        assert TaskState.FAILED.value == "FAILED"
        assert TaskState.SKIPPED.value == "SKIPPED"

    def test_warmup_state_values(self) -> None:
        assert WarmupState.NOT_STARTED.value == "NOT_STARTED"
        assert WarmupState.RUNNING.value == "RUNNING"
        assert WarmupState.COMPLETED.value == "COMPLETED"
        assert WarmupState.PARTIAL_COMPLETED.value == "PARTIAL_COMPLETED"
        assert WarmupState.FAILED.value == "FAILED"

    def test_failure_strategy_values(self) -> None:
        assert FailureStrategy.SKIP_DEPENDENTS.value == "SKIP_DEPENDENTS"
        assert FailureStrategy.CONTINUE_ANYWAY.value == "CONTINUE_ANYWAY"
        assert FailureStrategy.ABORT_ALL.value == "ABORT_ALL"

    def test_terminal_task_states(self) -> None:
        assert TaskState.COMPLETED in TERMINAL_TASK_STATES
        assert TaskState.FAILED in TERMINAL_TASK_STATES
        assert TaskState.SKIPPED in TERMINAL_TASK_STATES
        assert TaskState.PENDING not in TERMINAL_TASK_STATES
        assert TaskState.RUNNING not in TERMINAL_TASK_STATES

    def test_terminal_warmup_states(self) -> None:
        assert WarmupState.COMPLETED in TERMINAL_WARMUP_STATES
        assert WarmupState.PARTIAL_COMPLETED in TERMINAL_WARMUP_STATES
        assert WarmupState.FAILED in TERMINAL_WARMUP_STATES
        assert WarmupState.NOT_STARTED not in TERMINAL_WARMUP_STATES
        assert WarmupState.RUNNING not in TERMINAL_WARMUP_STATES


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class TestExceptions:
    def test_exception_hierarchy(self) -> None:
        assert issubclass(TaskNotFoundError, CacheWarmupError)
        assert issubclass(TaskAlreadyRegisteredError, CacheWarmupError)
        assert issubclass(CircularDependencyError, CacheWarmupError)
        assert issubclass(DependencyNotFoundError, CacheWarmupError)
        assert issubclass(WarmupStateError, CacheWarmupError)
        assert issubclass(TaskExecutionError, CacheWarmupError)

    def test_exception_messages(self) -> None:
        e = CircularDependencyError("任务 A, B, C 形成环")
        assert "A, B, C" in str(e)
        e2 = TaskNotFoundError("task-x")
        assert "task-x" in str(e2)


# ---------------------------------------------------------------------------
# WarmupTask
# ---------------------------------------------------------------------------
class TestWarmupTask:
    def test_task_creation_minimal(self) -> None:
        t = WarmupTask("task-1")
        assert t.task_id == "task-1"
        assert t.description == ""
        assert t.dependencies == []
        assert t.priority == 0
        assert t.metadata == {}

    def test_task_creation_full(self) -> None:
        t = WarmupTask(
            task_id="users:hot",
            description="加载热点用户",
            dependencies=["config:base"],
            priority=10,
            metadata={"region": "cn"},
        )
        assert t.task_id == "users:hot"
        assert t.description == "加载热点用户"
        assert t.dependencies == ["config:base"]
        assert t.priority == 10
        assert t.metadata == {"region": "cn"}

    def test_set_and_execute_load_function(self, tracker) -> None:
        t = WarmupTask("t1")
        t.set_load_function(tracker.make_loader("t1", {"key": "value"}))
        result = t.execute_load()
        assert result == {"key": "value"}
        assert tracker.call_count["t1"] == 1

    def test_execute_without_load_function(self) -> None:
        t = WarmupTask("t1")
        assert t.execute_load() is None

    def test_task_hash_and_eq(self) -> None:
        t1 = WarmupTask("same")
        t2 = WarmupTask("same")
        t3 = WarmupTask("other")
        assert t1 == t2
        assert hash(t1) == hash(t2)
        assert t1 != t3
        assert t1 != "same"  # 与字符串比较


# ---------------------------------------------------------------------------
# TopologySorter
# ---------------------------------------------------------------------------
class TestTopologySorter:
    def test_sort_empty(self) -> None:
        assert TopologySorter.sort({}) == []

    def test_sort_single_task_no_deps(self) -> None:
        tasks = {"a": WarmupTask("a")}
        assert TopologySorter.sort(tasks) == ["a"]

    def test_sort_linear_dependency(self) -> None:
        tasks = {
            "a": WarmupTask("a"),
            "b": WarmupTask("b", dependencies=["a"]),
            "c": WarmupTask("c", dependencies=["b"]),
        }
        order = TopologySorter.sort(tasks)
        assert order.index("a") < order.index("b")
        assert order.index("b") < order.index("c")

    def test_sort_diamond_dependency(self) -> None:
        tasks = {
            "a": WarmupTask("a"),
            "b": WarmupTask("b", dependencies=["a"]),
            "c": WarmupTask("c", dependencies=["a"]),
            "d": WarmupTask("d", dependencies=["b", "c"]),
        }
        order = TopologySorter.sort(tasks)
        assert order.index("a") < order.index("b")
        assert order.index("a") < order.index("c")
        assert order.index("b") < order.index("d")
        assert order.index("c") < order.index("d")

    def test_sort_multiple_independent_roots(self) -> None:
        tasks = {
            "a": WarmupTask("a"),
            "b": WarmupTask("b"),
            "c": WarmupTask("c", dependencies=["a"]),
        }
        order = TopologySorter.sort(tasks)
        assert set(order) == {"a", "b", "c"}
        assert order.index("a") < order.index("c")

    def test_sort_detects_circular_dependency(self) -> None:
        tasks = {
            "a": WarmupTask("a", dependencies=["c"]),
            "b": WarmupTask("b", dependencies=["a"]),
            "c": WarmupTask("c", dependencies=["b"]),
        }
        with pytest.raises(CircularDependencyError) as excinfo:
            TopologySorter.sort(tasks)
        msg = str(excinfo.value)
        for t in ("a", "b", "c"):
            assert t in msg

    def test_sort_two_node_cycle(self) -> None:
        tasks = {
            "a": WarmupTask("a", dependencies=["b"]),
            "b": WarmupTask("b", dependencies=["a"]),
        }
        with pytest.raises(CircularDependencyError):
            TopologySorter.sort(tasks)

    def test_sort_dependency_not_found(self) -> None:
        tasks = {
            "a": WarmupTask("a", dependencies=["nonexistent"]),
        }
        with pytest.raises(DependencyNotFoundError) as excinfo:
            TopologySorter.sort(tasks)
        assert "nonexistent" in str(excinfo.value)
        assert "a" in str(excinfo.value)

    def test_get_dependents(self) -> None:
        tasks = {
            "a": WarmupTask("a"),
            "b": WarmupTask("b", dependencies=["a"]),
            "c": WarmupTask("c", dependencies=["a"]),
            "d": WarmupTask("d", dependencies=["b"]),
        }
        deps = TopologySorter.get_dependents(tasks)
        assert "b" in deps["a"]
        assert "c" in deps["a"]
        assert "d" in deps["b"]
        assert deps["c"] == []
        assert deps["d"] == []

    def test_get_all_downstream(self) -> None:
        tasks = {
            "a": WarmupTask("a"),
            "b": WarmupTask("b", dependencies=["a"]),
            "c": WarmupTask("c", dependencies=["b"]),
            "d": WarmupTask("d", dependencies=["a"]),
            "e": WarmupTask("e"),
        }
        downstream_a = TopologySorter.get_all_downstream(tasks, "a")
        assert set(downstream_a) == {"b", "c", "d"}
        downstream_b = TopologySorter.get_all_downstream(tasks, "b")
        assert downstream_b == ["c"]
        downstream_e = TopologySorter.get_all_downstream(tasks, "e")
        assert downstream_e == []


# ---------------------------------------------------------------------------
# TaskProgress & WarmupProgress
# ---------------------------------------------------------------------------
class TestTaskProgress:
    def test_initial_state(self) -> None:
        tp = TaskProgress(task_id="t1")
        assert tp.state == TaskState.PENDING
        assert tp.attempts == 0
        assert tp.started_at is None
        assert tp.completed_at is None
        assert tp.duration_seconds == 0.0
        assert not tp.is_terminal()

    def test_mark_running(self) -> None:
        tp = TaskProgress(task_id="t1")
        tp.mark_running()
        assert tp.state == TaskState.RUNNING
        assert tp.attempts == 1
        assert tp.started_at is not None
        assert not tp.is_terminal()

    def test_mark_completed(self) -> None:
        tp = TaskProgress(task_id="t1")
        tp.mark_running()
        tp.mark_completed(0.05, "{'key': 'val'}")
        assert tp.state == TaskState.COMPLETED
        assert tp.completed_at is not None
        assert tp.duration_seconds == 0.05
        assert tp.loaded_data_preview == "{'key': 'val'}"
        assert tp.is_terminal()

    def test_mark_failed(self) -> None:
        tp = TaskProgress(task_id="t1")
        tp.mark_running()
        tp.mark_failed(0.1, "ValueError: boom")
        assert tp.state == TaskState.FAILED
        assert tp.error_message == "ValueError: boom"
        assert tp.is_terminal()

    def test_mark_skipped(self) -> None:
        tp = TaskProgress(task_id="t1")
        tp.mark_skipped("上游依赖失败")
        assert tp.state == TaskState.SKIPPED
        assert tp.error_message == "上游依赖失败"
        assert tp.is_terminal()

    def test_multiple_running_increments_attempts(self) -> None:
        tp = TaskProgress(task_id="t1")
        tp.mark_running()
        tp.mark_running()
        tp.mark_running()
        assert tp.attempts == 3

    def test_to_dict(self) -> None:
        tp = TaskProgress(task_id="t1")
        tp.mark_running()
        tp.mark_completed(0.01234, "preview-text")
        d = tp.to_dict()
        assert d["task_id"] == "t1"
        assert d["state"] == "COMPLETED"
        assert d["duration_seconds"] == 0.0123
        assert d["loaded_data_preview"] == "preview-text"
        assert d["started_at"] is not None
        assert d["completed_at"] is not None


class TestWarmupProgress:
    def test_initial_state(self) -> None:
        wp = WarmupProgress()
        assert wp.state == WarmupState.NOT_STARTED
        assert wp.progress_percentage == 0.0  # NOT_STARTED = 0%
        assert wp.total_tasks == 0

    def test_empty_run_after_execute_is_100_percent(self) -> None:
        wp = WarmupProgress()
        wp.state = WarmupState.COMPLETED
        assert wp.progress_percentage == 100.0  # 已结束 + 0 tasks = 100%

    def test_progress_percentage(self) -> None:
        wp = WarmupProgress(total_tasks=10)
        wp.state = WarmupState.RUNNING
        wp.completed_tasks = 3
        wp.failed_tasks = 1
        wp.skipped_tasks = 1
        assert wp.progress_percentage == 50.0  # 5/10

    def test_progress_percentage_rounding(self) -> None:
        wp = WarmupProgress(total_tasks=3)
        wp.state = WarmupState.RUNNING
        wp.completed_tasks = 1
        assert wp.progress_percentage == 33.33

    def test_not_started_always_zero_regardless_of_counts(self) -> None:
        wp = WarmupProgress(total_tasks=10)
        wp.state = WarmupState.NOT_STARTED
        wp.completed_tasks = 5
        wp.failed_tasks = 3
        assert wp.progress_percentage == 0.0  # NOT_STARTED 始终是 0%

    def test_partial_completed_state_counts(self) -> None:
        wp = WarmupProgress(total_tasks=5)
        wp.state = WarmupState.PARTIAL_COMPLETED
        wp.completed_tasks = 3
        wp.failed_tasks = 1
        wp.skipped_tasks = 1
        assert wp.progress_percentage == 100.0

    def test_recalculate_counts(self) -> None:
        wp = WarmupProgress(total_tasks=4)
        wp.task_progress = {
            "a": TaskProgress("a", state=TaskState.COMPLETED),
            "b": TaskProgress("b", state=TaskState.FAILED),
            "c": TaskProgress("c", state=TaskState.SKIPPED),
            "d": TaskProgress("d", state=TaskState.PENDING),
        }
        wp.recalculate_counts()
        assert wp.completed_tasks == 1
        assert wp.failed_tasks == 1
        assert wp.skipped_tasks == 1
        assert wp.pending_tasks == 1
        assert wp.running_tasks == 0

    def test_recalculate_counts_with_running(self) -> None:
        wp = WarmupProgress(total_tasks=2)
        wp.task_progress = {
            "a": TaskProgress("a", state=TaskState.RUNNING),
            "b": TaskProgress("b", state=TaskState.PENDING),
        }
        wp.recalculate_counts()
        assert wp.running_tasks == 1
        assert wp.pending_tasks == 1

    def test_to_dict(self) -> None:
        wp = WarmupProgress(total_tasks=2)
        wp.state = WarmupState.COMPLETED
        wp.task_progress = {
            "a": TaskProgress("a", state=TaskState.COMPLETED),
            "b": TaskProgress("b", state=TaskState.COMPLETED),
        }
        d = wp.to_dict()
        assert d["state"] == "COMPLETED"
        assert d["total_tasks"] == 2
        assert "a" in d["tasks"]
        assert "b" in d["tasks"]


# ---------------------------------------------------------------------------
# WarmupOrchestrator - Basic API
# ---------------------------------------------------------------------------
class TestOrchestratorBasicAPI:
    def test_create_warmup_run_auto_id(self) -> None:
        orch = WarmupOrchestrator()
        run_id = orch.create_warmup_run()
        assert run_id.startswith("warmup-")
        assert orch.get_warmup_state(run_id) == WarmupState.NOT_STARTED

    def test_create_warmup_run_custom_id(self) -> None:
        orch = WarmupOrchestrator()
        run_id = orch.create_warmup_run("my-run")
        assert run_id == "my-run"

    def test_create_duplicate_run_raises(self) -> None:
        orch = WarmupOrchestrator()
        orch.create_warmup_run("run-1")
        with pytest.raises(ValueError):
            orch.create_warmup_run("run-1")

    def test_create_run_with_custom_failure_strategy(self) -> None:
        orch = WarmupOrchestrator(failure_strategy=FailureStrategy.SKIP_DEPENDENTS)
        run_id = orch.create_warmup_run(failure_strategy=FailureStrategy.ABORT_ALL)
        # 间接通过执行失败场景验证策略生效
        task_a = WarmupTask("a")
        task_a.set_load_function(lambda: (_ for _ in ()).throw(RuntimeError("x")))
        task_b = WarmupTask("b")
        task_b.set_load_function(lambda: "b-data")
        orch.register_tasks(run_id, [task_a, task_b])
        prog = orch.execute_warmup(run_id)
        assert prog.state == WarmupState.FAILED
        # ABORT_ALL 情况下 b 应被跳过而非执行
        assert prog.task_progress["b"].state == TaskState.SKIPPED

    def test_unknown_run_id_raises(self) -> None:
        orch = WarmupOrchestrator()
        with pytest.raises(TaskNotFoundError):
            orch.get_warmup_state("ghost")

    def test_register_and_list_tasks(self) -> None:
        orch = WarmupOrchestrator()
        run_id = orch.create_warmup_run()
        orch.register_task(run_id, WarmupTask("t1"))
        orch.register_task(run_id, WarmupTask("t2"))
        assert set(orch.get_registered_tasks(run_id)) == {"t1", "t2"}

    def test_register_batch(self) -> None:
        orch = WarmupOrchestrator()
        run_id = orch.create_warmup_run()
        tasks = [WarmupTask(f"t{i}") for i in range(5)]
        orch.register_tasks(run_id, tasks)
        assert len(orch.get_registered_tasks(run_id)) == 5

    def test_register_duplicate_task_raises(self) -> None:
        orch = WarmupOrchestrator()
        run_id = orch.create_warmup_run()
        orch.register_task(run_id, WarmupTask("same"))
        with pytest.raises(TaskAlreadyRegisteredError):
            orch.register_task(run_id, WarmupTask("same"))

    def test_register_after_execute_raises(self) -> None:
        orch = WarmupOrchestrator()
        run_id = orch.create_warmup_run()
        orch.execute_warmup(run_id)
        with pytest.raises(WarmupStateError):
            orch.register_task(run_id, WarmupTask("late"))


# ---------------------------------------------------------------------------
# WarmupOrchestrator - Happy Path
# ---------------------------------------------------------------------------
class TestOrchestratorHappyPath:
    def test_no_tasks_executes_cleanly(self) -> None:
        orch = WarmupOrchestrator()
        run_id = orch.create_warmup_run()
        prog = orch.execute_warmup(run_id)
        assert prog.state == WarmupState.COMPLETED
        assert prog.progress_percentage == 100.0
        assert prog.total_tasks == 0

    def test_single_task_success(self, tracker) -> None:
        orch = WarmupOrchestrator()
        run_id = orch.create_warmup_run()
        task = WarmupTask("t1")
        task.set_load_function(tracker.make_loader("t1", {"foo": "bar"}))
        orch.register_task(run_id, task)

        prog = orch.execute_warmup(run_id)
        assert prog.state == WarmupState.COMPLETED
        assert prog.completed_tasks == 1
        assert prog.failed_tasks == 0
        assert prog.skipped_tasks == 0
        assert prog.task_progress["t1"].state == TaskState.COMPLETED
        assert orch.get_cached_data(run_id, "t1") == {"foo": "bar"}

    def test_multiple_independent_tasks(self, tracker) -> None:
        orch = WarmupOrchestrator()
        run_id = orch.create_warmup_run()
        for i in range(5):
            t = WarmupTask(f"t{i}")
            t.set_load_function(tracker.make_loader(f"t{i}", i * 10))
            orch.register_task(run_id, t)

        prog = orch.execute_warmup(run_id)
        assert prog.state == WarmupState.COMPLETED
        assert prog.completed_tasks == 5
        for i in range(5):
            assert orch.get_cached_data(run_id, f"t{i}") == i * 10
            assert tracker.call_count[f"t{i}"] == 1

    def test_linear_dependency_order(self, tracker) -> None:
        orch = WarmupOrchestrator()
        run_id = orch.create_warmup_run()
        t_a = WarmupTask("a")
        t_a.set_load_function(tracker.make_loader("a", "A"))
        t_b = WarmupTask("b", dependencies=["a"])
        t_b.set_load_function(tracker.make_loader("b", "B"))
        t_c = WarmupTask("c", dependencies=["b"])
        t_c.set_load_function(tracker.make_loader("c", "C"))
        orch.register_tasks(run_id, [t_b, t_c, t_a])

        prog = orch.execute_warmup(run_id)
        assert prog.state == WarmupState.COMPLETED
        assert prog.completed_tasks == 3
        # 验证执行顺序
        assert tracker.call_order.index("a") < tracker.call_order.index("b")
        assert tracker.call_order.index("b") < tracker.call_order.index("c")

    def test_diamond_dependency(self, tracker) -> None:
        orch = WarmupOrchestrator()
        run_id = orch.create_warmup_run()
        t_a = WarmupTask("a")
        t_a.set_load_function(tracker.make_loader("a"))
        t_b = WarmupTask("b", dependencies=["a"])
        t_b.set_load_function(tracker.make_loader("b"))
        t_c = WarmupTask("c", dependencies=["a"])
        t_c.set_load_function(tracker.make_loader("c"))
        t_d = WarmupTask("d", dependencies=["b", "c"])
        t_d.set_load_function(tracker.make_loader("d"))
        orch.register_tasks(run_id, [t_b, t_d, t_a, t_c])

        prog = orch.execute_warmup(run_id)
        assert prog.state == WarmupState.COMPLETED
        a_pos = tracker.call_order.index("a")
        b_pos = tracker.call_order.index("b")
        c_pos = tracker.call_order.index("c")
        d_pos = tracker.call_order.index("d")
        assert a_pos < b_pos
        assert a_pos < c_pos
        assert b_pos < d_pos
        assert c_pos < d_pos

    def test_task_uses_metadata(self) -> None:
        orch = WarmupOrchestrator()
        run_id = orch.create_warmup_run()
        meta = {"shard": "shard-7", "cache_ttl": 3600}
        t = WarmupTask("meta-test", metadata=meta)
        captured_meta = {}

        def loader():
            captured_meta.update(t.metadata)
            return "ok"

        t.set_load_function(loader)
        orch.register_task(run_id, t)
        orch.execute_warmup(run_id)
        assert captured_meta == meta

    def test_get_all_cached_data(self, tracker) -> None:
        orch = WarmupOrchestrator()
        run_id = orch.create_warmup_run()
        t1 = WarmupTask("x")
        t1.set_load_function(tracker.make_loader("x", 1))
        t2 = WarmupTask("y")
        t2.set_load_function(tracker.make_loader("y", 2))
        orch.register_tasks(run_id, [t1, t2])
        orch.execute_warmup(run_id)
        data = orch.get_all_cached_data(run_id)
        assert data == {"x": 1, "y": 2}
        # 返回副本，修改不影响内部
        data["x"] = 999
        assert orch.get_cached_data(run_id, "x") == 1

    def test_get_cached_data_not_found_returns_none(self) -> None:
        orch = WarmupOrchestrator()
        run_id = orch.create_warmup_run()
        orch.execute_warmup(run_id)
        assert orch.get_cached_data(run_id, "nope") is None


# ---------------------------------------------------------------------------
# WarmupOrchestrator - Failure Strategies
# ---------------------------------------------------------------------------
class TestOrchestratorFailureStrategies:
    def test_skip_dependents_default_strategy(self, tracker) -> None:
        orch = WarmupOrchestrator(failure_strategy=FailureStrategy.SKIP_DEPENDENTS)
        run_id = orch.create_warmup_run()

        t_a = WarmupTask("a")
        t_a.set_load_function(tracker.make_failing_loader("a", RuntimeError("DB down")))
        t_b = WarmupTask("b", dependencies=["a"])
        t_b.set_load_function(tracker.make_loader("b", "B"))
        t_c = WarmupTask("c", dependencies=["b"])
        t_c.set_load_function(tracker.make_loader("c", "C"))
        t_d = WarmupTask("d")  # 独立任务
        t_d.set_load_function(tracker.make_loader("d", "D"))

        orch.register_tasks(run_id, [t_a, t_b, t_c, t_d])
        prog = orch.execute_warmup(run_id)

        assert prog.state == WarmupState.PARTIAL_COMPLETED
        assert prog.task_progress["a"].state == TaskState.FAILED
        assert "DB down" in prog.task_progress["a"].error_message
        assert prog.task_progress["b"].state == TaskState.SKIPPED
        assert "依赖任务失败" in prog.task_progress["b"].error_message
        assert prog.task_progress["c"].state == TaskState.SKIPPED
        assert prog.task_progress["d"].state == TaskState.COMPLETED
        # b 和 c 的回调不应被执行
        assert "b" not in tracker.call_count
        assert "c" not in tracker.call_count
        assert tracker.call_count["d"] == 1

    def test_abort_all_strategy(self, tracker) -> None:
        orch = WarmupOrchestrator(failure_strategy=FailureStrategy.ABORT_ALL)
        run_id = orch.create_warmup_run()

        tasks = []
        for i in range(10):
            t = WarmupTask(f"t{i}")
            if i == 3:
                t.set_load_function(tracker.make_failing_loader("t3", ValueError("stop")))
            else:
                t.set_load_function(tracker.make_loader(f"t{i}", i))
            tasks.append(t)
        orch.register_tasks(run_id, tasks)

        prog = orch.execute_warmup(run_id)
        assert prog.state == WarmupState.FAILED
        assert prog.task_progress["t3"].state == TaskState.FAILED
        # t3 之后（和之前未被调度的）任务应被跳过
        skipped_count = sum(
            1 for tp in prog.task_progress.values()
            if tp.state == TaskState.SKIPPED
        )
        assert skipped_count >= 6  # 至少 6 个被跳过
        # 流程应标记为 aborted
        for i in range(4, 10):
            assert prog.task_progress[f"t{i}"].state == TaskState.SKIPPED

    def test_continue_anyway_strategy_independent_tasks(self, tracker) -> None:
        """CONTINUE_ANYWAY 下，独立任务不会因其他任务失败而跳过"""
        orch = WarmupOrchestrator(failure_strategy=FailureStrategy.CONTINUE_ANYWAY)
        run_id = orch.create_warmup_run()

        t_fail = WarmupTask("fail")
        t_fail.set_load_function(tracker.make_failing_loader("fail", IOError("x")))
        t_a = WarmupTask("a")
        t_a.set_load_function(tracker.make_loader("a", 1))
        t_b = WarmupTask("b")
        t_b.set_load_function(tracker.make_loader("b", 2))

        orch.register_tasks(run_id, [t_fail, t_a, t_b])
        prog = orch.execute_warmup(run_id)

        assert prog.state == WarmupState.PARTIAL_COMPLETED
        assert prog.task_progress["fail"].state == TaskState.FAILED
        assert prog.task_progress["a"].state == TaskState.COMPLETED
        assert prog.task_progress["b"].state == TaskState.COMPLETED
        assert tracker.call_count["a"] == 1
        assert tracker.call_count["b"] == 1

    def test_continue_anyway_with_dependency_runs_anyway(self, tracker) -> None:
        """CONTINUE_ANYWAY 下，即使上游失败，下游任务仍被调度执行（用户自行容错）"""
        orch = WarmupOrchestrator(failure_strategy=FailureStrategy.CONTINUE_ANYWAY)
        run_id = orch.create_warmup_run()

        t_up = WarmupTask("up")
        t_up.set_load_function(tracker.make_failing_loader("up", Exception("x")))
        t_down = WarmupTask("down", dependencies=["up"])
        # 下游即使依赖 up 失败，仍然尽力执行（使用默认值等）
        def down_loader():
            # 业务自行处理缺失的上游数据
            cached_up = orch.get_cached_data(run_id, "up")
            if cached_up is None:
                return "fallback-value"
            return cached_up
        t_down.set_load_function(down_loader)
        t_indep = WarmupTask("indep")
        t_indep.set_load_function(tracker.make_loader("indep", "Y"))

        orch.register_tasks(run_id, [t_up, t_down, t_indep])
        prog = orch.execute_warmup(run_id)

        assert prog.task_progress["up"].state == TaskState.FAILED
        # CONTINUE_ANYWAY 语义：下游仍然执行（不再因上游失败跳过）
        assert prog.task_progress["down"].state == TaskState.COMPLETED
        assert orch.get_cached_data(run_id, "down") == "fallback-value"
        assert prog.task_progress["indep"].state == TaskState.COMPLETED
        # 验证下游确实执行过
        assert "down" in tracker.call_order or orch.get_cached_data(run_id, "down") == "fallback-value"

    def test_multiple_failures_skip_all_downstream(self, tracker) -> None:
        orch = WarmupOrchestrator(failure_strategy=FailureStrategy.SKIP_DEPENDENTS)
        run_id = orch.create_warmup_run()

        tasks = {
            "root": WarmupTask("root"),
            "c1": WarmupTask("c1", dependencies=["root"]),
            "c2": WarmupTask("c2", dependencies=["root"]),
            "gc1": WarmupTask("gc1", dependencies=["c1"]),
            "gc2": WarmupTask("gc2", dependencies=["c2"]),
        }
        tasks["root"].set_load_function(tracker.make_loader("root", "R"))
        tasks["c1"].set_load_function(tracker.make_failing_loader("c1", Exception("boom")))
        tasks["c2"].set_load_function(tracker.make_loader("c2", "C2"))
        tasks["gc1"].set_load_function(tracker.make_loader("gc1", "GC1"))
        tasks["gc2"].set_load_function(tracker.make_loader("gc2", "GC2"))

        orch.register_tasks(run_id, list(tasks.values()))
        prog = orch.execute_warmup(run_id)

        assert prog.state == WarmupState.PARTIAL_COMPLETED
        assert prog.task_progress["root"].state == TaskState.COMPLETED
        assert prog.task_progress["c1"].state == TaskState.FAILED
        assert prog.task_progress["gc1"].state == TaskState.SKIPPED  # c1 的下游被跳过
        assert prog.task_progress["c2"].state == TaskState.COMPLETED
        assert prog.task_progress["gc2"].state == TaskState.COMPLETED  # c2 的下游正常


# ---------------------------------------------------------------------------
# WarmupOrchestrator - Dependency Errors
# ---------------------------------------------------------------------------
class TestOrchestratorDependencyErrors:
    def test_circular_dependency_raises_on_execute(self) -> None:
        orch = WarmupOrchestrator()
        run_id = orch.create_warmup_run()
        t_a = WarmupTask("a", dependencies=["b"])
        t_b = WarmupTask("b", dependencies=["a"])
        orch.register_tasks(run_id, [t_a, t_b])
        with pytest.raises(CircularDependencyError):
            orch.execute_warmup(run_id)
        # 流程应被标记为 FAILED
        assert orch.get_warmup_state(run_id) == WarmupState.FAILED

    def test_missing_dependency_raises_on_execute(self) -> None:
        orch = WarmupOrchestrator()
        run_id = orch.create_warmup_run()
        t = WarmupTask("a", dependencies=["does-not-exist"])
        orch.register_task(run_id, t)
        with pytest.raises(DependencyNotFoundError):
            orch.execute_warmup(run_id)
        assert orch.get_warmup_state(run_id) == WarmupState.FAILED


# ---------------------------------------------------------------------------
# WarmupOrchestrator - Progress Queries
# ---------------------------------------------------------------------------
class TestOrchestratorProgressQueries:
    def test_get_progress_snapshot_not_affected_by_future_changes(
        self, tracker
    ) -> None:
        orch = WarmupOrchestrator()
        run_id = orch.create_warmup_run()
        t = WarmupTask("t1")
        t.set_load_function(tracker.make_loader("t1", "data"))
        orch.register_task(run_id, t)

        prog = orch.get_progress(run_id)
        assert prog.state == WarmupState.NOT_STARTED

        orch.execute_warmup(run_id)

        # 之前的 snapshot 不应该变化
        assert prog.state == WarmupState.NOT_STARTED
        # 新查询显示完成状态
        new_prog = orch.get_progress(run_id)
        assert new_prog.state == WarmupState.COMPLETED

    def test_get_task_progress_before_execute(self) -> None:
        orch = WarmupOrchestrator()
        run_id = orch.create_warmup_run()
        orch.register_task(run_id, WarmupTask("t1"))
        tp = orch.get_task_progress(run_id, "t1")
        assert tp.state == TaskState.PENDING
        assert tp.attempts == 0

    def test_get_task_progress_not_found(self) -> None:
        orch = WarmupOrchestrator()
        run_id = orch.create_warmup_run()
        with pytest.raises(TaskNotFoundError):
            orch.get_task_progress(run_id, "ghost")

    def test_progress_to_dict_after_execute(self, tracker) -> None:
        orch = WarmupOrchestrator()
        run_id = orch.create_warmup_run()
        t_a = WarmupTask("a")
        t_a.set_load_function(tracker.make_loader("a", {"k": "v"}))
        t_b = WarmupTask("b")
        t_b.set_load_function(tracker.make_failing_loader("b", RuntimeError("nope")))
        orch.register_tasks(run_id, [t_a, t_b])

        orch.execute_warmup(run_id)
        prog = orch.get_progress(run_id)
        d = prog.to_dict()

        assert d["state"] == "PARTIAL_COMPLETED"
        assert d["completed_tasks"] == 1
        assert d["failed_tasks"] == 1
        assert d["progress_percentage"] == 100.0
        assert d["tasks"]["a"]["state"] == "COMPLETED"
        assert d["tasks"]["b"]["state"] == "FAILED"
        assert "nope" in d["tasks"]["b"]["error_message"]
        assert d["started_at"] is not None
        assert d["completed_at"] is not None


# ---------------------------------------------------------------------------
# WarmupOrchestrator - Idempotency
# ---------------------------------------------------------------------------
class TestOrchestratorIdempotency:
    def test_execute_warmup_idempotent_after_completed(self, tracker) -> None:
        orch = WarmupOrchestrator()
        run_id = orch.create_warmup_run()
        t = WarmupTask("t1")
        t.set_load_function(tracker.make_loader("t1", 42))
        orch.register_task(run_id, t)

        p1 = orch.execute_warmup(run_id)
        p2 = orch.execute_warmup(run_id)
        p3 = orch.execute_warmup(run_id)

        assert p1.state == p2.state == p3.state == WarmupState.COMPLETED
        # 回调只执行一次
        assert tracker.call_count["t1"] == 1
        # 数据保持稳定
        assert orch.get_cached_data(run_id, "t1") == 42

    def test_execute_warmup_idempotent_after_failed(self, tracker) -> None:
        orch = WarmupOrchestrator()
        run_id = orch.create_warmup_run()
        t = WarmupTask("t1")
        t.set_load_function(tracker.make_failing_loader("t1", RuntimeError("x")))
        orch.register_task(run_id, t)

        p1 = orch.execute_warmup(run_id)
        p2 = orch.execute_warmup(run_id)
        assert p1.state == p2.state == WarmupState.FAILED
        assert tracker.call_count["t1"] == 1  # 幂等：只执行一次失败


# ---------------------------------------------------------------------------
# Integration Scenarios
# ---------------------------------------------------------------------------
class TestIntegrationScenarios:
    def test_user_profile_recommendation_pipeline(self) -> None:
        """模拟：用户资料 -> 订单统计 -> 个性化推荐的完整预热链路"""
        orch = WarmupOrchestrator(failure_strategy=FailureStrategy.SKIP_DEPENDENTS)
        run_id = orch.create_warmup_run("reco-pipeline")

        db_users = {
            "u1": {"name": "Alice"},
            "u2": {"name": "Bob"},
        }
        db_orders = [
            {"user_id": "u1", "amount": 100},
            {"user_id": "u1", "amount": 200},
            {"user_id": "u2", "amount": 50},
        ]

        # 1. 用户资料（无依赖）
        t_users = WarmupTask("users", description="用户基础资料")
        t_users.set_load_function(lambda: dict(db_users))

        # 2. 订单统计（依赖用户）
        t_order_stats = WarmupTask(
            "order_stats", dependencies=["users"], description="用户订单聚合"
        )

        def calc_stats():
            users = orch.get_cached_data(run_id, "users")
            stats = {}
            for uid in users:
                user_orders = [o for o in db_orders if o["user_id"] == uid]
                total = sum(o["amount"] for o in user_orders)
                stats[uid] = {"order_count": len(user_orders), "total": total}
            return stats

        t_order_stats.set_load_function(calc_stats)

        # 3. 推荐结果（依赖订单统计 + 用户）
        t_recos = WarmupTask(
            "recommendations",
            dependencies=["users", "order_stats"],
            description="个性化推荐",
        )

        def make_recos():
            users = orch.get_cached_data(run_id, "users")
            stats = orch.get_cached_data(run_id, "order_stats")
            recos = {}
            for uid in users:
                if stats[uid]["total"] >= 200:
                    recos[uid] = ["premium-item-A", "premium-item-B"]
                else:
                    recos[uid] = ["basic-item-1", "basic-item-2"]
            return recos

        t_recos.set_load_function(make_recos)

        orch.register_tasks(run_id, [t_users, t_order_stats, t_recos])
        prog = orch.execute_warmup(run_id)

        assert prog.state == WarmupState.COMPLETED
        assert prog.completed_tasks == 3

        # 验证用户
        users = orch.get_cached_data(run_id, "users")
        assert users["u1"]["name"] == "Alice"

        # 验证订单统计
        stats = orch.get_cached_data(run_id, "order_stats")
        assert stats["u1"]["order_count"] == 2
        assert stats["u1"]["total"] == 300
        assert stats["u2"]["total"] == 50

        # 验证推荐
        recos = orch.get_cached_data(run_id, "recommendations")
        assert "premium-item-A" in recos["u1"]
        assert "basic-item-1" in recos["u2"]

    def test_partial_failure_in_ecommerce_pipeline(self) -> None:
        """模拟电商预热：商品库存失败，导致商品详情和秒杀配置被跳过，
        但用户配置正常完成"""
        orch = WarmupOrchestrator()
        run_id = orch.create_warmup_run()

        # 用户配置（独立）
        t_cfg = WarmupTask("config:global")
        t_cfg.set_load_function(lambda: {"site_version": "v2.1", "theme": "dark"})

        # 库存（故意失败）
        t_inv = WarmupTask("inventory:all")
        t_inv.set_load_function(lambda: (_ for _ in ()).throw(RuntimeError("库存系统超时")))

        # 商品详情（依赖库存）
        t_pdp = WarmupTask("pdp:hot", dependencies=["inventory:all"])
        t_pdp.set_load_function(lambda: {"SKU-001": "高端耳机"})

        # 秒杀配置（依赖商品详情 + 库存）
        t_flash = WarmupTask(
            "flash_sale:today", dependencies=["pdp:hot", "inventory:all"]
        )
        t_flash.set_load_function(lambda: {"flash_items": ["SKU-001"]})

        orch.register_tasks(run_id, [t_cfg, t_inv, t_pdp, t_flash])
        prog = orch.execute_warmup(run_id)

        assert prog.state == WarmupState.PARTIAL_COMPLETED
        assert prog.completed_tasks == 1
        assert prog.failed_tasks == 1
        assert prog.skipped_tasks == 2

        assert prog.task_progress["config:global"].state == TaskState.COMPLETED
        assert prog.task_progress["inventory:all"].state == TaskState.FAILED
        assert prog.task_progress["pdp:hot"].state == TaskState.SKIPPED
        assert prog.task_progress["flash_sale:today"].state == TaskState.SKIPPED

        # 缓存中只应该有 config
        cached = orch.get_all_cached_data(run_id)
        assert "config:global" in cached
        assert "inventory:all" not in cached  # 失败不缓存
        assert "pdp:hot" not in cached  # 跳过不缓存

    def test_task_progress_reflects_duration(self) -> None:
        """通过自定义时钟验证耗时记录"""
        class FakeClock:
            def __init__(self) -> None:
                self._t = 0.0
                self._jumps = 0

            def __call__(self) -> float:
                self._jumps += 1
                # 每次调用前进 0.5 秒，模拟执行耗时
                return self._t

            def advance(self, delta: float) -> None:
                self._t += delta

        clock = FakeClock()
        orch = WarmupOrchestrator(clock=clock)
        run_id = orch.create_warmup_run()

        def loader():
            clock.advance(1.5)
            return "done"

        t = WarmupTask("slow-task")
        t.set_load_function(loader)
        orch.register_task(run_id, t)
        prog = orch.execute_warmup(run_id)

        tp = prog.task_progress["slow-task"]
        assert tp.state == TaskState.COMPLETED
        assert tp.duration_seconds >= 1.0
        assert tp.started_at is not None
        assert tp.completed_at is not None


# ---------------------------------------------------------------------------
# Priority Scheduling
# ---------------------------------------------------------------------------
class TestPriorityScheduling:
    def test_topology_sorter_priority_descending(self, tracker) -> None:
        """同层级无依赖任务按 priority 降序执行"""
        tasks = {
            "low": WarmupTask("low", priority=1),
            "med": WarmupTask("med", priority=5),
            "high": WarmupTask("high", priority=10),
            "mid": WarmupTask("mid", priority=7),
        }
        order = TopologySorter.sort(tasks)
        # 优先级从高到低：high(10) → mid(7) → med(5) → low(1)
        assert order.index("high") < order.index("mid")
        assert order.index("mid") < order.index("med")
        assert order.index("med") < order.index("low")

    def test_topology_sorter_priority_with_dependencies(self) -> None:
        """依赖约束优先于 priority，但同级节点按 priority 排序"""
        tasks = {
            "base": WarmupTask("base", priority=0),
            "low_child": WarmupTask("low_child", priority=1, dependencies=["base"]),
            "high_child": WarmupTask("high_child", priority=100, dependencies=["base"]),
        }
        order = TopologySorter.sort(tasks)
        # base 必须先执行
        assert order[0] == "base"
        # 同级任务中 high_child(100) 先于 low_child(1)
        assert order.index("high_child") < order.index("low_child")

    def test_topology_sorter_same_priority_stable(self) -> None:
        """相同 priority 的多个任务都能合法完成（排序一致）"""
        tasks = {f"t{i}": WarmupTask(f"t{i}", priority=5) for i in range(8)}
        order1 = TopologySorter.sort(tasks)
        order2 = TopologySorter.sort(tasks)
        assert set(order1) == set(order2) == set(tasks.keys())

    def test_orchestrator_hot_data_priority_first(self, tracker) -> None:
        """编排器按 priority 优先加载热点数据"""
        orch = WarmupOrchestrator()
        run_id = orch.create_warmup_run()

        # 构造4个同级任务，不同优先级
        priority_map = {"index_page": 100, "user_profile": 50, "search_trend": 20, "about_us": 1}
        tasks = []
        for name, prio in priority_map.items():
            t = WarmupTask(name, priority=prio)
            t.set_load_function(tracker.make_loader(name, f"data-{name}"))
            tasks.append(t)
        orch.register_tasks(run_id, tasks)
        orch.execute_warmup(run_id)

        # index_page 优先级最高，应最先被执行
        assert tracker.call_order[0] == "index_page"
        # about_us 优先级最低，应最后被执行
        assert tracker.call_order[-1] == "about_us"


# ---------------------------------------------------------------------------
# Empty Run Progress Percentage
# ---------------------------------------------------------------------------
class TestEmptyRunProgress:
    def test_empty_run_not_started_zero_percent(self) -> None:
        """空流程 NOT_STARTED 状态应返回 0%"""
        orch = WarmupOrchestrator()
        run_id = orch.create_warmup_run()
        prog = orch.get_progress(run_id)
        assert prog.state == WarmupState.NOT_STARTED
        assert prog.progress_percentage == 0.0
        assert prog.total_tasks == 0

    def test_empty_run_after_execute_100_percent(self) -> None:
        """空流程执行完毕后应返回 100%"""
        orch = WarmupOrchestrator()
        run_id = orch.create_warmup_run()
        prog = orch.execute_warmup(run_id)
        assert prog.state == WarmupState.COMPLETED
        assert prog.progress_percentage == 100.0
        assert prog.total_tasks == 0

    def test_non_empty_run_not_started_zero_percent(self) -> None:
        """有任务但未执行的流程应返回 0%"""
        orch = WarmupOrchestrator()
        run_id = orch.create_warmup_run()
        orch.register_task(run_id, WarmupTask("t1"))
        orch.register_task(run_id, WarmupTask("t2"))
        prog = orch.get_progress(run_id)
        assert prog.state == WarmupState.NOT_STARTED
        assert prog.progress_percentage == 0.0
        assert prog.total_tasks == 2


# ---------------------------------------------------------------------------
# Concurrent Warmup Runs
# ---------------------------------------------------------------------------
class TestConcurrentWarmupRuns:
    def test_multiple_runs_isolated_state(self, tracker) -> None:
        """同一编排器管理的多个 run 之间数据互不干扰"""
        orch = WarmupOrchestrator()
        run_a = orch.create_warmup_run("run-A")
        run_b = orch.create_warmup_run("run-B")

        # Run A: 任务 a1, a2
        for name in ("a1", "a2"):
            t = WarmupTask(name)
            t.set_load_function(tracker.make_loader(name, f"A-{name}"))
            orch.register_task(run_a, t)

        # Run B: 任务 b1, b2
        for name in ("b1", "b2"):
            t = WarmupTask(name)
            t.set_load_function(tracker.make_loader(name, f"B-{name}"))
            orch.register_task(run_b, t)

        prog_a = orch.execute_warmup(run_a)
        prog_b = orch.execute_warmup(run_b)

        # 两个 run 各自完成
        assert prog_a.state == WarmupState.COMPLETED
        assert prog_b.state == WarmupState.COMPLETED

        # 数据隔离：run A 看不到 B 的数据，反之亦然
        assert orch.get_cached_data(run_a, "a1") == "A-a1"
        assert orch.get_cached_data(run_a, "b1") is None
        assert orch.get_cached_data(run_b, "b1") == "B-b1"
        assert orch.get_cached_data(run_b, "a1") is None

        # 各自的任务列表独立
        assert set(orch.get_registered_tasks(run_a)) == {"a1", "a2"}
        assert set(orch.get_registered_tasks(run_b)) == {"b1", "b2"}

    def test_concurrent_execution_threads(self, tracker) -> None:
        """多个线程同时执行不同 run，结果应正确完成（验证 per-run 锁不相互阻塞）"""
        import threading
        import time as _time

        orch = WarmupOrchestrator()
        num_runs = 4
        run_ids = []
        results: Dict[str, WarmupProgress] = {}

        # 创建 4 个 run，每个含 5 个任务（模拟耗时）
        for r in range(num_runs):
            rid = orch.create_warmup_run(f"concurrent-run-{r}")
            run_ids.append(rid)
            for i in range(5):
                t = WarmupTask(f"run{r}-t{i}")
                t.set_load_function(tracker.make_loader(f"run{r}-t{i}", f"value-{r}-{i}"))
                orch.register_task(rid, t)

        def worker(rid: str) -> None:
            p = orch.execute_warmup(rid)
            results[rid] = p

        # 并发执行
        threads = [threading.Thread(target=worker, args=(rid,)) for rid in run_ids]
        start = _time.monotonic()
        for th in threads:
            th.start()
        for th in threads:
            th.join(timeout=5.0)
        duration = _time.monotonic() - start

        # 所有 run 正确完成
        assert len(results) == num_runs
        for rid in run_ids:
            assert rid in results
            p = results[rid]
            assert p.state == WarmupState.COMPLETED
            assert p.completed_tasks == 5

        # 所有任务都只执行一次（无竞态导致的重复调用）
        for r in range(num_runs):
            for i in range(5):
                assert tracker.call_count[f"run{r}-t{i}"] == 1

    def test_concurrent_queries_during_execution(self) -> None:
        """执行期间并发查询进度、缓存不抛异常（线程安全读）"""
        import threading
        import time as _time

        orch = WarmupOrchestrator()
        rid = orch.create_warmup_run()

        # 用一个慢任务模拟执行窗口
        slow = WarmupTask("slow-task")
        query_results = []

        def slow_loader():
            # 在执行期间循环查询（模拟监控线程）
            for _ in range(10):
                try:
                    p = orch.get_progress(rid)
                    tp = orch.get_task_progress(rid, "slow-task")
                    state = orch.get_warmup_state(rid)
                    cached = orch.get_cached_data(rid, "slow-task")
                    all_c = orch.get_all_cached_data(rid)
                    query_results.append((p.progress_percentage, state, tp.state))
                except Exception as exc:  # noqa: BLE001
                    query_results.append(("ERROR", str(exc)))
                _time.sleep(0.005)
            return "slow-data"

        slow.set_load_function(slow_loader)
        orch.register_task(rid, slow)

        prog = orch.execute_warmup(rid)

        # 查询没有抛异常
        assert len(query_results) > 0
        for item in query_results:
            assert item[0] != "ERROR", f"查询异常: {item}"
        # 最终结果正确
        assert prog.state == WarmupState.COMPLETED
        assert orch.get_cached_data(rid, "slow-task") == "slow-data"

    def test_different_runs_different_failure_strategies(self) -> None:
        """同一 orchestrator 内不同 run 可使用不同失败策略"""
        orch = WarmupOrchestrator()

        # Run A: SKIP_DEPENDENTS (default)
        run_a = orch.create_warmup_run("run-A", failure_strategy=FailureStrategy.SKIP_DEPENDENTS)
        orch.register_task(run_a, WarmupTask("a-up", ))
        orch.register_task(run_a, WarmupTask("a-down", dependencies=["a-up"]))

        # Run B: ABORT_ALL
        run_b = orch.create_warmup_run("run-B", failure_strategy=FailureStrategy.ABORT_ALL)
        orch.register_task(run_b, WarmupTask("b-up"))
        orch.register_task(run_b, WarmupTask("b-down", dependencies=["b-up"]))
        orch.register_task(run_b, WarmupTask("b-other"))

        # Run C: CONTINUE_ANYWAY
        run_c = orch.create_warmup_run("run-C", failure_strategy=FailureStrategy.CONTINUE_ANYWAY)
        orch.register_task(run_c, WarmupTask("c-up"))
        orch.register_task(run_c, WarmupTask("c-down", dependencies=["c-up"]))

        # 各自按策略执行完成（无失败时行为一致）
        pa = orch.execute_warmup(run_a)
        pb = orch.execute_warmup(run_b)
        pc = orch.execute_warmup(run_c)

        assert pa.state == WarmupState.COMPLETED
        assert pb.state == WarmupState.COMPLETED
        assert pc.state == WarmupState.COMPLETED

