from typing import Any, Dict, List, Tuple

import pytest

from solocoder_4_py.module_init_graph import (
    CircularDependencyError,
    CycleReport,
    DependencyNotFoundError,
    InitProgress,
    InitState,
    InitStateError,
    ModuleAlreadyRegisteredError,
    ModuleInitError,
    ModuleInitializer,
    ModuleNode,
    ModuleNotFoundError,
    ModuleProgress,
    ModuleState,
    RetryLimitExceededError,
    TERMINAL_INIT_STATES,
    TERMINAL_MODULE_STATES,
    TopologyAnalyzer,
)


# ---------------------------------------------------------------------------
# 辅助类 & 夹具
# ---------------------------------------------------------------------------
class CallTracker:
    """追踪模块初始化回调的调用次数和顺序"""

    def __init__(self) -> None:
        self.call_count: Dict[str, int] = {}
        self.call_order: List[str] = []
        self.results: Dict[str, Any] = {}

    def make_init(self, module_id: str, result: Any = None) -> Any:
        def _init(ctx=None):
            self.call_count[module_id] = self.call_count.get(module_id, 0) + 1
            self.call_order.append(module_id)
            actual_result = (
                result if result is not None
                else {f"init_{module_id}": list(range(3))}
            )
            self.results[module_id] = actual_result
            return actual_result
        return _init

    def make_failing_init(self, module_id: str, error: Exception) -> Any:
        def _init(ctx=None):
            self.call_count[module_id] = self.call_count.get(module_id, 0) + 1
            self.call_order.append(module_id)
            raise error
        return _init

    def make_fail_then_succeed(
        self, module_id: str, fail_count: int, result: Any = None
    ) -> Any:
        state = {"fails_left": fail_count}

        def _init(ctx=None):
            self.call_count[module_id] = self.call_count.get(module_id, 0) + 1
            self.call_order.append(module_id)
            if state["fails_left"] > 0:
                state["fails_left"] -= 1
                raise RuntimeError(f"{module_id} 暂时失败")
            actual_result = (
                result if result is not None else {f"init_{module_id}": "ok"}
            )
            self.results[module_id] = actual_result
            return actual_result
        return _init


@pytest.fixture
def tracker() -> CallTracker:
    return CallTracker()


class FakeClock:
    def __init__(self) -> None:
        self._t = 0.0
        self._jumps = 0

    def __call__(self) -> float:
        self._jumps += 1
        self._t += 0.5
        return self._t - 0.5

    def advance(self, delta: float) -> None:
        self._t += delta


# ---------------------------------------------------------------------------
# Constants & Enums
# ---------------------------------------------------------------------------
class TestConstants:
    def test_module_state_values(self) -> None:
        assert ModuleState.PENDING.value == "PENDING"
        assert ModuleState.INITIALIZING.value == "INITIALIZING"
        assert ModuleState.INITIALIZED.value == "INITIALIZED"
        assert ModuleState.FAILED.value == "FAILED"
        assert ModuleState.ISOLATED.value == "ISOLATED"

    def test_init_state_values(self) -> None:
        assert InitState.NOT_STARTED.value == "NOT_STARTED"
        assert InitState.RUNNING.value == "RUNNING"
        assert InitState.COMPLETED.value == "COMPLETED"
        assert InitState.PARTIAL_COMPLETED.value == "PARTIAL_COMPLETED"
        assert InitState.FAILED.value == "FAILED"

    def test_terminal_module_states(self) -> None:
        assert ModuleState.INITIALIZED in TERMINAL_MODULE_STATES
        assert ModuleState.FAILED in TERMINAL_MODULE_STATES
        assert ModuleState.ISOLATED in TERMINAL_MODULE_STATES
        assert ModuleState.PENDING not in TERMINAL_MODULE_STATES
        assert ModuleState.INITIALIZING not in TERMINAL_MODULE_STATES

    def test_terminal_init_states(self) -> None:
        assert InitState.COMPLETED in TERMINAL_INIT_STATES
        assert InitState.PARTIAL_COMPLETED in TERMINAL_INIT_STATES
        assert InitState.FAILED in TERMINAL_INIT_STATES
        assert InitState.NOT_STARTED not in TERMINAL_INIT_STATES
        assert InitState.RUNNING not in TERMINAL_INIT_STATES


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class TestExceptions:
    def test_exception_hierarchy(self) -> None:
        assert issubclass(ModuleNotFoundError, ModuleInitError)
        assert issubclass(ModuleAlreadyRegisteredError, ModuleInitError)
        assert issubclass(CircularDependencyError, ModuleInitError)
        assert issubclass(DependencyNotFoundError, ModuleInitError)
        assert issubclass(InitStateError, ModuleInitError)
        assert issubclass(RetryLimitExceededError, ModuleInitError)

    def test_circular_dependency_contains_cycles(self) -> None:
        cycles = [["a", "b", "c"], ["x", "y"]]
        e = CircularDependencyError("有环", cycles=cycles)
        assert e.cycles == cycles
        assert "有环" in str(e)


