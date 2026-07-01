# 内存事务协调域模块 (transaction_coordination)

本模块使用纯内存数据结构实现了 **两阶段提交（Two-Phase Commit, 2PC）** 协议下的分布式事务协调过程，用于学习、测试和模拟真实分布式事务环境。

## 1. 模块功能

| 能力 | 说明 |
|------|------|
| 多参与者事务 | 支持在一个事务中注册任意数量的参与者 |
| 两阶段提交 | 实现标准的 Prepare / Commit / Abort 语义 |
| 超时决策 | Prepare 阶段若等待超时，协调器自动决策中止 |
| 幂等操作 | 对重复的 prepare/commit/abort 调用稳定返回结果，不产生重复副作用 |
| 自定义业务回调 | 通过注入 `on_prepare` / `on_commit` / `on_abort` 回调模拟真实业务逻辑 |
| 线程安全 | 内部使用 `threading.Lock` 保证基本并发安全 |
| 可测试时钟 | 协调器支持注入自定义 `clock` 函数，便于测试超时场景 |

## 2. 核心概念

### 2.1 组件

- **`TransactionParticipant`**：事务参与者。模拟一个独立的资源管理器（如数据库、微服务）。每个参与者对每个事务维护独立的状态。
- **`TransactionCoordinator`**：事务协调器。负责驱动整个 2PC 流程，管理所有参与者的状态与最终决策。
- **状态枚举**：`TransactionState`（全局事务状态）与 `ParticipantState`（参与者本地状态）。

### 2.2 两阶段提交流程 (2PC)

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
│    Coordinator ──Commit()──▶ 所有参与者 （释放资源锁+持久化）   │
│                                                               │
│  决策 Abort:                                                   │
│    Coordinator ──Abort()───▶ 所有参与者 （回滚+释放锁）        │
└───────────────────────────────────────────────────────────────┘
```

**事务状态机**：

```
INIT ─▶ PREPARING ─┬─▶ PREPARED ──▶ COMMITTING ──▶ COMMITTED
                    │
                    ├─ (任何失败/超时) ─▶ ABORTING ──▶ ABORTED
                    │                                      ▲
                    └──────────────────────────────────────┘
                                       └─ TIMEOUT_ABORTED (协调器超时决策中止，走 Abort 流程)
```

## 3. 异常场景与处理

### 3.1 参与者 Prepare 失败
- **现象**：任意参与者在 `on_prepare` 回调中返回 `False` 或抛出异常
- **协调器动作**：记录失败，最终决策为 `ABORTED`，对所有已 Prepare 成功的参与者调用 `abort` 进行回滚

### 3.2 Prepare 阶段超时
- **现象**：从 `prepare_started_at` 计时，超过 `prepare_timeout_seconds` 仍未收集到所有 YES
- **协调器动作**：决策 `TIMEOUT_ABORTED`，对所有已响应的参与者调用 `abort`
- **可测试性**：通过 `TransactionCoordinator(clock=FakeClock())` 注入可控时钟便于断言

### 3.3 重复请求（幂等性）
- **重复 Prepare**：
  - 已 `PREPARED` → 返回 `True`，不重复调用回调
  - 已失败/已中止 → 稳定返回 `False`
  - 已 `COMMITTED` → 抛 `TransactionStateError`
- **重复 Commit**：已 `COMMITTED` → 直接返回，业务回调仅执行一次
- **重复 Abort**：已 `ABORTED` → 直接返回，业务回调仅执行一次
- **重复 execute_transaction**：终态事务直接返回当前状态

### 3.4 非法状态转换
下列操作均会抛 `TransactionStateError`：
- 未 Prepare 就 Commit（需要先 `prepare_transaction` 成功）
- 已 Abort 的事务再 Commit
- 已 Commit 的事务再 Abort
- 在 PREPARED 之后才注册新参与者

### 3.5 其他异常
- `TransactionNotFoundError`：操作不存在的 `tx_id`
- `ParticipantAlreadyRegisteredError`：向同一事务重复注册参与者
- `PrepareFailedError` / `CommitFailedError` / `AbortFailedError`：参与者回调执行失败

## 4. 使用示例

### 4.1 最小示例：成功提交

```python
from solocoder_4_py.transaction_coordination import (
    TransactionCoordinator,
    TransactionParticipant,
    TransactionState,
)

# 构造协调器（可选 prepare 超时）
coord = TransactionCoordinator(prepare_timeout_seconds=10.0)

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
assert state == TransactionState.ABORTED
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

## 5. 文件结构

```
src/solocoder_4_py/transaction_coordination/
├── __init__.py          # 公共 API 导出
├── constants.py         # 状态枚举、终态常量集合
├── exceptions.py        # 事务相关异常类层级
├── participant.py       # TransactionParticipant 实现
├── coordinator.py       # TransactionCoordinator 实现
└── README.md            # 本文档

tests/transaction_coordination/
├── __init__.py
└── test_transaction_coordination.py  # 51 个单元测试用例
```

## 6. 运行测试

```bash
python -m pytest tests/transaction_coordination/ -v
```
