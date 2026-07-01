我来帮你实现这个内存事务协调域功能模块。首先让我了解一下当前项目的结构和代码约定。
        
            
toolName: view_folder
            
status: success
          
c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py
          

        
            
toolName: file_search
            
status: success
          
file_pattern: src/solocoder_4_py/**/*.py
          

        
            
toolName: file_search
            
status: success
          
file_pattern: tests/**/*.py
          

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\pyproject.toml
          

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\__init__.py
          

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\README.md
          
现在我对项目结构有了清晰的了解。让我创建一个详细的实现计划。

        
            
toolName: todo_write
            
status: success
          
Todos updated: 7 items
          

        
            
toolName: todo_write
            
status: success
          
Todos updated: 7 items
          
让我开始创建事务协调模块的核心文件。首先创建目录结构和常量、异常定义。

        
            
toolName: run_command
            
status: success
          
command: New-Item -ItemType Directory -Force -Path "c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\transaction_coordination" undefined
          

        
            
toolName: run_command
            
status: success
          
command: New-Item -ItemType Directory -Force -Path "c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\transaction_coordination" undefined
          
现在让我创建核心模块文件。首先是状态枚举和异常定义，然后是参与者和协调器。



        
            
toolName: Write
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\transaction_coordination\constants.py
          
changes: undefined
          

        
            
toolName: Write
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\transaction_coordination\exceptions.py
          
changes: undefined
          
现在让我实现 TransactionParticipant 参与者类。

        
            
toolName: todo_write
            
status: success
          
Todos updated: 7 items
          

        
            
toolName: Write
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\transaction_coordination\participant.py
          
changes: undefined
          
现在实现核心的协调器类 TransactionCoordinator，实现两阶段提交（2PC）流程和超时决策。



        
            
toolName: todo_write
            
status: success
          
Todos updated: 7 items
          

        
            
toolName: Write
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\transaction_coordination\coordinator.py
          
changes: undefined
          
现在创建模块的 `__init__.py`，导出公共接口。



        
            
toolName: todo_write
            
status: success
          
Todos updated: 7 items
          

        
            
toolName: Write
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\transaction_coordination\__init__.py
          
changes: undefined
          
现在让我创建测试文件 `tests/transaction_coordination/__init__.py` 和完整的测试套件。





        
            
toolName: todo_write
            
status: success
          
Todos updated: 7 items
          
现在创建测试文件，覆盖所有关键场景：

        
            
toolName: Write
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\transaction_coordination\__init__.py
          
changes: undefined
          

        
            
toolName: Write
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\transaction_coordination\test_transaction_coordination.py
          
changes: undefined
          
现在让我先运行测试，验证代码的正确性：







        
            
toolName: todo_write
            
status: success
          
Todos updated: 7 items
          

        
            
toolName: run_command
            
status: success
          
command: cd "c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py" ; python -m pytest tests/transaction_coordination/ -v --tb=short 2>&1 undefined
          
包还没有被安装到当前环境中。让我先通过 pip 以开发模式安装：


        
            
toolName: run_command
            
status: success
          
command: cd "c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py" ; pip install -e . 2>&1 undefined
          
安装成功。现在运行测试：


        
            
toolName: run_command
            
status: success
          
command: cd "c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py" ; python -m pytest tests/transaction_coordination/ -v --tb=short 2>&1 undefined
          
有 2 个测试失败，让我分析并修复：

1. **超时问题**：超时检查在调用参与者 prepare 之前执行，但参与者回调中推进了时间，导致回调结束后未再检查
2. **prepare_after_committed**：对已经 COMMITTED 的事务调用 prepare 应该抛异常而不是直接返回

让我修复协调器代码：




        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\transaction_coordination\coordinator.py
          
现在让我修复这两个问题：


        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\transaction_coordination\coordinator.py
          
changes: undefined
          
现在修复第二个问题：在每个参与者 prepare 之后也要检查超时。让我读取循环部分并修改：





        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\transaction_coordination\coordinator.py
          
changes: undefined
          
同样需要在 prepare 失败的分支后也检查超时：





        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\transaction_coordination\coordinator.py
          
changes: undefined
          
现在再次运行测试：







        
            
toolName: run_command
            
status: success
          
command: cd "c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py" ; python -m pytest tests/transaction_coordination/ -v --tb=short 2>&1 undefined
          
