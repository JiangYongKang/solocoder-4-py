让我先创建修复计划，然后逐一解决这些问题。


        
            
toolName: todo_write
            
status: success
          
Todos updated: 3 items
          
让我先读取当前的 set_local 和 set_shared 方法。




        
            
toolName: todo_write
            
status: success
          
Todos updated: 3 items
          

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\layered_cache\layered_cache.py
          
让我继续读取 set_local 和 set_shared 方法。





        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\layered_cache\layered_cache.py
          
让我继续读取 set_local 和 set_shared 的完整代码。







        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\layered_cache\layered_cache.py
          
现在修复 set_local 和 set_shared 方法。











        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\layered_cache\layered_cache.py
          
changes: undefined
          
现在处理第二个问题：提取 TTL 优先级解析逻辑为私有辅助方法。先看看当前两处重复的代码。















        
            
toolName: todo_write
            
status: success
          
Todos updated: 3 items
          

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\layered_cache\layered_cache.py
          
让我先看看共享命中回填的代码，以及 loader 回填的代码，提取为私有辅助方法。
























        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\layered_cache\layered_cache.py
          
现在提取两处重复的 TTL 解析逻辑为私有辅助方法。先添加两个辅助方法，然后替换两处调用。

























        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\layered_cache\layered_cache.py
          
changes: undefined
          
现在替换 `get` 方法中的两处重复代码。先替换共享命中回填部分。

























        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\layered_cache\layered_cache.py
          
changes: undefined
          
现在替换 `get` 方法中的 loader 回填部分。先读取当前代码。




























        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\layered_cache\layered_cache.py
          

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\layered_cache\layered_cache.py
          
现在替换 `get` 方法中的 loader 回填逻辑。































        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\layered_cache\layered_cache.py
          
changes: undefined
          
现在运行测试，确保所有修改正确。





























        
            
toolName: todo_write
            
status: success
          
Todos updated: 3 items
          

        
            
toolName: run_command
            
status: success
          
command: poetry run pytest tests/layered_cache/ -q undefined
          
测试全部通过！让我检查 IDE 诊断，然后更新 Todo。































        
            
toolName: todo_write
            
status: success
          
Todos updated: 3 items
          

        
            
toolName: GetDiagnostics
            
status: success
          
          
所有问题已修复完成！**95 个测试全部通过**，IDE 诊断无错误。

---

## 修复内容汇总

### 1. set_local 和 set_shared 方法 TTL 语义统一
**文件**：[layered_cache.py](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/layered_cache/layered_cache.py#L662-L700)

将 `set_local` 和 `set_shared` 方法的 `ttl` 参数默认值从 `None` 改为 `_UNSET`，保持与 `get`、`set`、`get_with_level` 等方法的语义一致：

| 调用方式 | 修复前行为 | 修复后行为 |
|----------|------------|------------|
| `set_local("k", "v")` | 永不过期（错误） | 使用本地默认 TTL（正确） |
| `set_local("k", "v", ttl=300)` | 300 秒后过期 | 300 秒后过期 |
| `set_local("k", "v", ttl=None)` | 永不过期 | 永不过期 |

```python
def set_local(self, key, value, tags=None, ttl=_UNSET):
    if ttl is _UNSET:
        self._local.set(key, value, tags)  # 使用 default_ttl
    else:
        self._local.set(key, value, tags, ttl=ttl)  # None 表示永不过期
```

---

### 2. 提取 TTL 解析逻辑为私有辅助方法，消除代码重复
**文件**：[layered_cache.py](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/layered_cache/layered_cache.py#L343-L407)

提取了三个私有辅助方法，消除 `get` 和 `get_with_level` 中的重复代码：

#### 2.1 `_resolve_shared_hit_backfill_ttl()`
处理共享缓存命中后回填本地时的 TTL 优先级解析：
```python
def _resolve_shared_hit_backfill_ttl(self, shared_entry, ttl, local_ttl) -> Optional[float]:
    if local_ttl is not _UNSET:
        return local_ttl
    elif ttl is not _UNSET:
        return ttl
    elif shared_entry.expires_at is not None:
        return max(0.0, shared_entry.remaining_ttl())
    else:
        return None  # 共享永不过期，本地也永不过期
```

#### 2.2 `_resolve_loader_backfill_ttls()`
处理 loader 回填时的 TTL 解析，返回 `(effective_local_ttl, effective_shared_ttl)`：
```python
def _resolve_loader_backfill_ttls(self, ttl, local_ttl, shared_ttl) -> Tuple[object, object]:
    # 优先级：local_ttl/shared_ttl > 统一 ttl > _UNSET（使用各层 default_ttl）
```

#### 2.3 `_set_both_levels()`
同时写入本地和共享缓存，封装重复的 set 调用逻辑：
```python
def _set_both_levels(self, key, value, tags, effective_local_ttl, effective_shared_ttl):
    # 根据 effective_ttl 是否为 _UNSET 决定是否传 ttl 参数
```

#### 2.4 重构后的调用代码
`get` 和 `get_with_level` 中的代码大幅简化：

```python
# 共享命中回填 - 重构前（20行）
if local_ttl is not _UNSET:
    effective_local_ttl = local_ttl
elif ttl is not _UNSET:
    effective_local_ttl = ttl
...

# 共享命中回填 - 重构后（3行）
effective_local_ttl = self._resolve_shared_hit_backfill_ttl(
    shared_entry, ttl, local_ttl
)
```

```python
# loader 回填 - 重构前（30行）
if shared_ttl is not _UNSET:
    effective_shared_ttl = shared_ttl
...
if effective_shared_ttl is _UNSET:
    self._shared.set(...)
else:
    self._shared.set(..., ttl=effective_shared_ttl)
...

# loader 回填 - 重构后（5行）
effective_local_ttl, effective_shared_ttl = self._resolve_loader_backfill_ttls(
    ttl, local_ttl, shared_ttl
)
self._set_both_levels(
    key=key, value=loaded_value, tags=effective_tags,
    effective_local_ttl=effective_local_ttl,
    effective_shared_ttl=effective_shared_ttl,
)
```

---

### 3. 测试结果
```
poetry run pytest tests/layered_cache/ -q
........................................................................ [ 75%]
.......................                                           [100%]
95 passed in 1.09s
```

---

### 修复收益
1. **语义一致性**：所有对外方法的 TTL 参数行为完全一致，消除了隐式陷阱
2. **代码复用**：消除了两处完全重复的 TTL 解析逻辑，TTL 规则调整时只需修改一处
3. **可维护性**：辅助方法有清晰的文档字符串和单一职责，便于理解和测试
4. **无回归**：所有 95 个测试全部通过，包括 TTL 回填、永不过期、过期清理等场景