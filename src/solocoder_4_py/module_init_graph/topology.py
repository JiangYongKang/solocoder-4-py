from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple

from .exceptions import CircularDependencyError, DependencyNotFoundError
from .module import ModuleNode


@dataclass
class CycleReport:
    """循环依赖详细报告

    包含所有检测到的循环以及每个循环的可读描述。
    """

    cycles: List[List[str]] = field(default_factory=list)

    @property
    def has_cycles(self) -> bool:
        return len(self.cycles) > 0

    @property
    def cycle_count(self) -> int:
        return len(self.cycles)

    def involved_modules(self) -> Set[str]:
        """获取所有涉及循环依赖的模块集合"""
        result: Set[str] = set()
        for cycle in self.cycles:
            result.update(cycle)
        return result

    def format_report(self) -> str:
        """格式化循环依赖报告为可读字符串"""
        if not self.has_cycles:
            return "未检测到循环依赖。"

        lines = [f"检测到 {self.cycle_count} 个循环依赖:"]
        for idx, cycle in enumerate(self.cycles, 1):
            formatted = " -> ".join(cycle + [cycle[0]])
            lines.append(f"  [{idx}] {formatted}")
        modules = ", ".join(sorted(self.involved_modules()))
        lines.append(f"涉及模块: {modules}")
        return "\n".join(lines)

    def __str__(self) -> str:
        return self.format_report()


