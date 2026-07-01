# Transaction Log Module (内存事务日志管理模块)

## 模块功能概述

本模块实现了一个基于内存数据结构的事务日志管理系统，提供以下核心功能：

1. **追加式事务日志 (Append-only Transaction Log)**：所有操作以日志形式顺序追加记录，日志在列表中的索引隐式作为 LSN (Log Sequence Number)。
2. **事务 ACID 支持**：支持 BEGIN、COMMIT、ROLLBACK 语义，确保事务的原子性。
3. **检查点压缩 (Checkpoint Compression)**：通过创建检查点将当前状态快照固化，压缩历史日志，减少恢复时间。
4. **崩溃恢复 (Crash Recovery)**：模拟系统崩溃后，基于检查点 + 日志 REDO/UNDO 算法恢复到一致性状态。
5. **状态存储 (State Store)**：提供键值对形式的内存状态存储，支持快照与回滚，None 作为合法值处理。

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

| 类/对象名 | 说明 |
|-----------|------|
| `OperationType` | 枚举：日志操作类型（BEGIN / COMMIT / ROLLBACK / SET / DELETE / CHECKPOINT） |
| `LogEntry` | 不可变日志条目数据类（含事务ID、键值、时间戳等，**无 LSN 字段**） |
| `StateStore` | 内存键值状态存储（支持快照、深拷贝、字典式访问） |
| `TransactionLogManager` | 事务日志管理器（主入口，封装所有日志与事务操作） |
| `_MISSING` | 哨兵对象：用于区分「键不存在」和「键值为 None」两种状态 |

---

## 核心设计修复说明

### LSN 维护策略（已修复）

**问题**：原设计将 LSN 存储在 `LogEntry` 内部，使用 `object.__setattr__` 绕过 `frozen=True` 限制修改 LSN，破坏了日志不可变性，且外部引用持有的日志条目 LSN 会静默改变。

**修复方案**：
- **移除 `LogEntry.lsn` 字段**：日志条目不再存储 LSN。
- **隐式 LSN**：LSN 由日志在列表中的索引隐式维护，`get_log_entry(lsn)` 直接通过列表索引访问。
- **LSN 重排**：日志截断后，新的列表索引自然成为新的 LSN，无需修改日志条目本身。
- **`next_lsn` 属性**：返回 `len(self._log)`，始终等于下一条将被追加日志的隐式 LSN。

### None 值处理（已修复）

**问题**：原设计使用 `old_value is None` 同时表示「键操作前不存在」和「键操作前值为 None」，导致回滚时将值为 None 的键错误删除，而非恢复为 None。

**修复方案**：
- 引入独立哨兵对象 `_MISSING = object()`，仅用于表示「键不存在」的状态。
- `StateStore.set()`：键不存在时返回 `_MISSING`，键存在时返回原值（包括 None）。
- `StateStore.delete()`：键不存在时返回 `(False, _MISSING)`，键存在时返回 `(True, old_value)`（old_value 可以是 None）。
- 回滚逻辑中使用 `entry.old_value is _MISSING` 判断键是否在操作前不存在，而非 `is None`。

### 冗余代码清理（已修复）

- **移除死代码**：删除 `simulate_crash_and_recover` 中定义但未使用的局部变量 `start_lsn`。
- **移除重复赋值**：`checkpoint()` 方法中移除重复的 `self._next_lsn = len(self._log)` 赋值。
- **移除 `object.__setattr__`**：不再需要强制修改 frozen 对象的 LSN 字段。

---

## 日志恢复流程 (Crash Recovery Procedure)

模块的 `simulate_crash_and_recover()` 方法实现了经典的 **ARIES 风格** REDO + UNDO 两阶段恢复算法：

### 第一阶段：分析 (Analysis)
- 从日志起始位置开始遍历（检查点快照已提前加载）。
- 识别已完成的事务（有 COMMIT 记录），放入 REDO 列表。
- 识别未完成的事务（只有 BEGIN 没有 COMMIT / ROLLBACK），放入 UNDO 列表。

