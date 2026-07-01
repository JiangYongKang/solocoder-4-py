import threading
import time
import pytest

from solocoder_4_py.plugin_registry import (
    PluginAlreadyRegisteredError,
    PluginCapabilityError,
    PluginDependencyError,
    PluginMetadata,
    PluginNotFoundError,
    PluginRegistry,
    PluginRegistryStats,
    PluginRuntimeInfo,
    PluginStateError,
    PluginStatus,
    PluginVersionError,
)
from unittest.mock import patch


# =====================================================================
# 测试辅助函数
# =====================================================================
def create_test_metadata(plugin_id: str, **kwargs) -> PluginMetadata:
    """创建测试用的插件元数据"""
    defaults = {
        "plugin_id": plugin_id,
        "name": f"Plugin {plugin_id}",
        "version": "1.0.0",
    }
    defaults.update(kwargs)
    return PluginMetadata(**defaults)


# =====================================================================
# PluginRegistry 基础测试
# =====================================================================
class TestPluginRegistryBasics:
    def test_create_registry(self):
        registry = PluginRegistry()
        assert len(registry) == 0
        assert registry.get_stats().total_plugins == 0

    def test_has_plugin_false(self):
        registry = PluginRegistry()
        assert registry.has_plugin("nonexistent") is False
        assert ("nonexistent" in registry) is False

    def test_get_plugin_not_found_raises(self):
        registry = PluginRegistry()
        with pytest.raises(PluginNotFoundError) as exc_info:
            registry.get_plugin("nonexistent")
        assert exc_info.value.plugin_id == "nonexistent"

    def test_get_metadata_not_found_raises(self):
        registry = PluginRegistry()
        with pytest.raises(PluginNotFoundError):
            registry.get_metadata("nonexistent")

    def test_get_status_not_found_raises(self):
        registry = PluginRegistry()
        with pytest.raises(PluginNotFoundError):
            registry.get_status("nonexistent")

    def test_is_enabled_not_found_raises(self):
        registry = PluginRegistry()
        with pytest.raises(PluginNotFoundError):
            registry.is_enabled("nonexistent")

    def test_iter_empty(self):
        registry = PluginRegistry()
        assert list(iter(registry)) == []


# =====================================================================
# 插件注册与注销测试
# =====================================================================
class TestPluginRegistration:
    def test_register_plugin(self):
        registry = PluginRegistry()
        metadata = create_test_metadata("plugin1")
        runtime_info = registry.register(metadata)

        assert isinstance(runtime_info, PluginRuntimeInfo)
        assert runtime_info.metadata is metadata
        assert runtime_info.status == PluginStatus.REGISTERED
        assert runtime_info.registered_at > 0
        assert runtime_info.enable_count == 0

        assert len(registry) == 1
        assert registry.has_plugin("plugin1") is True
        assert "plugin1" in registry

    def test_register_duplicate_raises(self):
        registry = PluginRegistry()
        metadata = create_test_metadata("plugin1")
        registry.register(metadata)

        with pytest.raises(PluginAlreadyRegisteredError) as exc_info:
            registry.register(metadata)
        assert exc_info.value.plugin_id == "plugin1"

    def test_unregister_plugin(self):
        registry = PluginRegistry()
        metadata = create_test_metadata("plugin1", capabilities=["cap1"], tags=["tag1"])
        registry.register(metadata)

        result = registry.unregister("plugin1")
        assert result is True
        assert len(registry) == 0
        assert registry.has_plugin("plugin1") is False
        assert registry.get_all_capabilities() == []
        assert registry.get_all_tags() == []

    def test_unregister_nonexistent(self):
        registry = PluginRegistry()
        result = registry.unregister("nonexistent")
        assert result is False

    def test_update_metadata(self):
        registry = PluginRegistry()
        metadata = create_test_metadata(
            "plugin1",
            version="1.0.0",
            capabilities=["old_cap"],
            tags=["old_tag"],
        )
        registry.register(metadata)

        new_metadata = create_test_metadata(
            "plugin1",
            version="2.0.0",
            description="Updated",
            capabilities=["new_cap"],
            tags=["new_tag"],
        )

        updated = registry.update_metadata("plugin1", new_metadata)
        assert updated.metadata.version == "2.0.0"
        assert updated.metadata.description == "Updated"
        assert "new_cap" in registry.get_all_capabilities()
        assert "old_cap" not in registry.get_all_capabilities()
        assert "new_tag" in registry.get_all_tags()
        assert "old_tag" not in registry.get_all_tags()

    def test_update_metadata_not_found_raises(self):
        registry = PluginRegistry()
        metadata = create_test_metadata("plugin1")
        with pytest.raises(PluginNotFoundError):
            registry.update_metadata("nonexistent", metadata)

    def test_update_metadata_id_mismatch_raises(self):
        registry = PluginRegistry()
        metadata1 = create_test_metadata("plugin1")
        registry.register(metadata1)

        metadata2 = create_test_metadata("plugin2")
        with pytest.raises(ValueError, match="plugin_id 必须与 plugin_id 一致"):
            registry.update_metadata("plugin1", metadata2)

    def test_clear(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("p1"))
        registry.register(create_test_metadata("p2"))

        count = registry.clear()
        assert count == 2
        assert len(registry) == 0
        assert registry.get_all_capabilities() == []
        assert registry.get_all_tags() == []


