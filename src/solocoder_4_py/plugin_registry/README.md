# Plugin Registry 插件注册中心模块

插件注册中心（Plugin Registry）功能模块，使用内存数据结构管理插件信息和运行状态，支持插件元数据声明、按能力发现、启用停用控制以及版本兼容性校验。

## 功能特性

- **插件元数据管理**：支持声明插件的基本信息、版本、能力、依赖和标签
- **语义化版本支持**：完整的语义化版本（SemVer）解析、比较和兼容性校验
- **版本要求表达式**：支持 `>=`、`<=`、`~`、`^` 等多种版本约束语法，以及逗号分隔的多约束组合
- **依赖校验**：启用插件前自动校验所有依赖插件已注册、已启用且版本满足要求
- **插件生命周期管理**：支持注册、注销、启用、停用等状态切换
- **统一状态入口**：`set_status()` 作为状态转变的统一入口，委托给 `enable()`/`disable()` 确保校验一致
- **按能力发现**：支持按单个能力、多个能力（全部匹配/任意匹配）发现插件
- **按标签筛选**：支持按标签组合筛选插件
- **状态查询**：支持查询插件运行状态、启用次数、时间戳等信息
- **版本校验启用**：支持在启用插件前自动校验版本和能力要求
- **精确异常契约**：批量操作仅捕获业务预期内的 `PluginStateError`，系统级异常直接传播
- **索引加速**：能力和标签自动建索引，查询效率高
- **线程安全**：所有操作均使用 `threading.RLock` 保护，支持多线程并发
- **统计信息**：提供插件总数、各状态数量、能力总数等统计数据

## 模块结构

```
plugin_registry/
├── __init__.py              # 模块导出
├── constants.py             # 枚举和常量（插件状态等）
├── exceptions.py            # 模块异常类
├── plugin_metadata.py       # 插件元数据、运行时信息数据类
├── plugin_registry.py       # 核心：插件注册中心、统计类
└── README.md                # 本文档
```

## 插件元数据

### PluginMetadata 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `plugin_id` | `str` | 是 | 插件唯一标识符，推荐使用反向域名风格 |
| `name` | `str` | 是 | 插件显示名称 |
| `version` | `str` | 否 | 版本号，语义化格式，默认 `0.1.0` |
| `description` | `str` | 否 | 插件描述 |
| `author` | `str` | 否 | 作者信息 |
| `capabilities` | `List[str]` | 否 | 能力列表，用于按能力发现 |
| `dependencies` | `Dict[str, str]` | 否 | 依赖的其他插件及版本要求 |
| `tags` | `List[str]` | 否 | 标签列表，用于分类筛选 |
| `extra` | `Dict[str, Any]` | 否 | 扩展字段，存储自定义信息 |

### 版本号格式

