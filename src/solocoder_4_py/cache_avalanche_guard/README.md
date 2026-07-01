# 缓存雪崩防护模块 (CacheAvalancheGuard)

使用纯内存数据结构模拟缓存读写和热点键重建，提供完整的缓存雪崩防护能力。

## 模块功能

本模块为内存缓存系统提供四层雪崩防护机制：

1. **过期时间随机抖动** - 避免大量缓存键在同一时间点集体过期
2. **热点键后台续期** - 自动识别高频访问的热点键，在后台提前续期防止过期
3. **单飞重建锁 (Single Flight)** - 缓存未命中时，确保只有一个调用方执行数据重建，避免重复加载
4. **降级占位值** - 数据重建失败或缓存不可用时，返回预设的降级值，防止请求穿透到后端

## 雪崩防护策略

### 1. 过期时间抖动 (Expiry Jitter)

**问题场景**：大量缓存键设置了相同的 TTL，在同一时刻集体过期，导致所有请求同时穿透到后端数据库，引发雪崩效应。

**防护策略**：
- 为每个缓存键的过期时间添加随机抖动（±jitter_ratio × TTL）
- 抖动比例范围：0 ~ 0.5（自动限制最大值）
- 抖动后的过期时间保证至少为当前时间 +0.001 秒
- 使用单一时间戳计算，避免高并发场景下的时间偏差问题

**配置参数**：
- `jitter_ratio`：抖动比例，默认 0.1（±10%）
- `default_ttl`：默认 TTL，默认 300 秒

### 2. 热点键检测与后台续期 (Hot Key Detection & Background Renewal)

**问题场景**：某些高频访问的"热点键"过期时，瞬间大量请求涌入后端，导致系统过载。

**防护策略**：
- 持续追踪每个键在滑动时间窗口内的访问频率
- 当访问频率超过阈值时，标记为"热点键"
- 后台线程定期检查热点键，当剩余 TTL 低于条目自身 TTL 的 30% 时自动续期
- 续期时同样应用过期时间抖动

**配置参数**：
- `hot_key_threshold`：热点键判定阈值（窗口内命中次数），默认 10
- `hot_key_window_seconds`：热点检测时间窗口（秒），默认 60
- `background_renew_interval_seconds`：后台续期检查间隔（秒），默认 60
- `enable_background_renew`：是否启用后台续期，默认 True

### 3. 单飞重建锁与重建策略 (Single Flight Rebuild & RebuildStrategy)

**问题场景**：缓存未命中时，多个并发请求同时调用数据加载函数，导致后端压力倍增。

**防护策略**：
- 当第一个请求发现缓存未命中时，获取该键的重建锁
- 其他请求进入等待状态，监听重建完成事件
- 重建完成后，所有等待的请求共享重建结果
- 等待超时后返回降级值或 None

**配置参数**：
- `rebuild_timeout_seconds`：重建超时时间（秒），默认 5

**重建策略（RebuildStrategy）**：

本模块提供两种重建策略，可在调用 `get()` 时通过 `rebuild_strategy` 参数指定：

**SYNC（同步策略，默认）**：
- 调用方阻塞等待，直至重建完成或超时
- 重建成功返回真实数据，超时返回降级值
- 适用于对数据一致性要求高、重建耗时短的场景

```python
from solocoder_4_py.cache_avalanche_guard import RebuildStrategy

result = guard.get(
    "key",
    loader=lambda: load_data(),
    degraded_value="fallback",
    rebuild_strategy=RebuildStrategy.SYNC,  # 默认值，可省略
)
```

**ASYNC（异步策略）**：
- 调用方立即返回降级值，不等待重建完成
- 重建工作由后台守护线程异步执行
- 重建成功后自动更新缓存，后续请求获得真实数据
- 适用于重建耗时较长、调用方对延迟敏感的场景
- **注意**：使用 ASYNC 策略时建议始终提供 `degraded_value`，未提供时返回 `None` 作为占位

```python
from solocoder_4_py.cache_avalanche_guard import RebuildStrategy

result = guard.get(
    "slow_loading_data",
    loader=lambda: expensive_database_query(),  # 可能耗时 30 秒
    degraded_value={"status": "loading", "data": None},
    rebuild_strategy=RebuildStrategy.ASYNC,
)
print(result)  # 立即返回 {"status": "loading", "data": None}
```

**状态流转**：
```
VALID (有效)
   ↓ (过期/未命中)
REBUILDING (重建中)
   ↓ (成功)        ↓ (失败)
VALID (更新)    DEGRADED (降级)
```

### 4. 降级占位值 (Degraded Value)

**问题场景**：数据加载函数执行失败（如数据库宕机、网络超时），导致请求失败并可能引发级联故障。

**防护策略**：
- 重建失败时，如果提供了 `degraded_value`，将缓存状态标记为 DEGRADED
- 后续请求直接返回降级值，避免重复尝试失败的加载
- 降级值有独立的 TTL，过期后可再次尝试重建
- 未提供降级值时，抛出 `CacheRebuildError` 异常