# =====================================================================
# 插件状态管理测试
# =====================================================================
class TestPluginStateManagement:
    def test_enable_plugin(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("plugin1"))

        runtime_info = registry.enable("plugin1")
        assert runtime_info.status == PluginStatus.ENABLED
        assert runtime_info.enabled_at is not None
        assert runtime_info.disabled_at is None
        assert runtime_info.enable_count == 1

        assert registry.is_enabled("plugin1") is True
        assert registry.get_status("plugin1") == PluginStatus.ENABLED

    def test_enable_already_enabled_raises(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("plugin1"))
        registry.enable("plugin1")

        with pytest.raises(PluginStateError) as exc_info:
            registry.enable("plugin1")
        assert exc_info.value.operation == "enable"

    def test_enable_with_version_check(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("plugin1", version="1.5.0"))

        runtime_info = registry.enable("plugin1", required_version=">=1.0.0")
        assert runtime_info.status == PluginStatus.ENABLED

    def test_enable_with_version_check_fails(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("plugin1", version="1.5.0"))

        with pytest.raises(PluginVersionError):
            registry.enable("plugin1", required_version=">=2.0.0")

    def test_disable_plugin(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("plugin1"))
        registry.enable("plugin1")

        runtime_info = registry.disable("plugin1")
        assert runtime_info.status == PluginStatus.DISABLED
        assert runtime_info.disabled_at is not None
        assert runtime_info.enabled_at is not None
        assert runtime_info.enable_count == 1

        assert registry.is_enabled("plugin1") is False
        assert registry.get_status("plugin1") == PluginStatus.DISABLED

    def test_disable_already_disabled_raises(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("plugin1"))
        registry.enable("plugin1")
        registry.disable("plugin1")

        with pytest.raises(PluginStateError) as exc_info:
            registry.disable("plugin1")
        assert exc_info.value.operation == "disable"

    def test_disable_registered_raises(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("plugin1"))

        with pytest.raises(PluginStateError) as exc_info:
            registry.disable("plugin1")
        assert exc_info.value.operation == "disable"
        assert "REGISTERED" in exc_info.value.current_status

    def test_set_status_enabled(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("plugin1"))

        runtime_info = registry.set_status("plugin1", PluginStatus.ENABLED)
        assert runtime_info.status == PluginStatus.ENABLED
        assert runtime_info.enable_count == 1

    def test_set_status_disabled(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("plugin1"))
        registry.enable("plugin1")

        runtime_info = registry.set_status("plugin1", PluginStatus.DISABLED)
        assert runtime_info.status == PluginStatus.DISABLED

    def test_set_status_registered(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("plugin1"))
        registry.enable("plugin1")

        runtime_info = registry.set_status("plugin1", PluginStatus.REGISTERED)
        assert runtime_info.status == PluginStatus.REGISTERED

    def test_set_status_not_found_raises(self):
        registry = PluginRegistry()
        with pytest.raises(PluginNotFoundError):
            registry.set_status("nonexistent", PluginStatus.ENABLED)

    def test_set_status_enabled_twice_raises_state_error(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("plugin1"))

        registry.set_status("plugin1", PluginStatus.ENABLED)

        with pytest.raises(PluginStateError) as exc_info:
            registry.set_status("plugin1", PluginStatus.ENABLED)

        assert exc_info.value.operation == "enable"
        assert exc_info.value.current_status == PluginStatus.ENABLED.value

        runtime_info = registry.get_plugin("plugin1")
        assert runtime_info.enable_count == 1

    def test_enable_disable_enable_increments_count(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("plugin1"))

        registry.enable("plugin1")
        registry.disable("plugin1")
        registry.enable("plugin1")

        runtime_info = registry.get_plugin("plugin1")
        assert runtime_info.enable_count == 2


