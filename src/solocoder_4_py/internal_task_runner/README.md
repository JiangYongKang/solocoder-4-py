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
- **可注入时间/睡眠提供者**：构造时注入自定义 `time_provider` / `sleep_provider`，测试中无需真实等待
- **线程安全**：所有公共操作均使用 `RLock` 保护
- **重试机制**：支持 `max_retries` 指定失败自动重试次数，可配置 `retry_delay_seconds` 插入重试间隔
- **handler 超时中断**：使用 `ThreadPoolExecutor + Future.result(timeout)` 实现超时保护，避免卡死调度
- **周期追赶补偿**：`resume(catch_up=True)` 逐周期补跑暂停期间遗漏的调度，追平后自动复位
- **触发器竞态防护**：执行前锁内终态二次校验，窗口期 cancel/unregister 一律记录为 SKIPPED 而非误执行
- **动态 handler 替换**：通过 `set_task_handler(task_id, handler)` 线程安全地替换任务执行逻辑

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

## Handler 超时机制

长时间阻塞的 handler 会阻塞整个 `tick()` 调度，导致其他任务无法执行。
通过在 `TaskDefinition` 中设置 `timeout_seconds`，可以让运行器在超时后立即
判定为失败，并继续执行其他任务。

**实现原理**：
- 当 `timeout_seconds` 为正数时，handler 通过内部 `ThreadPoolExecutor.submit()`
  提交执行，然后调用 `future.result(timeout=timeout_seconds)` 等待结果。
- 一旦抛出 `concurrent.futures.TimeoutError`，会立即调用 `future.cancel()`
  并向运行记录写入 `error_type = "TimeoutError"`，`status = FAILED`。
- 当 `timeout_seconds` 为 `None` 或 `<= 0` 时，走直接同步调用路径（无额外线程开销）。

**注意事项**：Python 标准线程**无法被强制 kill**。因此超时后虽然运行器会立即
返回，但被提交到线程池的 handler 线程可能仍在后台运行直到其自行结束。
建议在 handler 中自行实现可中断逻辑（例如检查 `Event` 标志位），或设置
足够宽裕的超时避免真实的资源泄漏。

```python
runner.register(TaskDefinition(
    task_id="risky_io",
    task_type=TaskType.MANUAL,
    handler=risky_network_call,
    timeout_seconds=5.0,   # 超过 5s 即判定失败
    max_retries=1,
))
runner.activate("risky_io")
rec = runner.trigger("risky_io")
if rec.is_failed and rec.error_type == "TimeoutError":
    print("网络调用超时，已跳过")
```

## 重试延迟策略

`max_retries` 控制失败自动重试次数，但如果没有间隔，瞬时故障也可能在微秒级
耗尽所有重试，既浪费资源也不利于故障自愈。配合 `retry_delay_seconds`
可以在每次重试前插入一个固定延迟（首次执行不延迟）。

**使用示例**：

```python
runner.register(TaskDefinition(
    task_id="flaky_api",
    task_type=TaskType.MANUAL,
    handler=call_flaky_api,
    max_retries=3,            # 最多重试 3 次（共 4 次尝试）
    retry_delay_seconds=1.5,  # 每次重试前等待 1.5s
))
```

- `attempt == 1`：立即执行，不睡眠
- `attempt > 1`：如果 `retry_delay_seconds > 0`，调用 `_sleep(retry_delay_seconds)`

**测试友好**：`_sleep` 通过可注入的 `sleep_provider` 执行，测试时可以传入
no-op 或计数器，避免真实等待：

```python
sleeps: List[float] = []
runner = InternalTaskRunner(sleep_provider=lambda s: sleeps.append(s))
# ... 触发重试后，sleeps 会记录所有延迟值
assert sleeps == [1.5, 1.5, 1.5]   # 3 次重试，3 次延迟
```

## 周期任务追赶补偿（catch-up）

对 `PERIODIC` 任务调用 `pause()` 后，如果暂停期间跨越了多个调度周期，
默认 `resume()` 会直接把 `next_run_at` 跳到 `now + interval`，丢弃所有
暂停期间应执行的周期。这对**心跳、最新状态快照**等只关心"最新值"的任务是正确的，
但对**每日结算、增量数据同步**等不可遗漏的场景就会出错。

### 两种恢复策略对比

```python
# 策略 1（默认）：丢弃暂停期间周期，从 now + interval 开始
runner.resume("heartbeat", catch_up=False)
# next_run_at = now + interval，中间错过的周期全部跳过

# 策略 2：逐周期补跑，直到追平当前时间
runner.resume("daily_settlement", catch_up=True)
# 保留原 next_run_at，每次 tick() 补跑一个周期
```

