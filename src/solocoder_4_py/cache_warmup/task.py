from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

from .constants import TaskState


@dataclass
class WarmupTask:
    """预热任务定义

    代表一个需要被加载到缓存中的热点数据项。
    每个任务可以声明对其他任务的依赖关系。
    """
    task_id: str
    description: str = ""
    dependencies: List[str] = field(default_factory=list)
    priority: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    _load_fn: Optional[Callable[[], Any]] = None

    def set_load_function(self, fn: Callable[[], Any]) -> None:
        """设置数据加载回调函数"""
        self._load_fn = fn

    def execute_load(self) -> Any:
        """执行数据加载"""
        if self._load_fn is not None:
            return self._load_fn()
        return None

    def __hash__(self) -> int:
        return hash(self.task_id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, WarmupTask):
            return False
        return self.task_id == other.task_id
