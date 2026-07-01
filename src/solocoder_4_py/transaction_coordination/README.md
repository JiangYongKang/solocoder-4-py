# 内存事务协调域模块 (transaction_coordination)

本模块使用纯内存数据结构实现了 **两阶段提交（Two-Phase Commit, 2PC）** 协议下的分布式事务协调过程，用于学习、测试和模拟真实分布式事务环境。

## 1. 模块功能

| 能力 | 说明 |
|------|------|
| 多参与者事务 | 支持在一个事务中注册任意数量的参与者 |
| 两阶段提交 | 实现标准的 Prepare / Commit / Abort 语义 |
| 超时决策 | Prepare 阶段若等待超时，协调器自动决策中止并抛出异常 |
| 幂等操作 | 对重复的 prepare/commit/abort 调用稳定返回结果，不产生重复副作用 |
| 中间状态区分 | 使用 `COMMIT_PARTIALLY_FAILED` / `ABORTING` 中间状态明确区分"部分失败"和"全部成功" |
| 失败重试 | 提供 `retry_commit()` / `retry_abort()` 方法重试失败的参与者 |
| 异常携带详情 | `CommitFailedError` 附带失败参与者和已成功参与者列表 |
| 自定义业务回调 | 通过注入 `on_prepare` / `on_commit` / `on_abort` 回调模拟真实业务逻辑 |
| 一键执行 | `execute_transaction()` 封装完整 2PC 流程，含自动重试，保证返回终态或抛明确异常 |
| 线程安全 | 内部使用 `threading.Lock` 保证基本并发安全 |
| 可测试时钟 | 协调器支持注入自定义 `clock` 函数，便于测试超时场景 |
| 可配置重试 | 通过 `max_retry_attempts` 配置 `execute_transaction` 的最大自动重试次数 |

## 2. 核心概念

### 2.1 组件

- **`TransactionParticipant`**：事务参与者。模拟一个独立的资源管理器（如数据库、微服务）。每个参与者对每个事务维护独立的状态。
- **`TransactionCoordinator`**：事务协调器。负责驱动整个 2PC 流程，管理所有参与者的状态与最终决策。
- **状态枚举**：`TransactionState`（全局事务状态）与 `ParticipantState`（参与者本地状态）。

### 2.2 TransactionCoordinator 完整 API

| 方法 | 说明 |
|------|------|
| `begin_transaction(tx_id=None) -> str` | 开启事务，返回事务 ID |
| `register_participant(tx_id, participant)` | 向事务注册参与者（仅 INIT/PREPARING 阶段） |
| `get_transaction_state(tx_id) -> TransactionState` | 查询事务状态 |
| `get_participants(tx_id) -> List[str]` | 查询参与者 ID 列表 |
| `prepare_transaction(tx_id) -> bool` | 阶段一：准备所有参与者，成功返回 True；失败/超时返回 False 或抛异常 |
| `commit_transaction(tx_id) -> None` | 阶段二：提交事务；部分失败抛 `CommitFailedError`，状态变为 `COMMIT_PARTIALLY_FAILED` |
| `retry_commit(tx_id) -> bool` | 仅重试 commit 失败的参与者，全部成功返回 True |
| `has_incomplete_commit(tx_id) -> bool` | 是否存在未成功 commit 的参与者 |
| `get_commit_failed_participants(tx_id) -> List[str]` | commit 失败的参与者 ID 列表 |
| `abort_transaction(tx_id) -> None` | 阶段二：中止事务；部分失败则状态保持 `ABORTING` |
| `retry_abort(tx_id) -> bool` | 仅重试 abort 失败的参与者，全部成功返回 True |
| `has_incomplete_abort(tx_id) -> bool` | 是否存在未成功 abort 的参与者 |
| `get_abort_failed_participants(tx_id) -> List[str]` | abort 失败的参与者 ID 列表 |
| `execute_transaction(tx_id) -> TransactionState` | 一键执行 2PC，自动重试，保证返回终态或抛异常 |

### 2.3 两阶段提交流程 (2PC)

