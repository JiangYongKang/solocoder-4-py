import copy
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

from .constants import (
    InitState,
    ModuleState,
    TERMINAL_INIT_STATES,
    TERMINAL_MODULE_STATES,
)
from .exceptions import (
    CircularDependencyError,
    DependencyNotFoundError,
    InitStateError,
    ModuleAlreadyRegisteredError,
    ModuleInitFailureError,
    ModuleNotFoundError,
    RetryLimitExceededError,
)
from .module import ModuleNode
from .topology import TopologyAnalyzer


@dataclass
class ModuleProgress:
    """单个模块的初始化进度追踪"""

    module_id: str
    state: ModuleState = ModuleState.PENDING
    attempts: int = 0
    error_message: str = ""
    init_result: Any = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    duration_seconds: float = 0.0

    def is_terminal(self) -> bool:
        return self.state in TERMINAL_MODULE_STATES

    def mark_initializing(self, clock: Callable[[], float] = time.monotonic) -> None:
        self.state = ModuleState.INITIALIZING
        self.attempts += 1
        self.started_at = clock()

    def mark_initialized(
        self,
        result: Any,
        duration: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.state = ModuleState.INITIALIZED
        self.init_result = result
        self.duration_seconds = duration
        self.completed_at = clock()
        self.error_message = ""

    def mark_failed(
        self,
        error: Exception,
        duration: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.state = ModuleState.FAILED
        self.duration_seconds = duration
        self.completed_at = clock()
        self.error_message = f"{type(error).__name__}: {error}"

    def mark_isolated(self, reason: str) -> None:
        self.state = ModuleState.ISOLATED
        self.error_message = reason

    def reset_for_retry(self) -> None:
        """将状态重置为 PENDING 以支持重试（保留 attempts 累计计数）"""
        self.state = ModuleState.PENDING
        self.error_message = ""
        self.init_result = None
        self.started_at = None
        self.completed_at = None
        self.duration_seconds = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "module_id": self.module_id,
            "state": self.state.value,
            "attempts": self.attempts,
            "error_message": self.error_message,
            "duration_seconds": round(self.duration_seconds, 4),
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


@dataclass
class InitProgress:
    """整体初始化流程的进度快照"""

    init_id: str = ""
    state: InitState = InitState.NOT_STARTED
    total_modules: int = 0
    initialized_modules: int = 0
    failed_modules: int = 0
    isolated_modules: int = 0
    pending_modules: int = 0
    initializing_modules: int = 0
    progress_percentage: float = 100.0
    module_progress: Dict[str, ModuleProgress] = field(default_factory=dict)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    error_message: str = ""

    def recalculate_counts(self) -> None:
        self.initialized_modules = 0
        self.failed_modules = 0
        self.isolated_modules = 0
        self.pending_modules = 0
        self.initializing_modules = 0

        for mp in self.module_progress.values():
            if mp.state == ModuleState.INITIALIZED:
                self.initialized_modules += 1
            elif mp.state == ModuleState.FAILED:
                self.failed_modules += 1
            elif mp.state == ModuleState.ISOLATED:
                self.isolated_modules += 1
            elif mp.state == ModuleState.INITIALIZING:
                self.initializing_modules += 1
            else:
                self.pending_modules += 1

        if self.total_modules == 0:
            self.progress_percentage = 100.0
        else:
            done = self.initialized_modules + self.failed_modules + self.isolated_modules
            self.progress_percentage = round(done / self.total_modules * 100, 2)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "init_id": self.init_id,
            "state": self.state.value,
            "total_modules": self.total_modules,
            "initialized_modules": self.initialized_modules,
            "failed_modules": self.failed_modules,
            "isolated_modules": self.isolated_modules,
            "pending_modules": self.pending_modules,
            "initializing_modules": self.initializing_modules,
            "progress_percentage": self.progress_percentage,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error_message": self.error_message,
            "modules": {mid: mp.to_dict() for mid, mp in self.module_progress.items()},
        }


class _InitRunContext:
    """单个初始化 run 的内部上下文"""

    def __init__(self, init_id: str) -> None:
        self.init_id = init_id
        self.state: InitState = InitState.NOT_STARTED
        self.modules: Dict[str, ModuleNode] = {}
        self.progress: Dict[str, ModuleProgress] = {}
        self.context_data: Dict[str, Any] = {}
        self.started_at: Optional[float] = None
        self.completed_at: Optional[float] = None
        self.error_message: str = ""


class ModuleInitializer:
    """模块初始化编排器

    负责管理模块注册、按依赖顺序初始化、失败隔离以及局部重试。

    典型使用流程：
    1. 创建编排器实例
    2. 创建一个初始化 run（create_init_run）
    3. 注册模块（register_module / register_modules）
    4. 执行初始化（execute_init）
    5. 查询进度或获取结果（get_progress / get_module_result）
    6. 对失败模块进行局部重试（retry_module）
    """

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._runs: Dict[str, _InitRunContext] = {}

    # ------------------------------------------------------------------
    # Run 管理
    # ------------------------------------------------------------------
    def create_init_run(self, init_id: Optional[str] = None) -> str:
        """创建一个新的初始化 run

        :param init_id: 可选的自定义 ID，不提供时自动生成
        :returns: 初始化 run 的 ID
        :raises ValueError: init_id 已存在
        """
        if init_id is None:
            init_id = f"init-{uuid.uuid4().hex[:12]}"
        if init_id in self._runs:
            raise ValueError(f"初始化 run {init_id!r} 已存在")
        self._runs[init_id] = _InitRunContext(init_id)
        return init_id

    def _get_run(self, init_id: str) -> _InitRunContext:
        if init_id not in self._runs:
            raise ModuleNotFoundError(f"初始化 run {init_id!r} 不存在")
        return self._runs[init_id]

    def get_init_state(self, init_id: str) -> InitState:
        return self._get_run(init_id).state

    # ------------------------------------------------------------------
    # 模块注册
    # ------------------------------------------------------------------
    def register_module(self, init_id: str, module: ModuleNode) -> None:
        """注册单个模块

        :raises InitStateError: 初始化流程已经开始执行后再注册
        :raises ModuleAlreadyRegisteredError: 模块 ID 重复
        """
        run = self._get_run(init_id)
        if run.state != InitState.NOT_STARTED:
            raise InitStateError(
                f"初始化 run {init_id!r} 已启动 (状态={run.state.value})，无法再注册模块"
            )
        if module.module_id in run.modules:
            raise ModuleAlreadyRegisteredError(
                f"模块 {module.module_id!r} 已在 run {init_id!r} 中注册"
            )
        run.modules[module.module_id] = module
        run.progress[module.module_id] = ModuleProgress(module_id=module.module_id)

    def register_modules(self, init_id: str, modules: List[ModuleNode]) -> None:
        """批量注册模块"""
        for m in modules:
            self.register_module(init_id, m)

    def get_registered_modules(self, init_id: str) -> List[str]:
        run = self._get_run(init_id)
        return list(run.modules.keys())

    # ------------------------------------------------------------------
    # 核心：执行初始化
    # ------------------------------------------------------------------
    def execute_init(self, init_id: str, context: Any = None) -> InitProgress:
        """执行初始化流程

        对已注册模块进行拓扑排序后按序初始化，
        失败模块的所有下游传递依赖将被隔离（标记为 ISOLATED），
        不影响独立子图的模块初始化。

        :raises CircularDependencyError: 模块依赖图存在环
        :raises DependencyNotFoundError: 存在未注册的依赖
        """
        run = self._get_run(init_id)

        if run.state in TERMINAL_INIT_STATES:
            return self._make_progress_snapshot(run)

        if run.state == InitState.RUNNING:
            raise InitStateError(
                f"初始化 run {init_id!r} 正在执行中，无法重复调用 execute_init"
            )

        run.state = InitState.RUNNING
        run.started_at = self._clock()

        try:
            order = TopologyAnalyzer.sort(run.modules)
        except (CircularDependencyError, DependencyNotFoundError) as exc:
            run.state = InitState.FAILED
            run.completed_at = self._clock()
            run.error_message = str(exc)
            raise

        for module_id in order:
            if run.progress[module_id].state != ModuleState.PENDING:
                continue

            deps_ok = self._check_dependencies_ready(run, module_id)
            if not deps_ok:
                self._isolate_module(run, module_id)
                self._isolate_all_downstream(run, module_id)
                continue

            self._initialize_module(run, module_id, context)

            if run.progress[module_id].state == ModuleState.FAILED:
                self._isolate_all_downstream(run, module_id)

        run.completed_at = self._clock()
        run.state = self._determine_final_state(run)
        return self._make_progress_snapshot(run)

    def _check_dependencies_ready(self, run: _InitRunContext, module_id: str) -> bool:
        """检查模块的所有直接依赖是否都已初始化成功"""
        node = run.modules[module_id]
        for dep in node.dependencies:
            if dep not in run.progress:
                return False
            dep_state = run.progress[dep].state
            if dep_state != ModuleState.INITIALIZED:
                return False
        return True

    def _initialize_module(
        self, run: _InitRunContext, module_id: str, context: Any
    ) -> None:
        """执行单个模块的初始化（含有限重试）"""
        node = run.modules[module_id]
        prog = run.progress[module_id]
        max_retries = node.max_retries
        total_attempts = max_retries + 1

        last_error: Optional[Exception] = None
        for _ in range(total_attempts):
            prog.mark_initializing(self._clock)
            start = self._clock()
            try:
                result = node.execute_init(context)
                duration = self._clock() - start
                prog.mark_initialized(result, duration, self._clock)
                run.context_data[module_id] = result
                last_error = None
                return
            except Exception as exc:
                duration = self._clock() - start
                last_error = exc
                prog.mark_failed(exc, duration, self._clock)

        if last_error is not None:
            prog.state = ModuleState.FAILED

    def _isolate_module(self, run: _InitRunContext, module_id: str, reason: str = "") -> None:
        """将单个模块标记为 ISOLATED（不执行初始化回调）"""
        prog = run.progress[module_id]
        if prog.state in TERMINAL_MODULE_STATES:
            return
        if not reason:
            reason = self._build_isolation_reason(run, module_id)
        prog.mark_isolated(reason)

    def _build_isolation_reason(self, run: _InitRunContext, module_id: str) -> str:
        """构建模块被隔离的原因说明"""
        node = run.modules[module_id]
        failed_deps = []
        isolated_deps = []
        for dep in node.dependencies:
            if dep in run.progress:
                dep_state = run.progress[dep].state
                if dep_state == ModuleState.FAILED:
                    failed_deps.append(dep)
                elif dep_state == ModuleState.ISOLATED:
                    isolated_deps.append(dep)
        parts = []
        if failed_deps:
            parts.append(f"依赖模块失败: {', '.join(sorted(failed_deps))}")
        if isolated_deps:
            parts.append(f"依赖模块被隔离: {', '.join(sorted(isolated_deps))}")
        if not parts:
            parts = ["上游依赖不满足"]
        return "; ".join(parts)

    def _isolate_all_downstream(self, run: _InitRunContext, module_id: str) -> None:
        """隔离某模块的所有下游传递依赖"""
        downstream = TopologyAnalyzer.get_all_downstream(run.modules, module_id)
        for downstream_id in downstream:
            self._isolate_module(run, downstream_id)

    def _determine_final_state(self, run: _InitRunContext) -> InitState:
        failed = sum(1 for p in run.progress.values() if p.state == ModuleState.FAILED)
        isolated = sum(1 for p in run.progress.values() if p.state == ModuleState.ISOLATED)
        if failed == 0 and isolated == 0:
            return InitState.COMPLETED
        total = len(run.progress)
        done_ok = sum(1 for p in run.progress.values() if p.state == ModuleState.INITIALIZED)
        if done_ok > 0 and (failed > 0 or isolated > 0):
            return InitState.PARTIAL_COMPLETED
        return InitState.FAILED

    def _make_progress_snapshot(self, run: _InitRunContext) -> InitProgress:
        prog = InitProgress(
            init_id=run.init_id,
            state=run.state,
            total_modules=len(run.modules),
            module_progress={mid: copy.deepcopy(mp) for mid, mp in run.progress.items()},
            started_at=run.started_at,
            completed_at=run.completed_at,
            error_message=run.error_message,
        )
        prog.recalculate_counts()
        return prog

    # ------------------------------------------------------------------
    # 进度 & 结果查询
    # ------------------------------------------------------------------
    def get_progress(self, init_id: str) -> InitProgress:
        """获取初始化进度快照（深拷贝，不随后续执行变化）"""
        run = self._get_run(init_id)
        return self._make_progress_snapshot(run)

    def get_module_progress(self, init_id: str, module_id: str) -> ModuleProgress:
        run = self._get_run(init_id)
        if module_id not in run.progress:
            raise ModuleNotFoundError(f"模块 {module_id!r} 未在 run {init_id!r} 中注册")
        return copy.deepcopy(run.progress[module_id])

    def get_module_result(self, init_id: str, module_id: str) -> Any:
        run = self._get_run(init_id)
        if module_id not in run.modules:
            raise ModuleNotFoundError(f"模块 {module_id!r} 未在 run {init_id!r} 中注册")
        return run.context_data.get(module_id)

    def get_all_results(self, init_id: str) -> Dict[str, Any]:
        run = self._get_run(init_id)
        return copy.deepcopy(run.context_data)

    def get_failed_modules(self, init_id: str) -> List[str]:
        run = self._get_run(init_id)
        return sorted(mid for mid, mp in run.progress.items() if mp.state == ModuleState.FAILED)

    def get_isolated_modules(self, init_id: str) -> List[str]:
        run = self._get_run(init_id)
        return sorted(mid for mid, mp in run.progress.items() if mp.state == ModuleState.ISOLATED)

    # ------------------------------------------------------------------
    # 局部重试
    # ------------------------------------------------------------------
    def retry_module(
        self,
        init_id: str,
        module_id: str,
        context: Any = None,
        extra_retries: int = 0,
    ) -> InitProgress:
        """对失败模块进行局部重试

        重试逻辑：
        1. 只允许重试状态为 FAILED 或 ISOLATED 的模块
        2. 若模块是因上游依赖失败/隔离导致的 ISOLATED，则先检查上游是否已就绪
        3. 重试成功后，会尝试恢复其下游中仅因本模块失败而被隔离的模块
        4. extra_retries 额外的重试次数（叠加模块自身的 max_retries）

        :raises ModuleNotFoundError: run 或 module 不存在
        :raises InitStateError: 初始化尚未执行
        :raises RetryLimitExceededError: 超过重试限制
        """
        run = self._get_run(init_id)

        if run.state == InitState.NOT_STARTED:
            raise InitStateError(
                f"初始化 run {init_id!r} 尚未执行，请先调用 execute_init"
            )

        if module_id not in run.modules:
            raise ModuleNotFoundError(f"模块 {module_id!r} 未在 run {init_id!r} 中注册")

        prog = run.progress[module_id]
        if prog.state not in (ModuleState.FAILED, ModuleState.ISOLATED):
            return self._make_progress_snapshot(run)

        if prog.state == ModuleState.ISOLATED:
            if not self._check_dependencies_ready(run, module_id):
                return self._make_progress_snapshot(run)

        node = run.modules[module_id]
        prog.reset_for_retry()

        max_retries = node.max_retries + extra_retries
        total_attempts = max_retries + 1
        last_error: Optional[Exception] = None

        for _ in range(total_attempts):
            prog.mark_initializing(self._clock)
            start = self._clock()
            try:
                result = node.execute_init(context)
                duration = self._clock() - start
                prog.mark_initialized(result, duration, self._clock)
                run.context_data[module_id] = result
                last_error = None
                break
            except Exception as exc:
                duration = self._clock() - start
                last_error = exc
                prog.mark_failed(exc, duration, self._clock)

        if prog.state == ModuleState.INITIALIZED:
            self._retry_affected_downstream(run, module_id, context)
        elif prog.state == ModuleState.FAILED:
            self._isolate_all_downstream(run, module_id)

        run.completed_at = self._clock()
        run.state = self._determine_final_state(run)

        if last_error is not None and prog.state == ModuleState.FAILED:
            raise RetryLimitExceededError(
                f"模块 {module_id!r} 重试次数已达上限（共尝试 {prog.attempts} 次），"
                f"最后错误: {type(last_error).__name__}: {last_error}"
            )

        return self._make_progress_snapshot(run)

    def _retry_affected_downstream(
        self, run: _InitRunContext, module_id: str, context: Any
    ) -> None:
        """当某模块重试成功后，尝试恢复（重试）仅因它而被隔离的下游模块"""
        downstream = TopologyAnalyzer.get_all_downstream(run.modules, module_id)
        dependents_map = TopologyAnalyzer.get_dependents(run.modules)
        visited: Set[str] = set()

        def _can_retry(mid: str) -> bool:
            node = run.modules[mid]
            for dep in node.dependencies:
                dep_state = run.progress[dep].state
                if dep_state != ModuleState.INITIALIZED:
                    return False
            return True

        def _retry_recursive(mid: str) -> None:
            if mid in visited:
                return
            visited.add(mid)
            prog = run.progress[mid]
            if prog.state == ModuleState.INITIALIZED:
                for child in dependents_map.get(mid, []):
                    _retry_recursive(child)
                return
            if prog.state != ModuleState.ISOLATED:
                return
            if not _can_retry(mid):
                return

            node = run.modules[mid]
            prog.reset_for_retry()
            prog.mark_initializing(self._clock)
            start = self._clock()
            try:
                result = node.execute_init(context)
                duration = self._clock() - start
                prog.mark_initialized(result, duration, self._clock)
                run.context_data[mid] = result
                for child in dependents_map.get(mid, []):
                    _retry_recursive(child)
            except Exception as exc:
                duration = self._clock() - start
                prog.mark_failed(exc, duration, self._clock)
                self._isolate_all_downstream(run, mid)

        for d in downstream:
            _retry_recursive(d)

    def retry_all_failed(
        self, init_id: str, context: Any = None, extra_retries: int = 1
    ) -> InitProgress:
        """重试所有 FAILED 或 ISOLATED 的模块

        按拓扑升序逐个重试，以尽可能先恢复上游后恢复下游。
        """
        run = self._get_run(init_id)

        candidates = [
            mid for mid, mp in run.progress.items()
            if mp.state in (ModuleState.FAILED, ModuleState.ISOLATED)
        ]
        if not candidates:
            return self._make_progress_snapshot(run)

        try:
            order = TopologyAnalyzer.sort(run.modules)
        except (CircularDependencyError, DependencyNotFoundError):
            order = list(run.modules.keys())

        sorted_candidates = [mid for mid in order if mid in candidates]

        last_prog = self._make_progress_snapshot(run)
        for mid in sorted_candidates:
            try:
                last_prog = self.retry_module(init_id, mid, context, extra_retries)
            except RetryLimitExceededError:
                last_prog = self._make_progress_snapshot(run)

        return last_prog
