# Request Snapshot Cache

请求结果快照缓存模块，用于在内存中缓存请求参数和结果快照，支持数据版本绑定和精准失效。

## 功能特性

- **稳定缓存键生成**：根据请求参数生成唯一且稳定的缓存键，相同语义的参数命中同一份快照
- **数据版本绑定**：缓存结果与相关数据实体的版本号绑定，数据变化后自动失效
- **内存存储**：使用 Python 内存数据结构存储，无需外部依赖
- **线程安全**：所有操作均支持多线程并发访问
- **统计信息**：提供缓存命中率、失效次数等统计数据
- **LRU 淘汰**：支持配置最大缓存容量，超出时自动淘汰最久未使用的条目
- **TTL 过期**：支持配置默认过期时间

## 模块结构

```
request_snapshot_cache/
├── __init__.py          # 模块导出
├── cache_key.py         # 缓存键生成逻辑
├── version_manager.py   # 版本管理和失效机制
├── snapshot_cache.py    # 快照缓存核心类
└── README.md            # 本文档
```

## 缓存键规则

### 生成算法

缓存键格式：`{prefix}:{hash_digest}`

- **prefix**：可配置的前缀，默认为 `snapshot`
- **hash_digest**：使用指定哈希算法（默认 SHA-256）生成的十六进制摘要

### 键计算输入

缓存键**仅基于 `request_params`（请求参数）**计算，`data_entities`（数据实体）不参与缓存键哈希。

**设计动机**：
- 相同请求参数应复用同一份缓存快照，提高缓存复用率
- 数据实体仅用于版本校验，不决定缓存键本身
- 当使用不同实体列表对同一参数多次 set 时，后写入的条目会覆盖先写入的条目（包括其依赖的实体版本）

缓存键计算细节：
- **request_params**：请求参数字典
  - 字典按键名排序后进行序列化
  - 支持嵌套字典、列表、元组、集合等复杂结构
  - 集合会先排序再序列化，确保相同元素的集合生成相同键

### 规范化规则

为了确保相同语义的参数生成相同的缓存键，遵循以下规范化规则：

| 数据类型 | 处理方式 |
|---------|---------|
| `None` | 保持为 `null` |
| `bool` | 保持原值（注意：`True` 不等同于 `1`） |
| `int`, `float`, `str` | 保持原值 |
| `dict` | 按键名排序后递归处理每个值 |
| `list`, `tuple` | 按顺序递归处理每个元素 |
| `set` | 先转换为排序列表，再递归处理每个元素 |
| 其他类型 | 转换为字符串表示 |

### 示例

```python
# 以下参数生成相同的缓存键
params1 = {"a": 1, "b": 2}
params2 = {"b": 2, "a": 1}  # 字典键顺序不影响

params3 = {"tags": ["x", "y"]}
params4 = {"tags": ("x", "y")}  # list 和 tuple 语义相同

params5 = {"ids": {1, 2, 3}}
params6 = {"ids": {3, 2, 1}}  # 集合顺序不影响

# 相同参数，不同实体列表也生成相同键（提高缓存复用率）
params = {"user_id": 123}
key_with_users = generator.generate(params, ["users"])
key_with_users_and_orders = generator.generate(params, ["users", "orders"])
assert key_with_users == key_with_users_and_orders
```

## 版本绑定机制

### 核心概念

- **数据实体（Data Entity）**：逻辑上相关的数据集合，如 `users`、`orders`、`products`
- **实体版本（Entity Version）**：每个数据实体维护一个递增的版本号
- **缓存依赖**：每个缓存条目记录其依赖的数据实体及其版本号

### 版本追踪

1. 当缓存条目被创建时，记录所有关联数据实体的当前版本号
2. 当查询缓存时，验证所有关联实体的当前版本是否与记录的版本一致
3. 如果任何关联实体的版本发生变化，缓存条目自动失效

### 精准失效

当数据发生变化时，通过调用 `bump_entity_version` 或 `invalidate_by_entity` 方法：

```python
# 数据发生变化，递增版本号
cache.bump_entity_version("users")

# 或直接失效所有依赖该实体的缓存
cache.invalidate_by_entity("users")
```

