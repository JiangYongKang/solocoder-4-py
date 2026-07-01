# Layered Cache 分层缓存模块

分层缓存（Layered Cache）功能模块，使用内存数据结构实现本地缓存和共享缓存两级缓存，支持读穿透、写后失效、标签批量失效以及完整的命中率统计。

## 功能特性

- **两级缓存架构**：L1 本地缓存（容量小、速度快） + L2 共享缓存（容量大、模拟分布式/跨进程）
- **读穿透（Read-Through）**：自动按 L1 → L2 → 数据源 顺序查找，未命中时自动回填上层缓存
- **写后失效（Invalidate-on-Write）**：写入数据后按 key 或 tag 精准让相关缓存失效
- **标签（Tag）批量失效**：支持为缓存条目关联多个标签，基于标签实现批量失效
- **LRU 淘汰**：每层缓存支持独立配置最大容量，超出时自动淘汰最久未使用条目
- **TTL 过期**：每层缓存支持独立配置默认过期时间，也支持 per-key 自定义 TTL
- **命中率统计**：分层统计访问次数、命中次数、命中率、失效次数、淘汰次数等
- **线程安全**：所有操作均使用 `threading.RLock` 保护，支持多线程并发
- **共享缓存复用**：多个 `LayeredCache` 实例可共享同一个共享缓存后端

## 模块结构

```
layered_cache/
├── __init__.py          # 模块导出
├── constants.py         # 枚举和常量（缓存层级、条目状态等）
├── exceptions.py        # 模块异常类
├── cache_entry.py       # 缓存条目数据类
├── layered_cache.py     # 核心：单层缓存、分层缓存、统计类
└── README.md            # 本文档
```

## 缓存层级

### 架构图

```
          ┌──────────────────────────┐
          │       LayeredCache       │
          └────────────┬─────────────┘
                       │
          ┌────────────▼─────────────┐
          │    L1 本地缓存 (LOCAL)    │  内存 dict + LRU + TTL
          │  (速度快，容量小，独立)   │
          └────────────┬─────────────┘
                       │ 未命中
          ┌────────────▼─────────────┐
          │   L2 共享缓存 (SHARED)    │  内存 dict + LRU + TTL
          │  (容量大，可多实例共享)   │  ─── 可跨 LayeredCache 共享 ───
          └────────────┬─────────────┘
                       │ 未命中
          ┌────────────▼─────────────┐
          │      数据源 (SOURCE)     │  用户提供 loader 函数
          │    (DB / API / FS ...)   │
          └──────────────────────────┘
```

### 各级说明

| 层级 | 说明 | 默认容量 | 默认 TTL | 典型用途 |
|------|------|---------|----------|---------|
| L1 本地 | 进程内内存，速度极快 | 1000 条 | 300s | 单次请求内热点数据复用 |
| L2 共享 | 进程内/可跨实例共享 | 10000 条 | 600s | 多请求/多客户端共享缓存 |
| 数据源 | 用户 loader 函数 | - | - | 数据库、外部 API 等 |

## 读穿透流程

调用 `cache.get(key, loader=...)` 时的处理流程：

1. **查询 L1 本地缓存**
   - 命中 → 直接返回值
   - 未命中 → 继续

2. **查询 L2 共享缓存**
   - 命中 → 将值回填到 L1（继承标签，**使用共享条目的剩余存活时间作为回填 TTL**），然后返回
   - 未命中 → 继续

3. **调用数据源 loader 函数**
   - 成功 → 将值同时写入 L2 和 L1（带标签、TTL），然后返回
   - 失败 → 抛出 `CacheLoaderError`（不污染缓存）
   - 返回 None → 不缓存，直接返回 None

```python
def get(key, loader=None, tags=None, ttl=None):
    # L1
    v = local.get(key)
    if v is not None: return v

    # L2
    v = shared.get(key)
    if v is not None:
        local.set(key, v, tags=v.tags)
        return v

    # SOURCE
    if loader is None: return None
    loaded = loader()
    shared.set(key, loaded, tags=tags, ttl=ttl)
    local.set(key, loaded, tags=tags, ttl=ttl)
    return loaded
```

## 失效规则

### 1. 按 Key 失效

