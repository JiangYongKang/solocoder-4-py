# 模块初始化依赖图模块 (module_init_graph)

本模块使用纯内存数据结构实现了**模块化应用启动的初始化编排引擎**，支持模块依赖声明、启动顺序解析、循环依赖检测（带详细报告）、失败隔离和局部重试。

## 1. 模块功能

| 能力 | 说明 |
|------|------|
| 模块依赖声明 | 每个模块可声明对其他模块的依赖（`dependencies`），形成有向图 |
| 拓扑排序启动 | 使用 Kahn 算法对依赖图拓扑排序，保证合法的启动顺序 |
| 循环依赖检测 | 基于 DFS 查找所有简单环，生成结构化的 `CycleReport` 报告 |
| 失败自动隔离 | 某模块初始化失败时，其所有**下游传递依赖**自动标记为 `ISOLATED` |
| 局部重试恢复 | 对失败模块重试成功后，自动级联恢复仅因它被隔离的下游模块 |
| 内置重试机制 | 每个模块可声明 `max_retries`，初始化失败时自动重试 |
| 进度追踪 | 支持查询每个模块和整体初始化流程的状态、耗时、尝试次数 |
| 上下文传递 | 初始化回调支持接收全局 context 对象，用于跨模块共享数据 |

## 2. 核心概念

### 2.1 组件

- **`ModuleNode`**：模块节点定义。封装模块 ID、依赖列表、初始化回调、最大重试次数、元数据等。
- **`ModuleInitializer`**：初始化编排器。负责管理初始化 run、模块注册、按序初始化、失败隔离、局部重试、进度追踪。
- **`TopologyAnalyzer`**：拓扑分析器。提供拓扑排序、循环依赖检测、上下游依赖分析、层级计算等工具方法。
- **`CycleReport`**：循环依赖详细报告。包含所有检测到的环以及可读的格式化描述。
- **状态枚举**：`ModuleState`（单模块状态）与 `InitState`（整体流程状态）。
- **进度对象**：`ModuleProgress`（单模块进度）与 `InitProgress`（整体进度快照）。

### 2.2 模块状态机 (ModuleState)

```
PENDING ──▶ INITIALIZING ──┬──▶ INITIALIZED   (初始化成功)
                             ├──▶ FAILED        (执行异常，尝试次数用尽)
                             └──▶ ISOLATED      (上游依赖失败/被隔离，不执行)
```

### 2.3 整体初始化状态机 (InitState)

```
NOT_STARTED ──▶ RUNNING ──┬──▶ COMPLETED          (全部模块初始化成功)
                            ├──▶ PARTIAL_COMPLETED  (部分成功，部分失败/被隔离)
                            └──▶ FAILED             (全部失败或依赖图异常)
```

### 2.4 初始化执行流程

```
┌──────────────────────────────────────────────────────────────────────┐
│  1. create_init_run() → 创建初始化 run                                │
│  2. register_module(s) → 注册模块（含依赖声明）                        │
│                                                                      │
│  3. execute_init() 触发:                                              │
│     ┌─ a. 拓扑排序 + 循环依赖检测（带 CycleReport）                    │
│     ├─ b. 按拓扑顺序逐个初始化模块:                                    │
│     │      i.   检查上游依赖是否全部 INITIALIZED                      │
│     │      ii.  依赖就绪 → 执行回调（自动重试 max_retries 次）          │
│     │      iii. 依赖失败/隔离 → 本模块标记 ISOLATED                   │
│     └─ c. 若某模块 FAILED → 其所有下游传递依赖标记 ISOLATED            │
│                                                                      │
│  4. 返回 InitProgress 进度快照                                        │
│  5. （可选）对失败模块调用 retry_module() → 级联恢复下游               │
└──────────────────────────────────────────────────────────────────────┘
```

## 3. 依赖解析与循环检测

### 3.1 拓扑排序 (Kahn 算法)

