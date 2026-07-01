import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .constants import CacheEntryStatus


@dataclass
class CacheEntry:
    """缓存条目数据类

    Attributes:
        key: 缓存键
        value: 缓存值
        tags: 关联标签列表，用于批量失效
        status: 缓存条目状态
        created_at: 创建时间戳
        expires_at: 过期时间戳（None表示永不过期）
        accessed_at: 最后访问时间戳
        hit_count: 命中次数
    """

    key: str
    value: Any
    tags: list = field(default_factory=list)
    status: CacheEntryStatus = CacheEntryStatus.VALID
    created_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    accessed_at: float = field(default_factory=time.time)
    hit_count: int = 0

    def __post_init__(self) -> None:
        self.tags = list(self.tags)

    def is_valid(self, now: Optional[float] = None) -> bool:
        """判断缓存条目是否有效

        Args:
            now: 当前时间戳，为 None 时使用 time.time()

        Returns:
            True 表示有效，False 表示已过期或已失效
        """
        if self.status != CacheEntryStatus.VALID:
            return False
        if self.expires_at is not None:
            current_time = now if now is not None else time.time()
            if current_time > self.expires_at:
                return False
        return True

    def touch(self, now: Optional[float] = None) -> None:
        """更新访问时间和命中次数"""
        current_time = now if now is not None else time.time()
        self.accessed_at = current_time
        self.hit_count += 1

    def invalidate(self) -> None:
        """标记缓存条目为失效状态"""
        self.status = CacheEntryStatus.INVALIDATED

    def remaining_ttl(self, now: Optional[float] = None) -> Optional[float]:
        """获取剩余 TTL（秒）

        Returns:
            剩余秒数，None 表示永不过期，负数或 0 表示已过期
        """
        if self.expires_at is None:
            return None
        current_time = now if now is not None else time.time()
        return self.expires_at - current_time

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "key": self.key,
            "value": self.value,
            "tags": list(self.tags),
            "status": self.status.value,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "accessed_at": self.accessed_at,
            "hit_count": self.hit_count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CacheEntry":
        """从字典反序列化"""
        return cls(
            key=data["key"],
            value=data["value"],
            tags=list(data.get("tags", [])),
            status=CacheEntryStatus(data.get("status", CacheEntryStatus.VALID.value)),
            created_at=data.get("created_at", time.time()),
            expires_at=data.get("expires_at"),
            accessed_at=data.get("accessed_at", time.time()),
            hit_count=data.get("hit_count", 0),
        )
