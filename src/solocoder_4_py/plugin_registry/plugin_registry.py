import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from .constants import MINIMUM_SUPPORTED_VERSION, PluginStatus
from .exceptions import (
    PluginAlreadyRegisteredError,
    PluginCapabilityError,
    PluginNotFoundError,
    PluginStateError,
)
from .plugin_metadata import PluginMetadata, PluginRuntimeInfo


@dataclass
class PluginRegistryStats:
    """插件注册中心统计信息"""

    total_plugins: int = 0
    enabled_plugins: int = 0
    disabled_plugins: int = 0
    registered_plugins: int = 0
    total_capabilities: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_plugins": self.total_plugins,
            "enabled_plugins": self.enabled_plugins,
            "disabled_plugins": self.disabled_plugins,
            "registered_plugins": self.registered_plugins,
            "total_capabilities": self.total_capabilities,
        }


class PluginRegistry:
    """插件注册中心核心类

    使用内存数据结构管理插件信息和运行状态，支持：
    - 插件注册与注销
    - 插件启用与停用
    - 按能力/标签/ID 发现插件
    - 版本兼容性校验
    - 线程安全操作
    """

    def __init__(self) -> None:
        self._plugins: Dict[str, PluginRuntimeInfo] = {}
        self._capability_index: Dict[str, Set[str]] = {}
        self._tag_index: Dict[str, Set[str]] = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------
    # 插件注册与注销
    # ------------------------------------------------------------
    def register(self, metadata: PluginMetadata) -> PluginRuntimeInfo:
        """注册插件

        Args:
            metadata: 插件元数据

        Returns:
            插件运行时信息

        Raises:
            PluginAlreadyRegisteredError: 如果插件已注册
        """
        with self._lock:
            plugin_id = metadata.plugin_id
            if plugin_id in self._plugins:
                raise PluginAlreadyRegisteredError(plugin_id)

            runtime_info = PluginRuntimeInfo(
                metadata=metadata,
                status=PluginStatus.REGISTERED,
                registered_at=time.time(),
            )

            self._plugins[plugin_id] = runtime_info
            self._build_indexes(plugin_id, metadata)

            return runtime_info

    def unregister(self, plugin_id: str) -> bool:
        """注销插件

        Args:
            plugin_id: 插件ID

        Returns:
            True 如果成功注销，False 如果插件不存在
        """
        with self._lock:
            if plugin_id not in self._plugins:
                return False

            metadata = self._plugins[plugin_id].metadata
            self._remove_indexes(plugin_id, metadata)
            del self._plugins[plugin_id]

            return True

    def update_metadata(self, plugin_id: str, metadata: PluginMetadata) -> PluginRuntimeInfo:
        """更新插件元数据

        Args:
            plugin_id: 插件ID
            metadata: 新的插件元数据

        Returns:
            更新后的插件运行时信息

        Raises:
            PluginNotFoundError: 如果插件不存在
            ValueError: 如果 plugin_id 不匹配
        """
        with self._lock:
            if plugin_id not in self._plugins:
                raise PluginNotFoundError(plugin_id)

            if metadata.plugin_id != plugin_id:
                raise ValueError("metadata.plugin_id 必须与 plugin_id 一致")

            old_metadata = self._plugins[plugin_id].metadata
            self._remove_indexes(plugin_id, old_metadata)

            runtime_info = self._plugins[plugin_id]
            runtime_info.metadata = metadata

            self._build_indexes(plugin_id, metadata)

            return runtime_info

    # ------------------------------------------------------------
    # 插件状态管理
    # ------------------------------------------------------------
    def enable(self, plugin_id: str, required_version: Optional[str] = None) -> PluginRuntimeInfo:
        """启用插件

        Args:
            plugin_id: 插件ID
            required_version: 可选的版本要求

        Returns:
            更新后的插件运行时信息

        Raises:
            PluginNotFoundError: 如果插件不存在
            PluginVersionError: 如果版本不满足要求
            PluginStateError: 如果插件已启用
        """
        with self._lock:
            runtime_info = self._get_plugin_or_raise(plugin_id)

            if runtime_info.status == PluginStatus.ENABLED:
                raise PluginStateError(plugin_id, runtime_info.status.value, "enable")

            if required_version is not None:
                runtime_info.metadata.check_compatibility(required_version)

            runtime_info.status = PluginStatus.ENABLED
            runtime_info.enabled_at = time.time()
            runtime_info.disabled_at = None
            runtime_info.enable_count += 1
            runtime_info.last_error = None

            return runtime_info

    def disable(self, plugin_id: str) -> PluginRuntimeInfo:
        """停用插件

        Args:
            plugin_id: 插件ID

        Returns:
            更新后的插件运行时信息

        Raises:
            PluginNotFoundError: 如果插件不存在
            PluginStateError: 如果插件已停用或未注册
        """
        with self._lock:
            runtime_info = self._get_plugin_or_raise(plugin_id)

            if runtime_info.status == PluginStatus.DISABLED:
                raise PluginStateError(plugin_id, runtime_info.status.value, "disable")

            if runtime_info.status == PluginStatus.REGISTERED:
                raise PluginStateError(plugin_id, runtime_info.status.value, "disable")

            runtime_info.status = PluginStatus.DISABLED
            runtime_info.disabled_at = time.time()

            return runtime_info

    def set_status(self, plugin_id: str, status: PluginStatus) -> PluginRuntimeInfo:
        """设置插件状态

        Args:
            plugin_id: 插件ID
            status: 目标状态

        Returns:
            更新后的插件运行时信息

        Raises:
            PluginNotFoundError: 如果插件不存在
        """
        with self._lock:
            runtime_info = self._get_plugin_or_raise(plugin_id)

            if status == PluginStatus.ENABLED and runtime_info.status != PluginStatus.ENABLED:
                runtime_info.status = PluginStatus.ENABLED
                runtime_info.enabled_at = time.time()
                runtime_info.disabled_at = None
                runtime_info.enable_count += 1
                runtime_info.last_error = None
            elif status == PluginStatus.DISABLED and runtime_info.status != PluginStatus.DISABLED:
                runtime_info.status = PluginStatus.DISABLED
                runtime_info.disabled_at = time.time()
            elif status == PluginStatus.REGISTERED:
                runtime_info.status = PluginStatus.REGISTERED

            return runtime_info

    def get_status(self, plugin_id: str) -> PluginStatus:
        """获取插件状态

        Args:
            plugin_id: 插件ID

        Returns:
            插件状态

        Raises:
            PluginNotFoundError: 如果插件不存在
        """
        with self._lock:
            return self._get_plugin_or_raise(plugin_id).status

    def is_enabled(self, plugin_id: str) -> bool:
        """检查插件是否已启用

        Args:
            plugin_id: 插件ID

        Returns:
            True 如果已启用，否则 False

        Raises:
            PluginNotFoundError: 如果插件不存在
        """
        return self.get_status(plugin_id) == PluginStatus.ENABLED

    # ------------------------------------------------------------
    # 插件查询与发现
    # ------------------------------------------------------------
    def get_plugin(self, plugin_id: str) -> PluginRuntimeInfo:
        """获取插件运行时信息

        Args:
            plugin_id: 插件ID

        Returns:
            插件运行时信息

        Raises:
            PluginNotFoundError: 如果插件不存在
        """
        with self._lock:
            return self._get_plugin_or_raise(plugin_id)

    def get_metadata(self, plugin_id: str) -> PluginMetadata:
        """获取插件元数据

        Args:
            plugin_id: 插件ID

        Returns:
            插件元数据

        Raises:
            PluginNotFoundError: 如果插件不存在
        """
        with self._lock:
            return self._get_plugin_or_raise(plugin_id).metadata

    def has_plugin(self, plugin_id: str) -> bool:
        """检查插件是否已注册

        Args:
            plugin_id: 插件ID

        Returns:
            True 如果已注册，否则 False
        """
        with self._lock:
            return plugin_id in self._plugins

    def list_plugins(
        self,
        status: Optional[PluginStatus] = None,
        capability: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> List[PluginRuntimeInfo]:
        """列出插件，支持按状态、能力、标签过滤

        Args:
            status: 按状态过滤
            capability: 按能力过滤
            tag: 按标签过滤

        Returns:
            符合条件的插件运行时信息列表
        """
        with self._lock:
            plugin_ids: Optional[Set[str]] = None

            if capability is not None:
                plugin_ids = set(self._capability_index.get(capability, set()))

            if tag is not None:
                tag_plugins = set(self._tag_index.get(tag, set()))
                if plugin_ids is None:
                    plugin_ids = tag_plugins
                else:
                    plugin_ids = plugin_ids & tag_plugins

            if plugin_ids is None:
                plugin_ids = set(self._plugins.keys())

            result: List[PluginRuntimeInfo] = []
            for plugin_id in plugin_ids:
                runtime_info = self._plugins[plugin_id]
                if status is None or runtime_info.status == status:
                    result.append(runtime_info)

            return sorted(result, key=lambda r: r.metadata.plugin_id)

    def find_by_capability(self, capability: str, enabled_only: bool = True) -> List[PluginRuntimeInfo]:
        """按能力查找插件

        Args:
            capability: 所需能力
            enabled_only: 是否只返回已启用的插件

        Returns:
            具有指定能力的插件列表
        """
        with self._lock:
            status = PluginStatus.ENABLED if enabled_only else None
            return self.list_plugins(status=status, capability=capability)

    def find_by_capabilities(
        self,
        capabilities: Iterable[str],
        match_all: bool = True,
        enabled_only: bool = True,
    ) -> List[PluginRuntimeInfo]:
        """按多个能力查找插件

        Args:
            capabilities: 所需能力列表
            match_all: True 表示需要满足所有能力，False 表示满足任意一个即可
            enabled_only: 是否只返回已启用的插件

        Returns:
            符合条件的插件列表
        """
        with self._lock:
            cap_list = list(capabilities)
            if not cap_list:
                return []

            status = PluginStatus.ENABLED if enabled_only else None
            candidates = self.list_plugins(status=status)

            if match_all:
                return [p for p in candidates if p.metadata.has_all_capabilities(cap_list)]
            else:
                return [p for p in candidates if p.metadata.has_any_capability(cap_list)]

    def find_by_tag(self, tag: str, enabled_only: bool = True) -> List[PluginRuntimeInfo]:
        """按标签查找插件

        Args:
            tag: 所需标签
            enabled_only: 是否只返回已启用的插件

        Returns:
            具有指定标签的插件列表
        """
        with self._lock:
            status = PluginStatus.ENABLED if enabled_only else None
            return self.list_plugins(status=status, tag=tag)

    def find_by_tags(
        self,
        tags: Iterable[str],
        match_all: bool = True,
        enabled_only: bool = True,
    ) -> List[PluginRuntimeInfo]:
        """按多个标签查找插件

        Args:
            tags: 所需标签列表
            match_all: True 表示需要满足所有标签，False 表示满足任意一个即可
            enabled_only: 是否只返回已启用的插件

        Returns:
            符合条件的插件列表
        """
        with self._lock:
            tag_list = list(tags)
            if not tag_list:
                return []

            status = PluginStatus.ENABLED if enabled_only else None
            candidates = self.list_plugins(status=status)

            if match_all:
                return [p for p in candidates if all(p.metadata.has_tag(t) for t in tag_list)]
            else:
                return [p for p in candidates if any(p.metadata.has_tag(t) for t in tag_list)]

    # ------------------------------------------------------------
    # 版本兼容性检查
    # ------------------------------------------------------------
    def check_plugin_version(self, plugin_id: str, required_version: str) -> bool:
        """检查插件版本是否满足要求

        Args:
            plugin_id: 插件ID
            required_version: 版本要求

        Returns:
            True 如果满足要求，否则 False

        Raises:
            PluginNotFoundError: 如果插件不存在
        """
        with self._lock:
            metadata = self._get_plugin_or_raise(plugin_id).metadata
            return metadata.satisfies_version(required_version)

    def check_and_enable(
        self,
        plugin_id: str,
        required_version: str,
        required_capabilities: Optional[Iterable[str]] = None,
    ) -> PluginRuntimeInfo:
        """检查版本和能力后启用插件

        Args:
            plugin_id: 插件ID
            required_version: 版本要求
            required_capabilities: 可选的能力要求列表

        Returns:
            启用后的插件运行时信息

        Raises:
            PluginNotFoundError: 如果插件不存在
            PluginVersionError: 如果版本不满足要求
            PluginCapabilityError: 如果缺少所需能力
        """
        with self._lock:
            runtime_info = self._get_plugin_or_raise(plugin_id)
            runtime_info.metadata.check_compatibility(required_version)

            if required_capabilities is not None:
                for cap in required_capabilities:
                    if not runtime_info.metadata.has_capability(cap):
                        raise PluginCapabilityError(plugin_id, cap)

            return self.enable(plugin_id)

    # ------------------------------------------------------------
    # 统计信息
    # ------------------------------------------------------------
    def get_stats(self) -> PluginRegistryStats:
        """获取注册中心统计信息

        Returns:
            统计信息对象
        """
        with self._lock:
            total = len(self._plugins)
            enabled = 0
            disabled = 0
            registered = 0
            capabilities: Set[str] = set()

            for runtime_info in self._plugins.values():
                if runtime_info.status == PluginStatus.ENABLED:
                    enabled += 1
                elif runtime_info.status == PluginStatus.DISABLED:
                    disabled += 1
                else:
                    registered += 1
                capabilities.update(runtime_info.metadata.capabilities)

            return PluginRegistryStats(
                total_plugins=total,
                enabled_plugins=enabled,
                disabled_plugins=disabled,
                registered_plugins=registered,
                total_capabilities=len(capabilities),
            )

    def get_all_capabilities(self) -> List[str]:
        """获取所有已注册的能力

        Returns:
            能力名称列表（去重后排序）
        """
        with self._lock:
            return sorted(self._capability_index.keys())

    def get_all_tags(self) -> List[str]:
        """获取所有已注册的标签

        Returns:
            标签名称列表（去重后排序）
        """
        with self._lock:
            return sorted(self._tag_index.keys())

    # ------------------------------------------------------------
    # 批量操作
    # ------------------------------------------------------------
    def enable_all(self) -> Dict[str, bool]:
        """启用所有已注册但未启用的插件

        Returns:
            {plugin_id: 是否成功启用} 的字典
        """
        with self._lock:
            results: Dict[str, bool] = {}
            for plugin_id in list(self._plugins.keys()):
                try:
                    self.enable(plugin_id)
                    results[plugin_id] = True
                except Exception:
                    results[plugin_id] = False
            return results

    def disable_all(self) -> Dict[str, bool]:
        """停用所有已启用的插件

        Returns:
            {plugin_id: 是否成功停用} 的字典
        """
        with self._lock:
            results: Dict[str, bool] = {}
            for plugin_id in list(self._plugins.keys()):
                try:
                    self.disable(plugin_id)
                    results[plugin_id] = True
                except Exception:
                    results[plugin_id] = False
            return results

    def clear(self) -> int:
        """清空所有插件

        Returns:
            清除的插件数量
        """
        with self._lock:
            count = len(self._plugins)
            self._plugins.clear()
            self._capability_index.clear()
            self._tag_index.clear()
            return count

    # ------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------
    def _get_plugin_or_raise(self, plugin_id: str) -> PluginRuntimeInfo:
        """获取插件，不存在则抛出异常"""
        runtime_info = self._plugins.get(plugin_id)
        if runtime_info is None:
            raise PluginNotFoundError(plugin_id)
        return runtime_info

    def _build_indexes(self, plugin_id: str, metadata: PluginMetadata) -> None:
        """构建能力和标签索引"""
        for capability in metadata.capabilities:
            if capability not in self._capability_index:
                self._capability_index[capability] = set()
            self._capability_index[capability].add(plugin_id)

        for tag in metadata.tags:
            if tag not in self._tag_index:
                self._tag_index[tag] = set()
            self._tag_index[tag].add(plugin_id)

    def _remove_indexes(self, plugin_id: str, metadata: PluginMetadata) -> None:
        """移除能力和标签索引"""
        for capability in metadata.capabilities:
            if capability in self._capability_index:
                self._capability_index[capability].discard(plugin_id)
                if not self._capability_index[capability]:
                    del self._capability_index[capability]

        for tag in metadata.tags:
            if tag in self._tag_index:
                self._tag_index[tag].discard(plugin_id)
                if not self._tag_index[tag]:
                    del self._tag_index[tag]

    # ------------------------------------------------------------
    # 魔法方法
    # ------------------------------------------------------------
    def __contains__(self, plugin_id: str) -> bool:
        return self.has_plugin(plugin_id)

    def __len__(self) -> int:
        with self._lock:
            return len(self._plugins)

    def __iter__(self):
        with self._lock:
            return iter(sorted(self._plugins.keys()))