# =====================================================================
# 插件发现测试
# =====================================================================
class TestPluginDiscovery:
    def test_list_plugins_all(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("plugin1"))
        registry.register(create_test_metadata("plugin2"))

        plugins = registry.list_plugins()
        assert len(plugins) == 2
        assert plugins[0].metadata.plugin_id == "plugin1"
        assert plugins[1].metadata.plugin_id == "plugin2"

    def test_list_plugins_by_status(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("plugin1"))
        registry.register(create_test_metadata("plugin2"))
        registry.enable("plugin1")

        enabled = registry.list_plugins(status=PluginStatus.ENABLED)
        assert len(enabled) == 1
        assert enabled[0].metadata.plugin_id == "plugin1"

        registered = registry.list_plugins(status=PluginStatus.REGISTERED)
        assert len(registered) == 1
        assert registered[0].metadata.plugin_id == "plugin2"

    def test_list_plugins_by_capability(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("plugin1", capabilities=["import", "export"]))
        registry.register(create_test_metadata("plugin2", capabilities=["import"]))
        registry.register(create_test_metadata("plugin3", capabilities=["other"]))

        import_plugins = registry.list_plugins(capability="import")
        assert len(import_plugins) == 2
        ids = [p.metadata.plugin_id for p in import_plugins]
        assert "plugin1" in ids
        assert "plugin2" in ids

    def test_list_plugins_by_tag(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("plugin1", tags=["data", "io"]))
        registry.register(create_test_metadata("plugin2", tags=["data"]))
        registry.register(create_test_metadata("plugin3", tags=["other"]))

        data_plugins = registry.list_plugins(tag="data")
        assert len(data_plugins) == 2
        ids = [p.metadata.plugin_id for p in data_plugins]
        assert "plugin1" in ids
        assert "plugin2" in ids

    def test_list_plugins_by_capability_and_tag(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("p1", capabilities=["import"], tags=["data"]))
        registry.register(create_test_metadata("p2", capabilities=["import"], tags=["other"]))
        registry.register(create_test_metadata("p3", capabilities=["export"], tags=["data"]))

        result = registry.list_plugins(capability="import", tag="data")
        assert len(result) == 1
        assert result[0].metadata.plugin_id == "p1"

    def test_list_plugins_by_capability_tag_and_status(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("p1", capabilities=["import"], tags=["data"]))
        registry.register(create_test_metadata("p2", capabilities=["import"], tags=["data"]))
        registry.enable("p1")

        result = registry.list_plugins(
            status=PluginStatus.ENABLED, capability="import", tag="data"
        )
        assert len(result) == 1
        assert result[0].metadata.plugin_id == "p1"

    def test_find_by_capability_enabled_only(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("p1", capabilities=["import"]))
        registry.register(create_test_metadata("p2", capabilities=["import"]))
        registry.enable("p1")

        plugins = registry.find_by_capability("import")
        assert len(plugins) == 1
        assert plugins[0].metadata.plugin_id == "p1"

    def test_find_by_capability_include_disabled(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("p1", capabilities=["import"]))
        registry.register(create_test_metadata("p2", capabilities=["import"]))
        registry.enable("p1")

        plugins = registry.find_by_capability("import", enabled_only=False)
        assert len(plugins) == 2

    def test_find_by_capability_nonexistent(self):
        registry = PluginRegistry()
        plugins = registry.find_by_capability("nonexistent")
        assert len(plugins) == 0

    def test_find_by_capabilities_match_all(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("p1", capabilities=["import", "export"]))
        registry.register(create_test_metadata("p2", capabilities=["import"]))
        registry.enable_all()

        plugins = registry.find_by_capabilities(["import", "export"], match_all=True)
        assert len(plugins) == 1
        assert plugins[0].metadata.plugin_id == "p1"

    def test_find_by_capabilities_match_any(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("p1", capabilities=["import"]))
        registry.register(create_test_metadata("p2", capabilities=["export"]))
        registry.register(create_test_metadata("p3", capabilities=["other"]))
        registry.enable_all()

        plugins = registry.find_by_capabilities(["import", "export"], match_all=False)
        assert len(plugins) == 2
        ids = [p.metadata.plugin_id for p in plugins]
        assert "p1" in ids
        assert "p2" in ids

    def test_find_by_capabilities_empty_list(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("p1", capabilities=["import"]))
        plugins = registry.find_by_capabilities([])
        assert len(plugins) == 0

    def test_find_by_tag(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("p1", tags=["data"]))
        registry.register(create_test_metadata("p2", tags=["io"]))
        registry.enable("p1")

        plugins = registry.find_by_tag("data")
        assert len(plugins) == 1
        assert plugins[0].metadata.plugin_id == "p1"

    def test_find_by_tag_include_disabled(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("p1", tags=["data"]))

        plugins = registry.find_by_tag("data", enabled_only=False)
        assert len(plugins) == 1

    def test_find_by_tags_match_all(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("p1", tags=["data", "io"]))
        registry.register(create_test_metadata("p2", tags=["data"]))
        registry.enable_all()

        plugins = registry.find_by_tags(["data", "io"], match_all=True)
        assert len(plugins) == 1
        assert plugins[0].metadata.plugin_id == "p1"

    def test_find_by_tags_match_any(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("p1", tags=["data"]))
        registry.register(create_test_metadata("p2", tags=["io"]))
        registry.register(create_test_metadata("p3", tags=["other"]))
        registry.enable_all()

        plugins = registry.find_by_tags(["data", "io"], match_all=False)
        assert len(plugins) == 2

    def test_find_by_tags_empty_list(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("p1", tags=["data"]))
        plugins = registry.find_by_tags([])
        assert len(plugins) == 0

    def test_get_plugin(self):
        registry = PluginRegistry()
        metadata = create_test_metadata("plugin1")
        registry.register(metadata)

        runtime_info = registry.get_plugin("plugin1")
        assert runtime_info.metadata is metadata

    def test_get_metadata(self):
        registry = PluginRegistry()
        metadata = create_test_metadata("plugin1", version="1.2.3")
        registry.register(metadata)

        result = registry.get_metadata("plugin1")
        assert result.plugin_id == "plugin1"
        assert result.version == "1.2.3"