# ---------------------------------------------------------------------------
# ModuleNode
# ---------------------------------------------------------------------------
class TestModuleNode:
    def test_creation_minimal(self) -> None:
        m = ModuleNode("mod-a")
        assert m.module_id == "mod-a"
        assert m.dependencies == []
        assert m.description == ""
        assert m.metadata == {}
        assert m.max_retries == 0

    def test_creation_full(self) -> None:
        m = ModuleNode(
            module_id="db:conn",
            dependencies=["config:env"],
            description="数据库连接模块",
            metadata={"db_driver": "postgres"},
            max_retries=3,
        )
        assert m.module_id == "db:conn"
        assert m.dependencies == ["config:env"]
        assert m.description == "数据库连接模块"
        assert m.metadata == {"db_driver": "postgres"}
        assert m.max_retries == 3

    def test_set_and_execute_init_callback(self, tracker) -> None:
        m = ModuleNode("t1")
        m.set_init_callback(tracker.make_init("t1", 42))
        result = m.execute_init()
        assert result == 42
        assert tracker.call_count["t1"] == 1

    def test_execute_without_callback(self) -> None:
        m = ModuleNode("t1")
        assert m.execute_init() is None

    def test_execute_with_context(self) -> None:
        captured = {}

        def init(ctx):
            captured["ctx"] = ctx
            return ctx["x"] * 2

        m = ModuleNode("m")
        m.set_init_callback(init)
        assert m.execute_init({"x": 10}) == 20
        assert captured["ctx"] == {"x": 10}

    def test_add_remove_dependency(self) -> None:
        m = ModuleNode("m")
        assert m.dependencies == []
        m.add_dependency("a")
        m.add_dependency("b")
        assert m.dependencies == ["a", "b"]
        m.add_dependency("a")
        assert m.dependencies == ["a", "b"]
        m.remove_dependency("a")
        assert m.dependencies == ["b"]
        m.remove_dependency("nonexistent")
        assert m.dependencies == ["b"]

    def test_hash_and_eq(self) -> None:
        m1 = ModuleNode("same", dependencies=["x"])
        m2 = ModuleNode("same", dependencies=["y"])
        m3 = ModuleNode("other")
        assert m1 == m2
        assert hash(m1) == hash(m2)
        assert m1 != m3
        assert m1 != "same"

    def test_repr(self) -> None:
        m = ModuleNode("m", dependencies=["a", "b"])
        r = repr(m)
        assert "m" in r
        assert "a" in r
        assert "b" in r


# ---------------------------------------------------------------------------
# TopologyAnalyzer - Basic Sorting
# ---------------------------------------------------------------------------
class TestTopologySort:
    def test_sort_empty(self) -> None:
        assert TopologyAnalyzer.sort({}) == []

    def test_sort_single(self) -> None:
        modules = {"a": ModuleNode("a")}
        assert TopologyAnalyzer.sort(modules) == ["a"]

    def test_sort_linear_chain(self) -> None:
        modules = {
            "a": ModuleNode("a"),
            "b": ModuleNode("b", dependencies=["a"]),
            "c": ModuleNode("c", dependencies=["b"]),
        }
        order = TopologyAnalyzer.sort(modules)
        assert order.index("a") < order.index("b")
        assert order.index("b") < order.index("c")

    def test_sort_diamond(self) -> None:
        modules = {
            "a": ModuleNode("a"),
            "b": ModuleNode("b", dependencies=["a"]),
            "c": ModuleNode("c", dependencies=["a"]),
            "d": ModuleNode("d", dependencies=["b", "c"]),
        }
        order = TopologyAnalyzer.sort(modules)
        assert order.index("a") < order.index("b") < order.index("d")
        assert order.index("a") < order.index("c") < order.index("d")

    def test_sort_multiple_roots(self) -> None:
        modules = {
            "a": ModuleNode("a"),
            "b": ModuleNode("b"),
            "c": ModuleNode("c", dependencies=["a"]),
        }
        order = TopologyAnalyzer.sort(modules)
        assert set(order) == {"a", "b", "c"}
        assert order.index("a") < order.index("c")

    def test_sort_dependency_not_found(self) -> None:
        modules = {"a": ModuleNode("a", dependencies=["ghost"])}
        with pytest.raises(DependencyNotFoundError) as excinfo:
            TopologyAnalyzer.sort(modules)
        msg = str(excinfo.value)
        assert "ghost" in msg
        assert "a" in msg


# ---------------------------------------------------------------------------
# TopologyAnalyzer - Cycle Detection
# ---------------------------------------------------------------------------
class TestTopologyCycleDetection:
    def test_detect_simple_three_cycle(self) -> None:
        modules = {
            "a": ModuleNode("a", dependencies=["c"]),
            "b": ModuleNode("b", dependencies=["a"]),
            "c": ModuleNode("c", dependencies=["b"]),
        }
        report = TopologyAnalyzer.detect_cycles(modules)
        assert report.has_cycles
        assert report.cycle_count == 1
        involved = report.involved_modules()
        assert involved == {"a", "b", "c"}

    def test_detect_two_node_cycle(self) -> None:
        modules = {
            "a": ModuleNode("a", dependencies=["b"]),
            "b": ModuleNode("b", dependencies=["a"]),
        }
        report = TopologyAnalyzer.detect_cycles(modules)
        assert report.has_cycles
        assert report.cycle_count == 1
        assert report.involved_modules() == {"a", "b"}

    def test_detect_self_loop(self) -> None:
        modules = {"a": ModuleNode("a", dependencies=["a"])}
        report = TopologyAnalyzer.detect_cycles(modules)
        assert report.has_cycles
        assert report.cycle_count == 1
        assert report.cycles == [["a"]]
        assert report.involved_modules() == {"a"}

    def test_self_loop_with_independent_modules(self) -> None:
        modules = {
            "a": ModuleNode("a", dependencies=["a"]),
            "b": ModuleNode("b"),
            "c": ModuleNode("c", dependencies=["b"]),
        }
        report = TopologyAnalyzer.detect_cycles(modules)
        assert report.cycle_count == 1
        assert report.involved_modules() == {"a"}

    def test_sort_self_loop_raises_with_cycles(self) -> None:
        modules = {"a": ModuleNode("a", dependencies=["a"])}
        with pytest.raises(CircularDependencyError) as excinfo:
            TopologyAnalyzer.sort(modules)
        exc = excinfo.value
        assert exc.cycles is not None
        assert ["a"] in exc.cycles
        assert "a" in str(exc)

    def test_self_loop_in_cycle_report_format(self) -> None:
        modules = {"a": ModuleNode("a", dependencies=["a"])}
        report = TopologyAnalyzer.detect_cycles(modules)
        formatted = report.format_report()
        assert "检测到 1 个循环依赖" in formatted
        assert "a -> a" in formatted
        assert "涉及模块: a" in formatted

    def test_mixed_self_loop_and_regular_cycle(self) -> None:
        modules = {
            "a": ModuleNode("a", dependencies=["a"]),
            "b": ModuleNode("b", dependencies=["c"]),
            "c": ModuleNode("c", dependencies=["b"]),
        }
        report = TopologyAnalyzer.detect_cycles(modules)
        assert report.cycle_count == 2
        assert report.involved_modules() == {"a", "b", "c"}
        assert ["a"] in report.cycles

    def test_detect_multiple_cycles(self) -> None:
        modules = {
            "a": ModuleNode("a"),
            "b": ModuleNode("b", dependencies=["a", "d"]),
            "c": ModuleNode("c", dependencies=["b"]),
            "d": ModuleNode("d", dependencies=["c"]),
            "x": ModuleNode("x", dependencies=["y"]),
            "y": ModuleNode("y", dependencies=["x"]),
        }
        report = TopologyAnalyzer.detect_cycles(modules)
        assert report.cycle_count == 2

    def test_no_cycles(self) -> None:
        modules = {
            "a": ModuleNode("a"),
            "b": ModuleNode("b", dependencies=["a"]),
            "c": ModuleNode("c", dependencies=["a", "b"]),
        }
        report = TopologyAnalyzer.detect_cycles(modules)
        assert not report.has_cycles
        assert report.cycle_count == 0
        assert report.involved_modules() == set()

    def test_sort_raises_with_cycle_report(self) -> None:
        modules = {
            "a": ModuleNode("a", dependencies=["b"]),
            "b": ModuleNode("b", dependencies=["a"]),
        }
        with pytest.raises(CircularDependencyError) as excinfo:
            TopologyAnalyzer.sort(modules)
        msg = str(excinfo.value)
        assert "a" in msg and "b" in msg

    def test_cycle_report_formatting(self) -> None:
        modules = {
            "a": ModuleNode("a", dependencies=["b"]),
            "b": ModuleNode("b", dependencies=["a"]),
        }
        report = TopologyAnalyzer.detect_cycles(modules)
        formatted = report.format_report()
        assert "检测到 1 个循环依赖" in formatted
        assert "涉及模块" in formatted
        assert "a" in formatted and "b" in formatted

    def test_cycle_report_str_no_cycles(self) -> None:
        report = TopologyAnalyzer.detect_cycles({})
        assert "未检测到" in str(report)