### 第二阶段：重做 (REDO)
- 从检查点状态快照出发（若无检查点则从空状态开始）。
- 按日志顺序重放所有已提交事务及无事务上下文的数据操作：
  - `SET`：重新写入键值对。
  - `DELETE`：重新删除键。

### 第三阶段：撤销 (UNDO)
- 对每个未完成的事务，按日志逆序回滚其数据操作：
  - `SET`：若 `old_value is _MISSING` 则删除该键（键之前不存在），否则恢复 `old_value`（包括 None）。
  - `DELETE`：若 `old_value is not _MISSING` 则恢复该键的值（包括 None）。

### 恢复输出
返回三元组 `(recovered_state, redo_count, undo_count)`：
- `recovered_state`：恢复后的 `StateStore` 实例。
- `redo_count`：REDO 阶段处理的数据操作数（精确计数）。
- `undo_count`：UNDO 阶段回滚的数据操作数（精确计数）。

---

## 检查点行为 (Checkpoint Behavior)

### 检查点触发条件
调用 `TransactionLogManager.checkpoint()` 方法，建议在事务空闲或日志积累到一定量时手动触发。

### 检查点执行步骤
1. **强制回滚**：先对所有活跃事务执行 ROLLBACK，确保检查点时刻状态一致。
2. **保存快照**：将当前 `StateStore` 的深拷贝作为检查点状态快照。
3. **记录日志**：追加一条 `CHECKPOINT` 类型日志条目。
4. **压缩日志**：丢弃检查点之前的所有历史日志条目。
5. **重置索引**：剩余日志的索引自然从 0 开始，无需修改日志条目本身。

### 检查点效果
- **日志占用减少**：历史日志被压缩，内存占用降低。
- **恢复加速**：恢复时从检查点快照开始，只需要重放之后的少量日志。
- **LSN 重置**：日志被截断后，索引从 0 重新开始。

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

### 示例 2：None 作为合法值
```python
# None 是完全合法的存储值
mgr.set("config:debug_mode", None)
print(mgr.state["config:debug_mode"])  # None
print("config:debug_mode" in mgr.state)  # True（键存在）

# 覆盖 None 值
old = mgr.set("config:debug_mode", True)
print(old)  # None（返回原值，不是 _MISSING）

# 重新设回 None
old = mgr.set("config:debug_mode", None)
print(old)  # True
```

### 示例 3：事务提交与回滚
```python
# 开始事务
tx_id = mgr.begin_transaction()

# 事务内操作
mgr.set("balance:alice", 800, transaction_id=tx_id)
mgr.set("balance:bob", 1200, transaction_id=tx_id)

# 提交事务
mgr.commit(tx_id)

# 回滚示例（包含 None 值）
tx_id2 = mgr.begin_transaction()
mgr.set("balance:alice", None, transaction_id=tx_id2)  # 临时设为 None
mgr.set("new_field", None, transaction_id=tx_id2)       # 新键设为 None
mgr.rollback(tx_id2)  # balance:alice 恢复为 800，new_field 被删除
print(mgr.state["balance:alice"])  # 800（正确恢复，不是被删除）
print("new_field" in mgr.state)    # False（正确删除）
```

### 示例 4：检查点压缩
```python
# 先做一些操作
for i in range(100):
    mgr.set(f"item:{i}", f"value-{i}")
mgr.set("nullable_item", None)

print(f"日志长度（检查点前）: {mgr.log_length}")  # 101

# 创建检查点
cp_lsn = mgr.checkpoint()

print(f"检查点索引: {cp_lsn}")  # 0
print(f"日志长度（检查点后）: {mgr.log_length}")  # 1 (只剩 CHECKPOINT 条目)
print(f"状态仍然完整: {len(mgr.state)}")          # 101
print(f"None 值保留: {mgr.state['nullable_item']}")  # None
```

