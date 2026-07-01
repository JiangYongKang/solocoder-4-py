import threading
import time
from typing import List
from unittest.mock import MagicMock

import pytest

from solocoder_4_py.internal_task_runner import (
    DEFAULT_HISTORY_LIMIT,
    InternalTaskRunner,
    InvalidScheduleError,
    RunStatus,
    TaskAlreadyRegisteredError,
    TaskDefinition,
    TaskNotFoundError,
    TaskRunRecord,
    TaskRunnerError,
    TaskRunnerStats,
    TaskRuntimeInfo,
    TaskStateError,
    TaskStatus,
    TaskType,
    TaskTypeError,
)


# =====================================================================
# 测试辅助工具
# =====================================================================
class FakeClock:
    """模拟时钟，用于测试时控制时间流逝，无需真实等待"""

    def __init__(self, start: float = 1000.0) -> None:
        self._time = start

    def now(self) -> float:
        return self._time

    def advance(self, seconds: float) -> float:
        self._time += seconds
        return self._time

    def set(self, value: float) -> None:
        self._time = value


def make_counter() -> tuple[MagicMock, List[int]]:
    """创建一个计数 handler，返回 (mock, counter_list)"""
    counter: List[int] = []
    mock = MagicMock(side_effect=lambda **kw: counter.append(len(counter)) or len(counter))
    return mock, counter


def create_test_definition(task_id: str, task_type: TaskType = TaskType.ONE_SHOT, **kwargs):
    """创建测试用的任务定义"""
    mock, _ = make_counter()
    defaults = {
        "task_id": task_id,
        "task_type": task_type,
        "handler": mock,
        "name": f"Task {task_id}",
    }
    if task_type == TaskType.PERIODIC and "interval_seconds" not in kwargs:
        defaults["interval_seconds"] = 5.0
    defaults.update(kwargs)
    return TaskDefinition(**defaults)


# =====================================================================
# 常量 & 枚举测试
# =====================================================================
class TestConstantsAndEnums:
    def test_task_type_values(self):
        assert TaskType.ONE_SHOT.value == "ONE_SHOT"
        assert TaskType.PERIODIC.value == "PERIODIC"
        assert TaskType.MANUAL.value == "MANUAL"

    def test_task_status_values(self):
        values = {s.value for s in TaskStatus}
        assert "PENDING" in values
        assert "ACTIVE" in values
        assert "PAUSED" in values
        assert "COMPLETED" in values
        assert "CANCELLED" in values
        assert "ERROR" in values

    def test_run_status_values(self):
        assert RunStatus.SUCCESS.value == "SUCCESS"
        assert RunStatus.FAILED.value == "FAILED"
        assert RunStatus.SKIPPED.value == "SKIPPED"

    def test_terminal_status_sets(self):
        from solocoder_4_py.internal_task_runner import TERMINAL_TASK_STATUSES, TERMINAL_RUN_STATUSES

        assert TaskStatus.COMPLETED in TERMINAL_TASK_STATUSES
        assert TaskStatus.CANCELLED in TERMINAL_TASK_STATUSES
        assert TaskStatus.ERROR in TERMINAL_TASK_STATUSES
        assert TaskStatus.PENDING not in TERMINAL_TASK_STATUSES

        assert RunStatus.SUCCESS in TERMINAL_RUN_STATUSES
        assert RunStatus.FAILED in TERMINAL_RUN_STATUSES
        assert RunStatus.SKIPPED in TERMINAL_RUN_STATUSES

    def test_defaults(self):
        assert DEFAULT_HISTORY_LIMIT == 1000


# =====================================================================
# TaskDefinition / TaskRunRecord 数据模型测试
# =====================================================================
class TestTaskDefinition:
    def test_create_one_shot(self):
        handler = MagicMock()
        d = TaskDefinition(task_id="t1", task_type=TaskType.ONE_SHOT, handler=handler)
        assert d.task_id == "t1"
        assert d.is_one_shot() is True
        assert d.is_periodic() is False
        assert d.is_manual() is False
        assert d.name == "t1"

    def test_create_periodic_requires_interval(self):
        handler = MagicMock()
        with pytest.raises(ValueError, match="PERIODIC 任务必须指定正的 interval_seconds"):
            TaskDefinition(task_id="t1", task_type=TaskType.PERIODIC, handler=handler)

        with pytest.raises(ValueError):
            TaskDefinition(
                task_id="t1", task_type=TaskType.PERIODIC, handler=handler, interval_seconds=0
            )

        d = TaskDefinition(
            task_id="t1", task_type=TaskType.PERIODIC, handler=handler, interval_seconds=5.0
        )
        assert d.is_periodic() is True
        assert d.interval_seconds == 5.0

    def test_create_manual(self):
        handler = MagicMock()
        d = TaskDefinition(task_id="t1", task_type=TaskType.MANUAL, handler=handler)
        assert d.is_manual() is True

    def test_tags(self):
        handler = MagicMock()
        d = TaskDefinition(
            task_id="t1", task_type=TaskType.ONE_SHOT, handler=handler, tags=["a", "b", "c"]
        )
        assert d.has_tag("a") is True
        assert d.has_tag("z") is False
        assert d.has_any_tag(["a", "z"]) is True
        assert d.has_all_tags(["a", "b"]) is True
        assert d.has_all_tags(["a", "z"]) is False

    def test_to_dict(self):
        handler = MagicMock()
        d = TaskDefinition(
            task_id="t1",
            task_type=TaskType.PERIODIC,
            handler=handler,
            interval_seconds=10.0,
            tags=["x"],
            metadata={"k": "v"},
        )
        data = d.to_dict()
        assert data["task_id"] == "t1"
        assert data["task_type"] == "PERIODIC"
        assert data["interval_seconds"] == 10.0
        assert data["tags"] == ["x"]
        assert data["metadata"] == {"k": "v"}


class TestTaskRunRecord:
    def test_properties(self):
        r = TaskRunRecord(task_id="t1", started_at=100.0, finished_at=100.5, status=RunStatus.SUCCESS)
        assert r.duration_ms == pytest.approx(500.0)
        assert r.is_success is True
        assert r.is_failed is False
        assert r.is_skipped is False

    def test_duration_zero_when_unset(self):
        r = TaskRunRecord(task_id="t1")
        assert r.duration_ms == 0.0

    def test_failed_and_skipped_properties(self):
        assert TaskRunRecord(task_id="t1", status=RunStatus.FAILED).is_failed is True
        assert TaskRunRecord(task_id="t1", status=RunStatus.SKIPPED).is_skipped is True

    def test_to_dict_and_from_dict_roundtrip(self):
        original = TaskRunRecord(
            task_id="t1",
            run_id="run-123",
            status=RunStatus.FAILED,
            started_at=100.0,
            finished_at=101.0,
            result=None,
            error_message="boom",
            error_type="ValueError",
            attempt=3,
            trigger="SCHEDULE",
            metadata={"foo": "bar"},
        )
        data = original.to_dict()
        assert data["run_id"] == "run-123"
        assert data["status"] == "FAILED"
        assert data["duration_ms"] == pytest.approx(1000.0)

        restored = TaskRunRecord.from_dict(data)
        assert restored.task_id == original.task_id
        assert restored.run_id == original.run_id
        assert restored.status == original.status
        assert restored.attempt == 3
        assert restored.trigger == "SCHEDULE"
        assert restored.metadata == {"foo": "bar"}


