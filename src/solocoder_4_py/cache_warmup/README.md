# 缓存预热编排模块 (cache_warmup)

本模块使用纯内存数据结构实现了**缓存热点数据预热的编排引擎**，支持任务依赖声明、按序执行、失败策略处理和实时进度追踪。

## 1. 模块功能

| 能力 | 说明 |
|------|------|
| 任务依赖声明 | 每个预热任务可声明对其他任务的依赖，形成 DAG 图 |
| 拓扑排序执行 | 使用 Kahn 算法对依赖图做拓扑排序，保证执行顺序合法 |
| 循环依赖检测 | 自动检测循环依赖并抛出异常 |
| 三种失败策略 | 跳过下游 / 继续执行 / 全部中止 |
| 进度追踪 | 支持查询每个任务和整体预热流程的进度、状态、耗时 |
| 内存缓存模拟 | 使用字典模拟缓存存储，存储预热加载的数据 |
| 多流程实例 | 一个编排器可管理多个独立的预热 run |

## 2. 核心概念

### 2.1 组件

- **`WarmupTask`**：预热任务定义。封装了一个热点数据项，包含任务 ID、依赖列表、数据加载回调等。
- **`WarmupOrchestrator`**：预热编排器。负责管理多个预热流程实例，调度任务执行，处理失败策略，追踪进度。
- **`TopologySorter`**：拓扑排序器。基于 Kahn 算法对任务依赖图排序，检测循环依赖。
- **状态枚举**：`TaskState`（单任务状态）与 `WarmupState`（整体流程状态）。
- **失败策略枚举**：`FailureStrategy`，定义三种任务失败后的处理方式。
- **进度对象**：`TaskProgress`（单任务进度）与 `WarmupProgress`（整体进度快照）。

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
| `CONTINUE_ANYWAY` | 任务失败后，仅标记自身 FAILED，不影响下游（但下游仍会因依赖失败被跳过） | 各任务相对独立，但仍需声明依赖顺序 |
| `ABORT_ALL` | 任一任务失败后，立即中止整个预热流程，后续所有任务标记 SKIPPED | 关键任务失败，整体预热失去意义 |

> **注意**：即使使用 `CONTINUE_ANYWAY`，声明了依赖的任务仍会因上游失败而被跳过。该策略只影响**无直接/间接依赖**的独立任务。

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

### 4.2 失败场景：依赖任务失败

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

### 4.3 使用 ABORT_ALL 策略

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

### 4.4 进度查询

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

## 6. 文件结构

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

## 7. 运行测试

```bash
python -m pytest tests/cache_warmup/ -v
```
