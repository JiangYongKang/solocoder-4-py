import hashlib
import json
from typing import Any, Dict, List, Optional, Tuple


def _normalize_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float, str)):
        return value
    if isinstance(value, dict):
        return _normalize_dict(value)
    if isinstance(value, (list, tuple)):
        return _normalize_sequence(value)
    if isinstance(value, set):
        return _normalize_sequence(sorted(value, key=lambda x: str(_normalize_value(x))))
    return str(value)


def _normalize_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    normalized = {}
    for key in sorted(d.keys()):
        normalized[key] = _normalize_value(d[key])
    return normalized


def _normalize_sequence(seq: List[Any] | Tuple[Any, ...]) -> List[Any]:
    return [_normalize_value(item) for item in seq]


def _serialize_to_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


class CacheKeyGenerator:
    def __init__(self, algorithm: str = "sha256", prefix: Optional[str] = None):
        self.algorithm = algorithm
        self.prefix = prefix or "snapshot"

    def generate(self, request_params: Dict[str, Any],
                 data_entities: Optional[List[str]] = None) -> str:
        normalized_params = _normalize_dict(request_params)
        normalized_entities = sorted(data_entities or [])

        key_components = {
            "params": normalized_params,
            "entities": normalized_entities,
        }

        serialized = _serialize_to_json(key_components)
        hash_digest = hashlib.new(self.algorithm, serialized.encode("utf-8")).hexdigest()

        return f"{self.prefix}:{hash_digest}"

    def generate_raw(self, data: Any) -> str:
        normalized = _normalize_value(data)
        serialized = _serialize_to_json(normalized)
        hash_digest = hashlib.new(self.algorithm, serialized.encode("utf-8")).hexdigest()
        return f"{self.prefix}:{hash_digest}"


def generate_cache_key(request_params: Dict[str, Any],
                       data_entities: Optional[List[str]] = None,
                       algorithm: str = "sha256",
                       prefix: Optional[str] = None) -> str:
    generator = CacheKeyGenerator(algorithm=algorithm, prefix=prefix)
    return generator.generate(request_params, data_entities)