好的，问题在于幂等性逻辑还需要优化。我需要区分：对已决策为 ABORTED 的事务再次 prepare 应返回 False（幂等），而对已 COMMITTED 的事务再次 prepare 才应该抛异常。同时 `execute_transaction` 对终态事务应直接返回。让我修复：







        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\transaction_coordination\coordinator.py
          
现在修复两个问题：

1. `prepare_transaction`：对于已决策为 ABORTED 的事务稳定返回 False，已 COMMITTED 的抛异常
2. `execute_transaction`：对终态事务直接返回，不再重新执行







        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\transaction_coordination\coordinator.py
          
changes: undefined
          
现在修复 `execute_transaction`，对于终态事务直接返回：









        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\transaction_coordination\coordinator.py
          
changes: undefined
          
现在再次运行测试：









        
            
toolName: run_command
            
status: success
          
command: cd "c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py" ; python -m pytest tests/transaction_coordination/ -v --tb=short 2>&1 undefined
          
完美！事务协调模块的 **51 个测试全部通过**！（其余失败的是另一个模块的测试，与本次任务无关）

现在让我编写模块的 README.md 文档：










        
            
toolName: todo_write
            
status: success
          
Todos updated: 7 items
          
现在编写 README.md 文档：

        
            
toolName: Write
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\transaction_coordination\README.md
          
changes: undefined
          
现在让我更新 Todo 状态并做最终确认：












        
            
toolName: todo_write
            
status: success
          
Todos updated: 7 items
          
内存事务协调域模块已全部实现完成！以下是交付内容的总结：

---

## 交付结构

### 源码包 [transaction_coordination](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/transaction_coordination/)

| 文件 | 职责 |
|------|------|
| [\_\_init\_\_.py](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/transaction_coordination/__init__.py) | 公共 API 导出 |
| [constants.py](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/transaction_coordination/constants.py) | `TransactionState` / `ParticipantState` 枚举 + 终态集合 |
| [exceptions.py](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/transaction_coordination/exceptions.py) | 事务异常层级（`PrepareFailedError`、`TimeoutDecisionAbortedError` 等） |
| [participant.py](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/transaction_coordination/participant.py) | `TransactionParticipant`：参与者幂等 prepare/commit/abort 实现 |
| [coordinator.py](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/transaction_coordination/coordinator.py) | `TransactionCoordinator`：2PC 流程 + 超时决策 + 状态机 |
| [README.md](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/transaction_coordination/README.md) | 模块功能文档、流程图、异常场景、使用示例 |

### 测试包 [transaction_coordination](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/tests/transaction_coordination/)

[test_transaction_coordination.py](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/tests/transaction_coordination/test_transaction_coordination.py)： **51 个测试用例全部通过** ✅

---

## 核心能力说明

1. **两阶段提交（2PC）**：通过 [prepare_transaction](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/transaction_coordination/coordinator.py#L112-L195) → [commit_transaction](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/transaction_coordination/coordinator.py#L200-L260) / [abort_transaction](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/transaction_coordination/coordinator.py#L264-L324) 驱动标准 2PC 流程；或使用 [execute_transaction](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/transaction_coordination/coordinator.py#L333-L360) 一键执行。

2. **超时决策**：通过 `prepare_timeout_seconds` 控制，支持注入自定义 `clock`（如 `FakeClock`）便于测试；每次参与者回调前后都会检查 [\_check_prepare_timeout_locked](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/transaction_coordination/coordinator.py#L364-L377)，超时后自动决策 `TIMEOUT_ABORTED`。

3. **幂等性保障**：
   - 参与者端：每个 `tx_id` 维护独立 [ParticipantTxContext](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/transaction_coordination/participant.py#L27-L34)，终态下重复调用直接返回，**业务回调仅执行一次**。
   - 协调器端：使用 `final_decision_made` 标志，终态事务对重复的 `prepare/commit/abort/execute` 调用稳定返回或直接抛错。

4. **业务可插拔**：通过 `set_callbacks(on_prepare, on_commit, on_abort)` 注入真实业务逻辑，灵活模拟成功/失败/异常。

---

## 运行测试

```bash
python -m pytest tests/transaction_coordination/ -v
```

当前测试结果：**51 passed**（覆盖常量定义、参与者单测、协调器基础/成功/回滚/超时/幂等路径、状态机校验、集成场景）。