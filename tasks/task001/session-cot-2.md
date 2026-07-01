我来逐一修复这些问题。首先创建一个详细的修复计划。
        
            
toolName: todo_write
            
status: success
          
Todos updated: 6 items
          

        
            
toolName: todo_write
            
status: success
          
Todos updated: 6 items
          
让我先读取当前的关键代码：

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\transaction_coordination\coordinator.py
          
现在让我开始逐一修复。首先修复 **问题1** 和 **问题2**，同时为 **问题3** 设计数据结构。

首先，我需要修改 `TransactionContext` 增加 abort 失败参与者追踪，然后修改 `_check_prepare_timeout_locked` 和 `prepare_transaction` 来抛出超时异常，修改 `commit_transaction` 区分「终态幂等」和「提交出错」。



        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\transaction_coordination\coordinator.py
          
changes: undefined
          
现在修改 `prepare_transaction`，在检测到超时时抛出 `TimeoutDecisionAbortedError`：





        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\transaction_coordination\coordinator.py
          
changes: undefined
          

        
            
toolName: todo_write
            
status: success
          
Todos updated: 6 items
          
现在修复 **问题2**。首先修改导入并在 `commit_transaction` 中区分异常类型：








        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\transaction_coordination\coordinator.py
          
changes: undefined
          
现在修改 `commit_transaction`，让它在提交过程出错时抛 `CommitFailedError` 而不是通用的 `TransactionStateError`：







        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\transaction_coordination\coordinator.py
          
changes: undefined
          
现在修改 `execute_transaction`，移除静默吞异常的逻辑，让真实的提交错误暴露给调用者：









        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\transaction_coordination\coordinator.py
          
changes: undefined
          

        
            
toolName: todo_write
            
status: success
          
Todos updated: 6 items
          
现在修复 **问题3**，为 abort 失败设计处置策略：

**策略设计**：
- 参与者 abort 回调失败时，标记到 `abort_failed_participants`
- 协调器保持 `ABORTING` 状态（不进入 `ABORTED` 终态）
- 提供 `retry_abort(tx_id)` 方法，仅重试失败的参与者
- 提供 `get_abort_failed_participants(tx_id)` 和 `has_incomplete_abort(tx_id)` 查询方法
- 当所有参与者 abort 成功后，才转为 `ABORTED` 终态

现在修改 `abort_transaction` 并新增方法：







        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\transaction_coordination\coordinator.py
          
现在修改 `abort_transaction`，并新增相关方法：










        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\transaction_coordination\coordinator.py
          
changes: undefined
          
现在让我更新 `__init__.py` 确保导出新的 API，并补充单元测试。首先检查一下：







        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\transaction_coordination\__init__.py
          

        
            
toolName: todo_write
            
status: success
          
Todos updated: 6 items
          
现在让我补充新的测试用例。首先读取测试文件末尾：







        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\transaction_coordination\test_transaction_coordination.py
          

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\transaction_coordination\test_transaction_coordination.py
          
现在追加新的测试用例：









        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\transaction_coordination\test_transaction_coordination.py
          
changes: undefined
          
现在让我先运行测试看看结果，再调整可能的问题：











        
            
toolName: todo_write
            
status: success
          
Todos updated: 6 items
          

        
            
toolName: run_command
            
status: success
          
command: cd "c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py" ; poetry run pytest tests/transaction_coordination/ -q 2>&1 undefined
          
有两个测试失败。第一个是旧的超时测试期望返回 `False` 而不是抛异常；第二个是测试中缺少 `TimeoutDecisionAbortedError` 的导入。让我修复：








        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\transaction_coordination\test_transaction_coordination.py
          

        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\transaction_coordination\test_transaction_coordination.py
          
changes: undefined
          
现在更新旧的超时测试 `test_prepare_timeout_triggers_abort`，让它期望抛出异常：









        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\transaction_coordination\test_transaction_coordination.py
          

        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\transaction_coordination\test_transaction_coordination.py
          
changes: undefined
          
还有一个问题需要修复：当超时决策 `decision = TIMEOUT_ABORTED` 时，所有 abort 成功后，`state` 应该设置为 `TIMEOUT_ABORTED` 而不是 `ABORTED`。让我修复：










        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\transaction_coordination\coordinator.py
          
changes: undefined
          
现在再次运行测试：










        
            
toolName: run_command
            
status: success
          
command: cd "c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py" ; poetry run pytest tests/transaction_coordination/ -q 2>&1 undefined
          
需要更新测试，超时场景最终状态应为 `TIMEOUT_ABORTED`：












        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\transaction_coordination\test_transaction_coordination.py
          
changes: undefined
          

        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\transaction_coordination\test_transaction_coordination.py
          
changes: undefined
          
再运行一次测试：











        
            
toolName: run_command
            
status: success
          
command: cd "c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py" ; poetry run pytest tests/transaction_coordination/ -q 2>&1 undefined
          
所有 **62 个测试** 全部通过 ✅！现在让我更新 README.md 文档。


        
            