`TopologyAnalyzer.sort()` 使用 Kahn 算法对 DAG 做拓扑排序：

1. 构建入度表 `in_degree` 和出边表 `out_edges`
2. 将所有入度为 0 的节点入队
3. 依次出队并输出，减少其邻居的入度；入度为 0 时继续入队
4. 若输出节点数少于总节点数 → 存在环

### 3.2 循环依赖检测

当 Kahn 算法检测到环后，会进一步通过**自环专项扫描 + 基于 DFS 的多环查找**找出所有循环，生成 `CycleReport`：

- **检测范围**：
  - **自循环**（模块依赖自身，如 `dependencies=["self"]`）：作为长度为 1 的环 `["self"]` 报告
  - **普通环**（长度 ≥ 2 的闭环）：基于 DFS 的 Johnson 算法查找所有简单环
- **`CycleReport.cycles`**：所有环的列表，每个环是模块 ID 的有序列表（自环是单元素列表）
- **`CycleReport.involved_modules()`**：所有涉及循环的模块集合
- **`CycleReport.format_report()`**：可读报告，自环格式化为 `a -> a`，形如：
  ```
  检测到 2 个循环依赖:
    [1] config -> logger -> db_pool -> config
    [2] auth -> user_service -> auth
  涉及模块: auth, config, db_pool, logger, user_service
  ```
  自环场景：
  ```
  检测到 1 个循环依赖:
    [1] flaky -> flaky
  涉及模块: flaky
  ```
- 抛出的 `CircularDependencyError` 异常中携带 `cycles` 字段，即使是自环也会被正确填充（不再为空列表）

### 3.3 其他分析能力

| 方法 | 用途 |
|------|------|
| `get_dependents()` | 每个模块的直接下游（谁依赖我） |
| `get_all_downstream()` | 所有传递下游（失败时需要隔离的范围） |
| `get_all_upstream()` | 所有传递上游（我依赖的所有模块） |
| `build_dependency_matrix()` | 依赖传递闭包矩阵（快速判断依赖关系） |
| `topological_levels()` | 计算每个模块的拓扑层级（便于并行调度） |

## 4. 失败隔离与重试

### 4.1 失败隔离策略

当模块 M 初始化失败后（状态变为 `FAILED`）：

1. 调用 `TopologyAnalyzer.get_all_downstream()` 获取 M 的所有传递下游
2. 对每个下游模块 D：
   - 若 D 尚未初始化（`PENDING`），标记为 `ISOLATED`
   - 隔离原因自动构建（例如："依赖模块失败: a, b; 依赖模块被隔离: c"）
3. 与 M 无依赖关系的独立子图继续正常初始化

> **关键特性**：隔离是"最小影响"的——只有真正依赖失败模块的下游才会被隔离。

### 4.2 局部重试 (`retry_module`)

对失败模块进行局部重试的完整流程：

```
重试模块 M:
  ├─ 情况 1：M 是 ISOLATED 状态
  │   └─ 先检查上游是否已就绪；若未就绪直接返回（不执行，不抛异常）
  │
  ├─ 情况 2：M 是 FAILED / ISOLATED（上游就绪）
  │   ├─ 重置 M 的状态为 PENDING（**保留 attempts 累计计数**）
  │   ├─ 执行初始化回调（次数 = max_retries + 1 + extra_retries）
  │   │   ├─ 成功 → INITIALIZED，继续级联恢复下游
  │   │   └─ 全部失败 → 状态 FAILED + 隔离下游 + **抛出 RetryLimitExceededError**
  │   │
  │   └─ 若 M 成功 → 级联恢复下游:
  │        遍历 M 的传递下游中状态为 ISOLATED 的模块:
  │          若某模块 D 的所有上游依赖都已 INITIALIZED:
  │            对 D 执行初始化回调（单次，attempts 同样累计）
  │              ├─ 成功 → 继续递归 D 的下游
  │              └─ 失败 → 隔离 D 的下游
```

