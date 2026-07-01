# internal_task_runner 模块

内部任务运行器模块，使用纯内存数据结构管理任务定义和运行记录，
支持**一次性任务**、**周期任务**和**手动触发任务**三种任务类型，
并提供完整的运行历史查询功能。

## 模块功能概览

- **任务注册与注销**：定义任务的类型、执行逻辑、调度参数、标签等元数据
- **生命周期控制**：激活 / 暂停 / 恢复 / 取消 / 重置任务
- **三种任务类型**：
  - `ONE_SHOT`：一次性任务，激活后在下次 `tick()` 时执行一次
  - `PERIODIC`：周期任务，按指定 `interval_seconds` 间隔重复执行
  - `MANUAL`：手动触发任务，仅在调用 `trigger()` 时执行
- **运行历史记录**：每次任务执行产生 `TaskRunRecord`，包含开始/结束时间、结果、错误信息、重试次数等
- **历史查询**：按时间范围、状态、运行 ID 等条件查询历史
- **可注入时间提供者**：构造时注入自定义 `time_provider`，测试中无需真实等待
- **线程安全**：所有公共操作均使用 `RLock` 保护
- **重试机制**：支持 `max_retries` 指定失败自动重试次数

## 任务类型

### `TaskType.ONE_SHOT` 一次性任务

激活后只执行一次，执行成功进入 `COMPLETED`，执行失败进入 `ERROR`。
适用于启动初始化、一次性数据迁移等场景。

```python
def sync_data(**kwargs):
    return "data synced"

definition = TaskDefinition(
    task_id="data_sync",
    task_type=TaskType.ONE_SHOT,
    handler=sync_data,
    description="同步数据",
    tags=["io", "data"],
)
runner.register(definition)
runner.activate("data_sync")
runner.tick()  # 实际执行
```

### `TaskType.PERIODIC` 周期任务

激活后按 `interval_seconds` 间隔重复执行，需调用 `tick()` 推进调度器。
支持 `pause()` / `resume()` 暂停恢复。适用于心跳、轮询、定期清理等场景。

```python
definition = TaskDefinition(
    task_id="heartbeat",
    task_type=TaskType.PERIODIC,
    handler=send_heartbeat,
    interval_seconds=30.0,
    tags=["health"],
)
runner.register(definition)
runner.activate("heartbeat")

# 事件循环中定期调用 tick 推进调度
while running:
    runner.tick()
    time.sleep(1)
```

### `TaskType.MANUAL` 手动触发任务

激活后不会自动执行，必须显式调用 `trigger(task_id, **kwargs)` 触发。
适用于按需 API、按钮操作、重试操作等需要明确触发的场景。

```python
def send_email(to, subject, body):
    return {"sent": True}

definition = TaskDefinition(
    task_id="send_email",
    task_type=TaskType.MANUAL,
    handler=send_email,
    max_retries=2,
)
runner.register(definition)
runner.activate("send_email")

record = runner.trigger(
    "send_email",
    to="user@example.com",
    subject="Hello",
    body="Welcome!",
)
print(record.result, record.is_success)
```

## 任务状态

| 状态 | 说明 |
|------|------|
| `PENDING` | 已注册，尚未激活 |
| `ACTIVE` | 已激活，可以被调度 / 手动触发 |
| `PAUSED` | 已暂停（仅 `PERIODIC` 任务） |
| `COMPLETED` | 一次性任务执行成功 |
| `CANCELLED` | 被主动取消 |
| `ERROR` | 一次性任务执行失败（耗尽重试后） |

终态集合：`{COMPLETED, CANCELLED, ERROR}`，终态任务可用 `reset()` 回到 `PENDING`。

## 运行历史与结果

### `TaskRunRecord` 字段

