# Transaction Log Module (内存事务日志管理模块)

## 模块功能概述

本模块实现了一个基于内存数据结构的事务日志管理系统，提供以下核心功能：

1. **追加式事务日志 (Append-only Transaction Log)**：所有操作以日志形式顺序追加记录，每条日志拥有唯一的 LSN (Log Sequence Number)。
2. **事务 ACID 支持**：支持 BEGIN、COMMIT、ROLLBACK 语义，确保事务的原子性。
3. **检查点压缩 (Checkpoint Compression)**：通过创建检查点将当前状态快照固化，压缩历史日志，减少恢复时间。
4. **崩溃恢复 (Crash Recovery)**：模拟系统崩溃后，基于检查点 + 日志 REDO/UNDO 算法恢复到一致性状态。
5. **状态存储 (State Store)**：提供键值对形式的内存状态存储，支持快照与回滚。

---

## 模块结构

```
transaction_log/
├── __init__.py          # 公共 API 导出
├── log_entry.py         # 日志条目与操作类型定义
├── state_store.py       # 状态存储（键值存储 + 快照）
├── transaction_log.py   # 事务日志管理器（核心逻辑）
└── README.md            # 本文档
```

### 导出的公共类

| 类名 | 说明 |
|------|------|
| `OperationType` | 枚举：日志操作类型（BEGIN / COMMIT / ROLLBACK / SET / DELETE / CHECKPOINT） |
| `LogEntry` | 不可变日志条目数据类（含 LSN、事务ID、键值、时间戳等） |
| `StateStore` | 内存键值状态存储（支持快照、深拷贝、字典式访问） |
| `TransactionLogManager` | 事务日志管理器（主入口，封装所有日志与事务操作） |

---

## 日志恢复流程 (Crash Recovery Procedure)

模块的 `simulate_crash_and_recover()` 方法实现了经典的 **ARIES 风格** REDO + UNDO 两阶段恢复算法：

### 第一阶段：分析 (Analysis)
- 从最近一个检查点（如果存在）开始遍历日志。
- 识别已完成的事务（有 COMMIT 记录），放入 REDO 列表。
- 识别未完成的事务（只有 BEGIN 没有 COMMIT / ROLLBACK），放入 UNDO 列表。

### 第二阶段：重做 (REDO)
- 从检查点状态快照出发（若无检查点则从空状态开始）。
- 按 LSN 升序重放所有已提交事务及无事务上下文的数据操作：
  - `SET`：重新写入键值对。
  - `DELETE`：重新删除键。

### 第三阶段：撤销 (UNDO)
- 对每个未完成的事务，按 LSN **逆序**回滚其数据操作：
  - `SET`：若 `old_value` 为 `None` 则删除该键，否则恢复 `old_value`。
  - `DELETE`：若 `old_value` 非 `None` 则恢复该键的值。

### 恢复输出
返回三元组 `(recovered_state, redo_count, undo_count)`：
- `recovered_state`：恢复后的 `StateStore` 实例。
- `redo_count`：REDO 阶段处理的数据操作数。
- `undo_count`：UNDO 阶段回滚的数据操作数。

---

## 检查点行为 (Checkpoint Behavior)

### 检查点触发条件
调用 `TransactionLogManager.checkpoint()` 方法，建议在事务空闲或日志积累到一定量时手动触发。

### 检查点执行步骤
1. **强制回滚**：先对所有活跃事务执行 ROLLBACK，确保检查点时刻状态一致。
2. **保存快照**：将当前 `StateStore` 的深拷贝作为检查点状态快照。
3. **记录日志**：追加一条 `CHECKPOINT` 类型日志条目。
4. **压缩日志**：丢弃检查点 LSN 之前的所有历史日志条目。
5. **重排 LSN**：剩余日志的 LSN 从 0 开始重新编号。

### 检查点效果
- **日志占用减少**：历史日志被压缩，内存占用降低。
- **恢复加速**：恢复时从检查点快照开始，只需要重放之后的少量日志。
- **LSN 重置**：日志被截断后，LSN 从 0 重新开始计数。

---

## 使用示例