# =====================================================================
# 版本兼容性测试
# =====================================================================
class TestVersionCompatibility:
    def test_check_plugin_version_true(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("plugin1", version="1.5.0"))

        assert registry.check_plugin_version("plugin1", ">=1.0.0") is True
        assert registry.check_plugin_version("plugin1", "^1.0.0") is True
        assert registry.check_plugin_version("plugin1", "~1.5.0") is True

    def test_check_plugin_version_false(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("plugin1", version="1.5.0"))

        assert registry.check_plugin_version("plugin1", ">=2.0.0") is False
        assert registry.check_plugin_version("plugin1", "<1.0.0") is False

    def test_check_plugin_version_not_found_raises(self):
        registry = PluginRegistry()
        with pytest.raises(PluginNotFoundError):
            registry.check_plugin_version("nonexistent", ">=1.0.0")

    def test_check_and_enable_success(self):
        registry = PluginRegistry()
        registry.register(
            create_test_metadata(
                "plugin1", version="1.5.0", capabilities=["import", "export"]
            )
        )

        runtime_info = registry.check_and_enable(
            "plugin1",
            required_version=">=1.0.0",
            required_capabilities=["import"],
        )
        assert runtime_info.status == PluginStatus.ENABLED

    def test_check_and_enable_version_fails(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("plugin1", version="1.5.0"))

        with pytest.raises(PluginVersionError):
            registry.check_and_enable("plugin1", required_version=">=2.0.0")

    def test_check_and_enable_capability_fails(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("plugin1", version="1.5.0", capabilities=["import"]))

        with pytest.raises(PluginCapabilityError) as exc_info:
            registry.check_and_enable(
                "plugin1",
                required_version=">=1.0.0",
                required_capabilities=["export"],
            )
        assert exc_info.value.missing_capability == "export"

    def test_check_and_enable_no_capabilities(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("plugin1", version="1.5.0"))

        runtime_info = registry.check_and_enable(
            "plugin1", required_version=">=1.0.0"
        )
        assert runtime_info.status == PluginStatus.ENABLED


# =====================================================================
# 统计信息测试
# =====================================================================
class TestPluginRegistryStats:
    def test_get_stats_empty(self):
        registry = PluginRegistry()
        stats = registry.get_stats()
        assert isinstance(stats, PluginRegistryStats)
        assert stats.total_plugins == 0
        assert stats.enabled_plugins == 0
        assert stats.disabled_plugins == 0
        assert stats.registered_plugins == 0
        assert stats.total_capabilities == 0

    def test_get_stats_mixed(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("p1", capabilities=["a", "b"]))
        registry.register(create_test_metadata("p2", capabilities=["b", "c"]))
        registry.register(create_test_metadata("p3"))
        registry.enable("p1")
        registry.enable("p2")
        registry.disable("p2")

        stats = registry.get_stats()
        assert stats.total_plugins == 3
        assert stats.enabled_plugins == 1
        assert stats.disabled_plugins == 1
        assert stats.registered_plugins == 1
        assert stats.total_capabilities == 3

    def test_stats_to_dict(self):
        stats = PluginRegistryStats(
            total_plugins=10,
            enabled_plugins=5,
            disabled_plugins=3,
            registered_plugins=2,
            total_capabilities=8,
        )
        d = stats.to_dict()
        assert d["total_plugins"] == 10
        assert d["enabled_plugins"] == 5
        assert d["disabled_plugins"] == 3
        assert d["registered_plugins"] == 2
        assert d["total_capabilities"] == 8

    def test_get_all_capabilities(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("p1", capabilities=["import", "export"]))
        registry.register(create_test_metadata("p2", capabilities=["import", "process"]))

        caps = registry.get_all_capabilities()
        assert caps == ["export", "import", "process"]

    def test_get_all_tags(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("p1", tags=["data", "io"]))
        registry.register(create_test_metadata("p2", tags=["data", "util"]))

        tags = registry.get_all_tags()
        assert tags == ["data", "io", "util"]

    def test_capability_index_cleanup_on_unregister(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("p1", capabilities=["cap1"]))
        registry.register(create_test_metadata("p2", capabilities=["cap1"]))

        assert "cap1" in registry.get_all_capabilities()

        registry.unregister("p1")
        assert "cap1" in registry.get_all_capabilities()

        registry.unregister("p2")
        assert "cap1" not in registry.get_all_capabilities()

    def test_tag_index_cleanup_on_unregister(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("p1", tags=["tag1"]))
        registry.register(create_test_metadata("p2", tags=["tag1"]))

        assert "tag1" in registry.get_all_tags()

        registry.unregister("p1")
        assert "tag1" in registry.get_all_tags()

        registry.unregister("p2")
        assert "tag1" not in registry.get_all_tags()