# ---------------------------------------------------------------------------
# TopologyAnalyzer - Dependency Analysis
# ---------------------------------------------------------------------------
class TestTopologyDependencyAnalysis:
    def test_get_dependents(self) -> None:
        modules = {
            "a": ModuleNode("a"),
            "b": ModuleNode("b", dependencies=["a"]),
            "c": ModuleNode("c", dependencies=["a"]),
            "d": ModuleNode("d", dependencies=["b"]),
        }
        dep = TopologyAnalyzer.get_dependents(modules)
        assert "b" in dep["a"]
        assert "c" in dep["a"]
        assert "d" in dep["b"]
        assert dep["d"] == []

    def test_get_all_downstream(self) -> None:
        modules = {
            "a": ModuleNode("a"),
            "b": ModuleNode("b", dependencies=["a"]),
            "c": ModuleNode("c", dependencies=["b"]),
            "d": ModuleNode("d", dependencies=["a"]),
            "e": ModuleNode("e"),
        }
        assert set(TopologyAnalyzer.get_all_downstream(modules, "a")) == {"b", "c", "d"}
        assert TopologyAnalyzer.get_all_downstream(modules, "b") == ["c"]
        assert TopologyAnalyzer.get_all_downstream(modules, "e") == []

    def test_get_all_upstream(self) -> None:
        modules = {
            "a": ModuleNode("a"),
            "b": ModuleNode("b", dependencies=["a"]),
            "c": ModuleNode("c", dependencies=["b"]),
            "d": ModuleNode("d", dependencies=["a"]),
        }
        assert set(TopologyAnalyzer.get_all_upstream(modules, "c")) == {"a", "b"}
        assert TopologyAnalyzer.get_all_upstream(modules, "a") == []
        assert TopologyAnalyzer.get_all_upstream(modules, "nonexistent") == []

    def test_dependency_matrix(self) -> None:
        modules = {
            "a": ModuleNode("a"),
            "b": ModuleNode("b", dependencies=["a"]),
            "c": ModuleNode("c", dependencies=["b"]),
        }
        matrix = TopologyAnalyzer.build_dependency_matrix(modules)
        assert matrix["a"] == set()
        assert matrix["b"] == {"a"}
        assert matrix["c"] == {"a", "b"}

    def test_topological_levels(self) -> None:
        modules = {
            "a": ModuleNode("a"),
            "b": ModuleNode("b"),
            "c": ModuleNode("c", dependencies=["a"]),
            "d": ModuleNode("d", dependencies=["c"]),
            "e": ModuleNode("e", dependencies=["c", "b"]),
        }
        levels = TopologyAnalyzer.topological_levels(modules)
        assert levels["a"] == 0
        assert levels["b"] == 0
        assert levels["c"] == 1
        assert levels["d"] == 2
        assert levels["e"] == 2