```
┌───────────────────────────────────────────────────────────────┐
│                        阶段一：Prepare                         │
│                                                               │
│  Coordinator ──Prepare()──▶ Participant_1                    │
│              ◀── YES/NO ───                                    │
│              ──Prepare()──▶ Participant_2                    │
│              ◀── YES/NO ───                                    │
│                            ...                                │
│                                                               │
│  全部 YES ──────────▶ 进入阶段二 Commit                       │
│  任一 NO / 超时 ─────▶ 进入阶段二 Abort                        │
└───────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────┐
│                        阶段二：Commit/Abort                    │
│                                                               │
│  决策 Commit:                                                  │
│    Coordinator ──Commit()──▶ 所有参与者                       │
│      ├─ 全部成功 ────────────────────▶ COMMITTED              │
│      └─ 部分失败 ──▶ COMMIT_PARTIALLY_FAILED ──retry_commit()▶│
│                                                               │
│  决策 Abort:                                                   │
│    Coordinator ──Abort()───▶ 所有参与者                       │
│      ├─ 全部成功 ────────────────────▶ ABORTED / TIMEOUT_ABORTED │
│      └─ 部分失败 ──▶ ABORTING ───────────retry_abort()────────▶│
└───────────────────────────────────────────────────────────────┘
```

**事务状态机**：

```
         ┌───────────────────────────────────────────────┐
         │                                               ▼
INIT ─▶ PREPARING ─┬─▶ PREPARED ──▶ COMMITTING ─┬─▶ COMMITTED
                    │                             │
                    │                             └─▶ COMMIT_PARTIALLY_FAILED ──retry_commit()──┐
                    │                                                                             │
                    ├─ (prepare 失败) ──▶ ABORTING ─┬─▶ ABORTED / TIMEOUT_ABORTED             │
                    │                                 │                                         │
                    │                                 └─ (abort 部分失败) ──retry_abort()──────┘
                    │
                    └─ (超时) ──▶ TIMEOUT_ABORTED（经 execute_transaction 自动 abort 后）
```

**终态**：`COMMITTED`、`ABORTED`、`TIMEOUT_ABORTED`
**中间状态（需重试）**：`COMMIT_PARTIALLY_FAILED`、`ABORTING`

## 3. 异常场景与处理

### 3.1 参与者 Prepare 失败
- **现象**：任意参与者在 `on_prepare` 回调中返回 `False` 或抛出异常
- **协调器动作**：记录失败，最终决策为 `ABORTED`，对所有已 Prepare 成功的参与者调用 `abort` 进行回滚

### 3.2 Prepare 阶段超时
- **现象**：从 `prepare_started_at` 计时，超过 `prepare_timeout_seconds` 仍未收集到所有 YES
- **协调器动作**：决策 `TIMEOUT_ABORTED`，`prepare_transaction` 抛出 **`TimeoutDecisionAbortedError`**
- **`execute_transaction` 行为**：捕获 `TimeoutDecisionAbortedError` 并自动执行 `abort_transaction` + 重试，最终状态为 `TIMEOUT_ABORTED`，然后重新抛出异常
- **可测试性**：通过 `TransactionCoordinator(clock=FakeClock())` 注入可控时钟便于断言

### 3.3 重复请求（幂等性）
- **重复 Prepare**：
  - 已 `PREPARED` → 返回 `True`，不重复调用回调
  - 已失败/已中止 → 稳定返回 `False`
  - 已 `COMMITTED` → 抛 `TransactionStateError`
- **重复 Commit**：已 `COMMITTED` → 直接返回，业务回调仅执行一次
- **重复 Abort**：已 `ABORTED` / `TIMEOUT_ABORTED` → 直接返回，业务回调仅执行一次
- **重复 execute_transaction**：终态事务直接返回当前状态

### 3.4 非法状态转换
下列操作均会抛 `TransactionStateError`：
- 未 Prepare 就 Commit（需要先 `prepare_transaction` 成功）
- 已 Abort 的事务再 Commit
- 已 Commit 的事务再 Abort
- 在 PREPARED 之后才注册新参与者
- 对非 ABORTING 状态调用 `retry_abort`
- 对非 COMMITTING / COMMIT_PARTIALLY_FAILED 状态调用 `retry_commit`

