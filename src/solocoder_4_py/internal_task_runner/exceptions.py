class TaskRunnerError(Exception):
    """任务运行器基础异常"""


class TaskNotFoundError(TaskRunnerError):
    """任务未找到异常"""

    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        super().__init__(f"任务 '{task_id}' 未找到")


class TaskAlreadyRegisteredError(TaskRunnerError):
    """任务已注册异常"""

    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        super().__init__(f"任务 '{task_id}' 已存在")


class TaskStateError(TaskRunnerError):
    """任务状态操作异常"""

    def __init__(self, task_id: str, current_status: str, operation: str) -> None:
        self.task_id = task_id
        self.current_status = current_status
        self.operation = operation
        super().__init__(
            f"任务 '{task_id}' 当前状态为 '{current_status}'，无法执行操作 '{operation}'"
        )


class TaskTypeError(TaskRunnerError):
    """任务类型不兼容异常"""

    def __init__(self, task_id: str, expected_type: str, actual_type: str) -> None:
        self.task_id = task_id
        self.expected_type = expected_type
        self.actual_type = actual_type
        super().__init__(
            f"任务 '{task_id}' 类型不兼容：期望 '{expected_type}'，实际 '{actual_type}'"
        )


class TaskExecutionError(TaskRunnerError):
    """任务执行异常"""

    def __init__(self, task_id: str, cause: Exception) -> None:
        self.task_id = task_id
        self.cause = cause
        super().__init__(f"任务 '{task_id}' 执行失败: {cause}")


class InvalidScheduleError(TaskRunnerError):
    """调度参数非法异常"""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(f"调度参数非法：{reason}")