# ---------------------------------------------------------------------------
# ModuleProgress
# ---------------------------------------------------------------------------
class TestModuleProgress:
    def test_initial_state(self) -> None:
        mp = ModuleProgress(module_id="m1")
        assert mp.state == ModuleState.PENDING
        assert mp.attempts == 0
        assert not mp.is_terminal()

    def test_state_transitions(self) -> None:
        clock = FakeClock()
        mp = ModuleProgress(module_id="m1")
        mp.mark_initializing(clock)
        assert mp.state == ModuleState.INITIALIZING
        assert mp.attempts == 1
        assert not mp.is_terminal()
        mp.mark_initialized({"key": "v"}, 0.1, clock)
        assert mp.state == ModuleState.INITIALIZED
        assert mp.init_result == {"key": "v"}
        assert mp.is_terminal()

    def test_mark_failed(self) -> None:
        clock = FakeClock()
        mp = ModuleProgress(module_id="m1")
        mp.mark_initializing(clock)
        mp.mark_failed(RuntimeError("boom"), 0.2, clock)
        assert mp.state == ModuleState.FAILED
        assert "RuntimeError" in mp.error_message
        assert "boom" in mp.error_message
        assert mp.is_terminal()

    def test_mark_isolated(self) -> None:
        mp = ModuleProgress(module_id="m1")
        mp.mark_isolated("上游依赖失败")
        assert mp.state == ModuleState.ISOLATED
        assert "上游" in mp.error_message
        assert mp.is_terminal()

    def test_reset_for_retry(self) -> None:
        clock = FakeClock()
        mp = ModuleProgress(module_id="m1")
        mp.mark_initializing(clock)
        mp.mark_failed(ValueError("x"), 0.1, clock)
        assert mp.is_terminal()
        assert mp.attempts == 1
        mp.reset_for_retry()
        assert mp.state == ModuleState.PENDING
        assert mp.error_message == ""
        assert mp.init_result is None
        assert mp.duration_seconds == 0.0
        assert mp.attempts == 1

    def test_reset_for_retry_preserves_multiple_attempts(self) -> None:
        clock = FakeClock()
        mp = ModuleProgress(module_id="m1")
        for _ in range(5):
            mp.mark_initializing(clock)
        assert mp.attempts == 5
        mp.reset_for_retry()
        assert mp.attempts == 5
        mp.mark_initializing(clock)
        assert mp.attempts == 6

    def test_multiple_initializing_increments_attempts(self) -> None:
        clock = FakeClock()
        mp = ModuleProgress(module_id="m1")
        for _ in range(3):
            mp.mark_initializing(clock)
        assert mp.attempts == 3

    def test_to_dict(self) -> None:
        clock = FakeClock()
        mp = ModuleProgress(module_id="m1")
        mp.mark_initializing(clock)
        mp.mark_initialized("ok", 0.01234, clock)
        d = mp.to_dict()
        assert d["module_id"] == "m1"
        assert d["state"] == "INITIALIZED"
        assert d["duration_seconds"] == 0.0123
        assert d["attempts"] == 1


# ---------------------------------------------------------------------------
# InitProgress
# ---------------------------------------------------------------------------
class TestInitProgress:
    def test_recalculate_counts(self) -> None:
        p = InitProgress(total_modules=5)
        p.module_progress = {
            "a": ModuleProgress("a", state=ModuleState.INITIALIZED),
            "b": ModuleProgress("b", state=ModuleState.FAILED),
            "c": ModuleProgress("c", state=ModuleState.ISOLATED),
            "d": ModuleProgress("d", state=ModuleState.INITIALIZING),
            "e": ModuleProgress("e", state=ModuleState.PENDING),
        }
        p.recalculate_counts()
        assert p.initialized_modules == 1
        assert p.failed_modules == 1
        assert p.isolated_modules == 1
        assert p.initializing_modules == 1
        assert p.pending_modules == 1
        assert p.progress_percentage == 60.0

    def test_to_dict(self) -> None:
        p = InitProgress(init_id="run-1", state=InitState.COMPLETED, total_modules=1)
        p.module_progress = {"m": ModuleProgress("m", state=ModuleState.INITIALIZED)}
        p.recalculate_counts()
        d = p.to_dict()
        assert d["init_id"] == "run-1"
        assert d["state"] == "COMPLETED"
        assert "m" in d["modules"]


# ---------------------------------------------------------------------------
# ModuleInitializer - Basic API
# ---------------------------------------------------------------------------
class TestInitializerBasicAPI:
    def test_create_run_auto_id(self) -> None:
        init = ModuleInitializer()
        rid = init.create_init_run()
        assert rid.startswith("init-")
        assert init.get_init_state(rid) == InitState.NOT_STARTED

    def test_create_run_custom_id(self) -> None:
        init = ModuleInitializer()
        rid = init.create_init_run("my-run")
        assert rid == "my-run"

    def test_create_duplicate_raises(self) -> None:
        init = ModuleInitializer()
        init.create_init_run("run-1")
        with pytest.raises(ValueError):
            init.create_init_run("run-1")

    def test_unknown_run_raises(self) -> None:
        init = ModuleInitializer()
        with pytest.raises(ModuleNotFoundError):
            init.get_init_state("ghost")

    def test_register_and_list_modules(self) -> None:
        init = ModuleInitializer()
        rid = init.create_init_run()
        init.register_module(rid, ModuleNode("a"))
        init.register_module(rid, ModuleNode("b"))
        assert set(init.get_registered_modules(rid)) == {"a", "b"}

    def test_register_batch(self) -> None:
        init = ModuleInitializer()
        rid = init.create_init_run()
        modules = [ModuleNode(f"m{i}") for i in range(5)]
        init.register_modules(rid, modules)
        assert len(init.get_registered_modules(rid)) == 5

    def test_register_duplicate_raises(self) -> None:
        init = ModuleInitializer()
        rid = init.create_init_run()
        init.register_module(rid, ModuleNode("same"))
        with pytest.raises(ModuleAlreadyRegisteredError):
            init.register_module(rid, ModuleNode("same"))

    def test_register_after_execute_raises(self) -> None:
        init = ModuleInitializer()
        rid = init.create_init_run()
        init.execute_init(rid)
        with pytest.raises(InitStateError):
            init.register_module(rid, ModuleNode("late"))