### 3.5 Commit 阶段部分失败
- **现象**：所有参与者 PREPARED 后进入 COMMITTING 阶段，但某参与者 `on_commit` 回调抛出异常
- **处置策略**：
  1. **区分状态**：事务状态设为 `COMMIT_PARTIALLY_FAILED`（不是 `COMMITTED`），与参与者端状态一致
  2. **异常携带详情**：`commit_transaction` 抛出 **`CommitFailedError`**，异常对象包含：
     - `failed_participants`：`List[str]`，commit 失败的参与者 ID 列表
     - `committed_participants`：`List[str]`，已成功 commit 的参与者 ID 列表
     - `str(exc)` 包含完整错误信息
  3. **查询接口**：
     - `has_incomplete_commit(tx_id)` → 是否存在未完成的 commit
     - `get_commit_failed_participants(tx_id)` → 需要重试的参与者列表
  4. **重试机制**：
     - `retry_commit(tx_id)` → 仅重试失败的参与者，返回 `True` 表示全部成功
     - `execute_transaction(tx_id)` → 自动重试最多 `max_retry_attempts` 次，若最终仍失败则抛出包含详情的 `CommitFailedError`
- **幂等性**：已 `COMMITTED` 的事务再次调用 `commit_transaction` 或 `retry_commit` 直接返回，无副作用。

### 3.6 参与者 Abort 回调失败（处置策略）
- **现象**：ABORTING 阶段某参与者 `on_abort` 回调抛出异常
- **处置策略**：
  1. **标记失败**：该参与者 ID 被记录到 `abort_failed_participants` 集合
  2. **状态保持**：协调器事务状态保持为 `ABORTING`（不进入终态），与参与者端状态一致（参与者端 `abort` 失败后会回退到前一状态）
  3. **查询接口**：
     - `has_incomplete_abort(tx_id)` → 是否存在未成功 abort 的参与者
     - `get_abort_failed_participants(tx_id)` → 需要重试的参与者 ID 列表
  4. **重试机制**：
     - `retry_abort(tx_id)` → 仅重试失败的参与者，返回 `True` 表示全部成功（转为 `ABORTED` 或 `TIMEOUT_ABORTED`）
     - `execute_transaction(tx_id)` → 自动重试最多 `max_retry_attempts` 次，若最终仍失败则抛出 `AbortFailedError`
- **终态转换**：当 `retry_abort` 返回 `True`（所有参与者成功）时，协调器才转为 `ABORTED` 或 `TIMEOUT_ABORTED` 终态。

### 3.7 其他异常
- `TransactionNotFoundError`：操作不存在的 `tx_id`
- `ParticipantAlreadyRegisteredError`：向同一事务重复注册参与者
- `PrepareFailedError` / `CommitFailedError` / `AbortFailedError`：参与者回调执行失败

### 3.8 execute_transaction 异常契约

`execute_transaction` 遵循"一键执行返回终态"的语义，所有路径最终要么返回终态，要么抛出明确异常：

| 场景 | 行为 |
|------|------|
| 已处终态 | 直接返回当前状态（幂等） |
| prepare 全部成功，commit 全部成功 | 返回 `COMMITTED` |
| prepare 全部成功，commit 部分失败 | 自动重试最多 `max_retry_attempts` 次 → 成功则返回 `COMMITTED`，失败则抛 `CommitFailedError`（状态保持 `COMMIT_PARTIALLY_FAILED`） |
| prepare 失败 | 执行 abort + 重试 → 成功则返回 `ABORTED`，失败则抛 `AbortFailedError`（状态保持 `ABORTING`） |
| prepare 超时 | 执行 abort + 重试 → 成功则抛 `TimeoutDecisionAbortedError`（状态为 `TIMEOUT_ABORTED`），失败则抛 `AbortFailedError` |

## 4. 使用示例

### 4.1 最小示例：成功提交