直接失效指定缓存键在所有层级中的条目：

```python
cache.invalidate("user:123")
# 返回 {"local": True/False, "shared": True/False}
```

### 2. 按标签（Tag）批量失效

为缓存条目打上一个或多个标签，后续可以按标签实现精准批量失效：

```python
# 设置时绑定标签
cache.set("user:1", user_data, tags=["users", "admins"])
cache.set("user:2", user_data, tags=["users"])
cache.set("order:1", order_data, tags=["orders", "users"])

# 让所有依赖 users 实体的缓存全部失效
cache.invalidate_by_tag("users")  # 会失效 user:1、user:2、order:1

# 也可以一次按多个标签失效
cache.invalidate_by_tags(["users", "orders"])
```

### 3. 分层单独失效

```python
# 仅失效本地缓存
cache.invalidate_local("key")
cache.invalidate_all_local()

# 仅失效共享缓存
cache.invalidate_shared("key")
cache.invalidate_all_shared()

# 失效所有层级所有缓存
cache.invalidate_all()
```

### 4. 过期失效

```python
# 手动清理所有过期条目
cache.invalidate_expired()
```

### 5. LRU 淘汰（自动）

当某层缓存条目数达到 `max_size` 上限时，自动淘汰最久未访问的条目。

## 使用示例

### 基础使用

```python
from solocoder_4_py.layered_cache import LayeredCache

# 创建分层缓存（使用默认配置）
cache = LayeredCache()

# 读穿透：如果缓存中没有，会调用 loader
def load_user_from_db(user_id):
    print(f"加载用户 {user_id} 从数据库...")
    return {"id": user_id, "name": f"User{user_id}"}

# 第一次调用：执行 loader，回填 L1 和 L2
user1 = cache.get(
    "user:1",
    loader=lambda: load_user_from_db(1),
    tags=["users"],
    ttl=600,
)  # 输出: 加载用户 1 从数据库...

# 第二次调用：直接从 L1 返回，不执行 loader
user1_again = cache.get("user:1", loader=lambda: load_user_from_db(1))
# 无输出

# 用户数据更新后，让相关缓存失效
cache.invalidate_by_tag("users")

# 下次查询会重新调用 loader
user1_refreshed = cache.get("user:1", loader=lambda: load_user_from_db(1))
# 输出: 加载用户 1 从数据库...
```

### 自定义缓存配置

```python
# 自定义每层容量和 TTL
cache = LayeredCache(
    local_max_size=500,      # L1 最多 500 条
    shared_max_size=5000,    # L2 最多 5000 条
    local_ttl=60,            # L1 默认 60s 过期
    shared_ttl=1800,         # L2 默认 30min 过期
)
```

### 自定义 per-key TTL

```python
# 为单个 key 指定更短/更长的过期时间
cache.set("token:abc", token_value, ttl=60)          # 统一 TTL
cache.set("config", config_value, local_ttl=300, shared_ttl=86400)  # 分层 TTL

# 读穿透时也可以指定
cache.get("slow_query", loader=run_slow_query, ttl=3600)
```

### 多客户端共享 L2 缓存

模拟多个应用实例共享同一个分布式缓存：

```python
from solocoder_4_py.layered_cache import LayeredCache, SingleLevelCache

# 创建全局共享的 L2 缓存（例如在 Redis/MC 场景中就是外部缓存）
global_shared_cache = SingleLevelCache(max_size=50000, default_ttl=None)

# 多个客户端实例（如多个进程、多个服务实例）
client_a = LayeredCache(shared_cache_instance=global_shared_cache)
client_b = LayeredCache(shared_cache_instance=global_shared_cache)

# Client A 写入共享缓存
client_a.set("global:config", config, write_local=False, write_shared=True)

# Client B 读取，L1 未命中但 L2 命中，自动回填 Client B 的 L1
value = client_b.get("global:config")
```

### 写后失效（推荐模式）

```python
# 写入数据库后调用失效，保证后续读取到新数据
def update_user(user_id, new_data):
    db.update(f"UPDATE users SET ... WHERE id = {user_id}")
    # 方式 1：按 key 失效
    cache.invalidate(f"user:{user_id}")
    # 方式 2：按标签失效（影响更大范围）
    cache.invalidate_by_tag("users")
```