class TestTaskRunnerStats:
    def test_to_dict(self):
        s = TaskRunnerStats(total_tasks=10, successful_runs=5, failed_runs=2)
        d = s.to_dict()
        assert d["total_tasks"] == 10
        assert d["successful_runs"] == 5
        assert d["failed_runs"] == 2


# =====================================================================
# InternalTaskRunner 基础 & 注册测试
# =====================================================================
class TestTaskRunnerBasics:
    def test_create_empty_runner(self):
        runner = InternalTaskRunner()
        assert len(runner) == 0
        assert runner.get_stats().total_tasks == 0

    def test_has_task_false(self):
        runner = InternalTaskRunner()
        assert runner.has_task("nope") is False
        assert ("nope" in runner) is False

    def test_get_task_not_found_raises(self):
        runner = InternalTaskRunner()
        with pytest.raises(TaskNotFoundError) as exc:
            runner.get_task("nope")
        assert exc.value.task_id == "nope"

    def test_get_definition_not_found_raises(self):
        runner = InternalTaskRunner()
        with pytest.raises(TaskNotFoundError):
            runner.get_definition("nope")

    def test_iter_empty(self):
        runner = InternalTaskRunner()
        assert list(iter(runner)) == []

    def test_register_task(self):
        runner = InternalTaskRunner()
        definition = create_test_definition("t1")
        info = runner.register(definition)

        assert isinstance(info, TaskRuntimeInfo)
        assert info.definition is definition
        assert info.status == TaskStatus.PENDING
        assert info.registered_at > 0

        assert len(runner) == 1
        assert runner.has_task("t1") is True
        assert "t1" in runner

    def test_register_duplicate_raises(self):
        runner = InternalTaskRunner()
        d = create_test_definition("t1")
        runner.register(d)
        with pytest.raises(TaskAlreadyRegisteredError) as exc:
            runner.register(d)
        assert exc.value.task_id == "t1"

    def test_register_periodic_without_interval_via_runner(self):
        runner = InternalTaskRunner()
        handler = MagicMock()
        # 周期任务缺少 interval_seconds，在 TaskDefinition 构造时就抛出 ValueError
        with pytest.raises(ValueError):
            TaskDefinition(task_id="p1", task_type=TaskType.PERIODIC, handler=handler)

    def test_unregister_task(self):
        runner = InternalTaskRunner()
        runner.register(create_test_definition("t1", tags=["x"]))
        assert runner.unregister("t1") is True
        assert len(runner) == 0
        assert runner.get_all_tags() == []

    def test_unregister_nonexistent(self):
        runner = InternalTaskRunner()
        assert runner.unregister("nope") is False

    def test_clear(self):
        runner = InternalTaskRunner()
        runner.register(create_test_definition("t1"))
        runner.register(create_test_definition("t2"))
        count = runner.clear()
        assert count == 2
        assert len(runner) == 0
        assert runner.get_all_tags() == []

    def test_magic_contains_len_iter(self):
        runner = InternalTaskRunner()
        runner.register(create_test_definition("t2"))
        runner.register(create_test_definition("t1"))
        runner.register(create_test_definition("t3"))

        assert "t1" in runner
        assert "t0" not in runner
        assert len(runner) == 3
        assert list(iter(runner)) == ["t1", "t2", "t3"]


# =====================================================================
# 任务生命周期控制测试
# =====================================================================
class TestTaskLifecycle:
    def test_activate_one_shot(self):
        runner = InternalTaskRunner()
        runner.register(create_test_definition("t1"))
        info = runner.activate("t1")
        assert info.status == TaskStatus.ACTIVE
        assert info.activated_at is not None
        assert info.next_run_at is None

    def test_activate_periodic_sets_next_run(self):
        clock = FakeClock(1000.0)
        runner = InternalTaskRunner(time_provider=clock.now)
        d = create_test_definition("p1", TaskType.PERIODIC, interval_seconds=30.0)
        runner.register(d)
        info = runner.activate("p1")
        assert info.next_run_at == pytest.approx(1030.0)

    def test_activate_already_active_raises(self):
        runner = InternalTaskRunner()
        runner.register(create_test_definition("t1"))
        runner.activate("t1")
        with pytest.raises(TaskStateError) as exc:
            runner.activate("t1")
        assert exc.value.operation == "activate"

    def test_activate_not_found_raises(self):
        runner = InternalTaskRunner()
        with pytest.raises(TaskNotFoundError):
            runner.activate("nope")

    def test_cancel_active(self):
        runner = InternalTaskRunner()
        runner.register(create_test_definition("t1"))
        runner.activate("t1")
        info = runner.cancel("t1")
        assert info.status == TaskStatus.CANCELLED
        assert info.cancelled_at is not None

    def test_cancel_pending(self):
        runner = InternalTaskRunner()
        runner.register(create_test_definition("t1"))
        info = runner.cancel("t1")
        assert info.status == TaskStatus.CANCELLED

    def test_cancel_terminal_raises(self):
        runner = InternalTaskRunner()
        runner.register(create_test_definition("t1"))
        runner.cancel("t1")
        with pytest.raises(TaskStateError) as exc:
            runner.cancel("t1")
        assert exc.value.operation == "cancel"

    def test_reset_terminal_status(self):
        runner = InternalTaskRunner()
        runner.register(create_test_definition("t1"))
        runner.activate("t1")
        runner.cancel("t1")
        info = runner.reset("t1")
        assert info.status == TaskStatus.PENDING
        assert info.cancelled_at is None

    def test_reset_non_terminal_raises(self):
        runner = InternalTaskRunner()
        runner.register(create_test_definition("t1"))
        with pytest.raises(TaskStateError):
            runner.reset("t1")

    def test_pause_only_periodic(self):
        runner = InternalTaskRunner()
        runner.register(create_test_definition("t1", TaskType.ONE_SHOT))
        runner.activate("t1")
        with pytest.raises(TaskTypeError) as exc:
            runner.pause("t1")
        assert exc.value.expected_type == "PERIODIC"

    def test_pause_not_active_raises(self):
        runner = InternalTaskRunner()
        runner.register(create_test_definition("p1", TaskType.PERIODIC, interval_seconds=5.0))
        with pytest.raises(TaskStateError):
            runner.pause("p1")

    def test_pause_and_resume_periodic(self):
        clock = FakeClock(1000.0)
        runner = InternalTaskRunner(time_provider=clock.now)
        d = create_test_definition("p1", TaskType.PERIODIC, interval_seconds=10.0)
        runner.register(d)
        runner.activate("p1")

        info = runner.pause("p1")
        assert info.status == TaskStatus.PAUSED
        assert info.paused_at == pytest.approx(1000.0)

        clock.advance(60.0)
        info = runner.resume("p1")
        assert info.status == TaskStatus.ACTIVE
        assert info.next_run_at == pytest.approx(1070.0)

    def test_resume_not_paused_raises(self):
        runner = InternalTaskRunner()
        runner.register(create_test_definition("p1", TaskType.PERIODIC, interval_seconds=5.0))
        runner.activate("p1")
        with pytest.raises(TaskStateError):
            runner.resume("p1")


