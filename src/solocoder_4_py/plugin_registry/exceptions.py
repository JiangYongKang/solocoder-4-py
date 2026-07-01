class PluginRegistryError(Exception):
    """插件注册中心基础异常"""


class PluginNotFoundError(PluginRegistryError):
    """插件未找到异常"""

    def __init__(self, plugin_id: str) -> None:
        self.plugin_id = plugin_id
        super().__init__(f"插件 '{plugin_id}' 未找到")


class PluginAlreadyRegisteredError(PluginRegistryError):
    """插件已注册异常"""

    def __init__(self, plugin_id: str) -> None:
        self.plugin_id = plugin_id
        super().__init__(f"插件 '{plugin_id}' 已存在")


class PluginVersionError(PluginRegistryError):
    """插件版本不兼容异常"""

    def __init__(self, plugin_id: str, plugin_version: str, required_version: str) -> None:
        self.plugin_id = plugin_id
        self.plugin_version = plugin_version
        self.required_version = required_version
        super().__init__(
            f"插件 '{plugin_id}' 版本 '{plugin_version}' 不满足要求 '{required_version}'"
        )


class PluginCapabilityError(PluginRegistryError):
    """插件能力不满足异常"""

    def __init__(self, plugin_id: str, missing_capability: str) -> None:
        self.plugin_id = plugin_id
        self.missing_capability = missing_capability
        super().__init__(f"插件 '{plugin_id}' 缺少所需能力 '{missing_capability}'")


class PluginStateError(PluginRegistryError):
    """插件状态操作异常"""

    def __init__(self, plugin_id: str, current_status: str, operation: str) -> None:
        self.plugin_id = plugin_id
        self.current_status = current_status
        self.operation = operation
        super().__init__(
            f"插件 '{plugin_id}' 当前状态为 '{current_status}'，无法执行操作 '{operation}'"
        )