**配置参数**：
- `degraded_ttl_seconds`：降级值 TTL（秒），默认 10

## 降级行为

### 降级触发条件

1. **缓存未命中 + 无 loader**：返回 `degraded_value`（如果提供）或 None
2. **重建超时**：等待重建超过 `rebuild_timeout_seconds`，返回降级值并自动持久化
3. **重建异常**：loader 函数抛出异常，返回降级值并自动持久化
4. **缓存已降级**：直接返回降级值
5. **ASYNC 策略**：立即返回 `degraded_value`（若提供）并触发后台重建，同时持久化降级值

### 降级持久化机制

除了显式的"重建异常"场景，以下路径同样会自动将降级值写入缓存并标记为 `DEGRADED` 状态：

- **非重建方等待超时**：当请求方不是重建锁持有者，等待重建超过 `rebuild_timeout_seconds` 后，`degraded_value` 会被写入缓存并设置独立 TTL
- **ASYNC 策略触发**：使用 `RebuildStrategy.ASYNC` 时，返回给调用方的降级值会被同时写入缓存
- **降级值的独立 TTL**：所有持久化的降级值均使用 `degraded_ttl_seconds` 作为过期时间（默认 10 秒）

**持久化后的效果**：后续对同一键的请求即使不再传入 `degraded_value` 参数，也能从缓存中读取到降级值并获得保护，直至降级值 TTL 过期后触发下一次重建尝试。

### 降级恢复

当缓存处于 DEGRADED 状态时：
- 降级值过期后，下一次请求将触发新的重建尝试
- 重建成功后，缓存恢复为 VALID 状态
- 可通过 `invalidate()` 主动触发重建

## 核心 API

### CacheAvalancheGuard

#### 构造函数

```python
CacheAvalancheGuard(
    max_size: Optional[int] = 10000,           # 缓存最大容量
    default_ttl: float = 300,                  # 默认 TTL（秒）
    jitter_ratio: float = 0.1,                 # 过期抖动比例
    hot_key_threshold: int = 10,               # 热点键阈值
    hot_key_window_seconds: int = 60,          # 热点检测窗口
    rebuild_timeout_seconds: float = 5,        # 重建超时
    background_renew_interval_seconds: float = 60,  # 后台续期间隔
    degraded_ttl_seconds: float = 10,          # 降级值 TTL
    enable_background_renew: bool = True,      # 启用后台续期
)
```

#### 主要方法

```python
# 获取缓存，支持读穿透和降级
get(
    key: str,
    loader: Optional[Callable[[], T]] = None,
    degraded_value: Optional[Any] = None,
    tags: Optional[Iterable[str]] = None,
    ttl: Optional[float] = None,
    rebuild_strategy: RebuildStrategy = RebuildStrategy.SYNC,
) -> Optional[T]

# 带强制 loader 的获取
get_or_load(key: str, loader: Callable[[], T], **kwargs) -> T

# 设置缓存
set(key: str, value: Any, tags: Optional[Iterable[str]] = None, ttl: Optional[float] = None) -> CacheEntry

# 失效操作
invalidate(key: str) -> bool
invalidate_by_tag(tag: str) -> int
invalidate_by_tags(tags: Iterable[str]) -> int
invalidate_all() -> int
invalidate_expired() -> int

# 查询
has(key: str) -> bool
keys() -> List[str]
get_entry(key: str) -> Optional[CacheEntry]
size() -> int
get_hot_keys() -> List[str]

# 统计
get_stats() -> CacheGuardStats
reset_stats() -> None

# 生命周期
stop() -> None  # 停止后台线程
```

## 使用示例

### 基础使用

```python
from solocoder_4_py.cache_avalanche_guard import CacheAvalancheGuard

# 创建缓存实例
guard = CacheAvalancheGuard(
    max_size=10000,
    default_ttl=300,
    jitter_ratio=0.1,
)

# 写入缓存
guard.set("user:1", {"id": 1, "name": "Alice"}, tags=["users"])

# 读取缓存
user = guard.get("user:1")
if user:
    print(user["name"])
```

### 读穿透 + 降级

```python
def load_user_from_db(user_id: int):
    """从数据库加载用户数据"""
    # 模拟数据库查询
    print(f"Loading user {user_id} from DB")
    return {"id": user_id, "name": f"User{user_id}"}

# 缓存未命中时自动调用 loader，失败时返回降级值
user = guard.get(
    "user:1",
    loader=lambda: load_user_from_db(1),
    degraded_value={"id": 1, "name": "Guest"},  # 降级占位值
    tags=["users"],
)
```

### 热点键保护

```python
# 配置热点检测
guard = CacheAvalancheGuard(
    hot_key_threshold=20,           # 60秒内访问20次判定为热点
    hot_key_window_seconds=60,
    enable_background_renew=True,
)

# 模拟热点访问
for _ in range(30):
    guard.get(
        "product:bestseller",
        loader=lambda: load_product("bestseller"),
        degraded_value={"id": "bestseller", "price": 99},
    )

# 查看当前热点键
hot_keys = guard.get_hot_keys()
print(f"Hot keys: {hot_keys}")  # ['product:bestseller']
```