> **重要语义**：
> - 当 `retry_module` 的**所有重试尝试耗尽仍失败**时，会抛出 `RetryLimitExceededError`。异常消息中包含模块 ID、累计尝试次数和最后一次错误。
> - `retry_all_failed` 内部会捕获该异常，继续处理剩余失败模块，保证不中断整体批量重试。
> - 调用方可通过 `try/except RetryLimitExceededError` 显式感知重试上限。

### 4.3 attempts 计数规则

`ModuleProgress.attempts` 记录模块的**累计初始化尝试次数**，规则如下：

| 场景 | attempts 处理方式 |
|------|------------------|
| `mark_initializing()` | 每次调用 +1（每次执行回调前都会调用一次） |
| `reset_for_retry()` | **不重置**（保留历史累计值，便于排障） |
| 首次 `execute_init` | 尝试次数 = `max_retries + 1`，全部计入 |
| 调用 `retry_module` | 新增尝试次数 = `max_retries + 1 + extra_retries`，累加到原值 |
| 级联恢复下游 | 下游模块的尝试也计入各自的 attempts |

**排障视角**：运维人员可通过 `module_progress[mid].attempts` 获知某模块从创建以来的**全部初始化尝试次数**，了解故障严重程度。

### 4.4 内置重试 vs 局部重试

| 方式 | 设置位置 | 触发时机 | 是否抛异常 | 用途 |
|------|---------|---------|-----------|------|
| 内置重试 `max_retries=N` | `ModuleNode(max_retries=N)` | 首次 `execute_init` 时自动重试 | ❌ 静默（单个失败不中断整体） | 应对瞬时故障（网络抖动） |
| 局部重试 `extra_retries=N` | `retry_module(extra_retries=N)` | 手动调用时 | ✅ 全部失败抛出 `RetryLimitExceededError` | 修复故障后手动触发恢复，明确感知上限 |

## 5. 使用示例

### 5.1 最小示例：三模块线性初始化

```python
from solocoder_4_py.module_init_graph import (
    ModuleInitializer,
    ModuleNode,
    InitState,
    ModuleState,
)

# 1. 创建编排器
init = ModuleInitializer()
run_id = init.create_init_run("app-boot-20260701")

# 2. 定义模块
config = ModuleNode("config", description="配置加载")
def load_config(ctx=None):
    return {"env": "prod", "db_url": "postgresql://..."}
config.set_init_callback(load_config)

db = ModuleNode("db_pool", dependencies=["config"], description="数据库连接池")
def init_db(ctx=None):
    cfg = init.get_module_result(run_id, "config")
    return {"pool_size": 10, "connected": True}
db.set_init_callback(init_db)

app = ModuleNode("api_server", dependencies=["db_pool"], description="API 服务器")
def start_api(ctx=None):
    return {"port": 8080, "status": "running"}
app.set_init_callback(start_api)

# 3. 注册 + 执行
init.register_modules(run_id, [db, app, config])
progress = init.execute_init(run_id)

# 4. 验证
assert progress.state == InitState.COMPLETED
assert progress.initialized_modules == 3
assert init.get_module_result(run_id, "api_server")["port"] == 8080
```

### 5.2 循环依赖检测与报告

```python
from solocoder_4_py.module_init_graph import (
    ModuleInitializer,
    ModuleNode,
    CircularDependencyError,
    TopologyAnalyzer,
)

modules = {
    "a": ModuleNode("a", dependencies=["c"]),
    "b": ModuleNode("b", dependencies=["a"]),
    "c": ModuleNode("c", dependencies=["b"]),
}

# 直接分析
report = TopologyAnalyzer.detect_cycles(modules)
print(report.format_report())
# 检测到 1 个循环依赖:
#   [1] a -> b -> c -> a
# 涉及模块: a, b, c

# 或在执行时捕获异常
init = ModuleInitializer()
rid = init.create_init_run()
init.register_modules(rid, list(modules.values()))
try:
    init.execute_init(rid)
except CircularDependencyError as e:
    print("循环:", e.cycles)  # [['a', 'b', 'c']]
```