系统会自动找到所有依赖该实体的缓存条目并使其失效，实现精准的缓存失效。

## 使用示例

### 基础使用

```python
from solocoder_4_py.request_snapshot_cache import RequestSnapshotCache

# 创建缓存实例
cache = RequestSnapshotCache()

# 存储缓存结果
params = {"user_id": 123, "include_profile": True}
result = {"name": "Alice", "age": 30}
cache.set(params, result, data_entities=["users"])

# 查询缓存
cached_result = cache.get(params, data_entities=["users"])
if cached_result is not None:
    print("缓存命中:", cached_result)
else:
    print("缓存未命中")

# 检查缓存是否存在
if cache.has(params, data_entities=["users"]):
    print("缓存存在且有效")
```

### 版本绑定与失效

```python
# 缓存依赖 users 和 orders 实体
params1 = {"user_id": 123}
cache.set(params1, result1, data_entities=["users", "orders"])

params2 = {"order_id": 456}
cache.set(params2, result2, data_entities=["orders"])

# 当 orders 数据变化时，失效所有依赖 orders 的缓存
invalidated_count = cache.invalidate_by_entity("orders")
print(f"失效了 {invalidated_count} 个缓存条目")  # 输出: 失效了 2 个缓存条目

# params1 和 params2 的缓存都已失效
assert cache.get(params1, data_entities=["users", "orders"]) is None
assert cache.get(params2, data_entities=["orders"]) is None
```

### 使用 get_or_compute 简化代码

```python
def expensive_query(user_id: int) -> dict:
    # 模拟耗时的数据库查询
    print("执行数据库查询...")
    return {"user_id": user_id, "name": "Alice"}

params = {"user_id": 123}
# 第一次调用会执行 expensive_query
result1 = cache.get_or_compute(
    params,
    lambda: expensive_query(123),
    data_entities=["users"]
)  # 输出: 执行数据库查询...

# 第二次调用直接返回缓存
result2 = cache.get_or_compute(
    params,
    lambda: expensive_query(123),
    data_entities=["users"]
)  # 无输出，直接返回缓存
```

### 配置 LRU 和 TTL

```python
# 最多缓存 1000 条，默认 1 小时过期
cache = RequestSnapshotCache(max_size=1000, default_ttl=3600)
```

### 查看统计信息

```python
stats = cache.get_stats()
print(f"缓存命中率: {stats['hits'] / (stats['hits'] + stats['misses']):.2%}")
print(f"缓存条目数: {stats['size']}")
print(f"失效次数: {stats['invalidations']}")
```

### 独立使用 CacheKeyGenerator

```python
from solocoder_4_py.request_snapshot_cache import CacheKeyGenerator, generate_cache_key

# 使用类
generator = CacheKeyGenerator(algorithm="md5", prefix="myapp")
key = generator.generate({"a": 1, "b": 2}, data_entities=["users"])

# 使用便捷函数
key = generate_cache_key({"a": 1, "b": 2})
```

### 独立使用 VersionManager

```python
from solocoder_4_py.request_snapshot_cache import VersionManager

vm = VersionManager()

# 注册缓存依赖
vm.register_cache_dependency("cache_key_1", ["users", "orders"])
vm.register_cache_dependency("cache_key_2", ["orders"])

# 获取受影响的缓存键
affected = vm.get_invalidated_caches(["orders"])
print(affected)  # {'cache_key_1', 'cache_key_2'}

# 获取版本签名
signature = vm.get_version_signature(["users", "orders"])
print(signature)  # "orders:0|users:0"
```

## 版本竞态防护

### 问题背景

`get_or_compute` 方法在 `get` 未命中后会执行 `compute_func` 计算新结果，然后 `set` 写入缓存。如果在 `compute_func` 执行期间，其他线程（或本线程内部）通过 `bump_entity_version` 递增了关联实体的版本号，那么刚计算出的结果对应的是旧版本数据，如果直接写入缓存会造成脏数据缓存。

### 防护策略

`get_or_compute` 实现了**计算前后版本二次校验**：

