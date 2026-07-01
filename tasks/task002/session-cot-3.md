让我先创建修复计划，然后逐一解决这些问题。

        
            
toolName: todo_write
            
status: success
          
Todos updated: 5 items
          
让我先读取当前代码文件，然后逐一修复。



        
            
toolName: todo_write
            
status: success
          
Todos updated: 5 items
          

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\layered_cache\layered_cache.py
          

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\layered_cache\README.md
          
让我先读取 LayeredCache 的 __init__ 和 get_stats 方法，了解当前的 _stats_loader_calls 使用情况。





        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\layered_cache\layered_cache.py
          
现在开始修复。首先处理 **问题 2**：统一使用 `_request_stats.loader_calls`，移除独立的 `_stats_loader_calls`。然后处理 **问题 3**：重构 `SingleLevelCache.set` 使 `ttl=None` 明确表示永不过期。



        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\layered_cache\layered_cache.py
          
现在开始修复。首先修改 **SingleLevelCache.set**，使用 sentinel 值区分「未传 ttl」和「显式传 None 表示永不过期」。然后统一 loader_calls 计数。





        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\layered_cache\layered_cache.py
          
changes: undefined
          
现在修改 `SingleLevelCache.set` 方法，使 `ttl=None` 明确表示永不过期。







        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\layered_cache\layered_cache.py
          
changes: undefined
          
现在修改 LayeredCache，统一使用 `_request_stats.loader_calls`，并简化回填逻辑。







        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\layered_cache\layered_cache.py
          
changes: undefined
          
现在修复 `get` 方法的回填逻辑，移除绕过接口修改 expires_at 的代码，并统一 loader_calls 计数。









        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\layered_cache\layered_cache.py
          
changes: undefined
          
现在替换所有 `_stats_loader_calls` 为 `_request_stats.loader_calls`，并更新 `get_stats` 和 `reset_stats`。













        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\layered_cache\layered_cache.py
          
changes: undefined
          
现在更新 `get_stats` 和 `reset_stats` 方法，移除对 `_stats_loader_calls` 的引用。















        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\layered_cache\layered_cache.py
          
现在更新 `get_stats` 和 `reset_stats` 方法，移除对 `_stats_loader_calls` 的引用。
















        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\layered_cache\layered_cache.py
          

        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\layered_cache\layered_cache.py
          
changes: undefined
          

        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\layered_cache\layered_cache.py
          
changes: undefined
          
现在更新 Todo 状态，然后修复 README.md API 表格。先仔细核对两个方法的实际签名。









        
            
toolName: todo_write
            
status: success
          
Todos updated: 5 items
          

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\layered_cache\layered_cache.py
          

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\layered_cache\layered_cache.py
          
现在更新 README.md API 表格，让签名更准确地反映实际代码。










        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\layered_cache\README.md
          
changes: undefined
          
现在运行测试，确保所有修改正确。同时检查是否还有遗留的 `_stats_loader_calls` 引用。
















        
            
toolName: todo_write
            
status: success
          
Todos updated: 5 items
          

        
            
toolName: search_by_regex
            
status: success
          
query: _stats_loader_calls
          

        
            
toolName: run_command
            
status: success
          
command: poetry run pytest tests/layered_cache/ -q undefined
          
有一个测试失败了。让我查看 `test_invalidate_expired` 测试和 `LayeredCache.set` 方法，看看 TTL 是如何传递的。

























        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\layered_cache\test_layered_cache.py
          

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\layered_cache\layered_cache.py
          
问题找到了！`LayeredCache.set` 方法中，当 `local_ttl` 和 `ttl` 都为 `None` 时，会传递 `None` 给 `SingleLevelCache.set`，而现在 `ttl=None` 表示「永不过期」，导致条目不会过期。需要修复 `LayeredCache.set` 的 TTL 计算逻辑。























        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\layered_cache\layered_cache.py
          
需要修复 `LayeredCache.set` 方法，使用 sentinel 模式区分「用户没传 TTL」和「用户传了 None 表示永不过期」。先修改参数签名。

























        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\layered_cache\layered_cache.py
          
changes: undefined
          
现在需要同样修复 `get` 和 `get_with_level` 方法中的回填逻辑，使用 sentinel 模式。让我检查一下当前的实现。


























        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\layered_cache\layered_cache.py
          
