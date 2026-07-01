我需要修复缓存雪崩防护模块中的多个问题。让我先创建任务列表，然后逐一修复。

        
            
toolName: todo_write
            
status: success
          
Todos updated: 8 items
          
让我先读取当前的核心实现文件，然后逐一修复问题。


        
            
toolName: todo_write
            
status: success
          
Todos updated: 8 items
          

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_avalanche_guard\cache_avalanche_guard.py
          
现在我已经看到了完整的代码。让我逐一修复这5个问题。首先需要修改 `CacheEntry` 添加 `original_ttl` 字段，然后修复各个方法。

先修改 `cache_entry.py` 添加 `original_ttl` 字段：



        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_avalanche_guard\cache_entry.py
          
现在开始修复所有问题。首先修改 `CacheEntry` 添加 `original_ttl` 字段：







        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_avalanche_guard\cache_entry.py
          
changes: undefined
          
更新 `to_dict` 和 `from_dict` 方法，以及 `mark_rebuilt` 方法：












        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_avalanche_guard\cache_entry.py
          
changes: undefined
          

        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_avalanche_guard\cache_entry.py
          
changes: undefined
          
现在更新 todo 列表并修复核心实现文件中的5个问题：









        
            
toolName: todo_write
            
status: success
          
Todos updated: 8 items
          
现在修复 `cache_avalanche_guard.py` 中的所有5个问题。首先修改 `_apply_jitter` 消除双重时间戳，然后修改其他方法：










        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_avalanche_guard\cache_avalanche_guard.py
          
changes: undefined
          
现在修复 `_find_hot_keys_locked` 和 `_renew_hot_key` 使用条目自身 TTL，同时更新调用方传入 `now` 参数：



















        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_avalanche_guard\cache_avalanche_guard.py
          
changes: undefined
          

        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_avalanche_guard\cache_avalanche_guard.py
          
changes: undefined
          
现在修复 `_rebuild_cache` 方法，实现 ASYNC 策略和超时降级持久化：























        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_avalanche_guard\cache_avalanche_guard.py
          
changes: undefined
          
现在更新 `_do_rebuild` 和 `set` 方法，设置 `original_ttl` 并传入 `now` 参数给 `_apply_jitter`：

























        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_avalanche_guard\cache_avalanche_guard.py
          
现在更新 `_do_rebuild` 方法，设置 `original_ttl` 并传入 `now` 参数：



























        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_avalanche_guard\cache_avalanche_guard.py
          
changes: undefined
          
现在更新 `set` 方法，设置 `original_ttl` 并传入 `now` 参数：




























        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_avalanche_guard\cache_avalanche_guard.py
          

        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_avalanche_guard\cache_avalanche_guard.py
          
changes: undefined
          
现在更新任务列表，然后编写新增功能的单元测试：




























        
            
toolName: todo_write
            
status: success
          
Todos updated: 8 items
          
现在编写新增功能的单元测试。先更新 `test_cache_entry.py` 添加 `original_ttl` 相关测试，然后在 `test_cache_avalanche_guard.py` 中添加新功能测试：






























        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\cache_avalanche_guard\test_cache_entry.py
          
changes: undefined
          
现在在 `test_cache_avalanche_guard.py` 末尾添加新功能测试：


































        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\cache_avalanche_guard\test_cache_avalanche_guard.py
          
现在添加新功能测试到测试文件末尾：

































        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\cache_avalanche_guard\test_cache_avalanche_guard.py
          
changes: undefined
          
现在更新任务列表，然后运行测试：



































        
            
toolName: todo_write
            
status: success
          
Todos updated: 8 items
          
现在更新 README.md 文档，添加异步重建、降级持久化和 TTL 继承的说明：



































        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_avalanche_guard\README.md
          
现在更新 README.md，添加修复后的功能说明：





































        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_avalanche_guard\README.md
          