**追赶执行过程**（假设 `interval=10s`，暂停了 105s，错过 10 个周期）：

| tick 次数 | 补跑调度点 | 结果 |
|-----------|-----------|------|
| 1 | t=20 | 执行，next_run_at += 10 → 30 |
| 2 | t=30 | 执行，next_run_at += 10 → 40 |
| ... | ... | ... |
| 10 | t=110 | 执行，next_run_at += 10 → 120 |
| 11 | — | 120 > now=115，`catch_up` 标志自动关闭，不再执行 |

- **避免一次 tick 爆发式运行**：追赶模式下，每个 tick 最多只补跑 1 个周期，
  下一个周期留给后续 tick，避免单线程阻塞时间过长。
- **追平自动关闭**：当 `next_run_at > now` 时，`catch_up` 自动设为 `False`，
  之后调度恢复默认的"跳跃"行为（即如果仍落后则跳到 `now + interval`）。

## 触发器竞态防护

### 问题背景

`trigger()` 原本的流程是：

```
持锁 → 校验状态（非终态）→ 放锁 → 执行 handler
```

在"放锁 → 执行 handler"的窗口期内，另一个线程完全可能调用 `cancel()`
或 `unregister()`，导致 handler 仍然被执行，但任务状态已经是终态，
产生矛盾的运行记录。

### 修复方案

将**终态二次校验**与**definition 快照**封装在 `_execute_single_run` 入口处的
**同一个锁保护范围**内，从而消除竞态窗口：

```
_execute_single_run 入口：
  持锁：
    1. 再次查找任务 → 不存在：返回 SKIPPED（"任务已被注销"）
    2. 检查 status → 终态：写入 SKIPPED 记录并返回
    3. 快照 definition_snapshot（确保本次执行使用同一份 handler/超时/重试配置）
  放锁：
    循环执行 handler（使用快照），不再访问共享可变状态
  持锁：
    提交记录到历史
```

窗口期被 cancel/unregister 的结果是产生一条 `SKIPPED` 记录，`skip_count += 1`，
handler 不会被调用，统计数据仍然一致。

### definition_snapshot 的一致性意义

除了终态防护，**快照**还解决了"handler 动态替换期间的不一致"问题：
如果在 handler 执行过程中（另一个线程）通过 `set_task_handler()` 替换了任务执行逻辑，
本次运行仍然使用入口处读取的 `definition_snapshot`，避免中途切换逻辑。

测试代码可以通过下面模式验证：

```python
# 在 handler 阻塞期间替换
runner.set_task_handler("mid", lambda **kw: "injected")
# 但运行结果仍然是阻塞 handler 的返回值
assert result.result == "blocking-result"
```

## 动态 Handler 替换

任务注册后，执行逻辑可能需要根据业务场景动态调整（例如故障降级、策略切换、热修复等）。
`InternalTaskRunner` 提供线程安全的 `set_task_handler()` 公共 API，避免直接操作内部数据结构。

### 基本用法

```python
# 注册时使用初始 handler
runner.register(TaskDefinition(
    task_id="payment",
    task_type=TaskType.MANUAL,
    handler=original_payment_flow,
))
runner.activate("payment")

# 后续需要切换到新的执行逻辑
runner.set_task_handler("payment", new_payment_flow)

# 后续 trigger 将使用 new_payment_flow
rec = runner.trigger("payment")
```

### 与 definition_snapshot 的交互

`set_task_handler()` 直接修改 `TaskDefinition.handler`，但由于 `_execute_single_run`
在**入口处锁内生成 `definition_snapshot`**，二者配合产生以下行为：

| 替换时机 | 对本次运行的影响 | 对后续运行的影响 |
|---------|------------------|------------------|
| 运行前（handler 尚未开始） | 使用新 handler | 使用新 handler |
| 运行中（handler 已在执行） | 仍使用快照的旧 handler | 使用新 handler |
| 运行后 | — | 使用新 handler |

这意味着：**正在飞行中的运行不会被中途替换逻辑**，保证了单次执行的一致性。
如果需要让新逻辑立即生效，必须等待当前运行结束或取消任务后重新触发。

### 线程安全

`set_task_handler()` 内部持 `RLock` 保护，与 `tick()`、`trigger()`、`cancel()`
等操作互斥，不会出现"读到半个 handler"的情况。

**注意**：`set_task_handler()` 只替换 `handler` 字段，不修改其他调度参数
（`timeout_seconds`、`retry_delay_seconds`、`interval_seconds` 等）。如果需要整体替换任务定义，
请先 `unregister()` 再重新 `register()`。

---

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