1. 调用 `compute_func` 之前，在锁内获取所有关联实体的版本号快照（`versions_before`）
2. 执行 `compute_func`（在此期间释放锁，允许其他线程操作）
3. 获取计算结果后，重新获取锁并再次获取所有关联实体的当前版本号（`versions_after`）
4. 如果 `versions_before != versions_after`，说明计算期间有版本变更：
   - 直接返回计算结果给调用方（保证业务正确性）
   - **不写入缓存**（避免缓存脏数据）
   - 统计 `version_race_detected` 计数 +1
5. 如果版本一致，则将结果写入缓存，并使用 `versions_after` 作为绑定版本号

### 示例场景

```python
def compute_and_bump():
    # 计算期间触发了实体版本变化
    cache.bump_entity_version("users")
    return {"name": "Alice"}

result = cache.get_or_compute(
    {"id": 123},
    compute_and_bump,
    data_entities=["users"]
)
# result 正确返回了计算结果
# 但由于检测到版本竞态，该结果不会被缓存
# 下次调用 get_or_compute 时会重新执行 compute
```

### 统计信息

通过 `get_stats()["version_race_detected"]` 可以查看版本竞态检测次数。如果该值持续偏高，说明：
- 实体版本更新频率过高，与缓存查询存在冲突
- 可以考虑缩短缓存时间或优化更新策略

## 模式失效与实体失效一致性

### 问题背景

`invalidate_by_entity` 会同时执行两个动作：（1）递增实体版本号；（2）清除依赖该实体的所有缓存条目。而旧版 `invalidate_by_pattern` 仅通过模式匹配清除部分缓存条目，不递增任何实体版本号。这导致：
- 依赖同一实体但未被模式匹配的其他缓存条目，仍持有旧版本号不会被动失效
- 两种失效方式的行为语义不一致

### 一致性策略

`invalidate_by_pattern` 现在遵循以下流程：

1. 惰性清理 TTL 过期条目
2. 根据 `pattern_func` 找出所有匹配的缓存条目
3. 收集这些条目关联的**所有数据实体**（去重后的并集）
4. **对每个受影响的实体执行版本递增**（与 `invalidate_by_entity` 行为一致）
5. 清除所有匹配的缓存条目
6. 统计 `invalidations` 计数

### 效果

- 通过模式清除的条目，其关联实体的版本号会被递增
- 依赖相同实体但未被模式匹配的其他缓存条目，会在下次查询时通过版本校验被动失效
- 保证了模式失效与实体失效在版本维度的一致性

### 示例

```python
cache.set({"type": "A", "id": 1}, "r1", data_entities=["products"])
cache.set({"type": "A", "id": 2}, "r2", data_entities=["products"])
cache.set({"type": "B", "id": 3}, "r3", data_entities=["products"])

# 仅清除 type=A 的条目
cache.invalidate_by_pattern(lambda p: p.get("type") == "A")
# products 实体版本被递增 +1

# 此时 type=B 的条目虽然还在缓存中，但因版本校验不通过也会失效
assert cache.get({"type": "B", "id": 3}, data_entities=["products"]) is None
```

## TTL 过期清理策略

### 问题背景

旧版实现仅在 `get` 方法中对目标条目做 TTL 检查。如果使用方只写不读（频繁调用 `set`/`has`/`len`/`get_stats`），过期条目会持续占用内存直到 LRU 淘汰或被显式失效，统计信息中的 `size` 也会失真。

### 惰性清理机制

引入统一的 `_cleanup_expired()` 方法作为内部清理入口，并在以下所有公共方法中**首先调用**：

| 触发方法 | 说明 |
|---------|------|
| `get` | 查询前清理所有过期条目 |
| `set` | 写入前清理所有过期条目 |
| `has` | 检查前清理所有过期条目 |
| `get_entry` | 获取条目前清理 |
| `invalidate_by_entity` | 失效前清理 |
| `invalidate_by_entities` | 失效前清理 |
| `invalidate_by_pattern` | 失效前清理 |
| `get_stats` | 统计前清理，保证 `size` 准确 |
| `__len__` | 计数前清理 |
| `__contains__` | 包含检查前清理 |