# =====================================================================
# Tick 调度（一次性 & 周期）测试
# =====================================================================
class TestTickScheduling:
    def test_one_shot_runs_once_on_tick(self):
        clock = FakeClock(100.0)
        runner = InternalTaskRunner(time_provider=clock.now)
        handler, counter = make_counter()
        runner.register(
            TaskDefinition(
                task_id="t1", task_type=TaskType.ONE_SHOT, handler=handler
            )
        )
        runner.activate("t1")

        records = runner.tick()
        assert len(records) == 1
        assert records[0].is_success
        assert records[0].trigger == "SCHEDULE"
        assert counter == [0]

        # 再次 tick 不会再执行
        records2 = runner.tick()
        assert len(records2) == 0
        assert counter == [0]

        info = runner.get_task("t1")
        assert info.status == TaskStatus.COMPLETED
        assert info.completed_at == pytest.approx(100.0)

    def test_periodic_runs_repeatedly_no_real_wait(self):
        """关键测试：使用 FakeClock 推进时间，无需真实 sleep"""
        clock = FakeClock(0.0)
        runner = InternalTaskRunner(time_provider=clock.now)
        handler, counter = make_counter()
        runner.register(
            TaskDefinition(
                task_id="p1",
                task_type=TaskType.PERIODIC,
                handler=handler,
                interval_seconds=10.0,
            )
        )
        runner.activate("p1")

        # t=0，next_run_at=10，还没到
        assert runner.tick() == []
        assert counter == []

        # t=9，还是没到
        clock.advance(9.0)
        assert runner.tick() == []
        assert counter == []

        # t=10，到达，执行第 1 次
        clock.advance(1.0)
        r = runner.tick()
        assert len(r) == 1
        assert counter == [0]
        info = runner.get_task("p1")
        assert info.next_run_at == pytest.approx(20.0)

        # 逐步推进时间，每 10 秒执行一次：t=20, 30, 40
        for expected_count in range(2, 5):  # 期望 counter 长度: 2, 3, 4
            clock.advance(10.0)
            records = runner.tick()
            assert len(records) == 1
            assert len(counter) == expected_count

        # 此时 t=40，counter=[0,1,2,3]，next_run_at=50
        info = runner.get_task("p1")
        assert info.next_run_at == pytest.approx(50.0)

        # 再 tick 没有新的执行
        assert runner.tick() == []

    def test_periodic_paused_does_not_run(self):
        clock = FakeClock(0.0)
        runner = InternalTaskRunner(time_provider=clock.now)
        handler, counter = make_counter()
        runner.register(
            TaskDefinition(
                task_id="p1",
                task_type=TaskType.PERIODIC,
                handler=handler,
                interval_seconds=5.0,
            )
        )
        runner.activate("p1")
        runner.pause("p1")

        clock.advance(100.0)
        assert runner.tick() == []
        assert counter == []

    def test_one_shot_error_sets_status_error(self):
        clock = FakeClock(0.0)
        runner = InternalTaskRunner(time_provider=clock.now)

        def bad(**kw):
            raise RuntimeError("boom")

        runner.register(
            TaskDefinition(task_id="t1", task_type=TaskType.ONE_SHOT, handler=bad)
        )
        runner.activate("t1")
        records = runner.tick()
        assert len(records) == 1
        assert records[0].is_failed
        assert records[0].error_type == "RuntimeError"
        assert records[0].error_message == "boom"

        info = runner.get_task("t1")
        assert info.status == TaskStatus.ERROR
        assert info.last_error == "boom"

    def test_tick_skips_inactive_tasks(self):
        runner = InternalTaskRunner()
        runner.register(create_test_definition("t1"))  # PENDING
        records = runner.tick()
        assert len(records) == 0


# =====================================================================
# 手动触发（MANUAL 类型）测试
# =====================================================================
class TestManualTrigger:
    def test_trigger_manual_task(self):
        runner = InternalTaskRunner()
        handler = MagicMock(return_value="ok")
        d = TaskDefinition(task_id="m1", task_type=TaskType.MANUAL, handler=handler)
        runner.register(d)
        runner.activate("m1")

        record = runner.trigger("m1", foo="bar", n=42)
        assert record.is_success
        assert record.result == "ok"
        assert record.trigger == "MANUAL"
        assert record.attempt == 1
        handler.assert_called_once_with(foo="bar", n=42)

    def test_trigger_manual_can_be_called_multiple_times(self):
        runner = InternalTaskRunner()
        handler, counter = make_counter()
        runner.register(
            TaskDefinition(task_id="m1", task_type=TaskType.MANUAL, handler=handler)
        )
        runner.activate("m1")

        for _ in range(5):
            r = runner.trigger("m1")
            assert r.is_success
        assert counter == [0, 1, 2, 3, 4]

    def test_trigger_non_manual_when_active(self):
        runner = InternalTaskRunner()
        handler, counter = make_counter()
        runner.register(
            TaskDefinition(task_id="t1", task_type=TaskType.ONE_SHOT, handler=handler)
        )
        runner.activate("t1")
        r = runner.trigger("t1")
        assert r.is_success
        assert counter == [0]

    def test_trigger_non_manual_when_inactive_raises(self):
        runner = InternalTaskRunner()
        runner.register(create_test_definition("t1", TaskType.ONE_SHOT))
        with pytest.raises(TaskStateError) as exc:
            runner.trigger("t1")
        assert exc.value.operation == "trigger"

    def test_trigger_manual_cancelled_raises(self):
        runner = InternalTaskRunner()
        runner.register(create_test_definition("m1", TaskType.MANUAL))
        runner.activate("m1")
        runner.cancel("m1")
        with pytest.raises(TaskStateError):
            runner.trigger("m1")

    def test_trigger_propagates_handler_args(self):
        runner = InternalTaskRunner()

        def add(a, b):
            return a + b

        runner.register(
            TaskDefinition(task_id="m1", task_type=TaskType.MANUAL, handler=add)
        )
        runner.activate("m1")
        r = runner.trigger("m1", a=3, b=4)
        assert r.result == 7