changes: undefined
          

        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_avalanche_guard\README.md
          
changes: undefined
          

        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_avalanche_guard\README.md
          
changes: undefined
          

        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_avalanche_guard\README.md
          
changes: undefined
          
现在更新使用示例部分，添加 ASYNC 策略的示例：







































        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_avalanche_guard\README.md
          
现在添加 ASYNC 异步重建策略的使用示例：









































        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_avalanche_guard\README.md
          
changes: undefined
          
现在更新任务列表并运行测试：











































        
            
toolName: todo_write
            
status: success
          
Todos updated: 8 items
          
现在运行测试，确保所有测试通过：











































        
            
toolName: run_command
            
status: success
          
command: poetry run pytest tests/cache_avalanche_guard/ -q undefined
          
测试命令运行了整个测试目录，我需要只运行 `cache_avalanche_guard` 目录的测试：













































        
            
toolName: run_command
            
status: success
          
command: poetry run pytest tests/cache_avalanche_guard/ -q undefined
          
让我直接指定具体的测试文件路径：















































        
            
toolName: run_command
            
status: running
          
command: poetry run pytest tests/cache_avalanche_guard/test_cache_entry.py tests/cache_avalanche_guard/test_cache_avalanche_guard.py -q undefined
          
让我等待测试完成：
















































        
            
toolName: check_command_status
            
status: success
          
          

        
            
toolName: check_command_status
            
status: success
          
          
测试似乎卡住了，让我停止并查看详细输出：


















































        
            
toolName: StopCommand
            
status: success
          
          

        
            
toolName: run_command
            
status: success
          
command: poetry run pytest tests/cache_avalanche_guard/test_cache_avalanche_guard.py::TestTimeoutDegradedValue -v --tb=short undefined
          
让我单独运行新添加的测试类，看看哪个测试失败了：

















































        
            
toolName: run_command
            
status: running
          
command: poetry run pytest tests/cache_avalanche_guard/test_cache_avalanche_guard.py::TestDegradedValuePersistence -v --tb=short undefined
          
测试卡住了，问题是 `test_timeout_degraded_value_has_independent_ttl` 测试中的循环。让我停止并修复这个测试：

















































        
            
toolName: StopCommand
            
status: success
          
          
让我查看并修复这个卡住的测试：



















































        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\cache_avalanche_guard\test_cache_avalanche_guard.py
          
问题是测试的逻辑有缺陷。第一个请求（worker）是重建者，它会阻塞在 loader 上等待 `can_complete`。而主线程调用 `get()` 时没有 `loader`，所以直接返回 `None`，造成死循环。让我修复这个测试：





















































        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\cache_avalanche_guard\test_cache_avalanche_guard.py
          
changes: undefined
          
现在让我运行所有 cache_avalanche_guard 测试，看是否还有其他问题：





















































        
            
toolName: run_command
            
status: success
          
command: poetry run pytest tests/cache_avalanche_guard/test_cache_entry.py tests/cache_avalanche_guard/test_cache_avalanche_guard.py::TestAsyncRebuildStrategy -v --tb=short undefined
          
很好！现在让我运行完整的 cache_avalanche_guard 测试套件：




















































        
            
toolName: run_command
            
status: success
          
command: poetry run pytest tests/cache_avalanche_guard/test_cache_entry.py tests/cache_avalanche_guard/test_cache_avalanche_guard.py -v --tb=short undefined
          
有3个测试失败。让我分析并修复这些问题：

1. 第一个测试的预期基于旧的阈值逻辑（使用 `default_ttl`）
2. 第二个测试的预期值计算错误（应该基于续期时的时间，不是原始过期时间）
3. 第三个测试的 `hit_count` 被直接设置，但 `get_recent_hit_count` 统计的是 `access_timestamps`

让我修复这些测试：























































        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\cache_avalanche_guard\test_cache_avalanche_guard.py
          