# ---------------------------------------------------------------------------
# ModuleInitializer - Happy Path
# ---------------------------------------------------------------------------
class TestInitializerHappyPath:
    def test_empty_run(self) -> None:
        init = ModuleInitializer()
        rid = init.create_init_run()
        prog = init.execute_init(rid)
        assert prog.state == InitState.COMPLETED
        assert prog.progress_percentage == 100.0
        assert prog.total_modules == 0

    def test_single_module(self, tracker) -> None:
        init = ModuleInitializer()
        rid = init.create_init_run()
        m = ModuleNode("m1")
        m.set_init_callback(tracker.make_init("m1", "hello"))
        init.register_module(rid, m)
        prog = init.execute_init(rid)
        assert prog.state == InitState.COMPLETED
        assert prog.initialized_modules == 1
        assert prog.module_progress["m1"].state == ModuleState.INITIALIZED
        assert init.get_module_result(rid, "m1") == "hello"

    def test_linear_dependency_order(self, tracker) -> None:
        init = ModuleInitializer()
        rid = init.create_init_run()
        ma = ModuleNode("a")
        ma.set_init_callback(tracker.make_init("a", "A"))
        mb = ModuleNode("b", dependencies=["a"])
        mb.set_init_callback(tracker.make_init("b", "B"))
        mc = ModuleNode("c", dependencies=["b"])
        mc.set_init_callback(tracker.make_init("c", "C"))
        init.register_modules(rid, [mb, mc, ma])
        prog = init.execute_init(rid)
        assert prog.state == InitState.COMPLETED
        assert prog.initialized_modules == 3
        assert tracker.call_order.index("a") < tracker.call_order.index("b")
        assert tracker.call_order.index("b") < tracker.call_order.index("c")

    def test_diamond_dependency(self, tracker) -> None:
        init = ModuleInitializer()
        rid = init.create_init_run()
        ma = ModuleNode("a")
        ma.set_init_callback(tracker.make_init("a"))
        mb = ModuleNode("b", dependencies=["a"])
        mb.set_init_callback(tracker.make_init("b"))
        mc = ModuleNode("c", dependencies=["a"])
        mc.set_init_callback(tracker.make_init("c"))
        md = ModuleNode("d", dependencies=["b", "c"])
        md.set_init_callback(tracker.make_init("d"))
        init.register_modules(rid, [mb, md, ma, mc])
        prog = init.execute_init(rid)
        assert prog.state == InitState.COMPLETED
        assert tracker.call_order.index("a") < tracker.call_order.index("b")
        assert tracker.call_order.index("a") < tracker.call_order.index("c")
        assert tracker.call_order.index("b") < tracker.call_order.index("d")
        assert tracker.call_order.index("c") < tracker.call_order.index("d")

    def test_get_all_results(self, tracker) -> None:
        init = ModuleInitializer()
        rid = init.create_init_run()
        for i in range(3):
            m = ModuleNode(f"m{i}")
            m.set_init_callback(tracker.make_init(f"m{i}", i * 10))
            init.register_module(rid, m)
        init.execute_init(rid)
        results = init.get_all_results(rid)
        assert results == {"m0": 0, "m1": 10, "m2": 20}
        results["m0"] = 999
        assert init.get_module_result(rid, "m0") == 0

    def test_progress_snapshot_is_deepcopy(self, tracker) -> None:
        init = ModuleInitializer()
        rid = init.create_init_run()
        m = ModuleNode("m1")
        m.set_init_callback(tracker.make_init("m1", "data"))
        init.register_module(rid, m)
        snap1 = init.get_progress(rid)
        assert snap1.state == InitState.NOT_STARTED
        init.execute_init(rid)
        assert snap1.state == InitState.NOT_STARTED
        snap2 = init.get_progress(rid)
        assert snap2.state == InitState.COMPLETED


# ---------------------------------------------------------------------------
# ModuleInitializer - Failure & Isolation
# ---------------------------------------------------------------------------
class TestInitializerFailureIsolation:
    def test_root_failure_isolates_all_downstream(self, tracker) -> None:
        init = ModuleInitializer()
        rid = init.create_init_run()

        ma = ModuleNode("a")
        ma.set_init_callback(tracker.make_failing_init("a", RuntimeError("DB down")))
        mb = ModuleNode("b", dependencies=["a"])
        mb.set_init_callback(tracker.make_init("b", "B"))
        mc = ModuleNode("c", dependencies=["b"])
        mc.set_init_callback(tracker.make_init("c", "C"))
        mi = ModuleNode("indep")
        mi.set_init_callback(tracker.make_init("indep", "I"))

        init.register_modules(rid, [ma, mb, mc, mi])
        prog = init.execute_init(rid)

        assert prog.state == InitState.PARTIAL_COMPLETED
        assert prog.module_progress["a"].state == ModuleState.FAILED
        assert "DB down" in prog.module_progress["a"].error_message
        assert prog.module_progress["b"].state == ModuleState.ISOLATED
        assert prog.module_progress["c"].state == ModuleState.ISOLATED
        assert prog.module_progress["indep"].state == ModuleState.INITIALIZED

        assert "b" not in tracker.call_count
        assert "c" not in tracker.call_count
        assert tracker.call_count["indep"] == 1

    def test_midlevel_failure_isolates_downstream(self, tracker) -> None:
        init = ModuleInitializer()
        rid = init.create_init_run()

        cfg = ModuleNode("config")
        cfg.set_init_callback(tracker.make_init("config", "CFG"))
        db = ModuleNode("db", dependencies=["config"])
        db.set_init_callback(tracker.make_failing_init("db", IOError("conn refused")))
        cache = ModuleNode("cache", dependencies=["config"])
        cache.set_init_callback(tracker.make_init("cache", "CACHE"))
        app = ModuleNode("app", dependencies=["db", "cache"])
        app.set_init_callback(tracker.make_init("app", "APP"))

        init.register_modules(rid, [cfg, db, cache, app])
        prog = init.execute_init(rid)

        assert prog.state == InitState.PARTIAL_COMPLETED
        assert prog.module_progress["config"].state == ModuleState.INITIALIZED
        assert prog.module_progress["db"].state == ModuleState.FAILED
        assert prog.module_progress["cache"].state == ModuleState.INITIALIZED
        assert prog.module_progress["app"].state == ModuleState.ISOLATED

    def test_all_failed_chain(self, tracker) -> None:
        init = ModuleInitializer()
        rid = init.create_init_run()
        m = ModuleNode("a")
        m.set_init_callback(tracker.make_failing_init("a", Exception("x")))
        init.register_module(rid, m)
        prog = init.execute_init(rid)
        assert prog.state == InitState.FAILED
        assert prog.failed_modules == 1

    def test_isolation_reason_reflects_failed_deps(self, tracker) -> None:
        init = ModuleInitializer()
        rid = init.create_init_run()
        ma = ModuleNode("a")
        ma.set_init_callback(tracker.make_failing_init("a", RuntimeError("err")))
        mb = ModuleNode("b", dependencies=["a"])
        mb.set_init_callback(tracker.make_init("b", "B"))
        mc = ModuleNode("c", dependencies=["b"])
        mc.set_init_callback(tracker.make_init("c", "C"))
        init.register_modules(rid, [ma, mb, mc])
        init.execute_init(rid)
        pb = init.get_module_progress(rid, "b")
        assert "依赖模块失败" in pb.error_message and "a" in pb.error_message
        pc = init.get_module_progress(rid, "c")
        assert "依赖模块被隔离" in pc.error_message and "b" in pc.error_message

    def test_circular_dependency_raises_and_marks_failed(self) -> None:
        init = ModuleInitializer()
        rid = init.create_init_run()
        init.register_modules(rid, [
            ModuleNode("a", dependencies=["b"]),
            ModuleNode("b", dependencies=["a"]),
        ])
        with pytest.raises(CircularDependencyError):
            init.execute_init(rid)
        assert init.get_init_state(rid) == InitState.FAILED

    def test_missing_dependency_raises(self) -> None:
        init = ModuleInitializer()
        rid = init.create_init_run()
        init.register_module(rid, ModuleNode("a", dependencies=["ghost"]))
        with pytest.raises(DependencyNotFoundError):
            init.execute_init(rid)
        assert init.get_init_state(rid) == InitState.FAILED

    def test_get_failed_and_isolated_modules(self, tracker) -> None:
        init = ModuleInitializer()
        rid = init.create_init_run()
        ma = ModuleNode("a")
        ma.set_init_callback(tracker.make_failing_init("a", Exception()))
        mb = ModuleNode("b", dependencies=["a"])
        mb.set_init_callback(tracker.make_init("b", "B"))
        mc = ModuleNode("c")
        mc.set_init_callback(tracker.make_init("c", "C"))
        init.register_modules(rid, [ma, mb, mc])
        init.execute_init(rid)
        assert init.get_failed_modules(rid) == ["a"]
        assert init.get_isolated_modules(rid) == ["b"]


