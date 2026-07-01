from collections import deque
import heapq
from typing import Dict, List

from .exceptions import CircularDependencyError, DependencyNotFoundError
from .task import WarmupTask


class TopologySorter:
    """拓扑排序器

    基于 Kahn 算法对有向无环图 (DAG) 进行拓扑排序，
    用于确定预热任务的执行顺序。
    同层级（入度相同）的任务按 priority 降序执行，确保高优先级热点数据优先预热。
    """

    @staticmethod
    def sort(tasks: Dict[str, WarmupTask]) -> List[str]:
        """对任务图进行拓扑排序

        使用最小堆（负 priority）实现按 priority 降序选择同层级任务。

        :param tasks: 任务字典 {task_id: WarmupTask}
        :returns: 按依赖顺序 + priority 降序排列的 task_id 列表
        :raises CircularDependencyError: 存在循环依赖
        :raises DependencyNotFoundError: 依赖的任务不存在
        """
        if not tasks:
            return []

        for task_id, task in tasks.items():
            for dep in task.dependencies:
                if dep not in tasks:
                    raise DependencyNotFoundError(
                        f"任务 {task_id} 的依赖 {dep} 不存在"
                    )

        in_degree: Dict[str, int] = {tid: 0 for tid in tasks}
        out_edges: Dict[str, List[str]] = {tid: [] for tid in tasks}

        for task_id, task in tasks.items():
            for dep in task.dependencies:
                in_degree[task_id] += 1
                out_edges[dep].append(task_id)

        heap: List[tuple] = []
        for task_id, degree in in_degree.items():
            if degree == 0:
                priority = tasks[task_id].priority
                heapq.heappush(heap, (-priority, task_id))

        result: List[str] = []
        while heap:
            _, current = heapq.heappop(heap)
            result.append(current)
            for neighbor in out_edges[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    priority = tasks[neighbor].priority
                    heapq.heappush(heap, (-priority, neighbor))

        if len(result) != len(tasks):
            remaining = set(tasks.keys()) - set(result)
            raise CircularDependencyError(
                f"检测到循环依赖，涉及任务: {', '.join(sorted(remaining))}"
            )

        return result

    @staticmethod
    def get_dependents(tasks: Dict[str, WarmupTask]) -> Dict[str, List[str]]:
        """获取每个任务的所有下游依赖者

        :returns: {task_id: [依赖该任务的 task_id 列表]}
        """
        dependents: Dict[str, List[str]] = {tid: [] for tid in tasks}
        for task_id, task in tasks.items():
            for dep in task.dependencies:
                dependents[dep].append(task_id)
        return dependents

    @staticmethod
    def get_all_downstream(
        tasks: Dict[str, WarmupTask], task_id: str
    ) -> List[str]:
        """获取某个任务的所有下游任务（传递依赖）

        :returns: 下游任务 id 列表，不包含自身
        """
        dependents = TopologySorter.get_dependents(tasks)
        visited: set = set()
        result: List[str] = []
        stack = list(dependents.get(task_id, []))
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            result.append(current)
            stack.extend(dependents.get(current, []))
        return result