# =====================================================================
# 批量操作测试
# =====================================================================
class TestBatchOperations:
    def test_enable_all(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("p1"))
        registry.register(create_test_metadata("p2"))

        results = registry.enable_all()
        assert results == {"p1": True, "p2": True}
        assert registry.is_enabled("p1") is True
        assert registry.is_enabled("p2") is True

    def test_enable_all_with_some_enabled(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("p1"))
        registry.register(create_test_metadata("p2"))
        registry.enable("p1")

        results = registry.enable_all()
        assert results["p1"] is False
        assert results["p2"] is True

    def test_disable_all(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("p1"))
        registry.register(create_test_metadata("p2"))
        registry.enable_all()

        results = registry.disable_all()
        assert results == {"p1": True, "p2": True}
        assert registry.get_status("p1") == PluginStatus.DISABLED
        assert registry.get_status("p2") == PluginStatus.DISABLED

    def test_disable_all_with_some_disabled(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("p1"))
        registry.register(create_test_metadata("p2"))
        registry.enable_all()
        registry.disable("p1")

        results = registry.disable_all()
        assert results["p1"] is False
        assert results["p2"] is True

    def test_disable_all_with_registered(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("p1"))

        results = registry.disable_all()
        assert results["p1"] is False
        assert registry.get_status("p1") == PluginStatus.REGISTERED


# =====================================================================
# 索引更新测试
# =====================================================================
class TestIndexUpdates:
    def test_capability_index_on_register(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("p1", capabilities=["cap1", "cap2"]))

        assert registry.find_by_capability("cap1", enabled_only=False)[0].metadata.plugin_id == "p1"
        assert registry.find_by_capability("cap2", enabled_only=False)[0].metadata.plugin_id == "p1"

    def test_tag_index_on_register(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("p1", tags=["tag1", "tag2"]))

        assert registry.find_by_tag("tag1", enabled_only=False)[0].metadata.plugin_id == "p1"
        assert registry.find_by_tag("tag2", enabled_only=False)[0].metadata.plugin_id == "p1"

    def test_index_update_on_metadata_update(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("p1", capabilities=["old_cap"], tags=["old_tag"]))

        new_metadata = create_test_metadata(
            "p1", capabilities=["new_cap"], tags=["new_tag"]
        )
        registry.update_metadata("p1", new_metadata)

        assert len(registry.find_by_capability("old_cap", enabled_only=False)) == 0
        assert len(registry.find_by_capability("new_cap", enabled_only=False)) == 1
        assert len(registry.find_by_tag("old_tag", enabled_only=False)) == 0
        assert len(registry.find_by_tag("new_tag", enabled_only=False)) == 1


# =====================================================================
# 魔法方法测试
# =====================================================================
class TestMagicMethods:
    def test_contains(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("p1"))

        assert "p1" in registry
        assert "p2" not in registry

    def test_len(self):
        registry = PluginRegistry()
        assert len(registry) == 0

        registry.register(create_test_metadata("p1"))
        assert len(registry) == 1

        registry.register(create_test_metadata("p2"))
        assert len(registry) == 2

    def test_iter(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("p2"))
        registry.register(create_test_metadata("p1"))
        registry.register(create_test_metadata("p3"))

        ids = list(iter(registry))
        assert ids == ["p1", "p2", "p3"]


# =====================================================================
# 线程安全测试
# =====================================================================
class TestThreadSafety:
    def test_concurrent_registration(self):
        registry = PluginRegistry()
        errors = []

        def register_plugin(start, end):
            try:
                for i in range(start, end):
                    metadata = create_test_metadata(f"plugin_{i}")
                    registry.register(metadata)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=register_plugin, args=(i * 25, (i + 1) * 25))
            for i in range(4)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(registry) == 100

    def test_concurrent_enable_disable(self):
        registry = PluginRegistry()
        for i in range(10):
            registry.register(create_test_metadata(f"plugin_{i}"))

        errors = []

        def toggle_plugins():
            try:
                for i in range(10):
                    plugin_id = f"plugin_{i}"
                    try:
                        registry.enable(plugin_id)
                    except PluginStateError:
                        pass
                    try:
                        registry.disable(plugin_id)
                    except PluginStateError:
                        pass
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=toggle_plugins) for _ in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    def test_concurrent_read_write(self):
        registry = PluginRegistry()
        for i in range(50):
            registry.register(
                create_test_metadata(
                    f"plugin_{i}", capabilities=[f"cap_{i % 5}"], tags=[f"tag_{i % 3}"]
                )
            )

        errors = []

        def reader():
            try:
                for _ in range(100):
                    registry.list_plugins(status=PluginStatus.REGISTERED)
                    registry.find_by_capability("cap_0", enabled_only=False)
                    registry.find_by_tag("tag_0", enabled_only=False)
                    registry.get_stats()
            except Exception as e:
                errors.append(e)

        def writer():
            try:
                for i in range(50):
                    plugin_id = f"plugin_{i}"
                    try:
                        registry.enable(plugin_id)
                    except PluginStateError:
                        pass
            except Exception as e:
                errors.append(e)

        threads = []
        for _ in range(3):
            threads.append(threading.Thread(target=reader))
            threads.append(threading.Thread(target=writer))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


