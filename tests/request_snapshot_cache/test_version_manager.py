import pytest

from solocoder_4_py.request_snapshot_cache import VersionManager


class TestVersionManager:
    def test_initial_version_is_zero(self):
        vm = VersionManager()
        assert vm.get_entity_version("users") == 0

    def test_bump_entity_version(self):
        vm = VersionManager()
        assert vm.bump_entity_version("users") == 1
        assert vm.bump_entity_version("users") == 2
        assert vm.get_entity_version("users") == 2

    def test_get_entities_version(self):
        vm = VersionManager()
        vm.bump_entity_version("users")
        vm.bump_entity_version("users")
        vm.bump_entity_version("orders")

        versions = vm.get_entities_version(["users", "orders", "products"])
        assert versions == {"users": 2, "orders": 1, "products": 0}

    def test_bump_entities_version(self):
        vm = VersionManager()
        result = vm.bump_entities_version(["users", "orders"])
        assert result == {"users": 1, "orders": 1}

        result = vm.bump_entities_version(["users", "products"])
        assert result == {"users": 2, "products": 1}

    def test_register_and_get_dependencies(self):
        vm = VersionManager()
        vm.register_cache_dependency("cache_1", ["users", "orders"])

        deps = vm.get_cache_dependencies("cache_1")
        assert deps == {"users", "orders"}

        deps_nonexistent = vm.get_cache_dependencies("nonexistent")
        assert deps_nonexistent == set()

    def test_unregister_cache(self):
        vm = VersionManager()
        vm.register_cache_dependency("cache_1", ["users", "orders"])
        vm.unregister_cache("cache_1")

        assert vm.get_cache_dependencies("cache_1") == set()

    def test_get_invalidated_caches(self):
        vm = VersionManager()
        vm.register_cache_dependency("cache_1", ["users", "orders"])
        vm.register_cache_dependency("cache_2", ["orders"])
        vm.register_cache_dependency("cache_3", ["products"])

        invalidated = vm.get_invalidated_caches(["orders"])
        assert invalidated == {"cache_1", "cache_2"}

        invalidated = vm.get_invalidated_caches(["users", "products"])
        assert invalidated == {"cache_1", "cache_3"}

    def test_invalidate_entity(self):
        vm = VersionManager()
        vm.register_cache_dependency("cache_1", ["users", "orders"])
        vm.register_cache_dependency("cache_2", ["orders"])

        invalidated = vm.invalidate_entity("orders")
        assert invalidated == {"cache_1", "cache_2"}

        assert vm.get_entity_version("orders") == 1
        assert vm.get_cache_dependencies("cache_1") == set()
        assert vm.get_cache_dependencies("cache_2") == set()

    def test_invalidate_entities(self):
        vm = VersionManager()
        vm.register_cache_dependency("cache_1", ["users"])
        vm.register_cache_dependency("cache_2", ["orders"])
        vm.register_cache_dependency("cache_3", ["products"])

        invalidated = vm.invalidate_entities(["users", "products"])
        assert invalidated == {"cache_1", "cache_3"}

        assert vm.get_entity_version("users") == 1
        assert vm.get_entity_version("orders") == 0
        assert vm.get_entity_version("products") == 1

    def test_version_signature(self):
        vm = VersionManager()
        vm.bump_entity_version("users")
        vm.bump_entity_version("users")
        vm.bump_entity_version("orders")

        sig = vm.get_version_signature(["orders", "users"])
        assert sig == "orders:1|users:2"

    def test_check_versions_valid(self):
        vm = VersionManager()
        vm.bump_entity_version("users")
        vm.bump_entity_version("orders")

        vm.register_cache_dependency("cache_1", ["users", "orders"])

        assert vm.check_versions_valid("cache_1", {"users": 1, "orders": 1}) is True

        vm.bump_entity_version("users")
        assert vm.check_versions_valid("cache_1", {"users": 1, "orders": 1}) is False

    def test_get_all_entities(self):
        vm = VersionManager()
        vm.bump_entity_version("users")
        vm.bump_entity_version("orders")
        vm.bump_entity_version("products")

        entities = vm.get_all_entities()
        assert entities == ["orders", "products", "users"]

    def test_get_all_cache_keys(self):
        vm = VersionManager()
        vm.register_cache_dependency("cache_1", ["users"])
        vm.register_cache_dependency("cache_2", ["orders"])
        vm.register_cache_dependency("cache_3", ["products"])

        keys = vm.get_all_cache_keys()
        assert keys == ["cache_1", "cache_2", "cache_3"]

    def test_clear(self):
        vm = VersionManager()
        vm.bump_entity_version("users")
        vm.register_cache_dependency("cache_1", ["users"])

        vm.clear()

        assert vm.get_entity_version("users") == 0
        assert vm.get_all_cache_keys() == []
        assert vm.get_all_entities() == []

    def test_get_stats(self):
        vm = VersionManager()
        vm.bump_entity_version("users")
        vm.bump_entity_version("orders")
        vm.register_cache_dependency("cache_1", ["users", "orders"])
        vm.register_cache_dependency("cache_2", ["users"])

        stats = vm.get_stats()
        assert stats == {
            "entity_count": 2,
            "cache_count": 2,
            "entity_to_cache_count": 2,
        }

    def test_unregister_updates_entity_to_caches(self):
        vm = VersionManager()
        vm.register_cache_dependency("cache_1", ["users"])
        vm.register_cache_dependency("cache_2", ["users"])

        vm.unregister_cache("cache_1")
        assert vm.get_invalidated_caches(["users"]) == {"cache_2"}

        vm.unregister_cache("cache_2")
        assert vm.get_invalidated_caches(["users"]) == set()

    def test_multiple_registration_overwrites(self):
        vm = VersionManager()
        vm.register_cache_dependency("cache_1", ["users"])
        vm.register_cache_dependency("cache_1", ["orders"])

        assert vm.get_cache_dependencies("cache_1") == {"orders"}
        assert vm.get_invalidated_caches(["users"]) == set()
        assert vm.get_invalidated_caches(["orders"]) == {"cache_1"}

    def test_invalidate_nonexistent_entity(self):
        vm = VersionManager()
        invalidated = vm.invalidate_entity("nonexistent")
        assert invalidated == set()
        assert vm.get_entity_version("nonexistent") == 1

    def test_unregister_nonexistent_cache(self):
        vm = VersionManager()
        vm.unregister_cache("nonexistent")

    def test_empty_entities_in_register(self):
        vm = VersionManager()
        vm.register_cache_dependency("cache_1", [])
        assert vm.get_cache_dependencies("cache_1") == set()

    def test_complex_dependency_graph(self):
        vm = VersionManager()

        for i in range(12):
            vm.register_cache_dependency(f"cache_{i}", [f"entity_{j}" for j in range((i % 3) + 1)])

        for i in range(5):
            vm.bump_entity_version(f"entity_{i}")

        invalidated = vm.invalidate_entity("entity_0")
        assert len(invalidated) == 12

        for i in range(12):
            vm.register_cache_dependency(f"cache_{i}", [f"entity_{j}" for j in range((i % 3) + 1)])

        invalidated = vm.invalidate_entity("entity_1")
        assert len(invalidated) == 8

        for i in range(12):
            vm.register_cache_dependency(f"cache_{i}", [f"entity_{j}" for j in range((i % 3) + 1)])

        invalidated = vm.invalidate_entity("entity_2")
        assert len(invalidated) == 4

    def test_get_version_signature_empty(self):
        vm = VersionManager()
        sig = vm.get_version_signature([])
        assert sig == ""

    def test_check_versions_valid_with_extra_entities(self):
        vm = VersionManager()
        vm.bump_entity_version("users")

        assert vm.check_versions_valid("cache_1", {"users": 1, "extra": 0}) is True

    def test_thread_safety(self):
        import threading

        vm = VersionManager()
        results = []

        def bump_repeatedly(entity):
            for _ in range(100):
                vm.bump_entity_version(entity)

        threads = [threading.Thread(target=bump_repeatedly, args=(f"entity_{i}",)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        for i in range(5):
            assert vm.get_entity_version(f"entity_{i}") == 100
