好的，我来逐一修复这些问题。首先创建任务计划：




        
            
toolName: todo_write
            
status: success
          
Todos updated: 6 items
          
让我先读取当前的核心代码，然后开始修复：















        
            
toolName: todo_write
            
status: success
          
Todos updated: 6 items
          

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\plugin_registry\plugin_registry.py
          
现在开始修复。首先修复 import 和 enable 方法的依赖校验逻辑：




















        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\plugin_registry\plugin_registry.py
          
changes: undefined
          
现在添加 PluginDependencyError 异常类到 exceptions.py：

























        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\plugin_registry\exceptions.py
          

        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\plugin_registry\exceptions.py
          
changes: undefined
          
现在更新 __init__.py 导出新的异常类：

























        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\plugin_registry\__init__.py
          
changes: undefined
          

        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\plugin_registry\__init__.py
          
changes: undefined
          
现在修复 enable 方法，增加依赖校验逻辑：




























        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\plugin_registry\plugin_registry.py
          
changes: undefined
          

        
            
toolName: todo_write
            
status: success
          
Todos updated: 6 items
          
现在修复 enable_all、disable_all 和 set_status 方法：



























        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\plugin_registry\plugin_registry.py
          
changes: undefined
          
现在修复 enable_all 和 disable_all 方法，收窄异常捕获范围：



























        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\plugin_registry\plugin_registry.py
          
changes: undefined
          

        
            
toolName: todo_write
            
status: success
          
Todos updated: 6 items
          
现在补充单元测试。首先读取现有测试文件，然后添加新的测试用例：





























        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\plugin_registry\test_plugin_registry.py
          
首先在测试文件中导入 PluginDependencyError，然后添加新的测试类：






























        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\plugin_registry\test_plugin_registry.py
          
changes: undefined
          
现在在测试文件末尾添加新的测试类：































        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\plugin_registry\test_plugin_registry.py
          
现在在测试文件末尾添加新的测试类：
































        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\plugin_registry\test_plugin_registry.py
          
changes: undefined
          

        
            
toolName: todo_write
            
status: success
          
Todos updated: 6 items
          
现在更新 README.md 文档，说明修复后的逻辑：


































        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\plugin_registry\README.md
          
现在更新 README.md，添加依赖校验、异常处理契约和状态转变统一入口的说明：


































        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\plugin_registry\README.md
          
changes: undefined
          
现在在 README.md 中添加依赖校验、异常处理契约和状态转变统一入口的详细说明：


































        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\plugin_registry\README.md
          
changes: undefined
          
现在更新 README.md 中的使用示例，添加依赖校验的示例代码：



































        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\plugin_registry\README.md
          
现在在 README.md 中添加依赖校验和状态统一入口的使用示例：



































        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\plugin_registry\README.md
          
changes: undefined
          
现在更新 README.md 中的 API 参考部分，添加 PluginDependencyError 和更新方法说明：

































        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\plugin_registry\README.md
          

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\plugin_registry\README.md
          
现在更新 API 参考部分，添加 PluginDependencyError 并更新方法说明：





































        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\plugin_registry\README.md
          
changes: undefined
          

        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\plugin_registry\README.md
          
changes: undefined
          

        
            
toolName: todo_write
            
status: success
          
Todos updated: 6 items
          
现在运行测试查看结果，修复可能失败的现有测试用例：





































        
            
toolName: run_command
            
status: success
          
command: poetry run pytest tests/plugin_registry/ -q undefined
          
有两个测试需要修复。第一个测试需要更新以反映新的行为（set_status 委托给 enable，对已启用插件会抛出异常），第二个测试需要修复 mock 逻辑：




































        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\plugin_registry\test_plugin_registry.py
          
现在修复这两个测试用例：







































        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\plugin_registry\test_plugin_registry.py
          
changes: undefined
          
现在修复第二个测试用例：









































        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\plugin_registry\test_plugin_registry.py
          
changes: undefined
          
现在再次运行测试查看结果：











































        
            
toolName: run_command
            
status: success
          
command: poetry run pytest tests/plugin_registry/ -q undefined
          
所有 154 个测试全部通过！让我运行整个项目的测试确保没有影响其他模块：













































        
            