# =====================================================================
# 综合场景测试
# =====================================================================
class TestIntegrationScenarios:
    def test_plugin_lifecycle(self):
        registry = PluginRegistry()

        metadata = create_test_metadata(
            "data_importer",
            version="1.2.0",
            description="数据导入插件",
            capabilities=["data_import", "validation"],
            tags=["data", "import"],
        )

        runtime_info = registry.register(metadata)
        assert runtime_info.status == PluginStatus.REGISTERED

        registry.enable("data_importer", required_version=">=1.0.0")
        assert registry.is_enabled("data_importer")

        importers = registry.find_by_capability("data_import")
        assert len(importers) == 1
        assert importers[0].metadata.plugin_id == "data_importer"

        data_plugins = registry.find_by_tag("data")
        assert len(data_plugins) == 1

        all_caps = registry.find_by_capabilities(["data_import", "validation"])
        assert len(all_caps) == 1

        registry.disable("data_importer")
        assert registry.is_enabled("data_importer") is False

        importers = registry.find_by_capability("data_import")
        assert len(importers) == 0

        registry.unregister("data_importer")
        assert len(registry) == 0

    def test_multiple_plugins_with_same_capability(self):
        registry = PluginRegistry()

        registry.register(
            create_test_metadata(
                "csv_importer", capabilities=["data_import"], tags=["csv"]
            )
        )
        registry.register(
            create_test_metadata(
                "json_importer", capabilities=["data_import"], tags=["json"]
            )
        )
        registry.register(
            create_test_metadata(
                "xml_importer", capabilities=["data_import"], tags=["xml"]
            )
        )

        registry.enable_all()

        all_importers = registry.find_by_capability("data_import")
        assert len(all_importers) == 3

        csv_importers = registry.find_by_capabilities(["data_import"], match_all=True)
        csv_importers = [p for p in csv_importers if p.metadata.has_tag("csv")]
        assert len(csv_importers) == 1
        assert csv_importers[0].metadata.plugin_id == "csv_importer"

    def test_version_compatibility_checks(self):
        registry = PluginRegistry()

        registry.register(create_test_metadata("api_v1", version="1.0.0", capabilities=["api"]))
        registry.register(create_test_metadata("api_v2", version="2.0.0", capabilities=["api"]))
        registry.register(create_test_metadata("api_v1_5", version="1.5.0", capabilities=["api"]))

        registry.enable_all()

        v1_compatible = registry.find_by_capabilities(["api"], enabled_only=True)
        v1_compatible = [
            p for p in v1_compatible if p.metadata.satisfies_version("^1.0.0")
        ]
        assert len(v1_compatible) == 2
        ids = [p.metadata.plugin_id for p in v1_compatible]
        assert "api_v1" in ids
        assert "api_v1_5" in ids
        assert "api_v2" not in ids

    def test_check_and_enable_flow(self):
        registry = PluginRegistry()

        registry.register(
            create_test_metadata(
                "payment_gateway",
                version="2.1.0",
                capabilities=["payment_processing", "refund"],
            )
        )

        runtime_info = registry.check_and_enable(
            "payment_gateway",
            required_version=">=2.0.0,<3.0.0",
            required_capabilities=["payment_processing", "refund"],
        )

        assert runtime_info.status == PluginStatus.ENABLED
        assert runtime_info.enable_count == 1

        with pytest.raises(PluginCapabilityError):
            registry.check_and_enable(
                "payment_gateway",
                required_version=">=2.0.0",
                required_capabilities=["subscription"],
            )


