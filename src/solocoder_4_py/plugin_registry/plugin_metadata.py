import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from .constants import DEFAULT_PLUGIN_VERSION, PluginStatus
from .exceptions import PluginVersionError


@dataclass
class PluginMetadata:
    """插件元数据类

    用于描述插件的基本信息、版本、能力和依赖关系。
    """

    plugin_id: str
    name: str
    version: str = DEFAULT_PLUGIN_VERSION
    description: str = ""
    author: str = ""
    capabilities: List[str] = field(default_factory=list)
    dependencies: Dict[str, str] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.plugin_id:
            raise ValueError("plugin_id 不能为空")
        if not self.name:
            raise ValueError("name 不能为空")
        self._validate_version_format(self.version)
        self.capabilities = list(self.capabilities)
        self.tags = list(self.tags)

    @staticmethod
    def _validate_version_format(version: str) -> None:
        """验证版本号格式（语义化版本 MAJOR.MINOR.PATCH）"""
        pattern = r"^\d+\.\d+\.\d+(-[0-9A-Za-z-]+(\.[0-9A-Za-z-]+)*)?(\+[0-9A-Za-z-]+(\.[0-9A-Za-z-]+)*)?$"
        if not re.match(pattern, version):
            raise ValueError(f"版本号格式不正确: '{version}'，应为语义化版本格式（如 1.0.0）")

    @staticmethod
    def _parse_version(version: str) -> tuple:
        """解析版本号为 (major, minor, patch, pre_release) 元组"""
        PluginMetadata._validate_version_format(version)
        main_part = version.split("-")[0].split("+")[0]
        parts = main_part.split(".")
        major = int(parts[0])
        minor = int(parts[1])
        patch = int(parts[2])
        pre_release = None
        if "-" in version:
            pre_release = version.split("-")[1].split("+")[0]
        return (major, minor, patch, pre_release)

    @staticmethod
    def _compare_versions(v1: str, v2: str) -> int:
        """比较两个版本号

        Returns:
            -1: v1 < v2
            0: v1 == v2
            1: v1 > v2
        """
        p1 = PluginMetadata._parse_version(v1)
        p2 = PluginMetadata._parse_version(v2)

        for i in range(3):
            if p1[i] < p2[i]:
                return -1
            if p1[i] > p2[i]:
                return 1

        if p1[3] is None and p2[3] is None:
            return 0
        if p1[3] is None:
            return 1
        if p2[3] is None:
            return -1

        if p1[3] < p2[3]:
            return -1
        if p1[3] > p2[3]:
            return 1

        return 0

    @staticmethod
    def _parse_requirement(requirement: str) -> tuple:
        """解析版本要求字符串

        支持的格式：
        - ">=1.0.0"  大于等于
        - "<=2.0.0"  小于等于
        - ">1.0.0"   大于
        - "<2.0.0"   小于
        - "==1.0.0"  等于
        - "!=1.0.0"  不等于
        - "~1.0.0"   兼容（>=1.0.0 且 <1.1.0）
        - "^1.0.0"   兼容（>=1.0.0 且 <2.0.0）
        - "1.0.0"    精确等于
        """
        requirement = requirement.strip()

        if requirement.startswith(">="):
            return (">=", requirement[2:].strip())
        elif requirement.startswith("<="):
            return ("<=", requirement[2:].strip())
        elif requirement.startswith(">"):
            return (">", requirement[1:].strip())
        elif requirement.startswith("<"):
            return ("<", requirement[1:].strip())
        elif requirement.startswith("=="):
            return ("==", requirement[2:].strip())
        elif requirement.startswith("!="):
            return ("!=", requirement[2:].strip())
        elif requirement.startswith("~"):
            return ("~", requirement[1:].strip())
        elif requirement.startswith("^"):
            return ("^", requirement[1:].strip())
        else:
            return ("==", requirement)

    def satisfies_version(self, requirement: str) -> bool:
        """检查当前版本是否满足版本要求

        Args:
            requirement: 版本要求字符串，支持逗号分隔多个约束（如 ">=1.0.0,<2.0.0"）

        Returns:
            True 如果满足所有要求，否则 False

        Raises:
            ValueError: 如果版本要求格式不正确
        """
        requirements = [r.strip() for r in requirement.split(",") if r.strip()]

        for req in requirements:
            if not self._satisfies_single_requirement(req):
                return False

        return True

    def _satisfies_single_requirement(self, requirement: str) -> bool:
        """检查单个版本要求"""
        operator, required_version = self._parse_requirement(requirement)
        cmp_result = self._compare_versions(self.version, required_version)

        if operator == ">=":
            return cmp_result >= 0
        elif operator == "<=":
            return cmp_result <= 0
        elif operator == ">":
            return cmp_result > 0
        elif operator == "<":
            return cmp_result < 0
        elif operator == "==":
            return cmp_result == 0
        elif operator == "!=":
            return cmp_result != 0
        elif operator == "~":
            req_parts = self._parse_version(required_version)
            min_version = required_version
            max_parts = [req_parts[0], req_parts[1] + 1, 0, None]
            max_version = f"{max_parts[0]}.{max_parts[1]}.{max_parts[2]}"
            return self._compare_versions(self.version, min_version) >= 0 and self._compare_versions(
                self.version, max_version
            ) < 0
        elif operator == "^":
            req_parts = self._parse_version(required_version)
            min_version = required_version
            if req_parts[0] > 0:
                max_parts = [req_parts[0] + 1, 0, 0, None]
            elif req_parts[1] > 0:
                max_parts = [0, req_parts[1] + 1, 0, None]
            else:
                max_parts = [0, 0, req_parts[2] + 1, None]
            max_version = f"{max_parts[0]}.{max_parts[1]}.{max_parts[2]}"
            return self._compare_versions(self.version, min_version) >= 0 and self._compare_versions(
                self.version, max_version
            ) < 0

        return False

    def check_compatibility(self, required_version: str) -> None:
        """检查版本兼容性，不满足则抛出异常

        Args:
            required_version: 要求的版本

        Raises:
            PluginVersionError: 如果版本不满足要求
        """
        if not self.satisfies_version(required_version):
            raise PluginVersionError(self.plugin_id, self.version, required_version)

    def has_capability(self, capability: str) -> bool:
        """检查插件是否具有指定能力

        Args:
            capability: 能力名称

        Returns:
            True 如果具有该能力，否则 False
        """
        return capability in self.capabilities

    def has_all_capabilities(self, capabilities: Iterable[str]) -> bool:
        """检查插件是否具有所有指定能力

        Args:
            capabilities: 能力名称列表

        Returns:
            True 如果具有所有能力，否则 False
        """
        return all(self.has_capability(cap) for cap in capabilities)

    def has_any_capability(self, capabilities: Iterable[str]) -> bool:
        """检查插件是否具有任意一个指定能力

        Args:
            capabilities: 能力名称列表

        Returns:
            True 如果具有任意一个能力，否则 False
        """
        return any(self.has_capability(cap) for cap in capabilities)

    def has_tag(self, tag: str) -> bool:
        """检查插件是否有指定标签

        Args:
            tag: 标签名称

        Returns:
            True 如果有该标签，否则 False
        """
        return tag in self.tags

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "plugin_id": self.plugin_id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "capabilities": list(self.capabilities),
            "dependencies": dict(self.dependencies),
            "tags": list(self.tags),
            "extra": dict(self.extra),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PluginMetadata":
        """从字典创建 PluginMetadata 实例"""
        return cls(
            plugin_id=data["plugin_id"],
            name=data["name"],
            version=data.get("version", DEFAULT_PLUGIN_VERSION),
            description=data.get("description", ""),
            author=data.get("author", ""),
            capabilities=list(data.get("capabilities", [])),
            dependencies=dict(data.get("dependencies", {})),
            tags=list(data.get("tags", [])),
            extra=dict(data.get("extra", {})),
        )


@dataclass
class PluginRuntimeInfo:
    """插件运行时信息类

    记录插件的运行状态、注册时间、启用时间等运行时数据。
    """

    metadata: PluginMetadata
    status: PluginStatus = PluginStatus.REGISTERED
    registered_at: float = 0.0
    enabled_at: Optional[float] = None
    disabled_at: Optional[float] = None
    enable_count: int = 0
    last_error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "metadata": self.metadata.to_dict(),
            "status": self.status.value,
            "registered_at": self.registered_at,
            "enabled_at": self.enabled_at,
            "disabled_at": self.disabled_at,
            "enable_count": self.enable_count,
            "last_error": self.last_error,
        }