# =====================================================================
# 重试机制测试
# =====================================================================
class TestRetryMechanism:
    def test_retries_on_failure_until_success(self):
        runner = InternalTaskRunner()
        attempts = []

        def flaky(**kw):
            attempts.append(len(attempts))
            if len(attempts) < 3:
                raise RuntimeError("fail")
            return "success"

        runner.register(
            TaskDefinition(
                task_id="m1",
                task_type=TaskType.MANUAL,
                handler=flaky,
                max_retries=3,
            )
        )
        runner.activate("m1")
        record = runner.trigger("m1")
        assert record.is_success
        assert record.attempt == 3
        assert record.result == "success"
        assert attempts == [0, 1, 2]

    def test_exhausts_retries_then_fails(self):
        runner = InternalTaskRunner()

        def always_fail(**kw):
            raise ValueError("nope")

        runner.register(
            TaskDefinition(
                task_id="m1",
                task_type=TaskType.MANUAL,
                handler=always_fail,
                max_retries=2,
            )
        )
        runner.activate("m1")
        record = runner.trigger("m1")
        assert record.is_failed
        assert record.attempt == 3
        assert record.error_type == "ValueError"


# =====================================================================
# 运行历史查询测试
# =====================================================================
class TestRunHistory:
    def _runner_with_history(self):
        clock = FakeClock(0.0)
        runner = InternalTaskRunner(time_provider=clock.now)
        handler = MagicMock(side_effect=lambda **kw: time.time() if False else None)

        def factory(run_number):
            def f(**kw):
                if run_number in {3, 7}:
                    raise RuntimeError(f"err-{run_number}")
                return f"result-{run_number}"

            return f

        # 使用多个任务记录：改用 trigger 推进，因为我们需要细粒度控制
        runner2 = InternalTaskRunner(time_provider=clock.now)
        base_handler = MagicMock()
        runner2.register(
            TaskDefinition(
                task_id="m1",
                task_type=TaskType.MANUAL,
                handler=base_handler,
            )
        )
        runner2.activate("m1")

        # 逐个触发
        for i in range(10):
            clock.advance(1.0)

            def make_handler(i):
                def h(**kw):
                    if i in {3, 7}:
                        raise RuntimeError(f"err-{i}")
                    return f"result-{i}"

                return h

            # 动态替换 handler
            info = runner2._tasks["m1"]
            info.definition.handler = make_handler(i)
            runner2.trigger("m1")

        return runner2, clock

    def test_query_all_history(self):
        runner, _ = self._runner_with_history()
        history = runner.get_run_history("m1")
        assert len(history) == 10
        assert history[0].started_at > history[-1].started_at  # 倒序

    def test_query_by_status_filter(self):
        runner, _ = self._runner_with_history()
        fails = runner.get_run_history("m1", status_filter=RunStatus.FAILED)
        assert len(fails) == 2
        assert all(r.is_failed for r in fails)

        successes = runner.get_run_history("m1", status_filter=RunStatus.SUCCESS)
        assert len(successes) == 8

    def test_query_limit(self):
        runner, _ = self._runner_with_history()
        latest_3 = runner.get_run_history("m1", limit=3)
        assert len(latest_3) == 3

    def test_query_by_time_range(self, clock=None):
        runner, clock = self._runner_with_history()
        # t=0~10 之间有 10 次，started_at 分别是 1..10
        since = 3.0
        until = 7.0
        history = runner.get_run_history("m1", since=since, until=until)
        assert len(history) == 5
        for r in history:
            assert since <= r.started_at <= until

    def test_latest_run(self):
        runner, _ = self._runner_with_history()
        latest = runner.get_latest_run("m1")
        assert latest is not None
        history = runner.get_run_history("m1", limit=1)
        assert latest.run_id == history[0].run_id

    def test_latest_run_empty(self):
        runner = InternalTaskRunner()
        runner.register(create_test_definition("t1"))
        assert runner.get_latest_run("t1") is None

    def test_run_by_id(self):
        runner, _ = self._runner_with_history()
        history = runner.get_run_history("m1")
        target = history[4]
        found = runner.get_run_by_id("m1", target.run_id)
        assert found is not None
        assert found.run_id == target.run_id
        assert runner.get_run_by_id("m1", "nonexistent") is None

    def test_history_limit_is_enforced(self):
        runner = InternalTaskRunner(history_limit=5)
        handler, counter = make_counter()
        runner.register(
            TaskDefinition(task_id="m1", task_type=TaskType.MANUAL, handler=handler)
        )
        runner.activate("m1")
        for _ in range(10):
            runner.trigger("m1")
        history = runner.get_run_history("m1")
        assert len(history) == 5

    def test_task_not_found_in_history_raises(self):
        runner = InternalTaskRunner()
        with pytest.raises(TaskNotFoundError):
            runner.get_run_history("nope")


