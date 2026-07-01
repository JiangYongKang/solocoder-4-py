import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .constants import CacheEntryState


@dataclass
class CacheEntry:
    """缓存条目数据类

    Attributes:
        key: 缓存键
        value: 缓存值
        state: 缓存条目状态
        created_at: 创建时间戳
        expires_at: 过期时间戳
        accessed_at: 最后访问时间戳
        hit_count: 命中次数
        access_timestamps: 访问时间戳列表，用于热点键检测
        degraded_value: 降级占位值
        degraded_at: 降级时间戳
        rebuild_attempts: 重建尝试次数
        last_rebuild_at: 最后重建时间戳
        tags: 标签列表
    """

    key: str
    value: Any
    state: CacheEntryState = CacheEntryState.VALID
    created_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    accessed_at: float = field(default_factory=time.time)
    hit_count: int = 0
    access_timestamps: List[float] = field(default_factory=list)
    degraded_value: Any = None
    degraded_at: Optional[float] = None
    rebuild_attempts: int = 0
    last_rebuild_at: Optional[float] = None
    tags: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.tags = list(self.tags)
        self.access_timestamps = list(self.access_timestamps)

    def is_valid(self, now: Optional[float] = None) -> bool:
        """判断缓存条目是否有效

        Args:
            now: 当前时间戳

        Returns:
            True 表示有效，False 表示已过期或状态无效
        """
        if self.state not in (CacheEntryState.VALID, CacheEntryState.DEGRADED):
            return False
        if self.expires_at is not None:
            current_time = now if now is not None else time.time()
            if current_time > self.expires_at:
                return False
        return True

    def is_expired(self, now: Optional[float] = None) -> bool:
        """判断缓存是否已过期"""
        if self.expires_at is None:
            return False
        current_time = now if now is not None else time.time()
        return current_time > self.expires_at

    def touch(self, now: Optional[float] = None, window_seconds: int = 60) -> None:
        """更新访问时间和命中次数，清理窗口外的访问记录

        Args:
            now: 当前时间戳
            window_seconds: 热点检测窗口大小（秒）
        """
        current_time = now if now is not None else time.time()
        self.accessed_at = current_time
        self.hit_count += 1
        self.access_timestamps.append(current_time)

        cutoff = current_time - window_seconds
        self.access_timestamps = [t for t in self.access_timestamps if t >= cutoff]

    def get_recent_hit_count(self, window_seconds: int, now: Optional[float] = None) -> int:
        """获取指定时间窗口内的命中次数

        Args:
            window_seconds: 时间窗口大小（秒）
            now: 当前时间戳

        Returns:
            窗口内的命中次数
        """
        current_time = now if now is not None else time.time()
        cutoff = current_time - window_seconds
        return sum(1 for t in self.access_timestamps if t >= cutoff)

    def remaining_ttl(self, now: Optional[float] = None) -> Optional[float]:
        """获取剩余 TTL（秒）"""
        if self.expires_at is None:
            return None
        current_time = now if now is not None else time.time()
        return self.expires_at - current_time

    def mark_rebuilding(self) -> None:
        """标记为正在重建"""
        self.state = CacheEntryState.REBUILDING
        self.rebuild_attempts += 1
        self.last_rebuild_at = time.time()

    def mark_rebuilt(self, value: Any, expires_at: float) -> None:
        """标记为重建完成"""
        self.value = value
        self.expires_at = expires_at
        self.state = CacheEntryState.VALID
        self.degraded_value = None
        self.degraded_at = None

    def mark_degraded(self, degraded_value: Any, degraded_ttl: float) -> None:
        """标记为降级状态

        Args:
            degraded_value: 降级占位值
            degraded_ttl: 降级值的 TTL（秒）
        """
        self.degraded_value = degraded_value
        self.degraded_at = time.time()
        self.expires_at = time.time() + degraded_ttl
        self.state = CacheEntryState.DEGRADED

    def invalidate(self) -> None:
        """标记缓存条目为过期"""
        self.expires_at = time.time() - 1

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "key": self.key,
            "value": self.value,
            "state": self.state.value,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "accessed_at": self.accessed_at,
            "hit_count": self.hit_count,
            "access_timestamps": list(self.access_timestamps),
            "degraded_value": self.degraded_value,
            "degraded_at": self.degraded_at,
            "rebuild_attempts": self.rebuild_attempts,
            "last_rebuild_at": self.last_rebuild_at,
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CacheEntry":
        """从字典反序列化"""
        return cls(
            key=data["key"],
            value=data["value"],
            state=CacheEntryState(data.get("state", CacheEntryState.VALID.value)),
            created_at=data.get("created_at", time.time()),
            expires_at=data.get("expires_at"),
            accessed_at=data.get("accessed_at", time.time()),
            hit_count=data.get("hit_count", 0),
            access_timestamps=list(data.get("access_timestamps", [])),
            degraded_value=data.get("degraded_value"),
            degraded_at=data.get("degraded_at"),
            rebuild_attempts=data.get("rebuild_attempts", 0),
            last_rebuild_at=data.get("last_rebuild_at"),
            tags=list(data.get("tags", [])),
        )
