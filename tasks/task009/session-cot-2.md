好的，我来逐一修复这些问题。先创建任务列表并分析现有代码：



        
            
toolName: todo_write
            
status: success
          
Todos updated: 9 items
          
先读取关键代码，分析每一个问题：







        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\internal_task_runner\internal_task_runner.py
          
好的，我已经完整分析了所有问题。现在开始逐一修复。先从简单的问题开始，然后处理复杂的问题。





        
            
toolName: todo_write
            
status: success
          
Todos updated: 8 items
          
现在开始修复。先扩展 `TaskRuntimeInfo` 添加 `catch_up` 字段，然后修改核心运行器：







        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\internal_task_runner\task_definition.py
          
现在进行大规模修复。先扩展 `TaskRuntimeInfo`，再重写核心运行器：









        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\internal_task_runner\task_definition.py
          
changes: undefined
          
现在重写 `internal_task_runner.py`，一次性修复所有问题：









        
            
toolName: Write
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\internal_task_runner\internal_task_runner.py
          
changes: undefined
          

        
            
toolName: todo_write
            
status: success
          
Todos updated: 8 items
          
现在补充新的单元测试（追加到测试文件末尾）：










        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\internal_task_runner\test_internal_task_runner.py
          
现在追加新的测试类到测试文件末尾：









        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\internal_task_runner\test_internal_task_runner.py
          
changes: undefined
          

        
            
toolName: CompactFake
            
status: success
          
          
我先检查当前代码状态，确认所有修复和新增测试已写入文件，然后按顺序完成 README 更新和测试验证。
        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\internal_task_runner\internal_task_runner.py
          

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\internal_task_runner\task_definition.py
          

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\internal_task_runner\README.md
          
让我检查测试文件是否包含所有新增的测试类：

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\internal_task_runner\test_internal_task_runner.py
          
好的，所有核心代码修复和新增测试都已确认写入。现在更新 TodoWrite 状态并开始 README 更新：



        
            
toolName: todo_write
            
status: success
          
Todos updated: 8 items
          
现在更新 README.md，补充四个新章节说明：

        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\internal_task_runner\README.md
          
changes: undefined
          
现在在"测试中模拟时间"章节之前插入四个新的详细说明章节：


        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\internal_task_runner\README.md
          
changes: undefined
          
README 更新完成。现在运行测试验证所有修复：



        
            
toolName: todo_write
            
status: success
          
Todos updated: 8 items
          

        
            
toolName: run_command
            
status: success
          
command: poetry run pytest tests/internal_task_runner/ -q undefined
          
有一个测试失败。问题是测试断言有误：resume 时 t=110，next_run_at=120，10 次 advance(1.0) 后到了 t=120，最后一次 tick 会触发执行。需要调整测试时序。让我修复这个测试：

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\internal_task_runner\test_internal_task_runner.py
          

        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\internal_task_runner\test_internal_task_runner.py
          
changes: undefined
          
重新运行测试验证修复：


        
            
toolName: run_command
            
status: success
          
command: poetry run pytest tests/internal_task_runner/ -q undefined
          
所有 98 个测试全部通过！更新任务状态：



        
            
toolName: todo_write
            
status: success
          
Todos updated: 8 items
          
## 修复完成，所有 8 项需求已全部落地：

### ✅ 核心代码修复（5 项）

| # | 问题 | 修复位置 | 修复内容 |
|---|------|----------|----------|
| 1 | 无超时中断 / 无重试延迟 | [internal_task_runner.py#L820-L877 | `_execute_single_run | 新增 ThreadPoolExecutor+Future.result(timeout) 做超时控制，重试前 `_sleep(retry_delay) | 重试延迟支持 sleep_provider 注入 |
| 2 | resume 丢弃暂停周期 | [internal_task_runner.py#L270-L310 + task_definition.py | `TaskRuntimeInfo.catch_up` 字段；resume(catch_up=True/False) 两档；tick() 中 catch_up=True 时每次只前进一 interval，追平后标志自动关闭 |
| 3 | 锁外冗余 last_error 赋值 | [internal_task_runner.py#L882-L891 | 删除锁外重复行，统一在 `_commit_run_record()` 内完成所有计数更新 |
| 4 | trigger 竞态窗口 | [internal_task_runner.py#L760-L794 | _execute_single_run 入口处持锁完成终态二次校验 + definition_snapshot 快照；窗口期 cancel/unregister 产生 SKIPPED 记录而非误执行 |
| 5 | register 冗余校验 | [internal_task_runner.py#L133-L163 | 删除 is_periodic() and interval is None 分支（已由 TaskDefinition.__post_init__ 拦截 |

### ✅ 新增单元测试（14 用例，5 个测试类）
- `TestHandlerTimeout`：超时 FAILED / 无超时正常 / 时限内正常
- `TestRetryDelay`：重试延迟调用次数 / 首次不延迟 / 零延迟不 sleep
- `TestResumeCatchUp`：catch_up=False 丢弃 / catch_up=True 补跑 / 追赶中时钟继续推进
- `TestRaceAndDynamicHandler`：cancel 窗口期→SKIPPED / unregister 窗口期安全 / 运行前动态替换生效 / 快照防止飞行中替换影响
- `TestCatchUpFlagsReset`：activate/reset 对 catch_up 字段正确清除

### ✅ 文档更新
[README.md](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/internal_task_runner/README.md) 新增四章：
- **Handler 超时机制（原理、Python 线程无法 kill 的注意事项、代码示例
- **重试延迟策略（首次不延迟、sleep_provider 注入示例
- **周期任务追赶补偿（catch-up）（两档策略对比、追赶执行过程表、自动关闭
- **触发器竞态防护（问题背景、终态二次校验、definition_snapshot 一致性

### ✅ 测试结果
```
98 passed in 0.31s
```
运行 `poetry run pytest tests/internal_task_runner/ -q`，98 个测试全部通过。