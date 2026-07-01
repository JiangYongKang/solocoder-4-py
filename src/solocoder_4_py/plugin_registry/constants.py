from enum import Enum


class PluginStatus(Enum):
    """插件状态枚举"""

    REGISTERED = "REGISTERED"
    ENABLED = "ENABLED"
    DISABLED = "DISABLED"


DEFAULT_PLUGIN_VERSION = "0.1.0"
MINIMUM_SUPPORTED_VERSION = "0.1.0"
