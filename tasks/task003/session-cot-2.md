好的，我来逐一修复这些问题。首先规划修复步骤：




        
            
toolName: todo_write
            
status: success
          
Todos updated: 7 items
          
让我先阅读现有代码，理解当前实现后进行修复：





        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_warmup\orchestrator.py
          

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_warmup\topology.py
          

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_warmup\progress.py
          
现在逐一修复这些问题。首先修复拓扑排序的 priority 支持和 progress_percentage：







        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_warmup\topology.py
          
changes: undefined
          
现在修复 progress_percentage 的空流程状态判断：









        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_warmup\progress.py
          
changes: undefined
          

        
            
toolName: todo_write
            
status: success
          
Todos updated: 7 items
          
现在修复线程安全和 CONTINUE_ANYWAY 策略问题。核心策略：给每个 WarmupContext 加独立的 per-run 锁，所有对 ctx 的读写统一通过该锁保护；CONTINUE_ANYWAY 下完全跳过依赖就绪检查：








        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_warmup\orchestrator.py
          
changes: undefined
          
现在重构 `execute_warmup` 及其内部方法，统一使用 per-run `_ctx_lock`，并修复 CONTINUE_ANYWAY 语义：









        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_warmup\orchestrator.py
          
changes: undefined
          
现在重构核心执行循环和内部方法：










        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_warmup\orchestrator.py
          
changes: undefined
          
现在修改 `_finalize_warmup` 和相关方法：











        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_warmup\orchestrator.py
          
changes: undefined
          

        
            
toolName: todo_write
            
status: success
          
Todos updated: 8 items
          
先运行现有测试验证重构不破坏原有功能：











        
            
toolName: run_command
            
status: success
          
command: python -m pytest tests/cache_warmup/ -v --tb=short 2>&1 undefined
          
好，有4个测试因语义变化需要更新。让我修改现有测试并添加新的测试用例：













        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\cache_warmup\test_cache_warmup.py
          
现在修改现有测试并添加新测试：
















        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\cache_warmup\test_cache_warmup.py
          
changes: undefined
          
现在修改 CONTINUE_ANYWAY 测试并添加新的测试类：
















        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\cache_warmup\test_cache_warmup.py
          
现在修改 CONTINUE_ANYWAY 测试并添加新测试类：

















        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\cache_warmup\test_cache_warmup.py
          
changes: undefined
          
现在在文件末尾添加三个新的测试类：优先级排序、空流程百分比和并发预热：

















        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\cache_warmup\test_cache_warmup.py
          

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\cache_warmup\test_cache_warmup.py
          
现在在文件末尾添加三个新的测试类：


















        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\cache_warmup\test_cache_warmup.py
          
changes: undefined
          

        
            
toolName: todo_write
            
status: success
          
Todos updated: 8 items
          
运行所有测试：



















        
            
toolName: run_command
            
status: success
          
command: python -m pytest tests/cache_warmup/ -v --tb=short 2>&1 undefined
          
2个小问题需要修复：1) 注册任务时同步更新 total_tasks；2) 并发测试的 key 字符串匹配错误。让我修复：

















        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_warmup\orchestrator.py
          
changes: undefined
          
现在修复并发测试的 key 匹配问题：



















        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\cache_warmup\test_cache_warmup.py
          
changes: undefined
          
再次运行测试：





















        
            
toolName: run_command
            
status: success
          
command: python -m pytest tests/cache_warmup/ -v --tb=short 2>&1 undefined
          
82 个测试全部通过！现在更新 README.md：





















        
            
toolName: todo_write
            
status: success
          
Todos updated: 8 items
          
现在更新 README.md，增加线程安全、CONTINUE_ANYWAY 明确语义和优先级排序的说明：


















        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_warmup\README.md
          

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_warmup\README.md
          
现在更新 README.md：先更新功能表、失败策略表和组件说明，然后新增线程安全和优先级排序章节：





















        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_warmup\README.md
          
