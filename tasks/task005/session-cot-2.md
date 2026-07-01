好的，我来逐一分析并修复这些问题。首先创建任务计划：

        
            
toolName: todo_write
            
status: success
          
Todos updated: 7 items
          
先读取当前的源文件以便修改：



        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\request_snapshot_cache\cache_key.py
          

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\request_snapshot_cache\snapshot_cache.py
          

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\request_snapshot_cache\version_manager.py
          

        
            
toolName: todo_write
            
status: success
          
Todos updated: 7 items
          
现在开始修复。首先修复问题1 - 缓存键生成逻辑：

**问题1**：entities 只用于版本校验，不纳入缓存键哈希计算。这样相同参数但不同实体列表的请求可以复用同一份快照（通过版本校验机制区分有效性）。



        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\request_snapshot_cache\cache_key.py
          
changes: undefined
          
现在修复问题2（版本竞态窗口）、问题3（模式失效一致性）、问题4（TTL惰性清理）：



        
            
toolName: todo_write
            
status: success
          
Todos updated: 7 items
          
现在重构 snapshot_cache.py，一次性修复问题2、3、4：

**问题2**：get_or_compute 在 compute 执行后，set 前需要记录 compute 开始时的版本号与 set 时的最新版本号对比，若不一致说明计算期间有版本变更，不写入缓存。

**问题3**：invalidate_by_pattern 需要在 evict 条目的同时，对这些条目的所有关联实体执行版本递增，以保证依赖相同实体的其他条目也会被动失效。

**问题4**：增加 `_cleanup_expired` 方法，在多个入口点触发惰性清理。





        
            
toolName: Write
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\request_snapshot_cache\snapshot_cache.py
          
changes: undefined
          

        
            
toolName: todo_write
            
status: success
          
Todos updated: 7 items
          
先运行测试看看哪些旧测试会失败：






        
            
toolName: run_command
            
status: success
          
command: cd c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py ; python -m pytest tests/request_snapshot_cache/ -v --tb=short 2>&1 | Select-Object -Last 80 undefined
          
有2个旧测试需要更新（这是预期的行为变化 - 缓存键不再包含 entities，提高了复用率）。现在修复这两个测试，并补充新的测试：




        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\request_snapshot_cache\test_snapshot_cache.py
          
现在修复这两个测试，然后补充新的测试用例。我需要更新旧测试反映新的行为（相同参数不同实体共享同一缓存键，最后一次 set 覆盖之前的结果）：

首先修复 test_different_entities_same_params - 现在相同参数不同实体共享缓存键：

        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\request_snapshot_cache\test_snapshot_cache.py
          
changes: undefined
          
现在修复 test_same_key_different_entities 测试：


        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\request_snapshot_cache\test_snapshot_cache.py
          
changes: undefined
          
现在读取 test_cache_key.py 并修复 entities 相关的测试：


        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\request_snapshot_cache\test_cache_key.py
          
test_generate_with_entities 测试应该仍然通过（entities 不参与键计算，所以无论顺序如何键都相同），以及 test_generate_function_with_entities 测试也需要检查：




        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\request_snapshot_cache\test_cache_key.py
          
好的，现有的 cache_key 测试应该能通过。现在补充新增的三个方面的测试：版本竞态窗口、模式失效与实体失效一致性、TTL 惰性清理覆盖率。我将这些新测试添加到 test_snapshot_cache.py 末尾：






        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\request_snapshot_cache\test_snapshot_cache.py
          
让我先运行一次现有测试，看看除了已经修复的2个外还有没有其他失败：






        
            
toolName: run_command
            
status: success
          
command: cd c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py ; python -m pytest tests/request_snapshot_cache/ -v --tb=short 2>&1 | Select-Object -Last 30 undefined
          
所有 93 个现有测试通过了。现在补充新增的三个方面的测试用例：







        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\request_snapshot_cache\test_snapshot_cache.py
          
现在在 test_snapshot_cache.py 末尾补充新测试：








        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\request_snapshot_cache\test_snapshot_cache.py
          
changes: undefined
          
现在运行测试验证新增的测试用例：







        
            
toolName: run_command
            
status: success
          
command: cd c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py ; python -m pytest tests/request_snapshot_cache/ -v --tb=short 2>&1 | Select-Object -Last 60 undefined
          
文件系统缓存问题，让我检查文件是否存在：








        
            
toolName: view_folder
            
status: success
          
c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\request_snapshot_cache
          
snapshot_cache.py 文件丢失了！让我重新创建它：










        
            
toolName: Write
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\request_snapshot_cache\snapshot_cache.py
          
changes: undefined
          
现在运行测试：









        
            
toolName: run_command
            
status: success
          
command: cd c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py ; python -m pytest tests/request_snapshot_cache/ -v --tb=short 2>&1 | Select-Object -Last 60 undefined
          
所有 109 个测试通过！现在更新 README.md，说明修复后的缓存键规则、版本竞态防护和过期清理策略：









        
            
toolName: todo_write
            
status: success
          
Todos updated: 7 items
          
现在读取并更新 README.md：




        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\request_snapshot_cache\README.md
          
现在更新 README.md，修复缓存键规则、增加版本竞态防护和过期清理策略说明：









        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\request_snapshot_cache\README.md
          