# ---------------------------------------------------------------------------
# ModuleInitializer - Retry
# ---------------------------------------------------------------------------
class TestInitializerRetry:
    def test_retry_failed_module_succeeds(self, tracker) -> None:
        init = ModuleInitializer()
        rid = init.create_init_run()
        ma = ModuleNode("a")
        ma.set_init_callback(tracker.make_fail_then_succeed("a", fail_count=1))
        mb = ModuleNode("b", dependencies=["a"])
        mb.set_init_callback(tracker.make_init("b", "B"))
        init.register_modules(rid, [ma, mb])

        prog1 = init.execute_init(rid)
        assert prog1.module_progress["a"].state == ModuleState.FAILED
        assert prog1.module_progress["b"].state == ModuleState.ISOLATED

        prog2 = init.retry_module(rid, "a", extra_retries=0)
        assert prog2.module_progress["a"].state == ModuleState.INITIALIZED
        assert prog2.module_progress["b"].state == ModuleState.INITIALIZED
        assert init.get_module_result(rid, "a") is not None
        assert init.get_module_result(rid, "b") == "B"
        assert tracker.call_count["a"] == 2

    def test_retry_cascades_multiple_levels(self, tracker) -> None:
        init = ModuleInitializer()
        rid = init.create_init_run()
        ma = ModuleNode("a")
        ma.set_init_callback(tracker.make_fail_then_succeed("a", fail_count=1, result="A"))
        mb = ModuleNode("b", dependencies=["a"])
        mb.set_init_callback(tracker.make_init("b", "B"))
        mc = ModuleNode("c", dependencies=["b"])
        mc.set_init_callback(tracker.make_init("c", "C"))
        init.register_modules(rid, [ma, mb, mc])

        init.execute_init(rid)
        assert init.get_isolated_modules(rid) == ["b", "c"]

        init.retry_module(rid, "a")
        for mid in ("a", "b", "c"):
            assert init.get_module_progress(rid, mid).state == ModuleState.INITIALIZED

    def test_retry_sibling_branches(self, tracker) -> None:
        init = ModuleInitializer()
        rid = init.create_init_run()
        root = ModuleNode("root")
        root.set_init_callback(tracker.make_fail_then_succeed("root", fail_count=1, result="R"))
        b1 = ModuleNode("b1", dependencies=["root"])
        b1.set_init_callback(tracker.make_init("b1", "B1"))
        b2 = ModuleNode("b2", dependencies=["root"])
        b2.set_init_callback(tracker.make_init("b2", "B2"))
        b2_child = ModuleNode("b2c", dependencies=["b2"])
        b2_child.set_init_callback(tracker.make_init("b2c", "B2C"))
        init.register_modules(rid, [root, b1, b2, b2_child])

        init.execute_init(rid)
        assert init.get_isolated_modules(rid) == ["b1", "b2", "b2c"]

        prog = init.retry_module(rid, "root")
        assert prog.initialized_modules == 4
        for mid in ("b1", "b2", "b2c"):
            assert tracker.call_count[mid] == 1

    def test_retry_isolated_module_directly(self, tracker) -> None:
        init = ModuleInitializer()
        rid = init.create_init_run()
        ma = ModuleNode("a")
        ma.set_init_callback(tracker.make_fail_then_succeed("a", fail_count=1, result="A"))
        mb = ModuleNode("b", dependencies=["a"])
        mb.set_init_callback(tracker.make_init("b", "B"))
        init.register_modules(rid, [ma, mb])

        init.execute_init(rid)
        assert init.get_module_progress(rid, "a").state == ModuleState.FAILED

        init.retry_module(rid, "a")
        assert init.get_module_progress(rid, "a").state == ModuleState.INITIALIZED
        assert init.get_module_progress(rid, "b").state == ModuleState.INITIALIZED

    def test_retry_isolated_module_without_upstream_fix_remains_isolated(self, tracker) -> None:
        init = ModuleInitializer()
        rid = init.create_init_run()
        ma = ModuleNode("a")
        ma.set_init_callback(tracker.make_failing_init("a", RuntimeError("perm")))
        mb = ModuleNode("b", dependencies=["a"])
        mb.set_init_callback(tracker.make_init("b", "B"))
        init.register_modules(rid, [ma, mb])
        init.execute_init(rid)

        prog = init.retry_module(rid, "b")
        assert prog.module_progress["a"].state == ModuleState.FAILED
        assert prog.module_progress["b"].state == ModuleState.ISOLATED
        assert "b" not in tracker.call_count

    def test_retry_failed_module_still_fails_raises(self, tracker) -> None:
        init = ModuleInitializer()
        rid = init.create_init_run()
        ma = ModuleNode("a")
        ma.set_init_callback(tracker.make_failing_init("a", ValueError("still broken")))
        mb = ModuleNode("b", dependencies=["a"])
        mb.set_init_callback(tracker.make_init("b", "B"))
        init.register_modules(rid, [ma, mb])
        init.execute_init(rid)

        with pytest.raises(RetryLimitExceededError) as excinfo:
            init.retry_module(rid, "a", extra_retries=1)

        err_msg = str(excinfo.value)
        assert "a" in err_msg
        assert "共尝试 3 次" in err_msg
        assert "ValueError" in err_msg or "still broken" in err_msg

        prog = init.get_progress(rid)
        assert prog.module_progress["a"].state == ModuleState.FAILED
        assert prog.module_progress["b"].state == ModuleState.ISOLATED
        assert tracker.call_count["a"] == 3
        assert prog.module_progress["a"].attempts == 3

    def test_retry_limit_exception_has_module_id(self, tracker) -> None:
        init = ModuleInitializer()
        rid = init.create_init_run()
        m = ModuleNode("svc:payments")
        m.set_init_callback(tracker.make_failing_init("svc:payments", RuntimeError("x")))
        init.register_module(rid, m)
        init.execute_init(rid)

        with pytest.raises(RetryLimitExceededError) as excinfo:
            init.retry_module(rid, "svc:payments", extra_retries=0)
        assert "svc:payments" in str(excinfo.value)

    def test_attempts_accumulate_across_retry_cycles(self, tracker) -> None:
        init = ModuleInitializer()
        rid = init.create_init_run()
        ma = ModuleNode("a")
        ma.set_init_callback(tracker.make_failing_init("a", RuntimeError("err")))
        init.register_module(rid, ma)
        init.execute_init(rid)

        prog1 = init.get_module_progress(rid, "a")
        attempts_after_execute = prog1.attempts
        assert attempts_after_execute == 1

        try:
            init.retry_module(rid, "a", extra_retries=0)
        except RetryLimitExceededError:
            pass
        prog2 = init.get_module_progress(rid, "a")
        assert prog2.attempts == attempts_after_execute + 1

        try:
            init.retry_module(rid, "a", extra_retries=2)
        except RetryLimitExceededError:
            pass
        prog3 = init.get_module_progress(rid, "a")
        assert prog3.attempts == 1 + 1 + 3

    def test_retry_all_failed(self, tracker) -> None:
        init = ModuleInitializer()
        rid = init.create_init_run()
        modules: Dict[str, ModuleNode] = {}
        for mid, fail_n in [("a", 1), ("b", 1)]:
            m = ModuleNode(mid)
            m.set_init_callback(
                tracker.make_fail_then_succeed(mid, fail_count=fail_n, result=f"{mid}-ok")
            )
            modules[mid] = m
        modules["c"] = ModuleNode("c", dependencies=["a", "b"])
        modules["c"].set_init_callback(tracker.make_init("c", "C"))
        init.register_modules(rid, list(modules.values()))

        init.execute_init(rid)
        assert len(init.get_failed_modules(rid)) == 2

        prog = init.retry_all_failed(rid)
        assert prog.state == InitState.COMPLETED
        assert prog.initialized_modules == 3
        for mid in ("a", "b", "c"):
            assert init.get_module_progress(rid, mid).state == ModuleState.INITIALIZED

    def test_retry_before_execute_raises(self) -> None:
        init = ModuleInitializer()
        rid = init.create_init_run()
        init.register_module(rid, ModuleNode("a"))
        with pytest.raises(InitStateError):
            init.retry_module(rid, "a")

    def test_retry_nonexistent_module_raises(self) -> None:
        init = ModuleInitializer()
        rid = init.create_init_run()
        init.execute_init(rid)
        with pytest.raises(ModuleNotFoundError):
            init.retry_module(rid, "ghost")

    def test_retry_initialized_module_noop(self, tracker) -> None:
        init = ModuleInitializer()
        rid = init.create_init_run()
        m = ModuleNode("a")
        m.set_init_callback(tracker.make_init("a", "A"))
        init.register_module(rid, m)
        init.execute_init(rid)
        init.retry_module(rid, "a")
        assert tracker.call_count["a"] == 1

    def test_builtin_retries_via_max_retries(self, tracker) -> None:
        init = ModuleInitializer()
        rid = init.create_init_run()
        m = ModuleNode("m", max_retries=2)
        m.set_init_callback(tracker.make_fail_then_succeed("m", fail_count=2, result="OK"))
        init.register_module(rid, m)
        prog = init.execute_init(rid)
        assert prog.module_progress["m"].state == ModuleState.INITIALIZED
        assert tracker.call_count["m"] == 3


