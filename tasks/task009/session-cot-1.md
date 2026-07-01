我来帮你实现这个内部任务运行器功能模块。首先让我了解一下项目结构和现有代码风格。
        
            
toolName: todo_write
            
status: success
          
Todos updated: 5 items
          

        
            
toolName: view_folder
            
status: success
          
c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py
          

        
            
toolName: view_folder
            
status: success
          
c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py
          

        
            
toolName: file_search
            
status: success
          
file_pattern: **/pyproject.toml
          
让我查看几个现有模块的代码风格和结构：

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\pyproject.toml
          

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\module_init_graph\__init__.py
          

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\plugin_registry\__init__.py
          

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\plugin_registry\plugin_registry.py
          

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\plugin_registry\exceptions.py
          

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\plugin_registry\constants.py
          

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\plugin_registry\test_plugin_registry.py
          

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\transaction_log\log_entry.py
          
很好，我已经完全理解了项目的代码风格和结构。现在开始实现内部任务运行器模块。


        
            
toolName: todo_write
            
status: success
          
Todos updated: 5 items
          
现在我开始创建模块的各个文件。按照项目的代码风格，我将创建以下文件：


        
            
toolName: Write
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\internal_task_runner\constants.py
          
changes: undefined
          

        
            
toolName: Write
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\internal_task_runner\exceptions.py
          
changes: undefined
          
现在创建任务定义和运行记录的数据模型：



        
            
toolName: Write
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\internal_task_runner\task_run_record.py
          
changes: undefined
          

        
            
toolName: Write
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\internal_task_runner\task_definition.py
          
changes: undefined
          
现在创建核心的任务运行器类。关键设计点：支持时间注入机制，使测试不依赖真实等待：




        
            
toolName: Write
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\internal_task_runner\internal_task_runner.py
          
changes: undefined
          
现在创建包的 `__init__.py` 文件导出所有公共接口：





        
            
toolName: Write
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\internal_task_runner\__init__.py
          
changes: undefined
          

        
            
toolName: todo_write
            
status: success
          
Todos updated: 5 items
          
现在创建测试文件：






        
            
toolName: Write
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\internal_task_runner\__init__.py
          
changes: undefined
          

        
            
toolName: Write
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\internal_task_runner\test_internal_task_runner.py
          
changes: undefined
          

        
            
toolName: todo_write
            
status: success
          
Todos updated: 5 items
          
现在编写 README.md 文档：







        
            
toolName: Write
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\internal_task_runner\README.md
          
changes: undefined
          
现在运行测试验证功能正确性：






        
            
toolName: todo_write
            
status: success
          
Todos updated: 5 items
          

        
            
toolName: run_command
            
status: success
          
command: python -m pytest tests/internal_task_runner/ -v undefined
          
有3个测试失败，我来逐一修复。问题分析：

1. `test_register_periodic_without_interval_via_runner`：TaskDefinition 创建在 raises 块外就已抛异常
2. `test_periodic_runs_repeatedly_no_real_wait`：落后多周期时 next_run_at 被跳到 `now + interval`，测试假设需调整
3. `test_stats_mixed`：active_tasks 实际是 1（只有 m1），断言值有误






        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\internal_task_runner\test_internal_task_runner.py
          

        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\internal_task_runner\test_internal_task_runner.py
          
changes: undefined
          
现在修复第二个和第三个测试：







        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\internal_task_runner\test_internal_task_runner.py
          

        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\internal_task_runner\test_internal_task_runner.py
          
changes: undefined
          
现在修复第三个测试：









        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\internal_task_runner\test_internal_task_runner.py
          

        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\internal_task_runner\test_internal_task_runner.py
          
changes: undefined
          
现在重新运行测试验证修复：








        
            
toolName: run_command
            
status: success
          
command: python -m pytest tests/internal_task_runner/ -v undefined
          
全部 84 个测试通过！现在标记任务完成：










        
            
toolName: todo_write
            
status: success
          
Todos updated: 5 items
          
## 实现完成 ✅

internal_task_runner 模块已完整实现，全部 **84 个单元测试通过**。以下是交付内容：

---

### 📁 模块文件结构

**源代码**（位于 `src/solocoder_4_py/internal_task_runner/`）：

| 文件 | 说明 |
|------|------|
| [\_\_init\_\_.py](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/internal_task_runner/__init__.py) | 包入口，导出所有公共 API |
| [constants.py](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/internal_task_runner/constants.py) | 枚举（TaskType / TaskStatus / RunStatus）和常量 |
| [exceptions.py](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/internal_task_runner/exceptions.py) | 异常层级定义（7 种异常） |
| [task_definition.py](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/internal_task_runner/task_definition.py) | TaskDefinition / TaskRuntimeInfo 数据模型 |
| [task_run_record.py](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/internal_task_runner/task_run_record.py) | TaskRunRecord 运行记录（含 duration_ms 属性、to_dict/from_dict） |
| [internal_task_runner.py](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/internal_task_runner/internal_task_runner.py) | 核心类 InternalTaskRunner + TaskRunnerStats |
| [README.md](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/internal_task_runner/README.md) | 模块文档（功能、任务类型、运行历史、使用示例） |

**测试代码**（位于 `tests/internal_task_runner/`）：
- [test_internal_task_runner.py](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/tests/internal_task_runner/test_internal_task_runner.py) — 84 个用例，覆盖常量枚举、数据模型、注册注销、生命周期、Tick 调度、手动触发、重试机制、历史查询、任务发现、统计、批量操作、线程安全、综合场景

---

### 🎯 核心特性

**1. 三种任务类型**
- `ONE_SHOT`：一次性任务，激活后下次 `tick()` 执行一次
- `PERIODIC`：周期任务，按 `interval_seconds` 重复调度，支持 `pause()` / `resume()`
- `MANUAL`：手动触发任务，调用 `trigger(task_id, **kwargs)` 执行

**2. 完整运行历史**
- 每次执行产生 `TaskRunRecord`（run_id、状态、起止时间、结果/错误、重试次数、触发方式等）
- 支持 `limit` / `status_filter` / `since` / `until` 多维查询，`get_latest_run` / `get_run_by_id` 快捷接口
- 每任务历史受 `history_limit` 保护（默认 1000 条）

**3. 测试无需真实等待**
- 构造时或 `set_time_provider()` 注入自定义时间函数（示例中的 `FakeClock`）
- 配合 `tick()` 手动推进调度器，周期任务验证纯逻辑完成

**4. 其它特性**
- `max_retries` 失败自动重试
- 标签索引 + 多标签匹配查询
- `threading.RLock` 线程安全（含并发测试）
- 批量操作：`activate_all()` / `cancel_all()` / `clear()`
- 统计信息 `get_stats()`：按任务状态、运行结果维度汇总