遵循 [语义化版本 2.0.0](https://semver.org/lang/zh-CN/) 规范：

```
MAJOR.MINOR.PATCH[-PRE_RELEASE][+BUILD_METADATA]
```

示例：
- `1.0.0` - 正式版本
- `1.0.0-alpha` - 预览版本
- `1.0.0-beta.1` - 测试版本
- `1.0.0+build.123` - 带构建元数据
- `2.10.3-rc.1+sha.5114f85` - 完整格式

### 版本要求表达式

支持以下版本约束语法：

| 表达式 | 说明 | 示例 | 匹配版本 |
|--------|------|------|---------|
| `==` | 精确等于 | `==1.2.3` | 1.2.3 |
| `!=` | 不等于 | `!=1.2.3` | 除 1.2.3 外 |
| `>` | 大于 | `>1.2.3` | 1.2.4, 1.3.0, 2.0.0 |
| `>=` | 大于等于 | `>=1.2.3` | 1.2.3, 1.2.4, 2.0.0 |
| `<` | 小于 | `<1.2.3` | 1.2.2, 1.1.0 |
| `<=` | 小于等于 | `<=1.2.3` | 1.2.3, 1.2.2 |
| `~` | 波浪符范围 | `~1.2.3` | >=1.2.3, <1.3.0 |
| `^` | 脱字符范围 | `^1.2.3` | >=1.2.3, <2.0.0 |
| 无操作符 | 精确等于 | `1.2.3` | 同 `==1.2.3` |

**波浪符（~）说明**：锁定主版本和次版本，允许补丁版本更新
- `~1.2.3` → `>=1.2.3, <1.3.0`
- `~1.2` → `>=1.2.0, <1.3.0`

**脱字符（^）说明**：锁定最左侧非零版本号，允许兼容更新
- `^1.2.3` → `>=1.2.3, <2.0.0`
- `^0.2.3` → `>=0.2.3, <0.3.0`
- `^0.0.3` → `>=0.0.3, <0.0.4`

## 插件状态

| 状态 | 说明 |
|------|------|
| `REGISTERED` | 已注册但未启用 |
| `ENABLED` | 已启用，可以正常使用 |
| `DISABLED` | 已停用，暂时不可用 |

状态流转：
```
REGISTERED → ENABLED → DISABLED → ENABLED → ...
     ↓           ↓           ↓
  (注销)      (注销)      (注销)
```

## 依赖校验机制

插件启用时会自动执行依赖校验，确保插件的所有依赖都满足要求。校验顺序和规则如下：

### 校验顺序
1. **插件自身版本校验**：如果指定了 `required_version`，先校验插件自身版本
2. **依赖存在性校验**：检查每个依赖插件是否已注册
3. **依赖状态校验**：检查每个依赖插件是否已启用（状态为 `ENABLED`）
4. **依赖版本校验**：检查每个依赖插件的版本是否满足版本要求

### 校验失败场景
- **依赖未注册**：抛出 `PluginDependencyError`，reason 为 "依赖插件未注册"
- **依赖未启用**：抛出 `PluginDependencyError`，reason 包含当前状态，如 "依赖插件未启用（当前状态: REGISTERED）"
- **依赖版本不匹配**：抛出 `PluginDependencyError`，reason 包含当前版本和要求版本

### 依赖声明示例
```python
metadata = PluginMetadata(
    plugin_id="my_plugin",
    name="我的插件",
    version="1.0.0",
    dependencies={
        "core_framework": ">=2.0.0,<3.0.0",  # 核心框架，要求 2.x 版本
        "auth_service": "^1.5.0",            # 认证服务，兼容 1.5.x
        "cache_plugin": "~1.2.0",            # 缓存插件，兼容 1.2.x
    },
)
```

### 启用顺序注意事项
插件必须按依赖顺序启用。例如，如果插件 A 依赖插件 B，必须先启用 B 再启用 A：

```python
# 正确顺序
registry.enable("plugin_b")  # 先启用被依赖的插件
registry.enable("plugin_a")  # 再启用依赖插件

# 错误顺序 - 会抛出 PluginDependencyError
registry.enable("plugin_a")  # plugin_b 未启用，校验失败
```

## 状态转变统一入口

`set_status()` 方法是所有状态转变的统一入口，确保所有状态变更共享相同的校验逻辑和副作用。

### 统一入口设计原则
1. **单一执行路径**：所有状态转变都通过 `set_status()` 委托给对应的专用方法
2. **校验一致性**：无论通过 `enable()` 还是 `set_status(ENABLED)`，执行的校验完全相同
3. **副作用一致**：`enable_count` 计数、`enabled_at` 时间戳等副作用在所有路径下行为一致

### 委托关系
| 目标状态 | 委托方法 | 执行的校验 |
|----------|----------|------------|
| `ENABLED` | `enable(plugin_id)` | 版本校验 + 依赖校验 + 状态检查 |
| `DISABLED` | `disable(plugin_id)` | 状态检查 |
| `REGISTERED` | 直接设置 | 无额外校验 |

### 示例对比
以下两种方式完全等价：

```python
# 方式一：直接调用专用方法
runtime_info = registry.enable("my_plugin", required_version=">=1.0.0")

# 方式二：通过统一入口
runtime_info = registry.set_status("my_plugin", PluginStatus.ENABLED)
```

> **注意**：`set_status()` 调用 `enable()` 时不传递 `required_version` 参数。如果需要额外的版本约束，请直接调用 `enable(plugin_id, required_version="...")`。

## 异常处理契约

批量操作方法 `enable_all()` 和 `disable_all()` 遵循精确的异常处理契约，确保系统级故障能够被及时发现。

### 异常捕获范围
- **仅捕获**：`PluginStateError`（业务预期内的状态错误，如重复启用、重复停用）
- **直接传播**：所有其他异常，包括但不限于：
  - `PluginDependencyError` - 依赖不满足
  - `PluginVersionError` - 版本不兼容
  - `PluginNotFoundError` - 插件不存在（理论上不会发生）
  - `MemoryError`、`RuntimeError` 等系统级异常

### 设计意图
这种设计确保了：
1. **业务失败可预期**：重复启用/停用等常规业务错误被捕获并记录为 `False`
2. **系统故障可感知**：内存错误、配置错误等严重问题不会被静默吞没
3. **调试效率高**：异常栈指向真正的故障源头，而不是被包装成简单的 `False`

### 调用方处理建议
```python
try:
    results = registry.enable_all()
    for plugin_id, success in results.items():
        if not success:
            print(f"插件 {plugin_id} 已经是启用状态，跳过")
except PluginDependencyError as e:
    print(f"依赖不满足: {e.plugin_id} 需要 {e.dependency_id}，原因: {e.reason}")
    # 处理依赖问题，如按正确顺序重新启用
except PluginVersionError as e:
    print(f"版本不兼容: {e.plugin_id} 当前版本 {e.plugin_version}，要求 {e.required_version}")
    # 处理版本问题
except Exception as e:
    print(f"系统异常: {e}")
    # 告警或降级处理
```

## 能力发现

### 核心概念

- **能力（Capability）**：插件提供的功能标识，使用字符串表示
- **标签（Tag）**：插件的分类标记，用于筛选和分组
- **索引**：注册时自动为能力和标签建立反向索引，查询时 O(1) 复杂度

### 发现方式

1. **按能力查找**：`find_by_capability(capability, enabled_only=True)`
2. **按多能力查找**：`find_by_capabilities(capabilities, match_all=True, enabled_only=True)`
3. **按标签查找**：`find_by_tag(tag, enabled_only=True)`
4. **按多标签查找**：`find_by_tags(tags, match_all=True, enabled_only=True)`
5. **组合过滤**：`list_plugins(status, capability, tag)`

## 使用示例

### 基础使用

```python
from solocoder_4_py.plugin_registry import (
    PluginMetadata,
    PluginRegistry,
    PluginStatus,
)

# 创建注册中心
registry = PluginRegistry()

# 创建插件元数据
metadata = PluginMetadata(
    plugin_id="com.example.data_importer",
    name="数据导入插件",
    version="1.2.0",
    description="支持多种格式的数据导入",
    author="Example Team",
    capabilities=["data_import", "validation", "preview"],
    dependencies={"core": ">=2.0.0"},
    tags=["data", "import", "io"],
    extra={"config_path": "/etc/plugins/importer"},
)

# 注册插件
runtime_info = registry.register(metadata)
print(f"插件已注册，状态: {runtime_info.status}")  # REGISTERED

# 启用插件（可指定版本要求）
registry.enable("com.example.data_importer", required_version=">=1.0.0")
print(f"插件已启用: {registry.is_enabled('com.example.data_importer')}")  # True

# 按能力查找插件
importers = registry.find_by_capability("data_import")
for plugin in importers:
    print(f"找到导入插件: {plugin.metadata.name} ({plugin.metadata.version})")

# 停用插件
registry.disable("com.example.data_importer")

# 注销插件
registry.unregister("com.example.data_importer")
```

### 版本兼容性校验

```python
# 创建不同版本的插件
registry.register(PluginMetadata(
    plugin_id="api.v1",
    name="API v1",
    version="1.0.0",
    capabilities=["api"],
))
registry.register(PluginMetadata(
    plugin_id="api.v2",
    name="API v2",
    version="2.1.0",
    capabilities=["api"],
))
registry.enable_all()

# 检查版本兼容性
assert registry.check_plugin_version("api.v1", "^1.0.0") is True
assert registry.check_plugin_version("api.v2", "^1.0.0") is False

# 查找兼容 v1 版本的 API 插件
api_plugins = registry.find_by_capability("api")
compatible = [
    p for p in api_plugins
    if p.metadata.satisfies_version("^1.0.0")
]
print(f"兼容 v1 的 API 插件数: {len(compatible)}")  # 1
```

### 能力和标签组合查询

```python
# 注册多个插件
registry.register(PluginMetadata(
    plugin_id="csv_importer",
    name="CSV 导入器",
    capabilities=["data_import", "file_read"],
    tags=["data", "csv", "import"],
))
registry.register(PluginMetadata(
    plugin_id="json_importer",
    name="JSON 导入器",
    capabilities=["data_import", "file_read"],
    tags=["data", "json", "import"],
))
registry.register(PluginMetadata(
    plugin_id="db_exporter",
    name="数据库导出器",
    capabilities=["data_export", "db_access"],
    tags=["data", "database", "export"],
))
registry.enable_all()

# 查找具有 data_import 能力的所有插件
importers = registry.find_by_capability("data_import")
print(f"导入插件数: {len(importers)}")  # 2

# 查找同时具有 data_import 和 file_read 能力的插件
file_importers = registry.find_by_capabilities(
    ["data_import", "file_read"],
    match_all=True,
)
print(f"文件导入插件数: {len(file_importers)}")  # 2

# 查找带有 csv 标签的插件
csv_plugins = registry.find_by_tag("csv")
print(f"CSV 插件数: {len(csv_plugins)}")  # 1

# 查找同时带有 data 和 import 标签的插件
data_import_plugins = registry.find_by_tags(
    ["data", "import"],
    match_all=True,
)
print(f"数据导入标签插件数: {len(data_import_plugins)}")  # 2

# 组合条件查询
enabled_importers = registry.list_plugins(
    status=PluginStatus.ENABLED,
    capability="data_import",
    tag="data",
)
print(f"已启用的数据导入插件数: {len(enabled_importers)}")  # 2
```

### 检查并启用插件

```python
# 注册支付网关插件
registry.register(PluginMetadata(
    plugin_id="payment.stripe",
    name="Stripe 支付网关",
    version="2.1.0",
    capabilities=["payment_processing", "refund", "subscription"],
))

# 启用前校验版本和能力
try:
    runtime_info = registry.check_and_enable(
        "payment.stripe",
        required_version=">=2.0.0,<3.0.0",
        required_capabilities=["payment_processing", "refund"],
    )
    print("插件启用成功!")
except PluginVersionError as e:
    print(f"版本不兼容: {e}")
except PluginCapabilityError as e:
    print(f"缺少能力: {e.missing_capability}")
except PluginNotFoundError as e:
    print(f"插件不存在: {e}")
```

### 依赖校验示例

```python
from solocoder_4_py.plugin_registry import (
    PluginDependencyError,
)

# 注册三个插件，形成依赖链：report_exporter → data_processor → core_framework
registry.register(PluginMetadata(
    plugin_id="core_framework",
    name="核心框架",
    version="2.1.0",
))

registry.register(PluginMetadata(
    plugin_id="data_processor",
    name="数据处理器",
    version="1.5.0",
    dependencies={
        "core_framework": ">=2.0.0,<3.0.0",
    },
))

registry.register(PluginMetadata(
    plugin_id="report_exporter",
    name="报表导出器",
    version="1.0.0",
    dependencies={
        "data_processor": "^1.5.0",
        "core_framework": ">=2.0.0",
    },
))

# 错误的启用顺序 - 直接启用 report_exporter 会失败
try:
    registry.enable("report_exporter")
except PluginDependencyError as e:
    print(f"启用失败: {e.reason}")  # 依赖插件未启用

# 正确的启用顺序 - 从被依赖的插件开始
registry.enable("core_framework")
registry.enable("data_processor")
registry.enable("report_exporter")

# 检查启用结果
assert registry.is_enabled("core_framework")
assert registry.is_enabled("data_processor")
assert registry.is_enabled("report_exporter")

# 版本不匹配的情况
registry.register(PluginMetadata(
    plugin_id="old_plugin",
    name="旧版本插件",
    version="0.8.0",
    dependencies={
        "core_framework": ">=3.0.0",  # 要求 3.0+，但实际是 2.1.0
    },
))
registry.enable("old_plugin")  # 会抛出 PluginDependencyError，版本不满足
```

### 状态统一入口示例

```python
# 注册插件
registry.register(PluginMetadata(
    plugin_id="my_service",
    name="我的服务",
    version="1.0.0",
    dependencies={"core_framework": ">=2.0.0"},
))

# set_status 作为统一入口，与直接调用 enable/disable 行为完全一致

# 启用插件 - set_status 会委托给 enable()，执行完整的依赖校验
try:
    registry.set_status("my_service", PluginStatus.ENABLED)
except PluginDependencyError:
    # 依赖不满足，先启用依赖
    registry.register(PluginMetadata(
        plugin_id="core_framework",
        name="核心框架",
        version="2.1.0",
    ))
    registry.enable("core_framework")
    # 现在可以成功启用
    runtime_info = registry.set_status("my_service", PluginStatus.ENABLED)
    assert runtime_info.status == PluginStatus.ENABLED
    assert runtime_info.enable_count == 1

# 重复启用 - 两种方式都会抛出相同的异常
try:
    registry.set_status("my_service", PluginStatus.ENABLED)
except PluginStateError:
    print("插件已启用")

# 停用插件 - set_status 会委托给 disable()
registry.set_status("my_service", PluginStatus.DISABLED)
assert registry.get_status("my_service") == PluginStatus.DISABLED

# 重置为已注册状态
registry.set_status("my_service", PluginStatus.REGISTERED)
assert registry.get_status("my_service") == PluginStatus.REGISTERED

# 再次启用 - 计数会递增
runtime_info = registry.set_status("my_service", PluginStatus.ENABLED)
assert runtime_info.enable_count == 2
```

### 批量操作异常处理示例

```python
# 注册带依赖的插件
registry.register(PluginMetadata(
    plugin_id="core",
    name="核心模块",
    version="1.0.0",
))
registry.register(PluginMetadata(
    plugin_id="feature_a",
    name="功能A",
    version="1.0.0",
    dependencies={"core": ">=1.0.0"},
))
registry.register(PluginMetadata(
    plugin_id="feature_b",
    name="功能B",
    version="1.0.0",
    dependencies={"nonexistent": ">=1.0.0"},  # 依赖不存在的插件
))

# 先启用 core，这样 feature_a 的依赖是满足的
registry.enable("core")

# 调用 enable_all - 会在 feature_b 处抛出 PluginDependencyError
# feature_a 可能已经被成功启用，但 feature_b 的错误会中断整个过程
try:
    results = registry.enable_all()
except PluginDependencyError as e:
    print(f"批量启用失败: 插件 {e.plugin_id} 的依赖 {e.dependency_id} 不满足")
    print(f"失败原因: {e.reason}")
    # 此时 core 是 ENABLED，feature_a 可能是 ENABLED，feature_b 是 REGISTERED
    # 调用方可以根据需要进行回滚或修复

# 正确的做法：逐个处理依赖，或确保所有依赖在调用 enable_all 前已就绪
registry.unregister("feature_b")  # 移除有问题的插件

# 现在可以安全地调用 enable_all
results = registry.enable_all()
for plugin_id, success in results.items():
    status = "成功" if success else "已启用"
    print(f"插件 {plugin_id}: {status}")
```

### 获取统计信息

```python
stats = registry.get_stats()
print(f"插件总数: {stats.total_plugins}")
print(f"已启用: {stats.enabled_plugins}")
print(f"已停用: {stats.disabled_plugins}")
print(f"已注册未启用: {stats.registered_plugins}")
print(f"能力总数: {stats.total_capabilities}")

# 获取所有能力和标签
all_caps = registry.get_all_capabilities()
all_tags = registry.get_all_tags()
print(f"所有能力: {all_caps}")
print(f"所有标签: {all_tags}")

# 转换为字典
stats_dict = stats.to_dict()
```

### 批量操作

```python
# 启用所有插件
results = registry.enable_all()
for plugin_id, success in results.items():
    print(f"{plugin_id}: {'成功' if success else '失败'}")

# 停用所有插件
results = registry.disable_all()

# 清空所有插件
count = registry.clear()
print(f"已清除 {count} 个插件")
```

### 插件元数据序列化

```python
metadata = PluginMetadata(
    plugin_id="test.plugin",
    name="Test Plugin",
    version="1.0.0",
    capabilities=["cap1"],
    tags=["tag1"],
)

# 序列化为字典
data = metadata.to_dict()

# 从字典反序列化
restored = PluginMetadata.from_dict(data)
assert restored.plugin_id == metadata.plugin_id
assert restored.version == metadata.version
```

### 版本比较高级用法

```python
from solocoder_4_py.plugin_registry import PluginMetadata

# 直接比较版本
cmp = PluginMetadata._compare_versions("1.2.0", "1.10.0")
assert cmp < 0  # 1.2.0 < 1.10.0

# 检查版本是否满足要求
metadata = PluginMetadata(plugin_id="test", name="Test", version="1.5.2")
assert metadata.satisfies_version(">=1.0.0") is True
assert metadata.satisfies_version("^1.0.0") is True
assert metadata.satisfies_version("~1.5.0") is True
assert metadata.satisfies_version(">=2.0.0") is False

# 不满足时抛出异常
try:
    metadata.check_compatibility(">=2.0.0")
except PluginVersionError as e:
    print(f"版本不兼容: {e.plugin_version} 不满足 {e.required_version}")
```

## API 参考

### PluginRegistry 主要方法

| 方法 | 说明 |
|------|------|
| `register(metadata)` | 注册插件 |
| `unregister(plugin_id)` | 注销插件 |
| `update_metadata(plugin_id, metadata)` | 更新插件元数据 |
| `enable(plugin_id, required_version=None)` | 启用插件（自动校验版本和依赖） |
| `disable(plugin_id)` | 停用插件 |
| `set_status(plugin_id, status)` | 设置插件状态（统一入口，委托给 enable/disable） |
| `get_status(plugin_id)` | 获取插件状态 |
| `is_enabled(plugin_id)` | 检查插件是否已启用 |
| `get_plugin(plugin_id)` | 获取插件运行时信息 |
| `get_metadata(plugin_id)` | 获取插件元数据 |
| `has_plugin(plugin_id)` | 检查插件是否已注册 |
| `list_plugins(status, capability, tag)` | 列出插件（支持组合过滤） |
| `find_by_capability(capability, enabled_only)` | 按能力查找 |
| `find_by_capabilities(capabilities, match_all, enabled_only)` | 按多能力查找 |
| `find_by_tag(tag, enabled_only)` | 按标签查找 |
| `find_by_tags(tags, match_all, enabled_only)` | 按多标签查找 |
| `check_plugin_version(plugin_id, required_version)` | 检查版本兼容性 |
| `check_and_enable(plugin_id, required_version, required_capabilities)` | 检查后启用（校验版本、能力、依赖） |
| `get_stats()` | 获取统计信息 |
| `get_all_capabilities()` | 获取所有能力列表 |
| `get_all_tags()` | 获取所有标签列表 |
| `enable_all()` | 批量启用所有插件（仅捕获 PluginStateError） |
| `disable_all()` | 批量停用所有插件（仅捕获 PluginStateError） |
| `clear()` | 清空所有插件 |
| `_validate_dependencies(plugin_id, dependencies)` | 校验插件依赖（内部方法） |

### PluginMetadata 主要方法

| 方法 | 说明 |
|------|------|
| `satisfies_version(requirement)` | 检查版本是否满足要求 |
| `check_compatibility(required_version)` | 检查兼容性，不满足抛异常 |
| `has_capability(capability)` | 检查是否具有指定能力 |
| `has_all_capabilities(capabilities)` | 检查是否具有所有能力 |
| `has_any_capability(capabilities)` | 检查是否具有任意能力 |
| `has_tag(tag)` | 检查是否具有指定标签 |
| `to_dict()` | 转换为字典 |
| `from_dict(data)` | 从字典创建（类方法） |

### 枚举和异常

| 名称 | 说明 |
|------|------|
| `PluginStatus.REGISTERED / ENABLED / DISABLED` | 插件状态枚举 |
| `PluginRegistryError` | 模块基础异常 |
| `PluginNotFoundError` | 插件未找到 |
| `PluginAlreadyRegisteredError` | 插件已注册 |
| `PluginVersionError` | 版本不兼容 |
| `PluginCapabilityError` | 缺少所需能力 |
| `PluginDependencyError` | 依赖不满足（未注册/未启用/版本不匹配） |
| `PluginStateError` | 状态操作非法（批量操作中唯一会被捕获的异常） |
