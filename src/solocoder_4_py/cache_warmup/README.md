# 缓存预热编排模块 (cache_warmup)

本模块使用纯内存数据结构实现了**缓存热点数据预热的编排引擎**，支持任务依赖声明、按序执行、失败策略处理和实时进度追踪。

## 1. 模块功能

| 能力 | 说明 |
|------|------|
| 任务依赖声明 | 每个预热任务可声明对其他任务的依赖，形成 DAG 图 |
| 拓扑排序执行 | 使用 Kahn 算法 + 最小堆，按依赖顺序 + **priority 降序**保证热点数据优先执行 |
| 优先级调度 | 同层级（入度相同）任务按 `priority` 值从大到小执行，无需依赖的热点数据优先加载 |
| 循环依赖检测 | 自动检测循环依赖并抛出异常 |
| 三种失败策略 | 跳过下游 / 尽力继续 / 全部中止 |
| 进度追踪 | 支持查询每个任务和整体预热流程的进度、状态、耗时；`NOT_STARTED` 时百分比为 0% |
| 线程安全执行 | **双层锁**：orchestrator 全局锁 + 每个 run 独立锁，多线程并发预热互不阻塞 |
| 内存缓存模拟 | 使用字典模拟缓存存储，存储预热加载的数据 |
| 多流程实例 | 一个编排器可管理多个独立的预热 run，数据、状态、进度完全隔离 |

## 2. 核心概念

### 2.1 组件

- **`WarmupTask`**：预热任务定义。封装了一个热点数据项，包含任务 ID、依赖列表、**priority（优先级，值越大越先执行）**、数据加载回调等。
- **`WarmupOrchestrator`**：预热编排器。负责管理多个预热流程实例，调度任务执行，处理失败策略，追踪进度。采用双层锁机制保证线程安全。
- **`TopologySorter`**：拓扑排序器。基于 Kahn 算法 + 最小堆（heapq）对任务依赖图排序：依赖约束优先，同层级任务按 `priority` 降序调度，检测循环依赖。
- **状态枚举**：`TaskState`（单任务状态）与 `WarmupState`（整体流程状态）。
- **失败策略枚举**：`FailureStrategy`，定义三种任务失败后的处理方式。
- **进度对象**：`TaskProgress`（单任务进度）与 `WarmupProgress`（整体进度快照）。进度百分比语义：`NOT_STARTED` → 0%；已进入终态或 0 task 完成 → 100%。

### 2.2 任务状态机 (TaskState)

```
PENDING ──▶ RUNNING ──┬──▶ COMPLETED  (成功加载数据)
                        ├──▶ FAILED     (执行异常)
                        └──▶ SKIPPED    (依赖失败/策略跳过)
```

### 2.3 整体预热状态机 (WarmupState)

```
NOT_STARTED ──▶ RUNNING ──┬──▶ COMPLETED          (全部成功)
                           ├──▶ PARTIAL_COMPLETED  (部分成功)
                           └──▶ FAILED             (全部失败或中止)
```

### 2.4 预热执行流程

```
┌───────────────────────────────────────────────────────────────┐
│  1. 创建 run → 2. 注册任务（含依赖声明）                        │
│                                                               │
│  3. execute_warmup() 触发:                                     │
│     ┌─ a. 拓扑排序 + 循环依赖检测                              │
│     ├─ b. 按排序顺序逐个执行任务:                              │
│     │      i.   检查上游依赖状态                               │
│     │      ii.  依赖就绪 → 执行加载回调                        │
│     │      iii. 依赖失败/跳过 → 本任务标记 SKIPPED             │
│     └─ c. 根据 FailureStrategy 处理失败任务                    │
│                                                               │
│  4. 返回 WarmupProgress 进度快照                               │
└───────────────────────────────────────────────────────────────┘
```

## 3. 失败策略 (FailureStrategy)

