好的，我来逐一修复这3个问题。先读取相关文件：


        
            
toolName: todo_write
            
status: success
          
Todos updated: 4 items
          

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\request_snapshot_cache\snapshot_cache.py
          

        
            
toolName: todo_write
            
status: success
          
Todos updated: 4 items
          
现在一次性修复所有3个问题：









        
            
toolName: Write
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\request_snapshot_cache\snapshot_cache.py
          
changes: undefined
          

        
            
toolName: todo_write
            
status: success
          
Todos updated: 5 items
          
现在补充新增功能的单元测试：











        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\request_snapshot_cache\test_snapshot_cache.py
          
现在在文件末尾添加新测试：













        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\request_snapshot_cache\test_snapshot_cache.py
          
changes: undefined
          
现在运行测试验证：












        
            
toolName: todo_write
            
status: success
          
Todos updated: 5 items
          

        
            
toolName: run_command
            
status: success
          
command: cd c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py ; poetry run pytest tests/request_snapshot_cache/ -q undefined
          

        
            
toolName: todo_write
            
status: success
          
Todos updated: 5 items
          
## 修复完成！所有 **122 个单元测试全部通过** ✅

### 修复详情

---

#### 问题1：删除 get 方法冗余的逐条目 TTL 检查
**文件**：[snapshot_cache.py](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/request_snapshot_cache/snapshot_cache.py#L79-L101)

- **修改前**：`get` 方法在 `_cleanup_expired()` 之后又做了一次逐条目 TTL 检查（第95-99行），导致 `ttl_cleanups` 统计不准确
- **修改后**：删除冗余检查，TTL 过期清理统一由 `_cleanup_expired()` 负责
- **新增测试**：`test_get_no_redundant_ttl_check`

---

#### 问题2：实现 per-entry TTL 功能
**文件**：[snapshot_cache.py](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/request_snapshot_cache/snapshot_cache.py)

- **CacheEntry**（第12-22行）：新增 `ttl: Optional[float] = None` 字段
- **`_set_internal`**（第136-165行）：将 `ttl` 参数存储到 `CacheEntry` 中
- **`_cleanup_expired`**（第51-72行）：
  - 优化跳过条件：`default_ttl is None` 且所有条目无 `ttl` 时直接返回
  - 每个条目使用 `entry.ttl if entry.ttl is not None else self._default_ttl` 作为有效 TTL
  - 逐条目判断是否过期

- **优先级规则**：
  - 若条目有 `ttl`（`set(..., ttl=60)`），使用该值
  - 否则使用全局 `default_ttl`
  - 两者都为 `None` 则永不过期

- **新增测试（8个）**：
  - `test_per_entry_ttl_overrides_default` - 条目 TTL 覆盖默认
  - `test_per_entry_ttl_without_default` - 无默认 TTL 时条目 TTL 生效
  - `test_per_entry_ttl_different_values` - 不同条目不同 TTL
  - `test_per_entry_ttl_cleanup_on_has` - has 触发 per-entry TTL 清理
  - `test_per_entry_ttl_cleanup_on_len` - len 触发 per-entry TTL 清理
  - `test_per_entry_ttl_effective_ttl_precedence` - 优先级验证
  - `test_per_entry_ttl_zero_is_invalid` - ttl=0 立即过期
  - `test_per_entry_ttl_cleanup_on_get_stats` - get_stats 触发清理

---

#### 问题3：has 方法版本校验失败时清理条目
**文件**：[snapshot_cache.py](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/request_snapshot_cache/snapshot_cache.py#L220-L233)

- **修改前**：版本校验失败时仅返回 `False`，条目仍保留在缓存中
- **修改后**：版本校验失败时调用 `_evict_internal(cache_key)` 清理条目，与 `get` 方法行为一致

```python
# 修改后
if not self._version_manager.check_versions_valid(cache_key, entry.entity_versions):
    self._evict_internal(cache_key)
    return False
return True
```

- **新增测试（5个）**：
  - `test_has_evicts_on_version_mismatch` - has 版本不匹配时驱逐
  - `test_has_version_mismatch_clears_dependencies` - 清理版本依赖
  - `test_contains_operator_evicts_on_version_mismatch` - `__contains__` 也触发清理
  - `test_has_no_evict_when_version_valid` - 版本有效时不清理

---

### 测试统计
```
poetry run pytest tests/request_snapshot_cache/ -q
........................................................................ [ 59%]
..................................................                       [100%]
122 passed in 2.76s
```

| 模块 | 测试数量 |
|------|----------|
| test_cache_key.py | 26 |
| test_version_manager.py | 23 |
| test_snapshot_cache.py | 73 |
| **总计** | **122** |