class TopologyAnalyzer:
    """拓扑分析器

    基于 Kahn 算法 + DFS 对模块依赖图进行分析，
    提供拓扑排序、循环依赖检测（带详细报告）、
    依赖链分析等能力。
    """

    @staticmethod
    def _validate_dependencies(modules: Dict[str, ModuleNode]) -> None:
        """校验所有依赖是否存在

        :raises DependencyNotFoundError: 某个依赖的模块不存在
        """
        for module_id, node in modules.items():
            for dep in node.dependencies:
                if dep not in modules:
                    raise DependencyNotFoundError(
                        f"模块 {module_id!r} 的依赖 {dep!r} 不存在"
                    )

    @staticmethod
    def detect_cycles(modules: Dict[str, ModuleNode]) -> CycleReport:
        """检测图中所有的循环依赖

        使用基于 DFS 的 Johnson 算法思想寻找所有简单环，
        每个环以起点终点相同的路径表示。

        :returns: CycleReport 详细报告对象
        """
        if not modules:
            return CycleReport(cycles=[])

        TopologyAnalyzer._validate_dependencies(modules)

        adj: Dict[str, List[str]] = {mid: [] for mid in modules}
        for module_id, node in modules.items():
            for dep in node.dependencies:
                adj[dep].append(module_id)

        cycles: List[List[str]] = []
        all_nodes = sorted(modules.keys())

        for start_idx in range(len(all_nodes)):
            start = all_nodes[start_idx]
            visited_in_run: Set[str] = set()
            stack: List[Tuple[str, List[str]]] = [(start, [start])]

            while stack:
                current, path = stack.pop()
                for neighbor in adj.get(current, []):
                    if neighbor == start and len(path) > 1:
                        cycles.append(list(path))
                    elif neighbor not in path and neighbor not in visited_in_run:
                        if all_nodes.index(neighbor) > start_idx:
                            stack.append((neighbor, path + [neighbor]))
                visited_in_run.add(current)

        unique_cycles = TopologyAnalyzer._normalize_cycles(cycles)
        return CycleReport(cycles=unique_cycles)

    @staticmethod
    def _normalize_cycles(cycles: List[List[str]]) -> List[List[str]]:
        """去重并规范化循环路径，避免同一环出现多个等价表示"""
        seen: Set[Tuple[str, ...]] = set()
        result: List[List[str]] = []

        for cycle in cycles:
            min_idx = cycle.index(min(cycle))
            rotated = cycle[min_idx:] + cycle[:min_idx]
            key = tuple(rotated)
            if key not in seen:
                seen.add(key)
                result.append(rotated)

        result.sort(key=lambda c: (len(c), c))
        return result

    @staticmethod
    def sort(modules: Dict[str, ModuleNode]) -> List[str]:
        """对模块图进行拓扑排序

        使用 Kahn 算法，当存在循环依赖时抛出包含详细报告的异常。

        :param modules: 模块字典 {module_id: ModuleNode}
        :returns: 按依赖顺序排列的 module_id 列表
        :raises CircularDependencyError: 存在循环依赖，异常中包含 CycleReport
        :raises DependencyNotFoundError: 依赖的模块不存在
        """
        if not modules:
            return []

        TopologyAnalyzer._validate_dependencies(modules)

        in_degree: Dict[str, int] = {mid: 0 for mid in modules}
        out_edges: Dict[str, List[str]] = {mid: [] for mid in modules}

        for module_id, node in modules.items():
            for dep in node.dependencies:
                in_degree[module_id] += 1
                out_edges[dep].append(module_id)

        queue: deque = deque()
        for module_id, degree in sorted(in_degree.items()):
            if degree == 0:
                queue.append(module_id)

        result: List[str] = []
        while queue:
            current = queue.popleft()
            result.append(current)
            for neighbor in out_edges[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(result) != len(modules):
            report = TopologyAnalyzer.detect_cycles(modules)
            remaining = set(modules.keys()) - set(result)
            raise CircularDependencyError(
                f"检测到循环依赖，涉及模块: {', '.join(sorted(remaining))}\n"
                f"{report.format_report()}",
                cycles=report.cycles,
            )

        return result

    @staticmethod
    def get_dependents(modules: Dict[str, ModuleNode]) -> Dict[str, List[str]]:
        """获取每个模块的所有直接下游依赖者

        :returns: {module_id: [依赖该模块的 module_id 列表]}
        """
        dependents: Dict[str, List[str]] = {mid: [] for mid in modules}
        for module_id, node in modules.items():
            for dep in node.dependencies:
                if dep in dependents:
                    dependents[dep].append(module_id)
        return dependents

    @staticmethod
    def get_all_downstream(
        modules: Dict[str, ModuleNode], module_id: str
    ) -> List[str]:
        """获取某个模块的所有下游模块（传递依赖）

        :returns: 下游模块 id 列表，不包含自身
        """
        dependents = TopologyAnalyzer.get_dependents(modules)
        visited: Set[str] = set()
        result: List[str] = []
        stack = list(dependents.get(module_id, []))
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            result.append(current)
            stack.extend(dependents.get(current, []))
        return result

    @staticmethod
    def get_all_upstream(
        modules: Dict[str, ModuleNode], module_id: str
    ) -> List[str]:
        """获取某个模块的所有上游模块（传递依赖）

        :returns: 上游模块 id 列表，不包含自身
        """
        if module_id not in modules:
            return []

        visited: Set[str] = set()
        result: List[str] = []
        stack = list(modules[module_id].dependencies)
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            if current not in modules:
                continue
            visited.add(current)
            result.append(current)
            stack.extend(modules[current].dependencies)
        return result

    @staticmethod
    def build_dependency_matrix(modules: Dict[str, ModuleNode]) -> Dict[str, Set[str]]:
        """构建依赖关系矩阵（传递闭包）

        :returns: {module_id: 该模块（直接或间接）依赖的所有 module_id 集合}
        """
        matrix: Dict[str, Set[str]] = {}
        for mid in modules:
            matrix[mid] = set()

        changed = True
        while changed:
            changed = False
            for mid, node in modules.items():
                for dep in node.dependencies:
                    if dep not in matrix[mid]:
                        matrix[mid].add(dep)
                        changed = True
                    for trans_dep in matrix.get(dep, set()):
                        if trans_dep not in matrix[mid]:
                            matrix[mid].add(trans_dep)
                            changed = True
        return matrix

    @staticmethod
    def topological_levels(modules: Dict[str, ModuleNode]) -> Dict[str, int]:
        """计算每个模块的拓扑层级（距根节点的最长路径）

        无依赖的模块层级为 0，依赖于层级 N 的模块层级至少为 N+1。

        :returns: {module_id: 层级编号}
        """
        order = TopologyAnalyzer.sort(modules)
        levels: Dict[str, int] = {}
        for mid in order:
            node = modules[mid]
            if not node.dependencies:
                levels[mid] = 0
            else:
                levels[mid] = max(
                    levels.get(dep, 0) for dep in node.dependencies if dep in levels
                ) + 1
        return levels