| 策略值 | 行为 | 适用场景 |
|--------|------|----------|
| `SKIP_DEPENDENTS` | 任务失败后，其所有下游传递依赖都被标记 SKIPPED | **默认策略**。数据强依赖场景，上游失败下游无意义 |
| `CONTINUE_ANYWAY` | **尽力执行所有任务**。即使上游失败，声明了依赖的下游任务仍会被调度执行；由用户回调自行处理缺失数据（如返回默认值、降级逻辑） | 弱依赖场景。任务间仍保持拓扑执行顺序，但每个任务都应尽力完成 |
| `ABORT_ALL` | 任一任务失败后，立即中止整个预热流程，剩余所有 PENDING 任务标记 SKIPPED | 关键任务失败，整体预热失去意义 |

> **CONTINUE_ANYWAY 的明确语义**：该策略完全绕过 `_dependencies_ready` 检查 —— 即使上游任务失败或被跳过，下游任务仍会按拓扑顺序被调度并执行 `execute_load()`。业务回调必须自行容错（例如通过 `orch.get_cached_data()` 查询上游缓存是否存在，不存在时使用默认值）。这与 `SKIP_DEPENDENTS` 形成清晰对比。

## 3.1 线程安全保证

本模块采用**双层锁模型**确保线程安全：

| 锁层级 | 作用范围 | 锁对象 | 保护内容 |
|--------|----------|--------|----------|
| 全局层 | `WarmupOrchestrator` 实例 | `self._lock` | `_contexts` 字典（run_id → WarmupContext 映射）的读写 |
| Run 层 | 每个预热流程实例 | `ctx._ctx_lock` | 单个 WarmupContext 内部所有共享字段（tasks、task_order、cache_store、progress、aborted、errors） |

**并发语义**：
- **多 run 并行**：不同 run 的 `_ctx_lock` 相互独立，多个线程同时执行不同 `run_id` 的预热不会相互阻塞，真正并行。
- **单 run 串行**：同一 run 的共享状态统一通过 `ctx._ctx_lock` 串行化访问，不存在进度计数器脏读、缓存写入竞态等问题。
- **回调无锁执行**：用户提供的 `execute_load()` 回调在锁外执行，避免长时间持锁；回调内部可安全地调用查询 API（读接口自行加锁）。
- **快照隔离**：`get_progress()` 和 `get_task_progress()` 返回数据副本，不引用内部共享对象，避免外部修改污染内部状态。

## 3.2 优先级调度行为

`WarmupTask` 的 `priority: int` 字段用于在拓扑排序的同层级任务中决定执行先后。调度规则：

1. **依赖约束优先**：只有当所有 `dependencies` 完成后，任务才会被加入就绪队列。
2. **就绪队列按 priority 降序**：使用最小堆（`heapq` + 负 priority）实现每次弹出当前就绪任务中 priority 值最大的那个。
3. **默认值为 0**：未显式设置 priority 的任务之间相对顺序不保证（但仍满足依赖约束）。

典型用法：将首页、热点商品详情等核心页面数据任务设为高 priority（如 100），将后台报表等非关键数据任务设为低 priority（如 1），确保高价值数据被优先加载。

## 4. 使用示例

### 4.1 最小示例：用户资料 + 订单历史预热

```python
from solocoder_4_py.cache_warmup import (
    WarmupOrchestrator,
    WarmupTask,
    WarmupState,
    FailureStrategy,
)

# 构造编排器（指定失败策略）
orch = WarmupOrchestrator(failure_strategy=FailureStrategy.SKIP_DEPENDENTS)

# 创建预热流程
run_id = orch.create_warmup_run("morning-warmup-20260701")

# 模拟数据库中的热点数据
db_users = {101: {"name": "Alice", "level": "VIP"}, 102: {"name": "Bob"}}
db_orders = {
    "o-1": {"user_id": 101, "amount": 999},
    "o-2": {"user_id": 101, "amount": 500},
}

# 任务1：加载用户信息（无依赖）
task_users = WarmupTask(
    task_id="users:hot",
    description="加载热点用户资料",
)
def load_users():
    return {uid: u.copy() for uid, u in db_users.items()}
task_users.set_load_function(load_users)

# 任务2：加载订单历史（依赖用户任务完成后才能聚合）
task_orders = WarmupTask(
    task_id="orders:by_user",
    description="按用户聚合订单历史",
    dependencies=["users:hot"],  # 声明依赖
)
def load_orders_by_user():
    result = {}
    for oid, order in db_orders.items():
        uid = order["user_id"]
        result.setdefault(uid, []).append(order)
    return result
task_orders.set_load_function(load_orders_by_user)

# 注册任务
orch.register_task(run_id, task_users)
orch.register_task(run_id, task_orders)

# 执行预热
final_progress = orch.execute_warmup(run_id)

# 验证结果
assert final_progress.state == WarmupState.COMPLETED
assert final_progress.progress_percentage == 100.0
assert final_progress.completed_tasks == 2

# 从缓存中取数据
users_cache = orch.get_cached_data(run_id, "users:hot")
orders_cache = orch.get_cached_data(run_id, "orders:by_user")
assert users_cache[101]["name"] == "Alice"
assert orders_cache[101] is not None
```