### 查看统计信息

```python
stats = cache.get_stats()

# overall 汇总
print(f"总访问次数: {stats['overall']['accesses']}")
print(f"总命中次数: {stats['overall']['hits']}")
print(f"总命中率:   {stats['overall']['hit_rate']:.2%}")
print(f"Loader 调用: {stats['overall']['loader_calls']}")
print(f"失效次数:    {stats['overall']['invalidations']}")

# 分层统计
print(f"L1 命中率: {stats['local']['hit_rate']:.2%}")
print(f"L2 命中率: {stats['shared']['hit_rate']:.2%}")

# 每层条目数
print(f"L1 条目数: {stats['sizes']['local']}")
print(f"L2 条目数: {stats['sizes']['shared']}")

# 重置统计
cache.reset_stats()
```

### 单独操作各层

```python
# 仅写入 L1（不希望其他客户端看到）
cache.set_local("temp:request_id", value, ttl=30)

# 仅写入 L2（本请求可能不会立即读）
cache.set_shared("daily:report", report_data, tags=["reports"])

# 单独查询（不触发穿透，不回填）
local_val = cache.get_local("key")
shared_val = cache.get_shared("key")

# 查询命中的层级
value, level = cache.get_with_level("key")
if level == CacheLevel.LOCAL:
    print("命中本地缓存")
elif level == CacheLevel.SHARED:
    print("命中共享缓存")
else:
    print("未命中任何缓存")
```

## API 参考

### LayeredCache 主要方法

| 方法 | 说明 |
|------|------|
| `get(key, loader=None, tags=None, ttl=None, local_ttl=None, shared_ttl=None)` | 分层读穿透获取 |
| `get_or_load(key, loader, tags=None, **kwargs)` | 强制带 loader 的 get |
| `get_local(key)` | 仅查 L1 |
| `get_shared(key)` | 仅查 L2 |
| `get_with_level(key)` | 获取值并返回命中层级 |
| `set(key, value, tags=None, ttl=None, local_ttl=None, shared_ttl=None, write_local=True, write_shared=True)` | 主动写入缓存 |
| `set_local(key, value, tags=None, ttl=None)` | 仅写入 L1 |
| `set_shared(key, value, tags=None, ttl=None)` | 仅写入 L2 |
| `invalidate(key)` | 按 key 失效所有层 |
| `invalidate_by_tag(tag)` | 按标签失效所有层 |
| `invalidate_by_tags(tags)` | 按多标签失效 |
| `invalidate_local(key)` | 仅失效 L1 的 key |
| `invalidate_shared(key)` | 仅失效 L2 的 key |
| `invalidate_all_local()` | 清空 L1 |
| `invalidate_all_shared()` | 清空 L2 |
| `invalidate_all()` | 清空所有层 |
| `invalidate_expired()` | 清理所有过期条目 |
| `has(key)` | 任意层存在有效缓存 |
| `has_local(key)` / `has_shared(key)` | 单层存在性检查 |
| `get_stats()` | 获取完整统计信息 |
| `reset_stats()` | 重置所有统计 |

### SingleLevelCache 主要方法

| 方法 | 说明 |
|------|------|
| `get(key)` / `get_value(key)` | 获取条目/值 |
| `set(key, value, tags=None, ttl=None)` | 设置缓存 |
| `has(key)` | 存在性检查 |
| `invalidate(key)` | 按 key 失效 |
| `invalidate_by_tag(tag)` | 按标签失效 |
| `invalidate_all()` | 清空全部 |
| `invalidate_expired()` | 清理过期 |
| `get_stats()` / `reset_stats()` | 统计相关 |
| `keys()` | 返回所有有效 key |
| `size()` | 条目数量 |

### 枚举和异常

| 名称 | 说明 |
|------|------|
| `CacheLevel.LOCAL / SHARED / SOURCE` | 缓存层级枚举 |
| `CacheEntryStatus.VALID / EXPIRED / INVALIDATED` | 条目状态枚举 |
| `LayeredCacheError` | 模块基础异常 |
| `CacheLoaderError` | loader 函数执行异常（含 key 和原始异常） |
| `InvalidationError` | 失效操作异常 |