# =====================================================================
# 任务发现（按标签/类型/状态）测试
# =====================================================================
class TestTaskDiscovery:
    def test_list_tasks_all(self):
        runner = InternalTaskRunner()
        runner.register(create_test_definition("t1"))
        runner.register(create_test_definition("t2"))
        items = runner.list_tasks()
        assert [i.definition.task_id for i in items] == ["t1", "t2"]

    def test_list_by_status(self):
        runner = InternalTaskRunner()
        runner.register(create_test_definition("t1"))
        runner.register(create_test_definition("t2"))
        runner.activate("t1")
        pending = runner.list_tasks(status=TaskStatus.PENDING)
        active = runner.list_tasks(status=TaskStatus.ACTIVE)
        assert [i.definition.task_id for i in pending] == ["t2"]
        assert [i.definition.task_id for i in active] == ["t1"]

    def test_list_by_type(self):
        runner = InternalTaskRunner()
        runner.register(create_test_definition("t1", TaskType.ONE_SHOT))
        runner.register(
            create_test_definition("p1", TaskType.PERIODIC, interval_seconds=5.0)
        )
        runner.register(create_test_definition("m1", TaskType.MANUAL))

        one_shots = runner.list_tasks(task_type=TaskType.ONE_SHOT)
        periodics = runner.list_tasks(task_type=TaskType.PERIODIC)
        manuals = runner.list_tasks(task_type=TaskType.MANUAL)
        assert len(one_shots) == 1
        assert len(periodics) == 1
        assert len(manuals) == 1

    def test_list_by_tag(self):
        runner = InternalTaskRunner()
        runner.register(create_test_definition("t1", tags=["a", "b"]))
        runner.register(create_test_definition("t2", tags=["a", "c"]))
        runner.register(create_test_definition("t3", tags=["d"]))

        a_tasks = runner.list_tasks(tag="a")
        assert [i.definition.task_id for i in a_tasks] == ["t1", "t2"]
        assert runner.list_tasks(tag="z") == []

    def test_find_by_tags_match_all(self):
        runner = InternalTaskRunner()
        runner.register(create_test_definition("t1", tags=["a", "b"]))
        runner.register(create_test_definition("t2", tags=["a", "b", "c"]))
        runner.register(create_test_definition("t3", tags=["a"]))

        result = runner.find_by_tags(["a", "b"], match_all=True)
        ids = [i.definition.task_id for i in result]
        assert "t1" in ids and "t2" in ids and "t3" not in ids

    def test_find_by_tags_match_any(self):
        runner = InternalTaskRunner()
        runner.register(create_test_definition("t1", tags=["a"]))
        runner.register(create_test_definition("t2", tags=["b"]))
        runner.register(create_test_definition("t3", tags=["c"]))

        result = runner.find_by_tags(["a", "b"], match_all=False)
        assert len(result) == 2

    def test_find_by_tags_empty(self):
        runner = InternalTaskRunner()
        assert runner.find_by_tags([]) == []

    def test_get_all_tags_and_cleanup(self):
        runner = InternalTaskRunner()
        runner.register(create_test_definition("t1", tags=["x"]))
        runner.register(create_test_definition("t2", tags=["x"]))
        assert "x" in runner.get_all_tags()

        runner.unregister("t1")
        assert "x" in runner.get_all_tags()
        runner.unregister("t2")
        assert "x" not in runner.get_all_tags()


# =====================================================================
# 统计信息测试
# =====================================================================
class TestRunnerStats:
    def test_stats_empty(self):
        runner = InternalTaskRunner()
        s = runner.get_stats()
        assert s.total_tasks == 0
        assert s.total_runs == 0

    def test_stats_mixed(self):
        clock = FakeClock(0.0)
        runner = InternalTaskRunner(time_provider=clock.now)

        runner.register(create_test_definition("t1"))
        runner.register(create_test_definition("t2"))
        runner.register(
            create_test_definition("p1", TaskType.PERIODIC, interval_seconds=5.0)
        )
        runner.register(create_test_definition("m1", TaskType.MANUAL))

        runner.activate("t1")
        runner.activate("t2")
        runner.activate("m1")
        runner.cancel("t2")

        # 执行一次 t1（成功）和 m1 3 次（2 次成功 1 次失败）
        runner.tick()  # t1 执行

        info = runner._tasks["m1"]
        info.definition.handler = MagicMock(return_value="ok")
        runner.trigger("m1")
        runner.trigger("m1")

        def fail(**kw):
            raise RuntimeError("x")

        info.definition.handler = fail
        runner.trigger("m1")

        s = runner.get_stats()
        assert s.total_tasks == 4
        assert s.pending_tasks == 1     # p1（未激活）
        assert s.active_tasks == 1      # m1（MANUAL 保持 ACTIVE）
        assert s.completed_tasks == 1   # t1（ONE_SHOT 执行完成）
        assert s.cancelled_tasks == 1   # t2
        assert s.successful_runs == 3   # t1, m1, m1
        assert s.failed_runs == 1       # m1 第3次
        assert s.total_runs == 4


# =====================================================================
# 批量操作测试
# =====================================================================
class TestBatchOperations:
    def test_activate_all(self):
        runner = InternalTaskRunner()
        runner.register(create_test_definition("t1"))
        runner.register(create_test_definition("t2"))
        results = runner.activate_all()
        assert results == {"t1": True, "t2": True}
        assert runner.get_task("t1").status == TaskStatus.ACTIVE

    def test_activate_all_with_some_active(self):
        runner = InternalTaskRunner()
        runner.register(create_test_definition("t1"))
        runner.register(create_test_definition("t2"))
        runner.activate("t1")
        results = runner.activate_all()
        assert results["t1"] is False
        assert results["t2"] is True

    def test_cancel_all(self):
        runner = InternalTaskRunner()
        runner.register(create_test_definition("t1"))
        runner.register(create_test_definition("t2"))
        runner.activate("t1")
        results = runner.cancel_all()
        assert results == {"t1": True, "t2": True}
        assert runner.get_task("t1").status == TaskStatus.CANCELLED
        assert runner.get_task("t2").status == TaskStatus.CANCELLED

    def test_cancel_all_with_terminal(self):
        runner = InternalTaskRunner()
        runner.register(create_test_definition("t1"))
        runner.cancel("t1")
        results = runner.cancel_all()
        assert results["t1"] is False


# =====================================================================
# 异常层级测试
# =====================================================================
class TestExceptionHierarchy:
    def test_all_exceptions_inherit_runner_error(self):
        assert issubclass(TaskNotFoundError, TaskRunnerError)
        assert issubclass(TaskAlreadyRegisteredError, TaskRunnerError)
        assert issubclass(TaskStateError, TaskRunnerError)
        assert issubclass(TaskTypeError, TaskRunnerError)
        assert issubclass(InvalidScheduleError, TaskRunnerError)


# =====================================================================
# 线程安全测试
# =====================================================================
class TestThreadSafety:
    def test_concurrent_registration(self):
        runner = InternalTaskRunner()
        errors: List[Exception] = []

        def register_range(start, end):
            try:
                for i in range(start, end):
                    runner.register(create_test_definition(f"t_{i}"))
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=register_range, args=(i * 25, (i + 1) * 25))
            for i in range(4)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0
        assert len(runner) == 100

    def test_concurrent_triggers(self):
        runner = InternalTaskRunner()
        handler, counter = make_counter()
        runner.register(
            TaskDefinition(task_id="m1", task_type=TaskType.MANUAL, handler=handler)
        )
        runner.activate("m1")
        errors: List[Exception] = []

        def do_triggers(n):
            try:
                for _ in range(n):
                    runner.trigger("m1")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=do_triggers, args=(20,)) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0
        assert len(counter) == 100
        stats = runner.get_stats()
        assert stats.total_runs == 100