### 5.3 失败隔离场景

```python
from solocoder_4_py.module_init_graph import (
    ModuleInitializer,
    ModuleNode,
    ModuleState,
    InitState,
)

init = ModuleInitializer()
rid = init.create_init_run()

# config 成功
cfg = ModuleNode("config")
cfg.set_init_callback(lambda ctx: {"env": "test"})

# db 失败
db = ModuleNode("db_pool", dependencies=["config"])
def fail_db(ctx):
    raise RuntimeError("数据库密码错误")
db.set_init_callback(fail_db)

# cache 成功（独立分支）
cache = ModuleNode("redis_cache", dependencies=["config"])
cache.set_init_callback(lambda ctx: {"status": "ok"})

# app 依赖 db + cache → 因 db 失败被隔离
app = ModuleNode("api_app", dependencies=["db_pool", "redis_cache"])
app.set_init_callback(lambda ctx: {"running": True})

init.register_modules(rid, [cfg, db, cache, app])
prog = init.execute_init(rid)

# 结果：
assert prog.state == InitState.PARTIAL_COMPLETED
assert prog.module_progress["config"].state == ModuleState.INITIALIZED
assert prog.module_progress["db_pool"].state == ModuleState.FAILED
assert prog.module_progress["redis_cache"].state == ModuleState.INITIALIZED  # 独立分支正常
assert prog.module_progress["api_app"].state == ModuleState.ISOLATED        # 被隔离
assert "依赖模块失败: db_pool" in prog.module_progress["api_app"].error_message
```

### 5.4 局部重试恢复级联下游

```python
from solocoder_4_py.module_init_graph import (
    ModuleInitializer,
    ModuleNode,
    InitState,
)

init = ModuleInitializer()
rid = init.create_init_run()

call_count = {"db": 0}
db_result = None

cfg = ModuleNode("config")
cfg.set_init_callback(lambda ctx: {"cfg": True})

db = ModuleNode("db_pool", dependencies=["config"], max_retries=0)
def init_db(ctx):
    call_count["db"] += 1
    # 第一次失败，之后成功（模拟修复密码后重试）
    if call_count["db"] == 1:
        raise RuntimeError("密码错误")
    return {"connected": True}
db.set_init_callback(init_db)

app = ModuleNode("api", dependencies=["db_pool", "config"])
app.set_init_callback(lambda ctx: {"running": True})

init.register_modules(rid, [cfg, db, app])

# 第一次执行：db 失败 → app 被隔离
p1 = init.execute_init(rid)
assert p1.state == InitState.PARTIAL_COMPLETED
assert init.get_failed_modules(rid) == ["db_pool"]
assert init.get_isolated_modules(rid) == ["api"]

# 修复故障后重试 db_pool
p2 = init.retry_module(rid, "db_pool")
assert p2.state == InitState.COMPLETED
# db 重试成功，app 自动级联恢复（无需额外调用）
assert init.get_module_progress(rid, "db_pool").state.value == "INITIALIZED"
assert init.get_module_progress(rid, "api").state.value == "INITIALIZED"
assert call_count["db"] == 2
```

### 5.5 使用内置重试应对瞬时故障

```python
from solocoder_4_py.module_init_graph import (
    ModuleInitializer,
    ModuleNode,
)

init = ModuleInitializer()
rid = init.create_init_run()

attempts = [0]

def flaky_init(ctx):
    attempts[0] += 1
    # 前两次网络抖动失败，第三次成功
    if attempts[0] < 3:
        raise ConnectionError("网络超时")
    return "success"

# 声明 max_retries=2，共尝试 3 次
mod = ModuleNode("flaky_service", max_retries=2)
mod.set_init_callback(flaky_init)

init.register_module(rid, mod)
prog = init.execute_init(rid)

assert prog.module_progress["flaky_service"].attempts == 3
assert prog.module_progress["flaky_service"].state.value == "INITIALIZED"
```