```python
from solocoder_4_py.transaction_coordination import (
    TransactionCoordinator,
    TransactionParticipant,
    TransactionState,
)

# 构造协调器（可选 prepare 超时和最大重试次数）
coord = TransactionCoordinator(
    prepare_timeout_seconds=10.0,
    max_retry_attempts=3,
)

# 构造两个参与者，并通过回调定义"业务逻辑"
account_a = TransactionParticipant("account-a")
account_a_balance = {"amount": 1000}
account_a.set_callbacks(
    on_prepare=lambda tx: account_a_balance["amount"] >= 100,  # 检查余额
    on_commit=lambda tx: account_a_balance.__setitem__("amount", account_a_balance["amount"] - 100),
    on_abort=lambda tx: None,
)

account_b = TransactionParticipant("account-b")
account_b_balance = {"amount": 500}
account_b.set_callbacks(
    on_prepare=lambda tx: True,
    on_commit=lambda tx: account_b_balance.__setitem__("amount", account_b_balance["amount"] + 100),
    on_abort=lambda tx: None,
)

# 开启事务，注册参与者
tx_id = coord.begin_transaction("transfer-#1")
coord.register_participant(tx_id, account_a)
coord.register_participant(tx_id, account_b)

# 一键执行 2PC
final_state = coord.execute_transaction(tx_id)
assert final_state == TransactionState.COMMITTED
assert account_a_balance["amount"] == 900
assert account_b_balance["amount"] == 600
```

### 4.2 模拟回滚：余额不足

```python
account_a_balance["amount"] = 50  # 余额不足

tx_id = coord.begin_transaction("transfer-#2")
coord.register_participant(tx_id, account_a)
coord.register_participant(tx_id, account_b)

final_state = coord.execute_transaction(tx_id)
assert final_state == TransactionState.ABORTED
# 双方余额均未改变
assert account_a_balance["amount"] == 50
assert account_b_balance["amount"] == 600
```

### 4.3 分阶段手动控制 + 超时测试

```python
class FakeClock:
    def __init__(self): self._t = 0.0
    def __call__(self): return self._t
    def advance(self, delta): self._t += delta

clock = FakeClock()
coord = TransactionCoordinator(prepare_timeout_seconds=5.0, clock=clock)

def slow_prepare(tx_id):
    clock.advance(100.0)  # 模拟慢速，将在内部触发超时判定
    return True

p = TransactionParticipant("slow-service")
p.set_callbacks(on_prepare=slow_prepare)

tx_id = coord.begin_transaction()
coord.register_participant(tx_id, p)

state = coord.execute_transaction(tx_id)
assert state == TransactionState.TIMEOUT_ABORTED
```

### 4.4 验证幂等性（无重复副作用）

```python
coord = TransactionCoordinator()
commit_count = {"n": 0}

def my_commit(tx):
    commit_count["n"] += 1

p = TransactionParticipant("svc")
p.set_callbacks(on_prepare=lambda tx: True, on_commit=my_commit)

tx_id = coord.begin_transaction()
coord.register_participant(tx_id, p)

coord.prepare_transaction(tx_id)
coord.commit_transaction(tx_id)
coord.commit_transaction(tx_id)  # 重复调用
coord.commit_transaction(tx_id)  # 重复调用

assert commit_count["n"] == 1  # 业务副作用仅发生一次
```

### 4.5 异常处理：捕获超时和提交失败

```python
from solocoder_4_py.transaction_coordination import (
    AbortFailedError,
    CommitFailedError,
    TimeoutDecisionAbortedError,
    TransactionCoordinator,
    TransactionParticipant,
    TransactionState,
)

coord = TransactionCoordinator(prepare_timeout_seconds=5.0, max_retry_attempts=2)

p_good = TransactionParticipant("good")
p_good.set_callbacks(on_prepare=lambda tx: True, on_commit=lambda tx: None)

p_bad = TransactionParticipant("bad")
p_bad.set_callbacks(
    on_prepare=lambda tx: True,
    on_commit=lambda tx: (_ for _ in ()).throw(RuntimeError("db down")),
)

tx_id = coord.begin_transaction("tx-with-possible-failure")
coord.register_participant(tx_id, p_good)
coord.register_participant(tx_id, p_bad)

try:
    coord.execute_transaction(tx_id)
except TimeoutDecisionAbortedError as exc:
    print(f"Prepare 超时，已中止：{exc}")
    final_state = coord.get_transaction_state(tx_id)
    assert final_state == TransactionState.TIMEOUT_ABORTED
except CommitFailedError as exc:
    print(f"部分参与者提交失败：{exc}")
    print(f"  失败参与者: {exc.failed_participants}")
    print(f"  已成功参与者: {exc.committed_participants}")
    # 事务状态为 COMMIT_PARTIALLY_FAILED，可通过 retry_commit 重试
    final_state = coord.get_transaction_state(tx_id)
    assert final_state == TransactionState.COMMIT_PARTIALLY_FAILED
    # 记录日志告警，通知人工处理或自动重试
except AbortFailedError as exc:
    print(f"部分参与者中止失败（重试后仍失败）：{exc}")
    final_state = coord.get_transaction_state(tx_id)
    assert final_state == TransactionState.ABORTING
```