### 清理算法

`_cleanup_expired()` 逻辑：

1. 如果 `default_ttl` 为 `None`，直接返回（无 TTL 配置时不扫描）
2. 遍历所有缓存条目，收集 `now - created_at > default_ttl` 的过期键
3. 对每个过期键调用 `_evict_internal`（清除缓存条目并注销版本依赖）
4. 统计 `ttl_cleanups` 计数 + 清理条数
5. 返回清理的条目数量

### 行为说明

- **复杂度**：O(n)，n 为当前缓存条目数。对常规容量（<10万条）可接受
- **非 TTL 模式**：不配置 `default_ttl` 时不会触发清理，零额外开销
- **统计信息**：`get_stats()["ttl_cleanups"]` 为累计 TTL 清理次数

### 示例

```python
cache = RequestSnapshotCache(default_ttl=3600)

# 写入后立即查询
cache.set({"id": 1}, "data1")
cache.set({"id": 2}, "data2")
assert len(cache) == 2

# 1 小时后...即使不调用 get
# 调用 len() 会自动触发清理
assert len(cache) == 0  # 过期条目被惰性清理

# 统计也准确
stats = cache.get_stats()
assert stats["size"] == 0
assert stats["ttl_cleanups"] >= 2
```

## 线程安全

所有公共方法都使用 `threading.RLock` 进行保护，支持在多线程环境下安全使用。

## API 参考

### RequestSnapshotCache

| 方法 | 说明 |
|-----|-----|
| `get(request_params, data_entities=None)` | 获取缓存结果（触发 TTL 清理） |
| `get_or_compute(request_params, compute_func, data_entities=None)` | 获取或计算缓存（含版本竞态防护） |
| `set(request_params, result, data_entities=None, ttl=None)` | 设置缓存（触发 TTL 清理） |
| `has(request_params, data_entities=None)` | 检查缓存是否存在且有效（触发 TTL 清理） |
| `invalidate_by_entity(entity_name)` | 按实体失效缓存（触发 TTL 清理） |
| `invalidate_by_entities(entity_names)` | 按多个实体失效缓存（触发 TTL 清理） |
| `invalidate_all()` | 失效所有缓存 |
| `invalidate_by_pattern(pattern_func)` | 按条件失效缓存（递增受影响实体版本，触发 TTL 清理） |
| `bump_entity_version(entity_name)` | 递增实体版本号 |
| `get_entity_version(entity_name)` | 获取实体版本号 |
| `get_stats()` | 获取统计信息（触发 TTL 清理） |
| `reset_stats()` | 重置统计信息 |
| `clear()` | 清空所有缓存 |

### get_stats() 统计字段

| 字段 | 说明 |
|-----|------|
| `hits` | 缓存命中次数 |
| `misses` | 缓存未命中次数 |
| `sets` | 缓存写入次数 |
| `evictions` | LRU 淘汰次数 |
| `invalidations` | 总失效次数（含实体失效、模式失效、全部失效） |
| `ttl_cleanups` | TTL 惰性清理累计清理条目数 |
| `version_race_detected` | `get_or_compute` 版本竞态检测次数 |
| `size` | 当前有效缓存条目数（清理后） |
| `max_size` | 配置的最大缓存容量 |
| `default_ttl` | 配置的默认 TTL 秒数 |

### CacheKeyGenerator

| 方法 | 说明 |
|-----|-----|
| `generate(request_params, data_entities=None)` | 生成缓存键 |
| `generate_raw(data)` | 对任意数据生成键 |

### VersionManager

| 方法 | 说明 |
|-----|-----|
| `get_entity_version(entity_name)` | 获取实体版本 |
| `bump_entity_version(entity_name)` | 递增实体版本 |
| `register_cache_dependency(cache_key, entity_names)` | 注册缓存依赖 |
| `unregister_cache(cache_key)` | 注销缓存 |
| `get_invalidated_caches(entity_names)` | 获取受影响的缓存键 |
| `invalidate_entity(entity_name)` | 失效实体相关缓存 |
| `get_version_signature(entity_names)` | 获取版本签名字符串 |
