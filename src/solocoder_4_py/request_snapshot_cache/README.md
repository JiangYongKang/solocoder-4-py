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

缓存键基于以下组件计算：

1. **request_params**：请求参数字典
   - 字典按键名排序后进行序列化
   - 支持嵌套字典、列表、元组、集合等复杂结构
   - 集合会先排序再序列化，确保相同元素的集合生成相同键

2. **data_entities**：关联的数据实体名称列表
   - 列表会先排序再序列化
   - 相同实体集合（不考虑顺序）生成相同键

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

## 线程安全

所有公共方法都使用 `threading.RLock` 进行保护，支持在多线程环境下安全使用。

## API 参考

### RequestSnapshotCache

| 方法 | 说明 |
|-----|-----|
| `get(request_params, data_entities=None)` | 获取缓存结果 |
| `get_or_compute(request_params, compute_func, data_entities=None)` | 获取或计算缓存 |
| `set(request_params, result, data_entities=None, ttl=None)` | 设置缓存 |
| `has(request_params, data_entities=None)` | 检查缓存是否存在且有效 |
| `invalidate_by_entity(entity_name)` | 按实体失效缓存 |
| `invalidate_by_entities(entity_names)` | 按多个实体失效缓存 |
| `invalidate_all()` | 失效所有缓存 |
| `invalidate_by_pattern(pattern_func)` | 按条件失效缓存 |
| `bump_entity_version(entity_name)` | 递增实体版本号 |
| `get_entity_version(entity_name)` | 获取实体版本号 |
| `get_stats()` | 获取统计信息 |
| `reset_stats()` | 重置统计信息 |
| `clear()` | 清空所有缓存 |

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