需要同样修复 `get` 和 `get_with_level` 方法的参数签名和回填逻辑。让我先检查 `get` 和 `get_with_level` 的方法签名，然后统一使用 sentinel 模式。





























        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\layered_cache\layered_cache.py
          
changes: undefined
          
现在修复 `get` 方法中的共享命中回填逻辑和 loader 回填逻辑。































        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\layered_cache\layered_cache.py
          
changes: undefined
          
现在修复 `get` 方法中的 loader 回填逻辑。


































        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\layered_cache\layered_cache.py
          
changes: undefined
          
现在修改 `get_with_level` 方法的参数签名，使用 sentinel 模式。

































        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\layered_cache\layered_cache.py
          

        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\layered_cache\layered_cache.py
          
changes: undefined
          
现在运行测试，看看所有修改是否正确。


































        
            
toolName: run_command
            
status: success
          
command: poetry run pytest tests/layered_cache/ -q undefined
          
测试全部通过！现在让我运行 IDE 诊断检查是否有类型错误，然后更新 Todo。



































        
            
toolName: todo_write
            
status: success
          
Todos updated: 5 items
          

        
            
toolName: GetDiagnostics
            
status: success
          
          
所有问题已修复完成！**95 个测试全部通过**，IDE 诊断无错误。

---

## 修复内容汇总

### 1. README.md API 表格更新
**文件**：[README.md](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/layered_cache/README.md#L297-L301)

所有方法签名已补充完整的参数列表和返回类型：
- `get(...) -> Optional[T]`
- `get_or_load(...) -> Optional[T]`
- `get_with_level(...) -> Tuple[Optional[T], Optional[CacheLevel]]`
- `get_local(key) -> Optional[Any]`
- `get_shared(key) -> Optional[Any]`

---

### 2. loader_calls 计数统一
**文件**：[layered_cache.py](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/layered_cache/layered_cache.py#L340-L341)

移除了独立的 `_stats_loader_calls` 整型变量，统一使用 `_request_stats.loader_calls`：
- `__init__`：移除 `self._stats_loader_calls = 0`
- `get()` 和 `get_with_level()`：`self._request_stats.loader_calls += 1`
- `get_stats()`：`"loader_calls": self._request_stats.loader_calls`
- `reset_stats()`：移除对 `_stats_loader_calls` 的重置

---

### 3. SingleLevelCache.set 永不过期语义
**文件**：[layered_cache.py](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/layered_cache/layered_cache.py#L114-L136)

引入 sentinel 值 `_UNSET` 区分三种场景：

| 调用方式 | 行为 |
|----------|------|
| `cache.set(key, value)` 不传 ttl | 使用 `default_ttl` |
| `cache.set(key, value, ttl=300)` | 300 秒后过期 |
| `cache.set(key, value, ttl=None)` | **永不过期** |

```python
_UNSET = object()

def set(self, key, value, tags=None, ttl=_UNSET):
    if ttl is _UNSET:
        effective_ttl = self._default_ttl  # 使用默认
    else:
        effective_ttl = ttl  # None 表示永不过期
```

---

### 4. 回填逻辑重构（消除对内部可变性的依赖）
**文件**：[layered_cache.py](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/layered_cache/layered_cache.py#L377-L395)

移除了绕过接口修改 `expires_at` 的代码，现在完全依赖 `SingleLevelCache.set` 的正确语义：

```python
# 修复后 - 简洁清晰，无内部对象修改
if local_ttl is not _UNSET:
    effective_local_ttl = local_ttl
elif ttl is not _UNSET:
    effective_local_ttl = ttl
elif shared_entry.expires_at is not None:
    effective_local_ttl = max(0.0, shared_entry.remaining_ttl())
else:
    effective_local_ttl = None  # 永不过期

self._local.set(
    key=key,
    value=shared_entry.value,
    tags=shared_entry.tags,
    ttl=effective_local_ttl,
)
```

---

### 5. LayeredCache 所有方法统一 sentinel 模式
`LayeredCache` 的 `get()`、`get_with_level()`、`set()` 方法的 `ttl`、`local_ttl`、`shared_ttl` 参数默认值全部改为 `_UNSET`，保持一致的语义：

- **显式传 `None`** → 永不过期
- **不传参数** → 使用默认 TTL（通过 `SingleLevelCache.default_ttl`）
- **传具体数值** → 指定秒数后过期

---

### 6. 测试结果
```
poetry run pytest tests/layered_cache/ -q
................................................................. [ 75%]
.......................                                           [100%]
95 passed in 1.08s
```