# =====================================================================
# 综合场景测试
# =====================================================================
class TestIntegrationScenarios:
    def test_periodic_with_fake_clock_multiple_tasks(self):
        """模拟多个周期任务，控制时间验证调度正确性"""
        clock = FakeClock(0.0)
        runner = InternalTaskRunner(time_provider=clock.now)

        handler_a, counter_a = make_counter()
        handler_b, counter_b = make_counter()

        runner.register(
            TaskDefinition(
                task_id="fast",
                task_type=TaskType.PERIODIC,
                handler=handler_a,
                interval_seconds=5.0,
            )
        )
        runner.register(
            TaskDefinition(
                task_id="slow",
                task_type=TaskType.PERIODIC,
                handler=handler_b,
                interval_seconds=15.0,
            )
        )
        runner.activate("fast")
        runner.activate("slow")

        # 在 60 秒内模拟连续 tick（每次推进 1 秒）
        for _ in range(60):
            clock.advance(1.0)
            runner.tick()

        # fast: 每 5 秒一次，60 秒应该执行 12 次（t=5,10,...,60）
        # 但我们从 t=0 开始，每次 +1s，所以到 t=60
        # next_run_at 初始是 5。t=5 执行，next=10；t=10 执行...
        # 最后到 t=60，刚好 12 次
        # 但实际是逐秒推进，所以到 t=60 时刚好 12 次（5,10,...,60）
        assert len(counter_a) == 12, f"fast 期望 12 次，实际 {len(counter_a)}"

        # slow: 每 15 秒一次，t=15,30,45,60 -> 4 次
        assert len(counter_b) == 4, f"slow 期望 4 次，实际 {len(counter_b)}"

    def test_full_lifecycle_one_shot(self):
        runner = InternalTaskRunner()
        calls = []

        def job(**kw):
            calls.append(1)
            return "done"

        runner.register(
            TaskDefinition(
                task_id="data_sync",
                task_type=TaskType.ONE_SHOT,
                handler=job,
                description="sync data",
                tags=["io", "data"],
            )
        )

        info = runner.get_task("data_sync")
        assert info.status == TaskStatus.PENDING

        runner.activate("data_sync")
        records = runner.tick()
        assert len(records) == 1
        assert records[0].result == "done"

        info = runner.get_task("data_sync")
        assert info.status == TaskStatus.COMPLETED
        assert info.success_count == 1

        history = runner.get_run_history("data_sync")
        assert len(history) == 1
        assert history[0].trigger == "SCHEDULE"

        data_tasks = runner.find_by_tag("data")
        assert len(data_tasks) == 1

    def test_full_lifecycle_manual_task_as_api_call(self):
        runner = InternalTaskRunner()

        def send_email(to, subject, body):
            return {"sent": True, "to": to}

        runner.register(
            TaskDefinition(
                task_id="send_email",
                task_type=TaskType.MANUAL,
                handler=send_email,
                max_retries=1,
            )
        )
        runner.activate("send_email")

        r1 = runner.trigger(
            "send_email", to="a@x.com", subject="hi", body="hello"
        )
        assert r1.is_success
        assert r1.result["to"] == "a@x.com"

        r2 = runner.trigger(
            "send_email", to="b@x.com", subject="hi", body="hello2"
        )
        assert r2.is_success

        history = runner.get_run_history("send_email")
        assert len(history) == 2

    def test_task_statistics_accumulation(self):
        clock = FakeClock(0.0)
        runner = InternalTaskRunner(time_provider=clock.now)

        def good(**kw):
            return "ok"

        def bad(**kw):
            raise RuntimeError("bad")

        runner.register(
            TaskDefinition(task_id="g1", task_type=TaskType.MANUAL, handler=good)
        )
        runner.register(
            TaskDefinition(task_id="b1", task_type=TaskType.MANUAL, handler=bad)
        )
        runner.activate("g1")
        runner.activate("b1")

        for _ in range(5):
            runner.trigger("g1")
        for _ in range(3):
            try:
                runner.trigger("b1")
            except Exception:
                pass

        stats = runner.get_stats()
        assert stats.total_runs == 8
        assert stats.successful_runs == 5
        assert stats.failed_runs == 3

        g_info = runner.get_task("g1")
        assert g_info.success_count == 5
        assert g_info.failure_count == 0

        b_info = runner.get_task("b1")
        assert b_info.failure_count == 3
        assert b_info.last_error == "bad"

    def test_custom_time_provider_via_setter(self):
        runner = InternalTaskRunner()
        clock = FakeClock(100.0)
        runner.set_time_provider(clock.now)

        runner.register(
            TaskDefinition(
                task_id="p1",
                task_type=TaskType.PERIODIC,
                handler=MagicMock(return_value=1),
                interval_seconds=10.0,
            )
        )
        runner.activate("p1")
        info = runner.get_task("p1")
        assert info.next_run_at == pytest.approx(110.0)


# =====================================================================
# handler 超时机制测试
# =====================================================================
class TestHandlerTimeout:
    def test_handler_timeout_produces_failed_record(self):
        """handler 长时间阻塞应通过 ThreadPoolExecutor 被判定为超时，
        记录 FAILED，error_type == 'TimeoutError'"""
        runner = InternalTaskRunner()

        stop_event = threading.Event()

        def never_return(**kw):
            stop_event.wait(timeout=10)
            return "never"

        try:
            runner.register(
                TaskDefinition(
                    task_id="slow",
                    task_type=TaskType.MANUAL,
                    handler=never_return,
                    timeout_seconds=0.05,  # 非常短，立即可超时
                )
            )
            runner.activate("slow")

            t0 = time.perf_counter()
            record = runner.trigger("slow")
            elapsed = time.perf_counter() - t0

            # 验证基本属性
            assert record.is_failed
            assert record.error_type == "TimeoutError"
            assert record.attempt == 1
            assert "超时" in (record.error_message or "")
            # 总体耗时应该接近 timeout，不是真的等 handler 返回
            assert elapsed < 2.0
        finally:
            stop_event.set()
            runner.shutdown(wait=False)

    def test_handler_no_timeout_runs_normally(self):
        """未设置 timeout_seconds 的 handler 正常执行（不走 ThreadPoolExecutor）"""
        runner = InternalTaskRunner()

        def quick(**kw):
            return 42

        runner.register(
            TaskDefinition(
                task_id="fast",
                task_type=TaskType.MANUAL,
                handler=quick,
                timeout_seconds=None,
            )
        )
        runner.activate("fast")
        r = runner.trigger("fast")
        assert r.is_success
        assert r.result == 42

        runner.shutdown(wait=True)

    def test_handler_within_timeout_runs_normally(self):
        """设置 timeout 但 handler 在时限内返回，正常 SUCCESS"""
        runner = InternalTaskRunner()

        def quick(**kw):
            return "ok"

        runner.register(
            TaskDefinition(
                task_id="ok",
                task_type=TaskType.MANUAL,
                handler=quick,
                timeout_seconds=10.0,
            )
        )
        runner.activate("ok")
        r = runner.trigger("ok")
        assert r.is_success
        assert r.result == "ok"

        runner.shutdown(wait=True)