| 字段 | 说明 |
|------|------|
| `run_id` | 每次运行的唯一 ID（UUID） |
| `task_id` | 所属任务 ID |
| `status` | `SUCCESS` / `FAILED` / `SKIPPED` |
| `started_at` / `finished_at` | 开始/结束时间戳 |
| `duration_ms` | 运行时长（毫秒，属性） |
| `result` | handler 返回值（成功时） |
| `error_message` / `error_type` | 异常信息（失败时） |
| `attempt` | 本次是第几次尝试（1-based，含重试） |
| `trigger` | 触发方式：`SCHEDULE` 或 `MANUAL` |
| `metadata` | 扩展元数据字典 |

### 历史查询 API

```python
# 全量历史（按时间倒序）
history = runner.get_run_history("task_id")

# 最近 10 次
latest = runner.get_run_history("task_id", limit=10)

# 按状态过滤
fails = runner.get_run_history("task_id", status_filter=RunStatus.FAILED)

# 按时间范围过滤
sliced = runner.get_run_history("task_id", since=1700000000.0, until=1700010000.0)

# 最近一次
last = runner.get_latest_run("task_id")

# 按 run_id 精确查找
record = runner.get_run_by_id("task_id", "run-uuid")
```

## 测试中模拟时间（无需真实等待）

构造 `InternalTaskRunner` 时传入自定义 `time_provider`，
或者调用 `set_time_provider()`，配合 `FakeClock` 控制时间：

```python
class FakeClock:
    def __init__(self, start=0.0):
        self._t = start
    def now(self):
        return self._t
    def advance(self, sec):
        self._t += sec

clock = FakeClock()
runner = InternalTaskRunner(time_provider=clock.now)

runner.register(TaskDefinition(
    task_id="p", task_type=TaskType.PERIODIC,
    handler=handler, interval_seconds=10.0,
))
runner.activate("p")

clock.advance(10.0)
records = runner.tick()  # 立即执行，无需 sleep(10)
assert len(records) == 1
```

## 使用示例

### 完整示例：组合使用三种任务

```python
from solocoder_4_py.internal_task_runner import (
    InternalTaskRunner, TaskDefinition, TaskType,
    TaskStatus, RunStatus,
)

runner = InternalTaskRunner()

# 1) 一次性：启动初始化
def bootstrap(**kw):
    return "bootstrap done"

runner.register(TaskDefinition(
    task_id="bootstrap", task_type=TaskType.ONE_SHOT,
    handler=bootstrap, tags=["init"],
))

# 2) 周期：每 60 秒检查健康
def health_check(**kw):
    return {"status": "ok"}

runner.register(TaskDefinition(
    task_id="health", task_type=TaskType.PERIODIC,
    handler=health_check, interval_seconds=60.0,
    tags=["health"],
))

# 3) 手动：按需报告
def generate_report(name: str):
    return f"report:{name}"

runner.register(TaskDefinition(
    task_id="report", task_type=TaskType.MANUAL,
    handler=generate_report, max_retries=1,
    tags=["report"],
))

# 激活所有
runner.activate_all()

# 推进一次调度（bootstrap + 周期任务首次检查）
runner.tick()

# 手动生成报告
r = runner.trigger("report", name="sales")
print(r.result)  # "report:sales"

# 查看运行统计
stats = runner.get_stats()
print(stats.total_runs, stats.successful_runs)

# 查询某个任务的运行历史
for record in runner.get_run_history("health", limit=5):
    print(record.started_at, record.status)

# 按标签发现任务
health_tasks = runner.find_by_tag("health")
```

## 核心类型

| 类名 | 说明 |
|------|------|
| `InternalTaskRunner` | 任务运行器主类 |
| `TaskDefinition` | 任务定义（注册时使用） |
| `TaskRuntimeInfo` | 任务运行时状态 |
| `TaskRunRecord` | 单次运行记录 |
| `TaskRunnerStats` | 运行器统计信息 |
| `TaskType` / `TaskStatus` / `RunStatus` | 枚举类型 |

模块公共 API 均从包根导出，使用 `from solocoder_4_py.internal_task_runner import ...` 即可导入。
