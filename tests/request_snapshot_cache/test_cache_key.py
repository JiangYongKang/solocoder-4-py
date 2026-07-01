import pytest

from solocoder_4_py.request_snapshot_cache import (
    CacheKeyGenerator,
    generate_cache_key,
)


class TestCacheKeyGenerator:
    def test_generate_basic(self):
        generator = CacheKeyGenerator()
        params = {"a": 1, "b": 2}
        key = generator.generate(params)
        assert key.startswith("snapshot:")
        assert len(key) == len("snapshot:") + 64

    def test_generate_with_entities(self):
        generator = CacheKeyGenerator()
        params = {"a": 1}
        entities = ["users", "orders"]
        key1 = generator.generate(params, entities)
        key2 = generator.generate(params, ["orders", "users"])
        assert key1 == key2

    def test_generate_different_params(self):
        generator = CacheKeyGenerator()
        key1 = generator.generate({"a": 1})
        key2 = generator.generate({"a": 2})
        assert key1 != key2

    def test_dict_order_independent(self):
        generator = CacheKeyGenerator()
        key1 = generator.generate({"a": 1, "b": 2, "c": 3})
        key2 = generator.generate({"c": 3, "a": 1, "b": 2})
        assert key1 == key2

    def test_nested_dict_order_independent(self):
        generator = CacheKeyGenerator()
        params1 = {"user": {"name": "Alice", "age": 30}}
        params2 = {"user": {"age": 30, "name": "Alice"}}
        key1 = generator.generate(params1)
        key2 = generator.generate(params2)
        assert key1 == key2

    def test_list_and_tuple_equivalent(self):
        generator = CacheKeyGenerator()
        key1 = generator.generate({"tags": ["x", "y", "z"]})
        key2 = generator.generate({"tags": ("x", "y", "z")})
        assert key1 == key2

    def test_set_order_independent(self):
        generator = CacheKeyGenerator()
        key1 = generator.generate({"ids": {1, 2, 3}})
        key2 = generator.generate({"ids": {3, 1, 2}})
        assert key1 == key2

    def test_nested_structures(self):
        generator = CacheKeyGenerator()
        params = {
            "query": {
                "filters": [
                    {"field": "status", "value": "active"},
                    {"field": "date", "value": "2024-01-01"},
                ],
                "options": {"limit": 10, "offset": 0},
            },
            "include": {"profile", "settings"},
        }
        key1 = generator.generate(params)

        params_reordered = {
            "include": {"settings", "profile"},
            "query": {
                "options": {"offset": 0, "limit": 10},
                "filters": [
                    {"field": "status", "value": "active"},
                    {"field": "date", "value": "2024-01-01"},
                ],
            },
        }
        key2 = generator.generate(params_reordered)
        assert key1 == key2

    def test_bool_not_equal_to_int(self):
        generator = CacheKeyGenerator()
        key1 = generator.generate({"active": True})
        key2 = generator.generate({"active": 1})
        assert key1 != key2

    def test_none_value(self):
        generator = CacheKeyGenerator()
        key1 = generator.generate({"filter": None})
        key2 = generator.generate({"filter": None})
        assert key1 == key2

    def test_different_algorithms(self):
        params = {"a": 1}
        gen_sha256 = CacheKeyGenerator(algorithm="sha256")
        gen_md5 = CacheKeyGenerator(algorithm="md5")
        key_sha256 = gen_sha256.generate(params)
        key_md5 = gen_md5.generate(params)
        assert key_sha256 != key_md5
        assert len(key_sha256) == len("snapshot:") + 64
        assert len(key_md5) == len("snapshot:") + 32

    def test_custom_prefix(self):
        generator = CacheKeyGenerator(prefix="myapp")
        key = generator.generate({"a": 1})
        assert key.startswith("myapp:")

    def test_generate_raw(self):
        generator = CacheKeyGenerator()
        key1 = generator.generate_raw("some string")
        key2 = generator.generate_raw("some string")
        assert key1 == key2

    def test_generate_raw_dict(self):
        generator = CacheKeyGenerator()
        key1 = generator.generate_raw({"a": 1, "b": 2})
        key2 = generator.generate_raw({"b": 2, "a": 1})
        assert key1 == key2

    def test_complex_nested_with_sets(self):
        generator = CacheKeyGenerator()
        data1 = {
            "users": [
                {"id": 1, "roles": {"admin", "user"}},
                {"id": 2, "roles": {"viewer"}},
            ],
            "config": {"enabled": True, "timeout": 30.5},
        }
        data2 = {
            "config": {"timeout": 30.5, "enabled": True},
            "users": [
                {"id": 1, "roles": {"user", "admin"}},
                {"id": 2, "roles": {"viewer"}},
            ],
        }
        key1 = generator.generate(data1)
        key2 = generator.generate(data2)
        assert key1 == key2

    def test_unicode_strings(self):
        generator = CacheKeyGenerator()
        key1 = generator.generate({"name": "张三", "email": "test@example.com"})
        key2 = generator.generate({"email": "test@example.com", "name": "张三"})
        assert key1 == key2

    def test_float_precision(self):
        generator = CacheKeyGenerator()
        key1 = generator.generate({"value": 1.0})
        key2 = generator.generate({"value": 1})
        assert key1 != key2

    def test_generate_function(self):
        params = {"a": 1, "b": 2}
        key1 = generate_cache_key(params)
        key2 = generate_cache_key(params)
        assert key1 == key2

    def test_generate_function_with_entities(self):
        params = {"a": 1}
        entities = ["users"]
        key1 = generate_cache_key(params, entities)
        key2 = generate_cache_key(params, entities, algorithm="sha256", prefix="test")
        assert key1 != key2
        assert key2.startswith("test:")

    def test_empty_params(self):
        generator = CacheKeyGenerator()
        key1 = generator.generate({})
        key2 = generator.generate({})
        assert key1 == key2

    def test_empty_entities(self):
        generator = CacheKeyGenerator()
        params = {"a": 1}
        key1 = generator.generate(params, [])
        key2 = generator.generate(params, None)
        assert key1 == key2

    def test_mixed_types_in_list(self):
        generator = CacheKeyGenerator()
        key1 = generator.generate({"data": [1, "two", 3.0, True, None]})
        key2 = generator.generate({"data": [1, "two", 3.0, True, None]})
        assert key1 == key2

    def test_custom_object(self):
        class CustomObj:
            def __str__(self):
                return "custom_value"

        generator = CacheKeyGenerator()
        obj = CustomObj()
        key1 = generator.generate({"obj": obj})
        key2 = generator.generate({"obj": obj})
        assert key1 == key2

        obj2 = CustomObj()
        key3 = generator.generate({"obj": obj2})
        assert key1 == key3

    def test_large_nested_structure(self):
        generator = CacheKeyGenerator()
        large_data = {
            f"key_{i}": {
                "nested": {
                    f"deep_{j}": list(range(j)) for j in range(5)
                }
            } for i in range(10)
        }
        key1 = generator.generate(large_data)
        key2 = generator.generate(large_data)
        assert key1 == key2