### 4.2 失败场景：SKIP_DEPENDENTS（默认）跳过下游

```python
from solocoder_4_py.cache_warmup import (
    WarmupOrchestrator,
    WarmupTask,
    WarmupState,
    TaskState,
)

orch = WarmupOrchestrator()
run_id = orch.create_warmup_run("fail-demo")

# A 任务：故意失败
task_a = WarmupTask("task-a", description="上游任务")
task_a.set_load_function(lambda: (_ for _ in ()).throw(RuntimeError("数据源连接超时")))

# B 任务：依赖 A
task_b = WarmupTask("task-b", dependencies=["task-a"], description="下游任务")
task_b.set_load_function(lambda: {"result": "never executed"})

orch.register_tasks(run_id, [task_a, task_b])
progress = orch.execute_warmup(run_id)

# A 失败 → B 被跳过
assert progress.state == WarmupState.FAILED
assert progress.failed_tasks == 1
assert progress.skipped_tasks == 1
assert progress.task_progress["task-a"].state == TaskState.FAILED
assert progress.task_progress["task-b"].state == TaskState.SKIPPED
assert "数据源连接超时" in progress.task_progress["task-a"].error_message
assert "依赖任务失败" in progress.task_progress["task-b"].error_message
```

### 4.3 CONTINUE_ANYWAY：上游失败下游仍执行（回调自行容错）

```python
from solocoder_4_py.cache_warmup import (
    WarmupOrchestrator,
    WarmupTask,
    WarmupState,
    FailureStrategy,
    TaskState,
)

orch = WarmupOrchestrator(failure_strategy=FailureStrategy.CONTINUE_ANYWAY)
run_id = orch.create_warmup_run("continue-anyway-demo")

# 上游任务：故意抛异常
upstream = WarmupTask("up", description="上游")
upstream.set_load_function(lambda: (_ for _ in ()).throw(RuntimeError("DB 挂了")))

# 下游任务：依赖 upstream，但 CONTINUE_ANYWAY 下仍会执行
def safe_recommend_loader():
    # 回调自行容错：如果上游缓存不存在就返回默认空列表
    cached_users = orch.get_cached_data(run_id, "up")
    if cached_users is None:
        return {"recommendations": [], "fallback": True}
    return {"recommendations": ["item-1", "item-2"], "fallback": False}

downstream = WarmupTask("down", dependencies=["up"], description="下游")
downstream.set_load_function(safe_recommend_loader)

orch.register_tasks(run_id, [upstream, downstream])
progress = orch.execute_warmup(run_id)

# 关键：upstream FAILED，但 downstream 仍然 COMPLETED（执行了降级逻辑）
assert progress.task_progress["up"].state == TaskState.FAILED
assert progress.task_progress["down"].state == TaskState.COMPLETED
reco_data = orch.get_cached_data(run_id, "down")
assert reco_data["fallback"] is True
assert reco_data["recommendations"] == []
```

### 4.4 优先级调度：热点商品优先加载

