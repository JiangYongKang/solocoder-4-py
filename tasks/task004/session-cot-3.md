我需要修复这些问题。先读取相关文件：
        
            
toolName: todo_write
            
status: success
          
Todos updated: 5 items
          

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_avalanche_guard\README.md
          

        
            
toolName: search_by_regex
            
status: success
          
query: test_renew_hot_key_default_ttl_fallback
          

        
            
toolName: todo_write
            
status: success
          
Todos updated: 5 items
          
现在开始修复所有问题。先修复 README.md 的三处问题：

        
            
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
          

        
            
toolName: todo_write
            
status: success
          
Todos updated: 5 items
          
现在修复测试：



        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\cache_avalanche_guard\test_cache_avalanche_guard.py
          
changes: undefined
          

        
            
toolName: todo_write
            
status: success
          
Todos updated: 5 items
          
现在运行测试：





        
            
toolName: run_command
            
status: success
          
command: poetry run pytest tests/cache_avalanche_guard/ -q undefined
          

        
            
toolName: todo_write
            
status: success
          
Todos updated: 5 items
          
所有问题已修复完成！**91 个测试全部通过**。

## 修复总结

### 1. README.md 续期阈值描述修正
[README.md 第37行](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/cache_avalanche_guard/README.md#L37)：将"当剩余 TTL 低于**默认 TTL** 的 30% 时自动续期"改为"当剩余 TTL 低于**条目自身 TTL** 的 30% 时自动续期"，与代码行为一致。

### 2. 新增 ASYNC 策略专门说明章节
在 [README.md 第59-96行](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/cache_avalanche_guard/README.md#L59-L96) 的"单飞重建锁与重建策略"章节中新增了完整的策略对比说明：

- **SYNC 策略**：阻塞等待、返回真实数据、适合高一致性短耗时场景（附代码示例）
- **ASYNC 策略**：立即返回降级值、后台线程重建、适合长耗时延迟敏感场景（附代码示例）
- 新增 ASYNC 策略注意事项：建议始终提供 `degraded_value`

### 3. 补充超时降级持久化机制说明
在 [README.md 第120-138行](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/cache_avalanche_guard/README.md#L120-L138) 中补充：

- 降级触发条件列表更新：超时/异常/ASYNC 场景均标注"自动持久化"
- 新增"降级持久化机制"子章节，明确说明：
  - 非重建方等待超时路径的持久化行为
  - ASYNC 策略的持久化行为
  - 降级值使用独立 TTL（`degraded_ttl_seconds`）
  - 持久化后的效果：后续请求无需传入 `degraded_value` 即可获得保护

### 4. 测试抖动消除
[test_renew_hot_key_default_ttl_fallback](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/tests/cache_avalanche_guard/test_cache_avalanche_guard.py#L1155-L1188)：
- 显式设置 `jitter_ratio=0`，与同类测试 `test_renew_hot_key_uses_entry_ttl` 保持一致
- 调整断言逻辑：先 `time.sleep(9)` 等待 TTL 接近过期，续期前记录 `now_before`，预期值基于 `now_before + 300 ± 1` 计算，消除不确定性

### 验证结果
```
91 passed in 27.74s
```