# =====================================================================
# 重试延迟机制测试（使用可注入 sleep_provider 避免真实等待）
# =====================================================================
class TestRetryDelay:
    def test_retry_delay_invocations_match_retry_count(self):
        """max_retries=2 且 retry_delay_seconds=5 时，sleep 应被调用 2 次"""
        sleep_calls: List[float] = []

        def fake_sleep(sec):
            sleep_calls.append(sec)

        runner = InternalTaskRunner(sleep_provider=fake_sleep)

        def always_fail(**kw):
            raise RuntimeError("boom")

        runner.register(
            TaskDefinition(
                task_id="f",
                task_type=TaskType.MANUAL,
                handler=always_fail,
                max_retries=2,
                retry_delay_seconds=5.0,
            )
        )
        runner.activate("f")

        record = runner.trigger("f")
        assert record.is_failed
        assert record.attempt == 3  # 1 次初跑 + 2 次重试
        assert sleep_calls == [5.0, 5.0]

        runner.shutdown(wait=True)

    def test_first_attempt_no_delay(self):
        """首次执行不触发 sleep"""
        sleep_calls: List[float] = []
        runner = InternalTaskRunner(sleep_provider=lambda s: sleep_calls.append(s))

        def once_ok(**kw):
            return "done"

        runner.register(
            TaskDefinition(
                task_id="g",
                task_type=TaskType.MANUAL,
                handler=once_ok,
                max_retries=3,
                retry_delay_seconds=10.0,
            )
        )
        runner.activate("g")
        runner.trigger("g")
        assert sleep_calls == []

        runner.shutdown(wait=True)

    def test_zero_or_negative_retry_delay_no_sleep(self):
        """retry_delay_seconds=0 或负数时，即使重试也不调用 sleep"""
        sleep_calls: List[float] = []
        runner = InternalTaskRunner(sleep_provider=lambda s: sleep_calls.append(s))

        def fail(**kw):
            raise RuntimeError

        runner.register(
            TaskDefinition(
                task_id="f2",
                task_type=TaskType.MANUAL,
                handler=fail,
                max_retries=3,
                retry_delay_seconds=0.0,
            )
        )
        runner.activate("f2")
        runner.trigger("f2")
        assert sleep_calls == []

        runner.shutdown(wait=True)


# =====================================================================
# resume 追赶补偿测试
# =====================================================================
class TestResumeCatchUp:
    def test_resume_no_catchup_drops_periods(self):
        """默认 catch_up=False：恢复后 next_run_at = now + interval，跳过暂停期间周期"""
        clock = FakeClock(0.0)
        runner = InternalTaskRunner(time_provider=clock.now)
        handler, counter = make_counter()

        runner.register(
            TaskDefinition(
                task_id="p",
                task_type=TaskType.PERIODIC,
                handler=handler,
                interval_seconds=10.0,
            )
        )
        runner.activate("p")

        # 执行一次（t=10）
        clock.advance(10.0)
        runner.tick()
        assert counter == [0]

        # 暂停在 t=10，此时 next_run_at = 20
        runner.pause("p")

        # 模拟 100 秒过去
        clock.advance(100.0)  # t=110

        # 默认 resume：next_run_at = now + interval = 120
        info = runner.resume("p", catch_up=False)
        assert info.next_run_at == pytest.approx(120.0)
        assert info.catch_up is False

        # 推进到 t=119，不到 120，不应执行
        for _ in range(9):
            clock.advance(1.0)
            runner.tick()
        # t=119 时还没到 next_run_at=120，counter 仍为 1
        assert len(counter) == 1
        # 再推进 11 秒（到 t=130），其中 t=120 会触发一次
        executed_in_this_window = 0
        for _ in range(11):
            clock.advance(1.0)
            recs = runner.tick()
            executed_in_this_window += len(recs)
        # t=120 执行 1 次，之后到 t=130 还没到下一个 130 的调度（下一个是 130 刚好）
        assert executed_in_this_window >= 1
        assert len(counter) >= 2

        runner.shutdown(wait=True)

    def test_resume_catchup_runs_missed_periods(self):
        """catch_up=True：每次 tick 补跑一个周期，直到追上 now"""
        clock = FakeClock(0.0)
        runner = InternalTaskRunner(time_provider=clock.now)
        handler, counter = make_counter()

        runner.register(
            TaskDefinition(
                task_id="q",
                task_type=TaskType.PERIODIC,
                handler=handler,
                interval_seconds=10.0,
            )
        )
        runner.activate("q")

        # t=10 首次执行
        clock.advance(10.0)
        runner.tick()
        assert counter == [0]
        # next_run_at = 20

        runner.pause("q")

        # 暂停期间过了 105 秒，相当于错过了 t=20,30,...,110 共 10 个周期
        clock.advance(105.0)  # t=115

        info = runner.resume("q", catch_up=True)
        assert info.catch_up is True
        assert info.next_run_at == pytest.approx(20.0)  # 保留原调度

        # 连续 tick（不推进时间）：每个 tick 补跑一次，加上 next_run_at 前进一个 interval
        # 预期补跑 10 次（20..110）
        runs_before = len(counter)
        for _ in range(20):
            runner.tick()
        runs_after = len(counter)
        # 应该补跑了 10 次（20,30,40,50,60,70,80,90,100,110）
        assert runs_after - runs_before == 10, (
            f"期望补跑 10 次，实际补跑 {runs_after - runs_before} 次"
        )
        # 追平后 catch_up 标志被关闭
        info = runner.get_task("q")
        assert info.catch_up is False
        # 新的 next_run_at 应该是 120（最后补跑 110 后加 interval）
        assert info.next_run_at == pytest.approx(120.0)

        runner.shutdown(wait=True)

    def test_resume_catchup_eventually_catches_up(self):
        """追赶过程中，同时 clock 继续推进，最终也能追上"""
        clock = FakeClock(0.0)
        runner = InternalTaskRunner(time_provider=clock.now)
        handler, counter = make_counter()

        runner.register(
            TaskDefinition(
                task_id="r",
                task_type=TaskType.PERIODIC,
                handler=handler,
                interval_seconds=10.0,
            )
        )
        runner.activate("r")
        clock.advance(10.0)
        runner.tick()  # t=10 run
        runner.pause("r")

        clock.advance(30.0)  # t=40，错过 20,30 两个周期（下一个应该是 40 即将到达）

        runner.resume("q" if False else "r", catch_up=True)
        # 先不推进时间，tick 两次：补跑 20、30
        runner.tick()  # 20
        runner.tick()  # 30
        # 再 tick：next_run_at=40，now=40，所以 40 也会跑
        runner.tick()  # 40
        assert len(counter) == 4  # 10,20,30,40

        # 追平后下一个是 50
        info = runner.get_task("r")
        assert info.next_run_at == pytest.approx(50.0)
        assert info.catch_up is False

        runner.shutdown(wait=True)


