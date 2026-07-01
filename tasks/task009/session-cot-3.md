我先检查当前代码状态，然后制定修复计划。

        
            
toolName: todo_write
            
status: success
          
Todos updated: 5 items
          

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\internal_task_runner\internal_task_runner.py
          

        
            
toolName: search_by_regex
            
status: success
          
query: definition\.handler|_tasks\[.*\]\.definition\.handler
          

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\internal_task_runner\README.md
          
让我检查 README.md 后面部分是否已经有四个独立章节：


        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\internal_task_runner\README.md
          
我看到 README.md 已经有四个独立章节了，但还需要补充 `set_task_handler` 方法的文档。让我先更新 Todo 并开始实现：



        
            
toolName: todo_write
            
status: success
          
Todos updated: 5 items
          
首先移除无效的 `InvalidScheduleError` 导入：




        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\internal_task_runner\internal_task_runner.py
          
changes: undefined
          
现在实现 `set_task_handler` 公共方法：







        
            
toolName: todo_write
            
status: success
          
Todos updated: 5 items
          

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\internal_task_runner\internal_task_runner.py
          

        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\internal_task_runner\internal_task_runner.py
          
changes: undefined
          
现在检查 `__init__.py` 确保新方法在公共 API 中可见，并重构所有涉及 handler 替换的测试：







        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\internal_task_runner\__init__.py
          
`__init__.py` 保留 `InvalidScheduleError` 导出是合理的（它是公共 API，其他模块可能使用）。现在重构测试代码中所有 8 处直接操作 handler 的地方。让我先查看每一处的上下文：







        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\internal_task_runner\test_internal_task_runner.py
          

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\internal_task_runner\test_internal_task_runner.py
          

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\internal_task_runner\test_internal_task_runner.py
          
现在重构所有 8 处 handler 替换。先修复前两处（第 709 行和第 894、901 行）：









        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\internal_task_runner\test_internal_task_runner.py
          
changes: undefined
          

        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\internal_task_runner\test_internal_task_runner.py
          
changes: undefined
          
现在修复第 1636-1691 行的 4 处 handler 替换：











        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\internal_task_runner\test_internal_task_runner.py
          
changes: undefined
          
现在验证是否还有遗漏的 handler 直接操作：










        
            
toolName: search_by_regex
            
status: success
          
query: definition\.handler|_tasks\[.*\]\.definition\.handler
          
现在更新 README.md，补充 `set_task_handler` 的文档说明，并在"模块功能概览"中添加对应的条目：











        
            
toolName: todo_write
            
status: success
          
Todos updated: 5 items
          

        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\internal_task_runner\README.md
          
changes: undefined
          
现在在"触发器竞态防护"章节之后添加"动态 Handler 替换"独立章节：











        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\internal_task_runner\README.md
          
changes: undefined
          
现在运行测试验证所有修复：













        
            
toolName: todo_write
            
status: success
          
Todos updated: 5 items
          

        
            
toolName: run_command
            
status: success
          
command: poetry run pytest tests/internal_task_runner/ -q undefined
          
所有 98 个测试全部通过！更新任务状态：















        
            
toolName: todo_write
            
status: success
          
Todos updated: 5 items
          
## 全部 4 项修复已完成

### ✅ 修复 #1：完善 README.md 文档
[README.md](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/internal_task_runner/README.md) 已包含 5 个完整独立章节：
- **## Handler 超时机制**：原理说明（ThreadPoolExecutor + Future.result(timeout)）、代码示例、Python 线程无法强制 kill 的注意事项
- **## 重试延迟策略**：首次不延迟规则、sleep_provider 可注入测试示例
- **## 周期任务追赶补偿（catch-up）**：catch_up=True/False 两档策略对比表、追赶执行过程表、追平自动关闭机制
- **## 触发器竞态防护**：问题背景、终态二次校验 + definition_snapshot 流程图、窗口期 cancel/unregister 行为说明
- **## 动态 Handler 替换**（新增）：`set_task_handler()` 基本用法、与 definition_snapshot 交互行为表、线程安全说明

---

### ✅ 修复 #2：实现 `set_task_handler` 公共方法

在 [internal_task_runner.py#L206-L228](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/internal_task_runner/internal_task_runner.py#L206-L228) 新增：

```python
def set_task_handler(
    self, task_id: str, handler: Callable[..., Any]
) -> TaskDefinition:
    """动态替换任务的 handler（线程安全）"""
```

并重构测试中 **8 处**直接操作私有字段的代码：

| 原代码 | 替换为 |
|--------|--------|
| `info = runner2._tasks["m1"]; info.definition.handler = make_handler(i)` | `runner2.set_task_handler("m1", make_handler(i))` |
| `info = runner._tasks["m1"]; info.definition.handler = MagicMock(...)` | `runner.set_task_handler("m1", MagicMock(...))` |
| `info.definition.handler = fail` | `runner.set_task_handler("m1", fail)` |
| `info = runner.get_task("dyn"); info.definition.handler = new_handler` | `runner.set_task_handler("dyn", new_handler)` |
| `info = runner.get_task("mid"); original_handler = info.definition.handler` | `original_handler = runner.get_definition("mid").handler` |
| `info.definition.handler = lambda **kw: "injected"` | `runner.set_task_handler("mid", lambda **kw: "injected")` |
| `info.definition.handler = original_handler` | `runner.set_task_handler("mid", original_handler)` |

---

### ✅ 修复 #3：移除无效导入

从 [internal_task_runner.py#L19-L25](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/internal_task_runner/internal_task_runner.py#L19-L25) 中移除了不再使用的 `InvalidScheduleError` 导入。

> **注意**：`__init__.py` 仍保留该导出（公共 API，不影响内部实现）。

---

### ✅ 修复 #4：测试全部通过
```
98 passed in 0.35s
```
运行 `poetry run pytest tests/internal_task_runner/ -q`，98 个测试全部通过。