### 高并发场景

```python
import threading

guard = CacheAvalancheGuard(
    rebuild_timeout_seconds=10,
    jitter_ratio=0.2,
)

call_count = [0]

def slow_loader():
    call_count[0] += 1
    time.sleep(0.5)  # 模拟慢查询
    return {"data": "important"}

# 100个并发请求，只有第一个会实际调用 loader
results = []
def worker():
    result = guard.get(
        "critical_data",
        loader=slow_loader,
        degraded_value={"data": "fallback"},
    )
    results.append(result)

threads = [threading.Thread(target=worker) for _ in range(100)]
for t in threads:
    t.start()
for t in threads:
    t.join()

print(f"Loader called: {call_count[0]} times")  # 仅 1 次
print(f"All got results: {len(results) == 100}")  # True
```

### 异步重建策略 (ASYNC)

```python
from solocoder_4_py.cache_avalanche_guard import RebuildStrategy

# 使用 ASYNC 策略，调用方无需等待重建完成
result = guard.get(
    "slow_loading_data",
    loader=lambda: expensive_database_query(),
    degraded_value={"status": "loading", "data": None},
    rebuild_strategy=RebuildStrategy.ASYNC,
)

# 立即返回降级值，后台异步执行重建
print(result)  # {"status": "loading", "data": None}

# 稍等片刻，后台重建完成
time.sleep(1)

# 后续请求获取到真实数据
result_after = guard.get("slow_loading_data")
print(result_after)  # 真实数据

# 结合自定义 TTL
result = guard.get(
    "short_ttl_data",
    loader=lambda: fast_query(),
    degraded_value="loading",
    ttl=60,  # 60秒 TTL，续期时也会继承此 TTL
    rebuild_strategy=RebuildStrategy.ASYNC,
)
```

### 降级值持久化

```python
# 首次请求传入降级值
result1 = guard.get(
    "failing_key",
    loader=lambda: failing_query(),  # 抛出异常
    degraded_value="safe_fallback",
)
print(result1)  # "safe_fallback"

# 后续请求即使不传入 degraded_value 也能获得降级保护
result2 = guard.get("failing_key")
print(result2)  # "safe_fallback"

# 超时场景同样会持久化降级值
guard2 = CacheAvalancheGuard(rebuild_timeout_seconds=0.1)
result3 = guard2.get(
    "slow_key",
    loader=lambda: slow_query(seconds=10),  # 超时
    degraded_value="timeout_fallback",
)
print(result3)  # "timeout_fallback"

# 后续请求无需传入 degraded_value
result4 = guard2.get("slow_key")
print(result4)  # "timeout_fallback"
```

### 按标签批量失效

```python
# 写入时添加标签
guard.set("user:1", {...}, tags=["users", "vip"])
guard.set("user:2", {...}, tags=["users"])
guard.set("order:1", {...}, tags=["orders"])

# 用户信息更新时，批量失效所有用户缓存
count = guard.invalidate_by_tag("users")
print(f"Invalidated {count} entries")  # 2
```

### 监控统计

```python
stats = guard.get_stats()
print(f"Hit rate: {stats.hit_rate:.2%}")
print(f"Rebuilds: {stats.rebuilds}")
print(f"Rebuild failures: {stats.rebuild_failures}")
print(f"Degraded returns: {stats.degraded_returns}")
print(f"Hot key hits: {stats.hot_key_hits}")
print(f"Background renews: {stats.background_renews}")
print(f"Evictions: {stats.evictions}")
```

## 异常处理

### CacheRebuildError

当 `loader` 执行失败且未提供 `degraded_value` 时抛出：

```python
from solocoder_4_py.cache_avalanche_guard import CacheRebuildError

try:
    guard.get("key", loader=flaky_loader)
except CacheRebuildError as e:
    print(f"Rebuild failed for key {e.key}: {e.original_error}")
```

## 最佳实践

1. **合理设置抖动比例**：根据业务场景设置 0.05~0.2 的抖动比例，避免过期时间过于分散
2. **热点键阈值调优**：通过监控数据调整 `hot_key_threshold`，避免误判
3. **降级值设计**：降级值应满足基本可用性，同时明确标识为降级状态
4. **资源清理**：程序退出前调用 `stop()` 方法停止后台线程
5. **监控告警**：关注 `rebuild_failures` 和 `degraded_returns` 指标，及时发现后端故障

## 模块文件结构

```
cache_avalanche_guard/
├── __init__.py              # 模块导出
├── constants.py             # 常量和枚举定义
├── exceptions.py            # 异常类定义
├── cache_entry.py           # 缓存条目数据类
├── cache_avalanche_guard.py # 核心实现类
└── README.md               # 本文档
```