# =====================================================================
# 依赖校验测试
# =====================================================================
class TestPluginDependencyValidation:
    def test_enable_with_dependency_not_registered_raises(self):
        registry = PluginRegistry()
        registry.register(
            create_test_metadata(
                "plugin_a",
                dependencies={"plugin_b": ">=1.0.0"},
            )
        )

        with pytest.raises(PluginDependencyError) as exc_info:
            registry.enable("plugin_a")

        assert exc_info.value.plugin_id == "plugin_a"
        assert exc_info.value.dependency_id == "plugin_b"
        assert "未注册" in exc_info.value.reason

    def test_enable_with_dependency_not_enabled_raises(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("plugin_b", version="1.2.0"))
        registry.register(
            create_test_metadata(
                "plugin_a",
                dependencies={"plugin_b": ">=1.0.0"},
            )
        )

        with pytest.raises(PluginDependencyError) as exc_info:
            registry.enable("plugin_a")

        assert exc_info.value.plugin_id == "plugin_a"
        assert exc_info.value.dependency_id == "plugin_b"
        assert "未启用" in exc_info.value.reason
        assert "REGISTERED" in exc_info.value.reason

    def test_enable_with_dependency_disabled_raises(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("plugin_b", version="1.2.0"))
        registry.register(
            create_test_metadata(
                "plugin_a",
                dependencies={"plugin_b": ">=1.0.0"},
            )
        )
        registry.enable("plugin_b")
        registry.disable("plugin_b")

        with pytest.raises(PluginDependencyError) as exc_info:
            registry.enable("plugin_a")

        assert exc_info.value.plugin_id == "plugin_a"
        assert exc_info.value.dependency_id == "plugin_b"
        assert "未启用" in exc_info.value.reason
        assert "DISABLED" in exc_info.value.reason

    def test_enable_with_dependency_version_mismatch_raises(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("plugin_b", version="0.8.0"))
        registry.register(
            create_test_metadata(
                "plugin_a",
                dependencies={"plugin_b": ">=1.0.0"},
            )
        )
        registry.enable("plugin_b")

        with pytest.raises(PluginDependencyError) as exc_info:
            registry.enable("plugin_a")

        assert exc_info.value.plugin_id == "plugin_a"
        assert exc_info.value.dependency_id == "plugin_b"
        assert "版本不满足要求" in exc_info.value.reason
        assert "0.8.0" in exc_info.value.reason
        assert ">=1.0.0" in exc_info.value.reason

    def test_enable_with_satisfied_dependencies_succeeds(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("plugin_b", version="1.5.0"))
        registry.register(
            create_test_metadata(
                "plugin_a",
                dependencies={"plugin_b": ">=1.0.0,<2.0.0"},
            )
        )
        registry.enable("plugin_b")

        runtime_info = registry.enable("plugin_a")
        assert runtime_info.status == PluginStatus.ENABLED
        assert runtime_info.enable_count == 1

    def test_enable_with_multiple_dependencies_all_satisfied(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("dep1", version="2.0.0"))
        registry.register(create_test_metadata("dep2", version="1.5.0"))
        registry.register(
            create_test_metadata(
                "plugin_a",
                dependencies={
                    "dep1": "^2.0.0",
                    "dep2": "~1.5.0",
                },
            )
        )
        registry.enable("dep1")
        registry.enable("dep2")

        runtime_info = registry.enable("plugin_a")
        assert runtime_info.status == PluginStatus.ENABLED

    def test_enable_with_multiple_dependencies_one_fails(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("dep1", version="2.0.0"))
        registry.register(create_test_metadata("dep2", version="0.5.0"))
        registry.register(
            create_test_metadata(
                "plugin_a",
                dependencies={
                    "dep1": "^2.0.0",
                    "dep2": ">=1.0.0",
                },
            )
        )
        registry.enable("dep1")
        registry.enable("dep2")

        with pytest.raises(PluginDependencyError) as exc_info:
            registry.enable("plugin_a")

        assert exc_info.value.dependency_id == "dep2"

    def test_enable_no_dependencies_succeeds(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("standalone"))

        runtime_info = registry.enable("standalone")
        assert runtime_info.status == PluginStatus.ENABLED

    def test_enable_with_empty_dependencies_succeeds(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("standalone", dependencies={}))

        runtime_info = registry.enable("standalone")
        assert runtime_info.status == PluginStatus.ENABLED

    def test_chain_dependencies_enable_in_correct_order(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("level1"))
        registry.register(
            create_test_metadata("level2", dependencies={"level1": ">=1.0.0"})
        )
        registry.register(
            create_test_metadata(
                "level3",
                dependencies={"level2": ">=1.0.0"},
            )
        )

        with pytest.raises(PluginDependencyError):
            registry.enable("level3")

        registry.enable("level1")
        with pytest.raises(PluginDependencyError):
            registry.enable("level3")

        registry.enable("level2")
        runtime_info = registry.enable("level3")
        assert runtime_info.status == PluginStatus.ENABLED

    def test_check_and_enable_triggers_dependency_check(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("plugin_b", version="1.0.0"))
        registry.register(
            create_test_metadata(
                "plugin_a",
                version="2.0.0",
                capabilities=["api"],
                dependencies={"plugin_b": ">=1.0.0"},
            )
        )

        with pytest.raises(PluginDependencyError):
            registry.check_and_enable(
                "plugin_a",
                required_version=">=2.0.0",
                required_capabilities=["api"],
            )

        registry.enable("plugin_b")
        runtime_info = registry.check_and_enable(
            "plugin_a",
            required_version=">=2.0.0",
            required_capabilities=["api"],
        )
        assert runtime_info.status == PluginStatus.ENABLED

    def test_plugin_dependency_error_attributes(self):
        error = PluginDependencyError(
            plugin_id="plugin_a",
            dependency_id="plugin_b",
            reason="测试原因",
        )
        assert error.plugin_id == "plugin_a"
        assert error.dependency_id == "plugin_b"
        assert error.reason == "测试原因"
        assert "plugin_a" in str(error)
        assert "plugin_b" in str(error)
        assert "测试原因" in str(error)


# =====================================================================
# 异常处理契约测试
# =====================================================================
class TestExceptionHandlingContract:
    def test_enable_all_propagates_dependency_error(self):
        registry = PluginRegistry()
        registry.register(
            create_test_metadata(
                "plugin_a",
                dependencies={"nonexistent": ">=1.0.0"},
            )
        )

        with pytest.raises(PluginDependencyError):
            registry.enable_all()

    def test_enable_all_propagates_version_error(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("plugin_a", version="0.5.0"))

        with patch.object(
            PluginRegistry, "enable", side_effect=PluginVersionError("plugin_a", "0.5.0", ">=1.0.0")
        ):
            with pytest.raises(PluginVersionError) as exc_info:
                registry.enable_all()
            assert exc_info.value.plugin_id == "plugin_a"
            assert exc_info.value.plugin_version == "0.5.0"
            assert exc_info.value.required_version == ">=1.0.0"

    def test_enable_all_only_catches_plugin_state_error(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("p1"))
        registry.register(create_test_metadata("p2"))
        registry.enable("p1")

        with patch.object(
            PluginRegistry, "enable", side_effect=MemoryError("系统内存不足")
        ):
            with pytest.raises(MemoryError) as exc_info:
                registry.enable_all()
            assert "系统内存不足" in str(exc_info.value)

    def test_disable_all_propagates_system_error(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("p1"))
        registry.enable("p1")

        with patch.object(
            PluginRegistry, "disable", side_effect=RuntimeError("系统错误")
        ):
            with pytest.raises(RuntimeError) as exc_info:
                registry.disable_all()
            assert "系统错误" in str(exc_info.value)

    def test_enable_all_still_returns_dict_on_success(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("p1"))
        registry.register(create_test_metadata("p2"))
        registry.enable("p1")

        results = registry.enable_all()
        assert results == {"p1": False, "p2": True}
        assert registry.is_enabled("p2") is True

    def test_disable_all_still_returns_dict_on_success(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("p1"))
        registry.register(create_test_metadata("p2"))
        registry.enable("p1")

        results = registry.disable_all()
        assert results == {"p1": True, "p2": False}
        assert registry.get_status("p1") == PluginStatus.DISABLED