toolName: todo_write
            
status: success
          
Todos updated: 6 items
          
现在更新 README.md，补充异常处理契约和 abort 失败处置策略的说明。让我先读取文档的关键部分：










        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\transaction_coordination\README.md
          
现在让我更新 README.md，补充修复后的异常处理契约和 abort 失败处置策略。首先更新超时部分：















        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\transaction_coordination\README.md
          
changes: undefined
          
现在在 3.5 节后新增 commit 部分失败和 abort 回调失败的说明：









        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\transaction_coordination\README.md
          
changes: undefined
          
现在在使用示例部分追加新的示例代码，展示异常处理和 abort 重试：













        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\transaction_coordination\README.md
          
现在在使用示例部分追加新的示例代码：

















        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\transaction_coordination\README.md
          
changes: undefined
          
现在更新文件结构中的测试用例数量，并更新状态机图：















        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\transaction_coordination\README.md
          
changes: undefined
          
现在更新测试用例数量：


















        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\transaction_coordination\README.md
          
changes: undefined
          

        
            
toolName: todo_write
            
status: success
          
Todos updated: 6 items
          
让我做最后的测试验证：



















        
            
toolName: run_command
            
status: success
          
command: cd "c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py" ; poetry run pytest tests/transaction_coordination/ -v 2>&1 | Select-Object -Last 20 undefined
          
完美！**62 个测试全部通过** ✅。以下是所有问题的修复总结：

---

## 修复内容总结

### 问题1：死代码 `TimeoutDecisionAbortedError` 捕获
- **修复**：修改 [prepare_transaction](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/transaction_coordination/coordinator.py#L112-L225)，当检测到超时时不再仅仅返回 `False`，而是真正抛出 `TimeoutDecisionAbortedError`。
- `execute_transaction` 中对该异常的捕获分支现在有效，捕获后自动执行 `abort_transaction`，最终状态为 `TIMEOUT_ABORTED`。

### 问题2：`execute_transaction` 静默吞掉 commit 异常
- **修复**：
  - [commit_transaction](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/transaction_coordination/coordinator.py#L230-L291) 中部分参与者提交失败时，改为抛出 **`CommitFailedError`**（而不是通用的 `TransactionStateError`）
  - [execute_transaction](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/transaction_coordination/coordinator.py#L354-L383) 移除了 `except TransactionStateError: pass`，让异常传播给调用者处理
  - 已 `COMMITTED` 的事务再次调用 `commit_transaction` 保持幂等返回（不抛错）
- **区分**：
  - ✅ 已 COMMITTED 幂等返回 → `return None`
  - ❌ 状态机非法转换 → `TransactionStateError`
  - ❌ 提交过程中出错 → `CommitFailedError`

### 问题3：参与者 abort 回调失败的不一致问题
- **处置策略**：
  1. **标记失败**：在 [TransactionContext](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/transaction_coordination/coordinator.py#L22-L37) 中新增 `abort_failed_participants` 字段
  2. **状态保持**：[abort_transaction](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/transaction_coordination/coordinator.py#L296-L334) 后若有失败，协调器保持 `ABORTING` 状态，与参与者端状态一致（参与者端 `abort` 失败后会回退到前一状态）
  3. **新增 API**：
     - [retry_abort(tx_id)](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/transaction_coordination/coordinator.py#L372-L395) → 仅重试失败的参与者，返回 `True` 表示全部成功
     - [has_incomplete_abort(tx_id)](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/transaction_coordination/coordinator.py#L397-L401) → 是否存在未完成的 abort
     - [get_abort_failed_participants(tx_id)](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/transaction_coordination/coordinator.py#L403-L407) → 需要重试的参与者列表

### 问题4：补充测试
新增 11 个测试用例（位于 [test_transaction_coordination.py](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/tests/transaction_coordination/test_transaction_coordination.py)）：
- `TestTimeoutExceptionRaised`（2 个）：超时异常抛出、`execute_transaction` 捕获处理
- `TestCommitPartialFailure`（3 个）：部分失败抛 `CommitFailedError`、异常传播、幂等性
- `TestAbortCallbackFailure`（5 个）：abort 失败保持 `ABORTING`、重试成功、非法状态重试、已 ABORTED 重试无副作用、多参与者失败
- `TestAbortFailedError`（1 个）：异常继承关系

### 问题5：更新 [README.md](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/transaction_coordination/README.md)
- 更新状态机图，补充 `ABORTING` → 失败保持 → `retry_abort` 重试的流转
- 新增 3.6 节「Commit 阶段部分失败」、3.7 节「参与者 Abort 回调失败（处置策略）」
- 新增 4.5 节「异常处理：捕获超时和提交失败」、4.6 节「Abort 回调失败与重试」使用示例
- 更新测试用例数量为 62 个

### 问题6：测试验证
```
poetry run pytest tests/transaction_coordination/ -q
============================= 62 passed in 0.12s ==============================
```