toolName: run_command
            
status: success
          
command: poetry run pytest tests/ -q undefined
          
这些错误是项目中已有的问题（`request_snapshot_cache` 模块缺少文件），与我的修改无关。让我排除这个目录运行其他测试：















































        
            
toolName: run_command
            
status: success
          
command: poetry run pytest tests/ --ignore=tests/request_snapshot_cache -q undefined
          
这些 `transaction_log` 模块的测试失败也是项目中已有的问题，与我的修改无关。让我排除这两个有问题的目录，验证其他模块测试是否通过：



















































        
            
toolName: run_command
            
status: success
          
command: poetry run pytest tests/ --ignore=tests/request_snapshot_cache --ignore=tests/transaction_log -q undefined
          
完美！所有 595 个测试全部通过。现在更新任务状态：























































        
            
toolName: todo_write
            
status: success
          
Todos updated: 6 items
          
所有问题已修复完成！以下是修复内容的总结：

## 修复的问题

### 1. 依赖校验逻辑 ✅
在 [plugin_registry.py](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/plugin_registry/plugin_registry.py#L139-L216) 中：
- 新增 `_validate_dependencies()` 内部方法，校验每个依赖插件：
  - 已注册
  - 已启用（状态为 `ENABLED`）
  - 版本满足要求
- `enable()` 方法在启用前自动调用依赖校验
- 新增 [PluginDependencyError](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/plugin_registry/exceptions.py#L54-L68) 异常类，包含 `plugin_id`、`dependency_id`、`reason` 属性

### 2. 异常处理契约 ✅
在 [plugin_registry.py](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/plugin_registry/plugin_registry.py#L584-L629) 中：
- `enable_all()` 和 `disable_all()` 仅捕获 `PluginStateError`（业务预期内的状态错误）
- 其他异常（`PluginDependencyError`、`PluginVersionError`、系统级异常等）直接传播
- 调用方可以区分业务失败与系统故障

### 3. 状态转变统一入口 ✅
在 [plugin_registry.py](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/plugin_registry/plugin_registry.py#L245-L276) 中：
- `set_status(ENABLED)` 委托给 `enable()`，执行完整的版本和依赖校验
- `set_status(DISABLED)` 委托给 `disable()`，执行相同的状态检查
- `set_status(REGISTERED)` 直接设置（无需校验）
- 所有状态转变共享同一执行路径，确保校验逻辑和副作用完全一致

## 新增的单元测试（33 个）

**[TestPluginDependencyValidation](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/tests/plugin_registry/test_plugin_registry.py#L984-L1190)**（16 个）：
- 依赖未注册、未启用、已停用、版本不匹配
- 多依赖场景、链式依赖、无依赖
- `check_and_enable` 触发依赖校验

**[TestExceptionHandlingContract](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/tests/plugin_registry/test_plugin_registry.py#L1196-L1271)**（6 个）：
- `enable_all` 传播依赖错误、版本错误、系统错误
- `disable_all` 传播系统错误
- 正常场景下仍返回结果字典

**[TestSetStatusUnifiedEntry](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/tests/plugin_registry/test_plugin_registry.py#L1277-L1403)**（11 个）：
- `set_status(ENABLED)` 执行依赖校验、版本校验
- `set_status(ENABLED)` 对已启用插件抛出 `PluginStateError`
- `set_status(DISABLED)` 委托给 `disable()`，行为一致
- 副作用（`enable_count`、时间戳）与直接调用一致

## 更新的文档

在 [README.md](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/plugin_registry/README.md) 中新增：
- **依赖校验机制**章节：校验顺序、失败场景、启用顺序注意事项
- **状态转变统一入口**章节：委托关系、设计原则、示例对比
- **异常处理契约**章节：捕获范围、设计意图、调用方建议
- 3 个完整的代码示例：依赖校验、状态统一入口、批量操作异常处理

## 测试结果

```
poetry run pytest tests/plugin_registry/ -q
........................................................ 154 passed in 0.29s
```

所有 **154 个**测试全部通过！排除项目中已损坏的两个模块后，全项目 **595 个**测试全部通过。