# =====================================================================
# trigger 竞态防护 & handler 动态替换 测试
# =====================================================================
class TestRaceAndDynamicHandler:
    def test_cancel_between_first_and_second_check_produces_skipped(self):
        """模拟 trigger 校验完成后、_execute_single_run 二次校验前任务被取消，
        应该得到 SKIPPED 记录，而不是真的执行 handler。

        实现方式：使用线程 + Event，恰好在窗口期内 cancel。"""
        runner = InternalTaskRunner()
        ready_e = threading.Event()
        proceed_e = threading.Event()
        handler_ran: List[bool] = [False]

        def my_handler(**kw):
            handler_ran[0] = True
            return "oops"

        runner.register(
            TaskDefinition(
                task_id="m",
                task_type=TaskType.MANUAL,
                handler=my_handler,
            )
        )
        runner.activate("m")

        # 保存原始方法
        orig_execute = InternalTaskRunner._execute_single_run

        def patched_execute(self_ref, info, trigger, extra_kwargs=None):
            # 在真正进入 _execute_single_run 之前，给测试线程机会去 cancel
            ready_e.set()
            proceed_e.wait(timeout=5)
            return orig_execute(self_ref, info, trigger, extra_kwargs)

        # 使用 monkeypatch 风格替换
        InternalTaskRunner._execute_single_run = patched_execute

        result_holder: List[TaskRunRecord] = []

        def trigger_thread():
            result_holder.append(runner.trigger("m"))

        t = threading.Thread(target=trigger_thread)
        t.start()
        ready_e.wait(timeout=5)
        # 现在处于窗口期：trigger 首次校验已过，_execute_single_run 即将开始
        runner.cancel("m")
        proceed_e.set()
        t.join(timeout=5)

        # 恢复
        InternalTaskRunner._execute_single_run = orig_execute

        assert len(result_holder) == 1
        record = result_holder[0]
        # 应该被二次校验拦截为 SKIPPED
        assert record.is_skipped
        assert record.status == RunStatus.SKIPPED
        # handler 不应被调用
        assert handler_ran[0] is False

        # 历史统计里 skip_count 应该增加
        info = runner.get_task("m")
        assert info.skip_count == 1

        runner.shutdown(wait=True)

    def test_unregister_between_checks_produces_skipped_no_error(self):
        """窗口期注销任务也应安全返回 SKIPPED 记录，不抛异常"""
        runner = InternalTaskRunner()
        ready_e = threading.Event()
        proceed_e = threading.Event()

        runner.register(
            TaskDefinition(
                task_id="x",
                task_type=TaskType.MANUAL,
                handler=lambda **kw: "x",
            )
        )
        runner.activate("x")

        orig_execute = InternalTaskRunner._execute_single_run

        def patched_execute(self_ref, info, trigger, extra_kwargs=None):
            ready_e.set()
            proceed_e.wait(timeout=5)
            return orig_execute(self_ref, info, trigger, extra_kwargs)

        InternalTaskRunner._execute_single_run = patched_execute

        result_holder: List[Optional[TaskRunRecord]] = [None]
        exc_holder: List[Optional[Exception]] = [None]

        def trigger_thread():
            try:
                result_holder[0] = runner.trigger("x")
            except Exception as e:
                exc_holder[0] = e

        t = threading.Thread(target=trigger_thread)
        t.start()
        ready_e.wait(timeout=5)
        # 窗口期注销
        runner.unregister("x")
        proceed_e.set()
        t.join(timeout=5)

        InternalTaskRunner._execute_single_run = orig_execute

        # 不抛异常，返回 SKIPPED
        assert exc_holder[0] is None
        assert result_holder[0] is not None
        assert result_holder[0].is_skipped

        runner.shutdown(wait=True)

    def test_handler_dynamic_replacement_before_run_picks_new_handler(self):
        """_execute_single_run 入口二次校验时读取 definition_snapshot，
        在进入前替换 handler 应该生效（新代码路径）"""
        runner = InternalTaskRunner()

        def old_handler(**kw):
            return "old"

        def new_handler(**kw):
            return "new"

        runner.register(
            TaskDefinition(
                task_id="dyn",
                task_type=TaskType.MANUAL,
                handler=old_handler,
            )
        )
        runner.activate("dyn")

        # 动态替换：直接改 definition.handler
        info = runner.get_task("dyn")
        info.definition.handler = new_handler

        r = runner.trigger("dyn")
        assert r.is_success
        assert r.result == "new"

        runner.shutdown(wait=True)

    def test_definition_snapshot_prevents_mid_flight_change(self):
        """definition_snapshot 在二次校验后生成，
        确保在 handler 执行过程中（如在另一个线程里）替换 handler
        不会影响本次运行。"""
        runner = InternalTaskRunner()
        start_e = threading.Event()
        wait_e = threading.Event()

        def blocking_handler(**kw):
            start_e.set()
            wait_e.wait(timeout=5)
            return "blocking-result"

        runner.register(
            TaskDefinition(
                task_id="mid",
                task_type=TaskType.MANUAL,
                handler=blocking_handler,
            )
        )
        runner.activate("mid")

        result_holder: List[Optional[TaskRunRecord]] = [None]

        def trigger_thread():
            result_holder[0] = runner.trigger("mid")

        t = threading.Thread(target=trigger_thread)
        t.start()
        start_e.wait(timeout=5)

        # 运行中尝试替换 handler
        info = runner.get_task("mid")
        original_handler = info.definition.handler
        info.definition.handler = lambda **kw: "injected"

        # 让 handler 结束
        wait_e.set()
        t.join(timeout=5)

        # 结果应为 "blocking-result" 而非 "injected"
        assert result_holder[0] is not None
        assert result_holder[0].result == "blocking-result"

        # 恢复（保持测试环境整洁）
        info.definition.handler = original_handler

        runner.shutdown(wait=True)


# =====================================================================
# 新增：确保 reset/cancel_all/activate_all 对 catch_up 字段的正确处理
# =====================================================================
class TestCatchUpFlagsReset:
    def test_activate_clears_catch_up(self):
        clock = FakeClock(0.0)
        runner = InternalTaskRunner(time_provider=clock.now)
        runner.register(
            TaskDefinition(
                task_id="p",
                task_type=TaskType.PERIODIC,
                handler=MagicMock(),
                interval_seconds=5.0,
            )
        )
        runner.activate("p")
        runner.pause("p")
        runner.resume("p", catch_up=True)
        assert runner.get_task("p").catch_up is True

        runner.cancel("p")
        runner.reset("p")
        # reset 后 catch_up 为 False
        assert runner.get_task("p").catch_up is False

        # 再 activate 也为 False
        runner.activate("p")
        assert runner.get_task("p").catch_up is False

        runner.shutdown(wait=True)