```python
from solocoder_4_py.cache_warmup import (
    WarmupOrchestrator,
    WarmupTask,
    WarmupState,
    TopologySorter,
)

# 多个无依赖的独立任务，用 priority 控制加载顺序
hot_tasks = [
    WarmupTask("homepage",   priority=100, description="首页（最高优先级）"),
    WarmupTask("product-1",  priority=90,  description="爆款商品页"),
    WarmupTask("category-A", priority=30,  description="分类页 A"),
    WarmupTask("report-B",   priority=1,   description="后台报表（低优先级）"),
]

# TopologySorter.sort 返回的顺序按 priority 降序排列
task_map = {t.task_id: t for t in hot_tasks}
sorted_ids = TopologySorter.sort(task_map)
assert sorted_ids.index("homepage") < sorted_ids.index("product-1") \
       < sorted_ids.index("category-A") < sorted_ids.index("report-B")

# 注册后执行，执行顺序与 sorted_ids 一致
orch = WarmupOrchestrator()
rid = orch.create_warmup_run("priority-demo")
for t in hot_tasks:
    t.set_load_function(lambda tid=t.task_id: {"loaded": tid})
orch.register_tasks(rid, hot_tasks)
progress = orch.execute_warmup(rid)
assert progress.state == WarmupState.COMPLETED
assert progress.completed_tasks == 4
```

### 4.5 使用 ABORT_ALL 策略

```python
from solocoder_4_py.cache_warmup import (
    WarmupOrchestrator,
    WarmupTask,
    WarmupState,
    FailureStrategy,
    TaskState,
)

orch = WarmupOrchestrator(failure_strategy=FailureStrategy.ABORT_ALL)
run_id = orch.create_warmup_run()

tasks = []
for i in range(5):
    t = WarmupTask(f"t{i}")
    if i == 2:
        t.set_load_function(lambda: (_ for _ in ()).throw(ValueError("boom")))
    else:
        t.set_load_function(lambda idx=i: {"data": idx})
    tasks.append(t)

orch.register_tasks(run_id, tasks)
progress = orch.execute_warmup(run_id)

# t2 失败 → 整个流程中止，t3、t4 被跳过
assert progress.state == WarmupState.FAILED
assert progress.task_progress["t2"].state == TaskState.FAILED
```

### 4.6 进度查询

```python
from solocoder_4_py.cache_warmup import WarmupOrchestrator, WarmupTask

orch = WarmupOrchestrator()
run_id = orch.create_warmup_run()

def slow_load():
    return [x * x for x in range(1000)]

for i in range(10):
    t = WarmupTask(f"item-{i}")
    t.set_load_function(slow_load)
    orch.register_task(run_id, t)

# 执行预热
orch.execute_warmup(run_id)

# 查询整体进度
prog = orch.get_progress(run_id)
print(f"状态: {prog.state.value}")
print(f"完成度: {prog.progress_percentage}%")
print(f"成功/失败/跳过: {prog.completed_tasks}/{prog.failed_tasks}/{prog.skipped_tasks}")

# 查询单个任务
for i in range(10):
    tp = orch.get_task_progress(run_id, f"item-{i}")
    print(f"  {tp.task_id}: {tp.state.value}, 耗时 {tp.duration_seconds:.4f}s")

# 导出结构化数据
prog_dict = prog.to_dict()
print(prog_dict["tasks"]["item-0"]["loaded_data_preview"])
```

## 5. 异常场景与处理

| 异常类型 | 触发场景 |
|---------|---------|
| `CircularDependencyError` | 任务依赖图存在环（如 A→B→C→A） |
| `DependencyNotFoundError` | 声明的依赖任务 ID 不存在 |
| `TaskAlreadyRegisteredError` | 同一 run 中重复注册相同 task_id |
| `WarmupStateError` | 非法状态转换（如已开始执行后再注册任务） |
| `TaskNotFoundError` | 查询不存在的 run_id 或 task_id |

## 8. 文件结构

```
src/solocoder_4_py/cache_warmup/
├── __init__.py          # 公共 API 导出
├── constants.py         # 状态枚举、失败策略枚举、终态集合
├── exceptions.py        # 预热相关异常类层级
├── task.py              # WarmupTask 数据模型
├── topology.py          # 拓扑排序 + 依赖分析工具
├── progress.py          # TaskProgress / WarmupProgress
├── orchestrator.py      # WarmupOrchestrator 核心编排器
└── README.md            # 本文档

tests/cache_warmup/
├── __init__.py
└── test_cache_warmup.py # 完整单元测试
```

## 9. 运行测试

```bash
python -m pytest tests/cache_warmup/ -v
```