changes: undefined
          
现在修改失败策略表和说明，然后增加线程安全、优先级调度和 CONTINUE_ANYWAY 额外示例的章节：





















        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_warmup\README.md
          
changes: undefined
          
现在在使用示例中增加 CONTINUE_ANYWAY 的降级处理示例和优先级调度示例。先读取现有的示例部分：

























        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_warmup\README.md
          
现在新增 CONTINUE_ANYWAY 示例和优先级调度示例：



























        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_warmup\README.md
          
changes: undefined
          
继续更新后续章节号：

























        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_warmup\README.md
          
更新章节号：


























        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_warmup\README.md
          
changes: undefined
          

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_warmup\README.md
          

        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_warmup\README.md
          
changes: undefined
          

        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_warmup\README.md
          
changes: undefined
          

        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_warmup\README.md
          
changes: undefined
          
再次运行测试确认全部通过：



























        
            
toolName: run_command
            
status: success
          
command: python -m pytest tests/cache_warmup/ -v --tb=short 2>&1 undefined
          
全部完成！总结如下：

---

## ✅ 所有问题已修复（82 个测试全部通过）

### 修复的 7 个问题汇总

| # | 问题 | 修复方式 | 涉及文件 |
|---|------|----------|----------|
| 1 | **线程安全**：锁持有范围零散，多 run 并发时有竞态 | **双层锁模型**：全局 `self._lock` 保护 `_contexts` 字典，每个 run 私有 `ctx._ctx_lock` 保护该 run 全部状态；所有 ctx 访问统一加锁，用户回调在锁外执行 | [orchestrator.py](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/cache_warmup/orchestrator.py) |
| 2 | **CONTINUE_ANYWAY 语义歧义**：实际与 SKIP_DEPENDENTS 行为一致 | `_dependencies_ready` 中当 `strategy == CONTINUE_ANYWAY` 直接返回 `True`，由用户回调自行容错上游缺失数据 | [orchestrator.py::_dependencies_ready](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/cache_warmup/orchestrator.py) |
| 3 | **进度百分比矛盾**：NOT_STARTED + 0 tasks 显示 100% | `progress_percentage` 属性先判断 `state == NOT_STARTED` 则返回 0.0；终态 + total=0 才返回 100% | [progress.py::WarmupProgress](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/cache_warmup/progress.py) |
| 4 | **priority 字段未使用**：Kahn 算法用 deque 与 priority 无关 | 用 `heapq` 最小堆替换 `deque`，入堆格式 `(-priority, task_id)`，同层级任务按 priority 降序弹出 | [topology.py::TopologySorter.sort](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/cache_warmup/topology.py) |
| 5 | **补充单元测试** | 新增 3 个测试类共 **13 个用例**：`TestPriorityScheduling`(4)、`TestEmptyRunProgress`(3)、`TestConcurrentWarmupRuns`(4) | [test_cache_warmup.py](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/tests/cache_warmup/test_cache_warmup.py) |
| 6 | **更新 README.md** | 新增：3.1 线程安全保证章节、3.2 优先级调度行为、4.3 CONTINUE_ANYWAY 降级处理示例、4.4 优先级调度示例；更新功能表和失败策略表；说明 progress_percentage 状态语义 | [README.md](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/cache_warmup/README.md) |
| 7 | **全部测试通过** | 运行 `python -m pytest tests/cache_warmup/ -v` → **82 passed** | ✅ |

### 新增测试覆盖

```
TestPriorityScheduling (4 用例)：验证 Kahn+heapq 的 priority 降序行为（含依赖混合、同优先级稳定、Orchestrator 端到端）
TestEmptyRunProgress  (3 用例)：NOT_STARTED → 0%，已执行空流程 → 100%，非空未开始 → 0% + total_tasks 同步
TestConcurrentWarmupRuns (4 用例)：多 run 状态隔离、多线程并发无重复执行、执行中并发查询安全、不同 run 不同策略
```