import pytest

from solocoder_4_py.plugin_registry import (
    DEFAULT_PLUGIN_VERSION,
    PluginMetadata,
    PluginVersionError,
)


# =====================================================================
# PluginMetadata 测试
# =====================================================================
class TestPluginMetadata:
    def test_create_metadata_minimal(self):
        metadata = PluginMetadata(plugin_id="test.plugin", name="Test Plugin")
        assert metadata.plugin_id == "test.plugin"
        assert metadata.name == "Test Plugin"
        assert metadata.version == DEFAULT_PLUGIN_VERSION
        assert metadata.description == ""
        assert metadata.author == ""
        assert metadata.capabilities == []
        assert metadata.dependencies == {}
        assert metadata.tags == []
        assert metadata.extra == {}

    def test_create_metadata_full(self):
        metadata = PluginMetadata(
            plugin_id="my.plugin",
            name="My Plugin",
            version="1.2.3",
            description="A test plugin",
            author="John Doe",
            capabilities=["data_import", "data_export"],
            dependencies={"core": ">=1.0.0", "utils": "^2.0.0"},
            tags=["data", "io"],
            extra={"config_path": "/etc/plugin"},
        )
        assert metadata.plugin_id == "my.plugin"
        assert metadata.name == "My Plugin"
        assert metadata.version == "1.2.3"
        assert metadata.description == "A test plugin"
        assert metadata.author == "John Doe"
        assert metadata.capabilities == ["data_import", "data_export"]
        assert metadata.dependencies == {"core": ">=1.0.0", "utils": "^2.0.0"}
        assert metadata.tags == ["data", "io"]
        assert metadata.extra == {"config_path": "/etc/plugin"}

    def test_empty_plugin_id_raises_error(self):
        with pytest.raises(ValueError, match="plugin_id 不能为空"):
            PluginMetadata(plugin_id="", name="Test")

    def test_empty_name_raises_error(self):
        with pytest.raises(ValueError, match="name 不能为空"):
            PluginMetadata(plugin_id="test", name="")

    def test_invalid_version_format_raises_error(self):
        with pytest.raises(ValueError, match="版本号格式不正确"):
            PluginMetadata(plugin_id="test", name="Test", version="invalid")

    def test_valid_version_formats(self):
        valid_versions = [
            "1.0.0",
            "0.1.0",
            "2.10.3",
            "1.0.0-alpha",
            "1.0.0-alpha.1",
            "1.0.0-0.3.7",
            "1.0.0-x.7.z.92",
            "1.0.0+build.1",
            "1.0.0-beta+exp.sha.5114f85",
        ]
        for version in valid_versions:
            metadata = PluginMetadata(plugin_id="test", name="Test", version=version)
            assert metadata.version == version

    def test_capabilities_list_independence(self):
        caps = ["cap1", "cap2"]
        metadata = PluginMetadata(plugin_id="test", name="Test", capabilities=caps)
        caps.append("cap3")
        assert metadata.capabilities == ["cap1", "cap2"]

    def test_tags_list_independence(self):
        tags = ["tag1", "tag2"]
        metadata = PluginMetadata(plugin_id="test", name="Test", tags=tags)
        tags.append("tag3")
        assert metadata.tags == ["tag1", "tag2"]

    # ------------------------------------------------------------
    # 版本比较测试
    # ------------------------------------------------------------
    def test_compare_versions_equal(self):
        assert PluginMetadata._compare_versions("1.0.0", "1.0.0") == 0

    def test_compare_versions_greater_major(self):
        assert PluginMetadata._compare_versions("2.0.0", "1.0.0") == 1

    def test_compare_versions_less_major(self):
        assert PluginMetadata._compare_versions("1.0.0", "2.0.0") == -1

    def test_compare_versions_greater_minor(self):
        assert PluginMetadata._compare_versions("1.1.0", "1.0.0") == 1

    def test_compare_versions_less_patch(self):
        assert PluginMetadata._compare_versions("1.0.0", "1.0.1") == -1

    def test_compare_versions_pre_release_less_than_release(self):
        assert PluginMetadata._compare_versions("1.0.0-alpha", "1.0.0") == -1

    def test_compare_versions_pre_release_order(self):
        assert PluginMetadata._compare_versions("1.0.0-alpha", "1.0.0-beta") == -1
        assert PluginMetadata._compare_versions("1.0.0-beta", "1.0.0-rc.1") == -1

    def test_compare_versions_ignores_build_metadata(self):
        assert PluginMetadata._compare_versions("1.0.0+build1", "1.0.0+build2") == 0

    # ------------------------------------------------------------
    # 版本要求满足测试
    # ------------------------------------------------------------
    def test_satisfies_version_exact_equal(self):
        metadata = PluginMetadata(plugin_id="test", name="Test", version="1.2.3")
        assert metadata.satisfies_version("1.2.3") is True
        assert metadata.satisfies_version("==1.2.3") is True

    def test_satisfies_version_exact_not_equal(self):
        metadata = PluginMetadata(plugin_id="test", name="Test", version="1.2.3")
        assert metadata.satisfies_version("1.2.4") is False
        assert metadata.satisfies_version("==1.2.4") is False

    def test_satisfies_version_not_equal(self):
        metadata = PluginMetadata(plugin_id="test", name="Test", version="1.2.3")
        assert metadata.satisfies_version("!=1.2.3") is False
        assert metadata.satisfies_version("!=1.2.4") is True

    def test_satisfies_version_greater_than(self):
        metadata = PluginMetadata(plugin_id="test", name="Test", version="1.2.3")
        assert metadata.satisfies_version(">1.2.0") is True
        assert metadata.satisfies_version(">1.2.3") is False
        assert metadata.satisfies_version(">2.0.0") is False

    def test_satisfies_version_greater_equal(self):
        metadata = PluginMetadata(plugin_id="test", name="Test", version="1.2.3")
        assert metadata.satisfies_version(">=1.2.3") is True
        assert metadata.satisfies_version(">=1.2.0") is True
        assert metadata.satisfies_version(">=1.2.4") is False

    def test_satisfies_version_less_than(self):
        metadata = PluginMetadata(plugin_id="test", name="Test", version="1.2.3")
        assert metadata.satisfies_version("<2.0.0") is True
        assert metadata.satisfies_version("<1.2.3") is False
        assert metadata.satisfies_version("<1.0.0") is False

    def test_satisfies_version_less_equal(self):
        metadata = PluginMetadata(plugin_id="test", name="Test", version="1.2.3")
        assert metadata.satisfies_version("<=1.2.3") is True
        assert metadata.satisfies_version("<=2.0.0") is True
        assert metadata.satisfies_version("<=1.2.2") is False

    def test_satisfies_version_tilde_range(self):
        metadata = PluginMetadata(plugin_id="test", name="Test", version="1.2.3")
        assert metadata.satisfies_version("~1.2.0") is True
        assert metadata.satisfies_version("~1.2.3") is True
        assert metadata.satisfies_version("~1.3.0") is False
        assert metadata.satisfies_version("~1.1.0") is False

    def test_satisfies_version_caret_range(self):
        metadata = PluginMetadata(plugin_id="test", name="Test", version="1.2.3")
        assert metadata.satisfies_version("^1.0.0") is True
        assert metadata.satisfies_version("^1.2.0") is True
        assert metadata.satisfies_version("^2.0.0") is False

    def test_satisfies_version_caret_range_zero_major(self):
        metadata = PluginMetadata(plugin_id="test", name="Test", version="0.2.3")
        assert metadata.satisfies_version("^0.2.0") is True
        assert metadata.satisfies_version("^0.3.0") is False
        assert metadata.satisfies_version("^0.2.3") is True
        assert metadata.satisfies_version("^0.2.4") is False

    def test_satisfies_version_caret_range_zero_major_minor(self):
        metadata = PluginMetadata(plugin_id="test", name="Test", version="0.0.3")
        assert metadata.satisfies_version("^0.0.3") is True
        assert metadata.satisfies_version("^0.0.2") is False
        assert metadata.satisfies_version("^0.0.4") is False

    def test_satisfies_version_multiple_constraints(self):
        metadata = PluginMetadata(plugin_id="test", name="Test", version="1.5.2")
        assert metadata.satisfies_version(">=1.0.0,<2.0.0") is True
        assert metadata.satisfies_version(">=1.5.0,<1.6.0") is True
        assert metadata.satisfies_version(">=1.0.0,<=1.5.2") is True
        assert metadata.satisfies_version(">=2.0.0,<3.0.0") is False
        assert metadata.satisfies_version(">=1.0.0,<1.5.0") is False

    def test_satisfies_version_multiple_constraints_with_spaces(self):
        metadata = PluginMetadata(plugin_id="test", name="Test", version="2.1.0")
        assert metadata.satisfies_version(">=2.0.0, <3.0.0") is True
        assert metadata.satisfies_version(" >=1.0.0 , <3.0.0 ") is True

    def test_satisfies_version_three_or_more_constraints(self):
        metadata = PluginMetadata(plugin_id="test", name="Test", version="1.5.2")
        assert metadata.satisfies_version(">=1.0.0,<2.0.0,!=1.6.0") is True
        assert metadata.satisfies_version(">=1.5.0,<1.6.0,>=1.5.2") is True
        assert metadata.satisfies_version(">=1.0.0,<2.0.0,!=1.5.2") is False

    # ------------------------------------------------------------
    # check_compatibility 测试
    # ------------------------------------------------------------
    def test_check_compatibility_passes(self):
        metadata = PluginMetadata(plugin_id="test", name="Test", version="1.2.3")
        metadata.check_compatibility(">=1.0.0")

    def test_check_compatibility_raises(self):
        metadata = PluginMetadata(plugin_id="test", name="Test", version="1.2.3")
        with pytest.raises(PluginVersionError) as exc_info:
            metadata.check_compatibility(">=2.0.0")
        assert exc_info.value.plugin_id == "test"
        assert exc_info.value.plugin_version == "1.2.3"
        assert exc_info.value.required_version == ">=2.0.0"

    # ------------------------------------------------------------
    # 能力检查测试
    # ------------------------------------------------------------
    def test_has_capability_true(self):
        metadata = PluginMetadata(
            plugin_id="test", name="Test", capabilities=["import", "export"]
        )
        assert metadata.has_capability("import") is True
        assert metadata.has_capability("export") is True

    def test_has_capability_false(self):
        metadata = PluginMetadata(plugin_id="test", name="Test", capabilities=["import"])
        assert metadata.has_capability("export") is False

    def test_has_all_capabilities_true(self):
        metadata = PluginMetadata(
            plugin_id="test", name="Test", capabilities=["a", "b", "c"]
        )
        assert metadata.has_all_capabilities(["a", "b"]) is True
        assert metadata.has_all_capabilities(["a", "b", "c"]) is True

    def test_has_all_capabilities_false(self):
        metadata = PluginMetadata(plugin_id="test", name="Test", capabilities=["a", "b"])
        assert metadata.has_all_capabilities(["a", "c"]) is False
        assert metadata.has_all_capabilities(["d"]) is False

    def test_has_all_capabilities_empty_list(self):
        metadata = PluginMetadata(plugin_id="test", name="Test", capabilities=["a"])
        assert metadata.has_all_capabilities([]) is True

    def test_has_any_capability_true(self):
        metadata = PluginMetadata(plugin_id="test", name="Test", capabilities=["a", "b"])
        assert metadata.has_any_capability(["a", "c"]) is True
        assert metadata.has_any_capability(["b"]) is True

    def test_has_any_capability_false(self):
        metadata = PluginMetadata(plugin_id="test", name="Test", capabilities=["a", "b"])
        assert metadata.has_any_capability(["c", "d"]) is False

    def test_has_any_capability_empty_list(self):
        metadata = PluginMetadata(plugin_id="test", name="Test", capabilities=["a"])
        assert metadata.has_any_capability([]) is False

    # ------------------------------------------------------------
    # 标签检查测试
    # ------------------------------------------------------------
    def test_has_tag_true(self):
        metadata = PluginMetadata(plugin_id="test", name="Test", tags=["data", "io"])
        assert metadata.has_tag("data") is True
        assert metadata.has_tag("io") is True

    def test_has_tag_false(self):
        metadata = PluginMetadata(plugin_id="test", name="Test", tags=["data"])
        assert metadata.has_tag("io") is False

    # ------------------------------------------------------------
    # 序列化/反序列化测试
    # ------------------------------------------------------------
    def test_to_dict(self):
        metadata = PluginMetadata(
            plugin_id="my.plugin",
            name="My Plugin",
            version="1.2.3",
            description="A test plugin",
            author="John Doe",
            capabilities=["data_import"],
            dependencies={"core": ">=1.0.0"},
            tags=["data"],
            extra={"key": "value"},
        )
        data = metadata.to_dict()
        assert data["plugin_id"] == "my.plugin"
        assert data["name"] == "My Plugin"
        assert data["version"] == "1.2.3"
        assert data["description"] == "A test plugin"
        assert data["author"] == "John Doe"
        assert data["capabilities"] == ["data_import"]
        assert data["dependencies"] == {"core": ">=1.0.0"}
        assert data["tags"] == ["data"]
        assert data["extra"] == {"key": "value"}

    def test_from_dict(self):
        data = {
            "plugin_id": "my.plugin",
            "name": "My Plugin",
            "version": "1.2.3",
            "description": "A test plugin",
            "author": "John Doe",
            "capabilities": ["data_import"],
            "dependencies": {"core": ">=1.0.0"},
            "tags": ["data"],
            "extra": {"key": "value"},
        }
        metadata = PluginMetadata.from_dict(data)
        assert metadata.plugin_id == "my.plugin"
        assert metadata.name == "My Plugin"
        assert metadata.version == "1.2.3"
        assert metadata.description == "A test plugin"
        assert metadata.author == "John Doe"
        assert metadata.capabilities == ["data_import"]
        assert metadata.dependencies == {"core": ">=1.0.0"}
        assert metadata.tags == ["data"]
        assert metadata.extra == {"key": "value"}

    def test_from_dict_defaults(self):
        data = {"plugin_id": "test", "name": "Test"}
        metadata = PluginMetadata.from_dict(data)
        assert metadata.version == DEFAULT_PLUGIN_VERSION
        assert metadata.description == ""
        assert metadata.author == ""
        assert metadata.capabilities == []
        assert metadata.dependencies == {}
        assert metadata.tags == []
        assert metadata.extra == {}

    def test_roundtrip_dict(self):
        original = PluginMetadata(
            plugin_id="my.plugin",
            name="My Plugin",
            version="1.2.3",
            capabilities=["a", "b"],
            tags=["t1"],
        )
        restored = PluginMetadata.from_dict(original.to_dict())
        assert original.plugin_id == restored.plugin_id
        assert original.name == restored.name
        assert original.version == restored.version
        assert original.capabilities == restored.capabilities
        assert original.tags == restored.tags