### 示例 5：模拟崩溃与恢复（带精确计数）
```python
# 设置初始状态并创建检查点
mgr.set("version", "1.0")
mgr.set("beta_flag", None)
mgr.checkpoint()

# 已提交的操作（应该被 REDO）
tx_good = mgr.begin_transaction()
mgr.set("version", "2.0", transaction_id=tx_good)
mgr.set("release_date", "2024-06-01", transaction_id=tx_good)
mgr.set("beta_flag", True, transaction_id=tx_good)
mgr.commit(tx_good)

# 未提交的操作（应该被 UNDO）
tx_bad = mgr.begin_transaction()
mgr.set("version", "3.0-beta", transaction_id=tx_bad)  # 未提交！
mgr.set("beta_flag", None, transaction_id=tx_bad)      # 未提交！

# 模拟崩溃！
recovered, redo_count, undo_count = mgr.simulate_crash_and_recover()

print(f"REDO 操作数: {redo_count}")   # 3（已提交的 3 个 SET）
print(f"UNDO 操作数: {undo_count}")   # 2（未提交的 2 个 SET）
print(f"恢复后 version: {recovered['version']}")        # "2.0"
print(f"恢复后 beta_flag: {recovered['beta_flag']}")    # True（正确恢复，不是 None）
print(f"恢复后 release_date: {recovered['release_date']}")  # "2024-06-01"
```

### 示例 6：日志条目访问与序列化
```python
from solocoder_4_py.transaction_log import LogEntry, _MISSING

# 获取单条日志（LSN 是列表索引）
entry = mgr.get_log_entry(0)
print(f"OP={entry.operation.value}, KEY={entry.key}")  # 无 entry.lsn

# 验证 LogEntry 没有 lsn 属性
print(hasattr(entry, "lsn"))  # False

# 获取指定范围日志
entries = mgr.get_log_entries(start_lsn=10, end_lsn=20)

# 序列化 / 反序列化（用于持久化扩展）
d = entry.to_dict()
print(d["old_value_is_missing"])  # bool，区分 None 和 _MISSING
restored_entry = LogEntry.from_dict(d)

# _MISSING 哨兵使用
print(old is _MISSING)  # 键之前不存在
print(old is None)      # 键之前值为 None
```

### 示例 7：日志截断与重置
```python
# 手动截断指定 LSN 之前的日志
removed = mgr.truncate_log_before(lsn=50)
print(f"移除了 {removed} 条旧日志")

# 完全重置管理器（清空日志、状态、检查点）
mgr.reset()
```

---

## 设计说明

### LSN (Log Sequence Number)
LSN 由日志在内部列表中的索引隐式维护，不存储在日志条目中。日志条目一旦创建即为完全不可变，确保审计追溯和恢复的可信度。检查点触发后，日志被截断，LSN 从 0 重新开始。

### `_MISSING` 哨兵对象
- **唯一标识**：`_MISSING = object()`，全局唯一，与任何可能的用户值（包括 None）都不相同。
- **使用场景**：仅用于 `StateStore.set()` 和 `StateStore.delete()` 的返回值，以及 `LogEntry.old_value` 字段，统一表示「键不存在」。
- **对比 None**：
  - `old_value is _MISSING` → 键在操作前不存在。
  - `old_value is None` → 键在操作前存在，且值为 None。

### 日志不可变性
`LogEntry` 使用 `@dataclass(frozen=True)` 实现完全不可变性，创建后任何字段都无法修改（包括过去的 LSN 字段）。防止日志被事后篡改，保证审计与恢复的可信度。

### StateStore 深拷贝
状态快照和序列化都使用 `copy.deepcopy`，确保嵌套可变对象（dict、list）也被正确隔离。

### 事务隔离性
本模块为**单线程内存模型**，事务隔离级别等价于 Read Uncommitted（因为是直接修改内存状态，REDO/UNDO 保证一致性而非隔离性）。如需更高隔离级别应在外层加锁。
