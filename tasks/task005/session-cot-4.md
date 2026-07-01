好的，我来修复这个性能问题。先读取当前代码：



        
            
toolName: todo_write
            
status: success
          
Todos updated: 2 items
          

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\request_snapshot_cache\snapshot_cache.py
          
现在修复这个问题，移除预检查，改为单次遍历：











        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\request_snapshot_cache\snapshot_cache.py
          
changes: undefined
          

        
            
toolName: todo_write
            
status: success
          
Todos updated: 2 items
          

        
            
toolName: run_command
            
status: success
          
command: cd c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py ; poetry run pytest tests/request_snapshot_cache/ -q undefined
          

        
            
toolName: todo_write
            
status: success
          
Todos updated: 2 items
          
## 修复完成！所有 **122 个单元测试全部通过** ✅

### 修复详情

#### 问题：`_cleanup_expired` 方法的二次遍历性能问题
**文件**：[snapshot_cache.py](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/request_snapshot_cache/snapshot_cache.py#L51-L67)

**问题分析**：
```python
# 修改前 - 存在两次全量遍历
if self._default_ttl is None and not any(
    entry.ttl is not None for entry in self._cache.values()  # 第一次遍历
):
    return 0

for cache_key, entry in self._cache.items():  # 第二次遍历
    ...
```

- **第一次遍历**（预检查）：`any(...)` 会遍历所有条目检查是否有 per-entry TTL
- **第二次遍历**（主循环）：再次遍历所有条目做实际的过期检查
- 无论是否有 per-entry TTL，都会至少遍历一次全部条目
- 如果有 per-entry TTL 或配置了 `default_ttl`，则会遍历两次

**修复方案**：
移除预检查，改为单次遍历同时完成所有检查：

```python
# 修改后 - 单次遍历
now = time.time()
expired_keys: List[str] = []

for cache_key, entry in self._cache.items():
    effective_ttl = entry.ttl if entry.ttl is not None else self._default_ttl
    if effective_ttl is not None and (now - entry.created_at > effective_ttl):
        expired_keys.append(cache_key)
```

**性能改进**：
- 时间复杂度从 **O(2n)** 优化为 **O(n)**
- 当 `default_ttl is None` 且无 per-entry TTL 时，`effective_ttl` 为 `None`，`if` 条件快速跳过，额外开销可忽略
- 代码更简洁，逻辑更清晰

---

### 测试验证
```
poetry run pytest tests/request_snapshot_cache/ -q
........................................................................ [ 59%]
..................................................                       [100%]
122 passed in 2.63s
```