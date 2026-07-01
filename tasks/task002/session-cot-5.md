让我先读取 set 方法的当前代码，然后将其 TTL 解析逻辑统一到辅助方法中。



        
            
toolName: todo_write
            
status: success
          
Todos updated: 2 items
          

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\layered_cache\layered_cache.py
          
现在重构 set 方法，复用已有的 TTL 解析辅助方法。同时修改 `_set_both_levels` 增加 `write_local` 和 `write_shared` 参数支持。





        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\layered_cache\layered_cache.py
          
changes: undefined
          
现在重构 `set` 方法，复用已有的 TTL 解析和写入辅助方法。






        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\layered_cache\layered_cache.py
          
changes: undefined
          
现在运行测试，确保所有修改正确。









        
            
toolName: todo_write
            
status: success
          
Todos updated: 2 items
          

        
            
toolName: run_command
            
status: success
          
command: poetry run pytest tests/layered_cache/ -q undefined
          
测试全部通过！让我检查 IDE 诊断，然后更新 Todo。











        
            
toolName: todo_write
            
status: success
          
Todos updated: 2 items
          

        
            
toolName: GetDiagnostics
            
status: success
          
          
所有问题已修复完成！**95 个测试全部通过**，IDE 诊断无错误。

---

## 修复内容汇总

### 1. set 方法统一使用辅助方法，消除重复代码
**文件**：[layered_cache.py](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/layered_cache/layered_cache.py#L624-L638)

#### 1.1 扩展 `_set_both_levels` 辅助方法
增加 `write_local` 和 `write_shared` 参数，支持可选写入单层或双层：

```python
def _set_both_levels(
    self,
    key: str,
    value: Any,
    tags: Iterable[str],
    effective_local_ttl: object,
    effective_shared_ttl: object,
    write_local: bool = True,      # 新增
    write_shared: bool = True,     # 新增
) -> None:
    """写入本地和/或共享缓存"""
    if write_shared:
        # ... 写入共享缓存
    if write_local:
        # ... 写入本地缓存
```

#### 1.2 重构 `set` 方法
从 **45 行** 重复代码缩减为 **15 行**，完全复用辅助方法：

**重构前（45行）：**
```python
with self._lock:
    tag_list = list(tags) if tags is not None else []

    if shared_ttl is not _UNSET:
        effective_shared_ttl = shared_ttl
    elif ttl is not _UNSET:
        effective_shared_ttl = ttl
    else:
        effective_shared_ttl = _UNSET

    if local_ttl is not _UNSET:
        effective_local_ttl = local_ttl
    elif ttl is not _UNSET:
        effective_local_ttl = ttl
    else:
        effective_local_ttl = _UNSET

    if write_shared:
        if effective_shared_ttl is _UNSET:
            self._shared.set(key=key, value=value, tags=tag_list)
        else:
            self._shared.set(key=key, value=value, tags=tag_list, ttl=effective_shared_ttl)
    if write_local:
        if effective_local_ttl is _UNSET:
            self._local.set(key=key, value=value, tags=tag_list)
        else:
            self._local.set(key=key, value=value, tags=tag_list, ttl=effective_local_ttl)
```

**重构后（15行）：**
```python
with self._lock:
    tag_list = list(tags) if tags is not None else []

    effective_local_ttl, effective_shared_ttl = self._resolve_loader_backfill_ttls(
        ttl, local_ttl, shared_ttl
    )
    self._set_both_levels(
        key=key,
        value=value,
        tags=tag_list,
        effective_local_ttl=effective_local_ttl,
        effective_shared_ttl=effective_shared_ttl,
        write_local=write_local,
        write_shared=write_shared,
    )
```

---

### 2. TTL 规则统一维护点（当前状态）
修复后，TTL 优先级解析规则**只维护在两处**辅助方法中：

| 辅助方法 | 用途 | 调用方 |
|----------|------|--------|
| `_resolve_shared_hit_backfill_ttl()` | 共享命中→本地回填 TTL 解析 | `get()`, `get_with_level()` |
| `_resolve_loader_backfill_ttls()` | loader 回填/主动写入 TTL 解析 | `get()`, `get_with_level()`, `set()` |
| `_set_both_levels()` | 写入缓存封装 | `get()`, `get_with_level()`, `set()` |

未来修改 TTL 规则时，**只需修改对应辅助方法**，无需在多个调用点同步修改。

---

### 3. 测试结果
```
poetry run pytest tests/layered_cache/ -q
........................................................................ [ 75%]
.......................                                           [100%]
95 passed in 1.18s
```