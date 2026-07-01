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
    """参与者提交失败异常"""
    pass


class AbortFailedError(TransactionError):
    """参与者中止失败异常"""
    pass