# ---------------------------------------------------------------------------
# ModuleInitializer - Idempotency
# ---------------------------------------------------------------------------
class TestInitializerIdempotency:
    def test_execute_idempotent_after_completed(self, tracker) -> None:
        init = ModuleInitializer()
        rid = init.create_init_run()
        m = ModuleNode("m1")
        m.set_init_callback(tracker.make_init("m1", 42))
        init.register_module(rid, m)
        p1 = init.execute_init(rid)
        p2 = init.execute_init(rid)
        assert p1.state == p2.state == InitState.COMPLETED
        assert tracker.call_count["m1"] == 1

    def test_execute_idempotent_after_partial(self, tracker) -> None:
        init = ModuleInitializer()
        rid = init.create_init_run()
        ma = ModuleNode("a")
        ma.set_init_callback(tracker.make_failing_init("a", Exception("x")))
        init.register_module(rid, ma)
        init.execute_init(rid)
        p = init.execute_init(rid)
        assert p.state == InitState.FAILED
        assert tracker.call_count["a"] == 1


# ---------------------------------------------------------------------------
# Integration scenarios
# ---------------------------------------------------------------------------
class TestIntegrationScenarios:
    def test_full_webapp_stack(self, tracker) -> None:
        """模拟 Web 应用完整初始化链路"""
        init = ModuleInitializer()
        rid = init.create_init_run("webapp-boot")

        modules_spec: List[Tuple[str, List[str], Any]] = [
            ("config", [], {"env": "prod", "port": 8080}),
            ("logger", ["config"], {"log_level": "INFO"}),
            ("db_pool", ["config", "logger"], {"pool_size": 10}),
            ("redis", ["config"], {"cache": "ok"}),
            ("auth_svc", ["db_pool", "redis"], {"jwt": "secret"}),
            ("api_server", ["auth_svc", "logger"], {"running": True}),
        ]

        for mid, deps, result in modules_spec:
            m = ModuleNode(mid, dependencies=deps, description=f"{mid} 模块")
            m.set_init_callback(tracker.make_init(mid, result))
            init.register_module(rid, m)

        prog = init.execute_init(rid)
        assert prog.state == InitState.COMPLETED
        assert prog.initialized_modules == 6

        order = tracker.call_order
        assert order.index("config") < order.index("logger")
        assert order.index("config") < order.index("db_pool")
        assert order.index("logger") < order.index("db_pool")
        assert order.index("db_pool") < order.index("auth_svc")
        assert order.index("redis") < order.index("auth_svc")
        assert order.index("auth_svc") < order.index("api_server")

        assert init.get_module_result(rid, "api_server")["running"] is True

    def test_partial_failure_with_retry_full_recovery(self, tracker) -> None:
        init = ModuleInitializer()
        rid = init.create_init_run("etl-pipeline")

        cfg = ModuleNode("config")
        cfg.set_init_callback(tracker.make_init("config", {"batch_size": 100}))

        src = ModuleNode("source_db", dependencies=["config"])
        src.set_init_callback(
            tracker.make_fail_then_succeed("source_db", fail_count=1, result="connected")
        )

        tgt = ModuleNode("target_db", dependencies=["config"])
        tgt.set_init_callback(tracker.make_init("target_db", "connected"))

        pipeline = ModuleNode("etl_pipeline", dependencies=["source_db", "target_db"])
        pipeline.set_init_callback(tracker.make_init("etl_pipeline", "running"))

        init.register_modules(rid, [cfg, src, tgt, pipeline])

        p1 = init.execute_init(rid)
        assert p1.state == InitState.PARTIAL_COMPLETED
        assert init.get_failed_modules(rid) == ["source_db"]
        assert init.get_isolated_modules(rid) == ["etl_pipeline"]

        p2 = init.retry_module(rid, "source_db")
        assert p2.state == InitState.COMPLETED
        for mid in ("config", "source_db", "target_db", "etl_pipeline"):
            assert init.get_module_progress(rid, mid).state == ModuleState.INITIALIZED
        assert tracker.call_count["source_db"] == 2
        assert tracker.call_count["etl_pipeline"] == 1

    def test_microservices_independent_failure(self, tracker) -> None:
        """模拟多个微服务独立启动，某一个失败不影响其他"""
        init = ModuleInitializer()
        rid = init.create_init_run("micro-boot")

        svc_ids = ["orders", "users", "payments", "inventory", "notifications"]
        fail_idx = 2

        for i, sid in enumerate(svc_ids):
            m = ModuleNode(
                sid, description=f"微服务 {sid}", metadata={"version": f"v{i+1}"}
            )
            if i == fail_idx:
                m.set_init_callback(
                    tracker.make_failing_init(sid, RuntimeError("端口被占用"))
                )
            else:
                m.set_init_callback(tracker.make_init(sid, {"status": "up"}))
            init.register_module(rid, m)

        prog = init.execute_init(rid)
        assert prog.state == InitState.PARTIAL_COMPLETED
        assert prog.initialized_modules == 4
        assert prog.failed_modules == 1

        for i, sid in enumerate(svc_ids):
            expected_state = (
                ModuleState.FAILED if i == fail_idx else ModuleState.INITIALIZED
            )
            assert prog.module_progress[sid].state == expected_state

    def test_context_data_passing(self) -> None:
        """通过 init context 共享数据"""
        init = ModuleInitializer()
        rid = init.create_init_run()

        captured_ctx = {}

        m1 = ModuleNode("m1")
        def m1_init(ctx):
            captured_ctx["m1"] = ctx
            return "r1"
        m1.set_init_callback(m1_init)

        m2 = ModuleNode("m2", dependencies=["m1"])
        def m2_init(ctx):
            captured_ctx["m2"] = ctx
            return "r2"
        m2.set_init_callback(m2_init)

        init.register_modules(rid, [m1, m2])
        init.execute_init(rid, context={"global_key": "gv"})
        assert captured_ctx["m1"] == {"global_key": "gv"}
        assert captured_ctx["m2"] == {"global_key": "gv"}
