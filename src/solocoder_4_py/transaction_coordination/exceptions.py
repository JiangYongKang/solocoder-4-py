class TransactionError(Exception):
    """事务基础异常"""
    pass


class TransactionNotFoundError(TransactionError):
    """事务不存在异常"""
    pass


class TransactionStateError(TransactionError):
    """事务状态非法异常"""
    pass


class ParticipantAlreadyRegisteredError(TransactionError):
    """参与者重复注册异常"""
    pass


class ParticipantNotFoundError(TransactionError):
    """参与者未找到异常"""
    pass


class TimeoutDecisionAbortedError(TransactionError):
    """协调器等待超时，决策中止"""
    pass


class PrepareFailedError(TransactionError):
    """参与者准备失败异常"""
    pass


class CommitFailedError(TransactionError):
    """参与者提交失败异常

    当协调器处于 COMMITTING 阶段，但部分参与者 commit 回调失败时抛出。
    异常中包含失败参与者和已成功参与者的 ID 列表，便于调用者进行补偿处理。
    """

    def __init__(
        self,
        message: str,
        failed_participants: list[str] | None = None,
        committed_participants: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.failed_participants = failed_participants if failed_participants is not None else []
        self.committed_participants = committed_participants if committed_participants is not None else []

    def __str__(self) -> str:
        base = super().__str__()
        if not self.failed_participants and not self.committed_participants:
            return base
        return (
            f"{base}\n"
            f"  失败参与者: {self.failed_participants}\n"
            f"  已成功参与者: {self.committed_participants}"
        )


class AbortFailedError(TransactionError):
    """参与者中止失败异常"""
    pass
