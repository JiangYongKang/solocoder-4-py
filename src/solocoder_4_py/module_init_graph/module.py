from typing import Any, Callable, Dict, List, Optional


class ModuleNode:
    """模块节点数据模型

    描述一个可被初始化的模块，包含模块标识、依赖声明、
    初始化回调函数、可选元数据等。
    """

    def __init__(
        self,
        module_id: str,
        dependencies: Optional[List[str]] = None,
        description: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        max_retries: int = 0,
    ) -> None:
        self._module_id = module_id
        self._dependencies = list(dependencies) if dependencies else []
        self._description = description
        self._metadata = dict(metadata) if metadata else {}
        self._max_retries = max_retries
        self._init_callback: Optional[Callable[[Any], Any]] = None

    @property
    def module_id(self) -> str:
        return self._module_id

    @property
    def dependencies(self) -> List[str]:
        return list(self._dependencies)

    @property
    def description(self) -> str:
        return self._description

    @property
    def metadata(self) -> Dict[str, Any]:
        return dict(self._metadata)

    @property
    def max_retries(self) -> int:
        return self._max_retries

    def set_init_callback(self, callback: Callable[[Any], Any]) -> None:
        """设置模块初始化回调函数

        :param callback: 接受 context 参数并返回初始化结果的可调用对象
        """
        self._init_callback = callback

    def execute_init(self, context: Any = None) -> Any:
        """执行初始化回调

        :param context: 传递给回调的上下文对象
        :returns: 回调函数的返回值（初始化结果）
        """
        if self._init_callback is None:
            return None
        return self._init_callback(context)

    def add_dependency(self, dep: str) -> None:
        """添加一个依赖模块"""
        if dep not in self._dependencies:
            self._dependencies.append(dep)

    def remove_dependency(self, dep: str) -> None:
        """移除一个依赖模块"""
        if dep in self._dependencies:
            self._dependencies.remove(dep)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ModuleNode):
            return NotImplemented
        return self._module_id == other._module_id

    def __hash__(self) -> int:
        return hash(self._module_id)

    def __repr__(self) -> str:
        deps = ", ".join(self._dependencies)
        return f"ModuleNode(id={self._module_id!r}, deps=[{deps}])"