### 示例 1：基本读写与日志
```python
from solocoder_4_py.transaction_log import TransactionLogManager

mgr = TransactionLogManager()

# 无事务的直接操作（自动记录日志）
mgr.set("user:1:name", "Alice")
mgr.set("user:1:age", 30)
mgr.delete("user:1:age")

print(mgr.state["user:1:name"])  # "Alice"
print(mgr.log_length)            # 3 (SET, SET, DELETE)
```

### 示例 2：事务提交与回滚
```python
# 开始事务
tx_id = mgr.begin_transaction()

# 事务内操作
mgr.set("balance:alice", 800, transaction_id=tx_id)
mgr.set("balance:bob", 1200, transaction_id=tx_id)

# 提交事务
mgr.commit(tx_id)

# 回滚示例
tx_id2 = mgr.begin_transaction()
mgr.set("balance:alice", 9999, transaction_id=tx_id2)
mgr.rollback(tx_id2)  # balance:alice 恢复为 800
```

### 示例 3：检查点压缩
```python
# 先做一些操作
for i in range(100):
    mgr.set(f"item:{i}", f"value-{i}")

print(f"日志长度（检查点前）: {mgr.log_length}")  # 100+

# 创建检查点
cp_lsn = mgr.checkpoint()

print(f"检查点 LSN: {cp_lsn}")
print(f"日志长度（检查点后）: {mgr.log_length}")  # 1 (只剩 CHECKPOINT 条目)
print(f"状态仍然完整: {len(mgr.state)}")          # 100
```

### 示例 4：模拟崩溃与恢复
```python
# 设置初始状态并创建检查点
mgr.set("version", "1.0")
mgr.checkpoint()

# 已提交的操作（应该被 REDO）
tx_good = mgr.begin_transaction()
mgr.set("version", "2.0", transaction_id=tx_good)
mgr.set("release_date", "2024-06-01", transaction_id=tx_good)
mgr.commit(tx_good)

# 未提交的操作（应该被 UNDO）
tx_bad = mgr.begin_transaction()
mgr.set("version", "3.0-beta", transaction_id=tx_bad)  # 未提交！

# 模拟崩溃！
recovered, redo_count, undo_count = mgr.simulate_crash_and_recover()

print(f"REDO 操作数: {redo_count}")   # 已提交的 SET
print(f"UNDO 操作数: {undo_count}")   # 未提交的 SET
print(f"恢复后 version: {recovered['version']}")        # "2.0"  (不是 3.0-beta)
print(f"恢复后 release_date: {recovered['release_date']}")  # "2024-06-01"
```

### 示例 5：日志截断与重置
```python
# 手动截断指定 LSN 之前的日志
removed = mgr.truncate_log_before(lsn=50)
print(f"移除了 {removed} 条旧日志")

# 完全重置管理器（清空日志、状态、检查点）
mgr.reset()
```

### 示例 6：日志条目访问与序列化
```python
from solocoder_4_py.transaction_log import LogEntry

# 获取单条日志
entry = mgr.get_log_entry(0)
print(f"LSN={entry.lsn}, OP={entry.operation.value}, KEY={entry.key}")

# 获取指定范围日志
entries = mgr.get_log_entries(start_lsn=10, end_lsn=20)

# 序列化 / 反序列化（用于持久化扩展）
d = entry.to_dict()
restored_entry = LogEntry.from_dict(d)
```

---

## 设计说明

### LSN (Log Sequence Number)
每条日志拥有唯一的单调递增序号，作为日志的身份标识。检查点触发后 LSN 会重新从 0 开始。

### 日志不可变性
`LogEntry` 使用 `@dataclass(frozen=True)` 实现不可变性，防止日志被事后篡改，保证审计与恢复的可信度。

### StateStore 深拷贝
状态快照和序列化都使用 `copy.deepcopy`，确保嵌套可变对象（dict、list）也被正确隔离。

### 事务隔离性
本模块为**单线程内存模型**，事务隔离级别等价于 Read Uncommitted（因为是直接修改内存状态，REDO/UNDO 保证一致性而非隔离性）。如需更高隔离级别应在外层加锁。