# =====================================================================
# set_status 统一入口测试
# =====================================================================
class TestSetStatusUnifiedEntry:
    def test_set_status_enabled_delegates_to_enable(self):
        registry = PluginRegistry()
        registry.register(
            create_test_metadata(
                "plugin_a",
                version="1.5.0",
                dependencies={"plugin_b": ">=1.0.0"},
            )
        )
        registry.register(create_test_metadata("plugin_b", version="1.2.0"))

        with pytest.raises(PluginDependencyError):
            registry.set_status("plugin_a", PluginStatus.ENABLED)

        registry.enable("plugin_b")
        runtime_info = registry.set_status("plugin_a", PluginStatus.ENABLED)
        assert runtime_info.status == PluginStatus.ENABLED
        assert runtime_info.enable_count == 1

    def test_set_status_enabled_performs_version_check(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("plugin_a", version="1.5.0"))

        with patch.object(
            PluginRegistry, "enable", wraps=registry.enable
        ) as mock_enable:
            registry.set_status("plugin_a", PluginStatus.ENABLED)
            mock_enable.assert_called_once_with("plugin_a")

    def test_set_status_enabled_on_already_enabled_raises(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("plugin_a"))
        registry.enable("plugin_a")

        with pytest.raises(PluginStateError) as exc_info:
            registry.set_status("plugin_a", PluginStatus.ENABLED)

        assert exc_info.value.operation == "enable"
        assert exc_info.value.current_status == PluginStatus.ENABLED.value

    def test_set_status_disabled_delegates_to_disable(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("plugin_a"))
        registry.enable("plugin_a")

        with patch.object(
            PluginRegistry, "disable", wraps=registry.disable
        ) as mock_disable:
            registry.set_status("plugin_a", PluginStatus.DISABLED)
            mock_disable.assert_called_once_with("plugin_a")

    def test_set_status_disabled_on_registered_raises(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("plugin_a"))

        with pytest.raises(PluginStateError) as exc_info:
            registry.set_status("plugin_a", PluginStatus.DISABLED)

        assert exc_info.value.operation == "disable"
        assert exc_info.value.current_status == PluginStatus.REGISTERED.value

    def test_set_status_disabled_on_disabled_raises(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("plugin_a"))
        registry.enable("plugin_a")
        registry.disable("plugin_a")

        with pytest.raises(PluginStateError) as exc_info:
            registry.set_status("plugin_a", PluginStatus.DISABLED)

        assert exc_info.value.operation == "disable"
        assert exc_info.value.current_status == PluginStatus.DISABLED.value

    def test_set_status_registered_does_not_need_validation(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("plugin_a"))
        registry.enable("plugin_a")

        runtime_info = registry.set_status("plugin_a", PluginStatus.REGISTERED)
        assert runtime_info.status == PluginStatus.REGISTERED

    def test_set_status_registered_on_registered_succeeds(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("plugin_a"))

        runtime_info = registry.set_status("plugin_a", PluginStatus.REGISTERED)
        assert runtime_info.status == PluginStatus.REGISTERED

    def test_set_status_unified_side_effects(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("plugin_a"))

        r1 = registry.set_status("plugin_a", PluginStatus.ENABLED)
        assert r1.enable_count == 1
        assert r1.enabled_at is not None

        r2 = registry.set_status("plugin_a", PluginStatus.DISABLED)
        assert r2.disabled_at is not None

        r3 = registry.set_status("plugin_a", PluginStatus.ENABLED)
        assert r3.enable_count == 2

    def test_set_status_unknown_status_raises(self):
        registry = PluginRegistry()
        registry.register(create_test_metadata("plugin_a"))

        with pytest.raises(ValueError, match="未知的插件状态"):
            registry.set_status("plugin_a", "INVALID_STATUS")

    def test_set_status_enabled_with_required_version(self):
        registry = PluginRegistry()
        registry.register(
            create_test_metadata(
                "plugin_a",
                version="1.5.0",
                dependencies={"plugin_b": ">=1.0.0"},
            )
        )
        registry.register(create_test_metadata("plugin_b", version="1.2.0"))
        registry.enable("plugin_b")

        with patch.object(
            PluginRegistry, "enable", wraps=registry.enable
        ) as mock_enable:
            registry.set_status("plugin_a", PluginStatus.ENABLED)
            mock_enable.assert_called_once_with("plugin_a")

