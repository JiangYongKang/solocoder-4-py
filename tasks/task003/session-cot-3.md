好的，我来逐一修复这5个问题。先创建任务清单：
        
            
toolName: todo_write
            
status: success
          
Todos updated: 5 items
          
开始修复。先读取相关文件：

        
            
toolName: todo_write
            
status: success
          
Todos updated: 5 items
          

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_warmup\topology.py
          

        
            
toolName: search_by_regex
            
status: success
          
query: orch\.get_cached_data\s*# no-op
          

        
            
toolName: search_by_regex
            
status: success
          
query: _handle_failure
          

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_warmup\README.md
          
继续查看 _handle_failure 完整内容和 README 结构：


        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_warmup\orchestrator.py
          

        
            
toolName: search_by_regex
            
status: success
          
query: ^## \d
          
先检查 `get_all_downstream` 函数实现确认其只读特性：



        
            
toolName: search_by_regex
            
status: success
          
query: def get_all_downstream
          
好的，`get_all_downstream` 是纯只读函数。现在开始修复所有问题：






        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_warmup\topology.py
          
changes: undefined
          

        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\cache_warmup\test_cache_warmup.py
          
changes: undefined
          

        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_warmup\orchestrator.py
          
changes: undefined
          

        
            
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
          
所有代码修改完成，更新状态并运行测试：







        
            
toolName: todo_write
            
status: success
          
Todos updated: 5 items
          

        
            
toolName: run_command
            
status: success
          
command: python -m pytest tests/cache_warmup/ -v --tb=short 2>&1 undefined
          
82 个测试全部通过！现在更新状态：









        
            
toolName: todo_write
            
status: success
          
Todos updated: 5 items
          
---

## ✅ 全部 5 个问题已修复（82 个测试通过）

### 修复汇总

| # | 问题 | 修复方式 | 涉及文件 |
|---|------|----------|----------|
| 1 | `topology.py` 中 `deque` import 未使用 | 删除 `from collections import deque` | [topology.py](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/cache_warmup/topology.py#L1-L1) |
| 2 | 测试中孤立的 `orch.get_cached_data  # no-op` 语句 | 删除该行无操作残留代码 | [test_cache_warmup.py:1248](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/tests/cache_warmup/test_cache_warmup.py#L1248-L1248) |
| 3 | `_handle_failure` 中 `get_all_downstream` 在锁内执行，深依赖图时长时间持锁 | 锁内先获取 `ctx.tasks` 快照（浅拷贝 dict），然后在**锁外**调用 `get_all_downstream(tasks_snapshot, ...)` 做 BFS，锁持有时间从 O(n) 降为 O(1) | [orchestrator.py::_handle_failure](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/cache_warmup/orchestrator.py#L336-L342) |
| 4 | README 章节号断裂（4.6 后直接跳到 7） | 将 7→5、8→6、9→7，章节号连续 | [README.md](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/cache_warmup/README.md) |
| 5 | 测试通过 | `python -m pytest tests/cache_warmup/ -v` → **82 passed** | ✅ |

### 问题 3 的关键代码变更

**修复前**（锁内 BFS，O(n) 持锁时间）：
```python
if strategy == FailureStrategy.SKIP_DEPENDENTS:
    with ctx._ctx_lock:
        downstream = TopologySorter.get_all_downstream(ctx.tasks, failed_task_id)  # 🔴 锁内 BFS
    ...
```

**修复后**（锁内仅拷贝引用，O(1) 持锁；BFS 在锁外）：
```python
if strategy == FailureStrategy.SKIP_DEPENDENTS:
    with ctx._ctx_lock:
        tasks_snapshot = dict(ctx.tasks)  # ✅ 锁内仅做浅拷贝
    downstream = TopologySorter.get_all_downstream(tasks_snapshot, failed_task_id)  # ✅ 锁外 BFS
    ...
```

### 最终 README 章节结构

```
1. 模块功能
2. 核心概念
3. 失败策略 (FailureStrategy)
   3.1 线程安全保证
   3.2 优先级调度行为
4. 使用示例
   4.1 ~ 4.6
5. 异常场景与处理
6. 文件结构
7. 运行测试
```