### 4.6 Commit 部分失败与 retry_commit

```python
coord = TransactionCoordinator()
bad_state = {"should_fail": True}

def flaky_commit(tx_id: str) -> None:
    if bad_state["should_fail"]:
        raise RuntimeError("网络分区，无法连接数据库")
    # 否则正常提交

p = TransactionParticipant("unreliable-db")
p.set_callbacks(on_prepare=lambda tx: True, on_commit=flaky_commit)

tx_id = coord.begin_transaction("tx-with-flaky-commit")
coord.register_participant(tx_id, p)

coord.prepare_transaction(tx_id)
try:
    coord.commit_transaction(tx_id)
except CommitFailedError as exc:
    print(f"首次 commit 失败：{exc.failed_participants}")

# 检测到部分失败
assert coord.get_transaction_state(tx_id) == TransactionState.COMMIT_PARTIALLY_FAILED
assert coord.has_incomplete_commit(tx_id) is True
assert coord.get_commit_failed_participants(tx_id) == ["unreliable-db"]

# 修复问题后重试
bad_state["should_fail"] = False
success = coord.retry_commit(tx_id)
assert success is True
assert coord.get_transaction_state(tx_id) == TransactionState.COMMITTED
assert coord.has_incomplete_commit(tx_id) is False
```

### 4.7 Abort 回调失败与 retry_abort

```python
coord = TransactionCoordinator()
unreliable_state = {"network_down": True}

def unreliable_abort(tx_id: str) -> None:
    if unreliable_state["network_down"]:
        raise RuntimeError("网络分区，无法连接资源管理器")
    # 否则正常回滚

p = TransactionParticipant("unreliable-svc")
p.set_callbacks(on_prepare=lambda tx: True, on_abort=unreliable_abort)

tx_id = coord.begin_transaction("tx-with-flaky-abort")
coord.register_participant(tx_id, p)

coord.prepare_transaction(tx_id)
coord.abort_transaction(tx_id)

# 检测到 abort 失败
assert coord.get_transaction_state(tx_id) == TransactionState.ABORTING
assert coord.has_incomplete_abort(tx_id) is True
failed = coord.get_abort_failed_participants(tx_id)
assert failed == ["unreliable-svc"]

# 修复问题后重试
unreliable_state["network_down"] = False
success = coord.retry_abort(tx_id)
assert success is True
assert coord.get_transaction_state(tx_id) == TransactionState.ABORTED
assert coord.has_incomplete_abort(tx_id) is False
```

### 4.8 execute_transaction 自动重试

```python
# 设置最多重试 5 次
coord = TransactionCoordinator(max_retry_attempts=5)
fail_count = {"n": 0}

def commit_with_transient_failures(tx_id: str) -> None:
    if fail_count["n"] < 3:
        fail_count["n"] += 1
        raise RuntimeError(f"瞬时故障 #{fail_count['n']}")
    # 第 4 次成功

p = TransactionParticipant("eventually-consistent")
p.set_callbacks(on_prepare=lambda tx: True, on_commit=commit_with_transient_failures)

tx_id = coord.begin_transaction()
coord.register_participant(tx_id, p)

# execute_transaction 会自动重试
final_state = coord.execute_transaction(tx_id)
assert final_state == TransactionState.COMMITTED
assert fail_count["n"] == 3  # 失败了 3 次，第 4 次成功
```

## 5. 文件结构

```
src/solocoder_4_py/transaction_coordination/
├── __init__.py          # 公共 API 导出
├── constants.py         # 状态枚举、终态常量集合
├── exceptions.py        # 事务相关异常类层级（含 CommitFailedError 详情字段）
├── participant.py       # TransactionParticipant 实现
├── coordinator.py       # TransactionCoordinator 实现（含 retry_commit / retry_abort）
└── README.md            # 本文档

tests/transaction_coordination/
├── __init__.py
└── test_transaction_coordination.py  # 67 个单元测试用例
```

## 6. 运行测试

```bash
poetry run pytest tests/transaction_coordination/ -v
```