changes: undefined
          
现在更新示例部分，增加缓存键与实体分离的示例，以及在使用示例后面增加版本竞态防护和过期清理策略章节：










        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\request_snapshot_cache\README.md
          
changes: undefined
          
现在在"线程安全"章节之前，插入"版本竞态防护"、"模式失效一致性"和"TTL 过期清理策略"章节：













        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\request_snapshot_cache\README.md
          
changes: undefined
          
现在更新 API 参考表，增加新增的两个统计字段说明：












        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\request_snapshot_cache\README.md
          
changes: undefined
          
现在运行 poetry run pytest 测试：













        
            
toolName: todo_write
            
status: success
          
Todos updated: 7 items
          

        
            
toolName: run_command
            
status: success
          
command: cd c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py ; poetry run pytest tests/request_snapshot_cache/ -q undefined
          

        
            
toolName: todo_write
            
status: success
          
Todos updated: 7 items
          
## 修复完成！所有 **109 个单元测试全部通过** ✅

### 修复总结

#### 问题1：缓存键生成规则修正
**文件**：[cache_key.py](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/request_snapshot_cache/cache_key.py#L48-L55)

- **修改前**：`CacheKeyGenerator.generate()` 同时将 `request_params` 和 `data_entities` 纳入哈希计算
- **修改后**：仅基于 `request_params` 生成缓存键，`data_entities` 只用于版本校验，不参与键计算
- **效果**：相同参数不同实体列表的请求复用同一份缓存键，大幅提高缓存复用率

#### 问题2：get_or_compute 版本竞态防护
**文件**：[snapshot_cache.py](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/request_snapshot_cache/snapshot_cache.py#L105-L127)

- **实现**：`get_or_compute` 增加**计算前后版本二次校验**
  1. `compute_func` 调用前，在锁内获取 `versions_before`
  2. 执行计算（释放锁）
  3. 计算完成后重新获取锁，对比 `versions_after`
  4. 版本不一致 → 返回结果但**不写入缓存**，记录 `version_race_detected`
  5. 版本一致 → 使用 `versions_after` 写入缓存

#### 问题3：模式失效与实体失效一致性
**文件**：[snapshot_cache.py](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/request_snapshot_cache/snapshot_cache.py#L196-L219)

- **修改前**：`invalidate_by_pattern` 仅调用 `_evict` 清理条目，不递增版本
- **修改后**：
  1. 收集所有匹配条目的关联实体并去重
  2. 对每个受影响实体执行 `bump_entity_version()`
  3. 再清除匹配的缓存条目
- **效果**：依赖相同实体但未被模式匹配的其他条目，也会通过版本校验被动失效

#### 问题4：TTL 惰性清理机制全覆盖
**文件**：[snapshot_cache.py](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/request_snapshot_cache/snapshot_cache.py#L50-L68)

- **新增**统一的 `_cleanup_expired()` 方法：
  - 遍历所有条目，收集过期键并批量清理
  - 返回清理数量，记录 `ttl_cleanups` 统计
  - `default_ttl=None` 时零开销直接返回

- **在以下所有公共方法开头自动调用**：
  `get`、`set`、`has`、`get_entry`、`invalidate_by_entity`、`invalidate_by_entities`、`invalidate_by_pattern`、`get_stats`、`__len__`、`__contains__`

#### 问题5：新增单元测试（共 18 个）

| 分类 | 新增测试 | 数量 |
|------|----------|------|
| **缓存键规则** | `test_same_params_entities_order_independent`、`test_cache_key_independent_of_entities` | 2 |
| **版本竞态防护** | `test_version_race_window_get_or_compute`、`test_version_race_no_false_positive`、`test_version_race_multiple_entities`、`test_get_or_compute_race_result_used_but_not_cached` | 4 |
| **模式失效一致性** | `test_invalidate_by_pattern_bumps_entity_versions`、`test_invalidate_by_pattern_consistency_with_entity_invalidate`、`test_invalidate_by_pattern_multiple_entities_bumped` | 3 |
| **TTL 惰性清理** | `test_ttl_lazy_cleanup_on_has`、`test_ttl_lazy_cleanup_on_len`、`test_ttl_lazy_cleanup_on_contains`、`test_ttl_lazy_cleanup_on_get_stats`、`test_ttl_lazy_cleanup_on_get_entry`、`test_ttl_lazy_cleanup_on_set`、`test_ttl_lazy_cleanup_on_invalidate_methods`、`test_ttl_cleanup_preserves_valid_entries`、`test_no_ttl_no_cleanup_triggered` | 9 |

#### 问题6：README.md 更新
**文件**：[README.md](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/request_snapshot_cache/README.md)

新增三大章节：
- **版本竞态防护**：问题背景、5步防护策略、示例场景、统计解读
- **模式失效与实体失效一致性**：问题背景、一致性流程、效果说明、示例
- **TTL 过期清理策略**：问题背景、触发方法表、清理算法、行为说明、示例
- 并更新了**缓存键规则**章节（明确 entities 不参与哈希）和 **API 参考**（新增统计字段表）

---

**最终验证**：
```
poetry run pytest tests/request_snapshot_cache/ -q
........................................................................ [ 66%]
.....................................                                    [100%]
109 passed in 1.49s
```