现在修复这些测试：

























































        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\cache_avalanche_guard\test_cache_avalanche_guard.py
          
changes: undefined
          

        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\cache_avalanche_guard\test_cache_avalanche_guard.py
          
changes: undefined
          

        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\cache_avalanche_guard\test_cache_avalanche_guard.py
          
changes: undefined
          
现在再次运行测试：


























































        
            
toolName: run_command
            
status: success
          
command: poetry run pytest tests/cache_avalanche_guard/test_cache_entry.py tests/cache_avalanche_guard/test_cache_avalanche_guard.py -q undefined
          
还有一个测试失败。问题是两个条目的 `remaining_ttl` 都是 2 秒，而 `long` 条目的阈值是 `300 * 0.3 = 90` 秒，所以 `2 < 90`，两个都被判定为需要续期。让我修复测试设置：


























































        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\cache_avalanche_guard\test_cache_avalanche_guard.py
          
changes: undefined
          
现在再次运行测试：

























































        
            
toolName: run_command
            
status: success
          
command: poetry run pytest tests/cache_avalanche_guard/test_cache_entry.py tests/cache_avalanche_guard/test_cache_avalanche_guard.py -q undefined
          
两个测试失败都是因为抖动导致新的过期时间可能比原始过期时间更早。让我修复这些测试，禁用抖动并调整时间：

























































        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\cache_avalanche_guard\test_cache_avalanche_guard.py
          
changes: undefined
          

        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\cache_avalanche_guard\test_cache_avalanche_guard.py
          
changes: undefined
          
现在再次运行测试：



























































        
            
toolName: run_command
            
status: success
          
command: poetry run pytest tests/cache_avalanche_guard/ -q undefined
          
所有 91 个测试全部通过！现在更新任务列表：



























































        
            
toolName: todo_write
            
status: success
          
Todos updated: 8 items
          
所有问题已修复完成！以下是修复总结：

## 修复内容

### 1. ASYNC 异步重建策略实现
在 `_rebuild_cache` 方法中添加了对 `strategy` 参数的检查，当使用 `RebuildStrategy.ASYNC` 时：
- 启动守护线程后台执行 `_do_rebuild_async`
- 立即返回降级值并持久化到缓存
- 调用方无需等待重建完成

### 2. 降级值持久化
重建超时后，降级值会被写入缓存并标记为 `DEGRADED` 状态，使用 `degraded_ttl_seconds` 作为过期时间，后续请求无需传入 `degraded_value` 即可获得降级保护。

### 3. 续期 TTL 继承
- `_renew_hot_key` 方法使用 `entry.original_ttl` 计算新过期时间
- 新增 `original_ttl` 字段存储条目创建时的 TTL
- `set()` 和 `_do_rebuild()` 方法都会设置该字段

### 4. 续期阈值基于条目 TTL
`_find_hot_keys_locked` 方法使用 `entry.original_ttl * 0.3` 作为续期阈值，避免短 TTL 条目在检查间隔内过期。

### 5. 消除双重时间戳
`_apply_jitter` 方法接受 `now` 参数，使用调用方传入的时间戳计算抖动，避免高并发场景下的精度问题。

## 测试结果
**91 个测试全部通过**，包括：
- 7 个 `original_ttl` 相关测试
- 4 个异步重建策略测试
- 3 个降级持久化测试
- 4 个自定义 TTL 续期测试
- 4 个短 TTL 续期阈值测试

修改的文件：
- [cache_avalanche_guard.py](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/cache_avalanche_guard/cache_avalanche_guard.py)
- [cache_entry.py](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/cache_avalanche_guard/cache_entry.py)
- [test_cache_avalanche_guard.py](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/tests/cache_avalanche_guard/test_cache_avalanche_guard.py)
- [test_cache_entry.py](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/tests/cache_avalanche_guard/test_cache_entry.py)
- [README.md](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/cache_avalanche_guard/README.md)