### 5.6 批量重试所有失败模块

```python
# 修复环境后，一键重试所有 FAILED / ISOLATED 模块
final_prog = init.retry_all_failed(run_id, extra_retries=1)
print(f"最终状态: {final_prog.state.value}")
print(f"成功: {final_prog.initialized_modules}, "
      f"失败: {final_prog.failed_modules}, "
      f"隔离: {final_prog.isolated_modules}")
```

### 5.7 自循环依赖检测

```python
from solocoder_4_py.module_init_graph import (
    TopologyAnalyzer,
    ModuleNode,
    CircularDependencyError,
)

# 模块误声明了自身依赖
modules = {
    "bootstrap": ModuleNode("bootstrap", dependencies=["bootstrap"]),
    "other": ModuleNode("other"),
}

# detect_cycles 可正确识别自环
report = TopologyAnalyzer.detect_cycles(modules)
assert report.has_cycles
assert ["bootstrap"] in report.cycles
print(report.format_report())
# 检测到 1 个循环依赖:
#   [1] bootstrap -> bootstrap
# 涉及模块: bootstrap

# sort 抛出异常同样携带 cycles 字段
try:
    TopologyAnalyzer.sort(modules)
except CircularDependencyError as e:
    assert ["bootstrap"] in e.cycles  # 不再是空列表
```

### 5.8 捕获重试上限异常

```python
from solocoder_4_py.module_init_graph import (
    ModuleInitializer,
    ModuleNode,
    RetryLimitExceededError,
)

init = ModuleInitializer()
rid = init.create_init_run()

# 模拟永久性故障
mod = ModuleNode("permanent_failing")
mod.set_init_callback(lambda ctx: (_ for _ in ()).throw(
    RuntimeError("许可证已过期，无法启动")
))
init.register_module(rid, mod)
init.execute_init(rid)

# 手动尝试重试，耗尽所有尝试后会抛出异常
try:
    init.retry_module(rid, "permanent_failing", extra_retries=2)
except RetryLimitExceededError as e:
    print(f"重试终止: {e}")
    # 类似: 模块 'permanent_failing' 重试次数已达上限（共尝试 4 次），
    #       最后错误: RuntimeError: 许可证已过期，无法启动

# attempts 记录完整累计次数
prog = init.get_module_progress(rid, "permanent_failing")
print(f"累计尝试次数: {prog.attempts}")  # 1 (execute_init) + 3 (retry) = 4
```

## 6. 异常速查

| 异常类型 | 触发场景 |
|---------|---------|
| `CircularDependencyError` | 依赖图存在环（含自环），异常中带 `cycles` 字段（含单元素自环列表） |
| `DependencyNotFoundError` | 声明的依赖模块 ID 未注册 |
| `ModuleAlreadyRegisteredError` | 同一 run 中重复注册相同 module_id |
| `InitStateError` | 非法状态转换（如已执行后再注册、未执行就重试） |
| `ModuleNotFoundError` | 查询的 run_id 或 module_id 不存在 |
| `RetryLimitExceededError` | 调用 `retry_module` 时，所有重试尝试（`max_retries+1+extra_retries`）耗尽仍失败 |

## 7. 文件结构

```
src/solocoder_4_py/module_init_graph/
├── __init__.py           # 公共 API 导出
├── constants.py          # 状态枚举、终态集合
├── exceptions.py         # 异常类层级
├── module.py             # ModuleNode 数据模型
├── topology.py           # TopologyAnalyzer + CycleReport
├── initializer.py        # ModuleProgress / InitProgress / ModuleInitializer
└── README.md             # 本文档

tests/module_init_graph/
├── __init__.py
└── test_module_init_graph.py   # 完整单元测试
```

## 8. 运行测试

```bash
python -m pytest tests/module_init_graph/ -v
```
