我来帮你实现缓存预热编排功能模块。首先让我了解一下项目的结构和现有代码风格。
        
            
toolName: todo_write
            
status: success
          
Todos updated: 9 items
          

        
            
toolName: view_folder
            
status: success
          
c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py
          

        
            
toolName: view_folder
            
status: success
          
c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py
          

        
            
toolName: view_folder
            
status: success
          
c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests
          

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\transaction_coordination\constants.py
          
让我进一步查看现有模块的代码风格和测试风格：

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\transaction_coordination\__init__.py
          

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\transaction_coordination\coordinator.py
          

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\transaction_coordination\exceptions.py
          

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\transaction_coordination\test_transaction_coordination.py
          

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\transaction_coordination\README.md
          

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\pyproject.toml
          
好的，我已经充分了解了项目的代码结构和风格。现在开始实现缓存预热编排模块。


        
            
toolName: todo_write
            
status: success
          
Todos updated: 9 items
          
现在开始创建 cache_warmup 模块的基础文件：

        
            
toolName: run_command
            
status: success
          
command: New-Item -ItemType Directory -Force -Path "c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_warmup" | Out-Null ; New-Item -ItemType Directory -Force -Path "c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\cache_warmup" | Out-Null ; echo "Directories created" undefined
          
目录创建成功。现在开始创建核心文件：


        
            
toolName: Write
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_warmup\constants.py
          
changes: undefined
          

        
            
toolName: Write
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_warmup\exceptions.py
          
changes: undefined
          

        
            
toolName: todo_write
            
status: success
          
Todos updated: 9 items
          
现在创建数据模型、拓扑排序和进度追踪：



        
            
toolName: Write
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_warmup\task.py
          
changes: undefined
          

        
            
toolName: Write
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_warmup\topology.py
          
changes: undefined
          

        
            
toolName: Write
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_warmup\progress.py
          
changes: undefined
          

        
            
toolName: todo_write
            
status: success
          
Todos updated: 9 items
          
现在创建核心的预热编排器 orchestrator.py 和 __init__.py：



        
            
toolName: Write
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_warmup\orchestrator.py
          
changes: undefined
          

        
            
toolName: Write
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_warmup\__init__.py
          
changes: undefined
          

        
            
toolName: todo_write
            
status: success
          
Todos updated: 9 items
          
现在编写模块 README.md：





        
            
toolName: Write
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_warmup\README.md
          
changes: undefined
          

        
            
toolName: todo_write
            
status: success
          
Todos updated: 9 items
          
现在创建测试目录初始化文件和完整的单元测试：





        
            
toolName: Write
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\cache_warmup\__init__.py
          
changes: undefined
          

        
            
toolName: Write
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\cache_warmup\test_cache_warmup.py
          
changes: undefined
          

        
            
toolName: todo_write
            
status: success
          
Todos updated: 9 items
          
现在运行测试验证功能：





        
            
toolName: run_command
            
status: success
          
command: python -m pytest tests/cache_warmup/ -v --tb=short 2>&1 undefined
          
有 4 个测试失败，需要修复两个问题：
1. **幂等性问题**：终态流程重复调用时仍执行循环
2. **ABORT_ALL 策略**：中止后剩余的 PENDING 任务未标记为 SKIPPED

让我修复 `orchestrator.py`：







        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_warmup\orchestrator.py
          
现在看到了问题所在。让我修复这两个问题：

1. `execute_warmup` 中 `_prepare_execution` 返回终态时直接跳过执行循环
2. `_finalize_warmup` 中把 aborted 后剩余的 PENDING 任务标记为 SKIPPED










        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_warmup\orchestrator.py
          
现在清楚了问题所在。修复两个问题：








        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_warmup\orchestrator.py
          
changes: undefined
          
现在修复第二个问题 —— aborted 后剩余任务标记为 SKIPPED：









        
            
toolName: edit_file_search_replace
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_warmup\orchestrator.py
          
changes: undefined
          
现在再次运行测试：









        
            
toolName: run_command
            
status: success
          
command: python -m pytest tests/cache_warmup/ -v --tb=short 2>&1 undefined
          
所有 68 个测试全部通过！让我再检查一下诊断信息确保代码质量：





        
            
toolName: GetDiagnostics
            
status: success
          
          

        
            
toolName: todo_write
            
status: success
          
Todos updated: 9 items
          
缓存预热编排模块已完整实现并通过所有测试！以下是实现总结：

---

## 模块文件结构

### 源码包 (`src/solocoder_4_py/cache_warmup/`)
| 文件 | 功能 |
|------|------|
| [__init__.py](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/cache_warmup/__init__.py) | 公共 API 导出 |
| [constants.py](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/cache_warmup/constants.py) | `TaskState` / `WarmupState` / `FailureStrategy` 枚举 + 终态集合 |
| [exceptions.py](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/cache_warmup/exceptions.py) | 8 个异常类层级（继承自 `CacheWarmupError`） |
| [task.py](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/cache_warmup/task.py) | `WarmupTask` 数据模型（任务ID、依赖、加载回调、元数据） |
| [topology.py](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/cache_warmup/topology.py) | `TopologySorter` - Kahn 算法拓扑排序、循环依赖检测、下游分析 |
| [progress.py](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/cache_warmup/progress.py) | `TaskProgress` / `WarmupProgress` 进度追踪 + 百分比计算 + `to_dict()` |
| [orchestrator.py](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/cache_warmup/orchestrator.py) | `WarmupOrchestrator` 核心编排器 |
| [README.md](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/cache_warmup/README.md) | 完整模块文档（功能说明、流程图、4个使用示例） |

### 测试 (`tests/cache_warmup/`)
| 文件 | 说明 |
|------|------|
| [__init__.py](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/tests/cache_warmup/__init__.py) | 测试包初始化 |
| [test_cache_warmup.py](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/tests/cache_warmup/test_cache_warmup.py) | **68 个单元测试用例**，9 个测试类 |

---

## 核心能力

### 1. 依赖声明与拓扑排序
- 每个 `WarmupTask` 通过 `dependencies: List[str]` 声明依赖
- `TopologySorter.sort()` 使用 Kahn 算法执行拓扑排序，确保执行顺序合法
- 自动检测循环依赖（抛 `CircularDependencyError`）和缺失依赖（抛 `DependencyNotFoundError`）

### 2. 三种失败策略
| 策略 | 行为 |
|------|------|
| **`SKIP_DEPENDENTS`**（默认） | 任务失败 → 所有传递下游标记 `SKIPPED` |
| **`CONTINUE_ANYWAY`** | 仅标记自身失败，独立任务继续执行（有依赖仍按规则跳过） |
| **`ABORT_ALL`** | 任一任务失败 → 立即中止，剩余所有 PENDING 任务标记 `SKIPPED` |

### 3. 进度查询 API
```python
orch.get_progress(run_id)           # WarmupProgress：整体百分比、各状态计数、状态机
orch.get_task_progress(run_id, tid) # TaskProgress：单任务状态、耗时、错误信息、数据预览
progress.to_dict()                  # 结构化 JSON 导出
```

### 4. 其他特性
- 线程安全（`threading.Lock`）
- 幂等执行（终态流程重复调用不重复执行回调）
- 内存缓存存储（`Dict[str, Any]` 模拟缓存，支持按 task_id 取数）
- 进度快照隔离（返回的进度对象不受后续修改影响）
- 自定义时钟注入（便于测试耗时场景）

---

## 测试覆盖概览

| 测试类 | 用例数 | 覆盖范围 |
|--------|--------|----------|
| `TestConstants` | 5 | 枚举值正确性、终态集合 |
| `TestExceptions` | 2 | 异常继承层级 |
| `TestWarmupTask` | 5 | 任务模型、回调执行、hash/eq |
| `TestTopologySorter` | 10 | 线性/菱形/环依赖、缺失依赖、下游分析 |
| `TestTaskProgress` | 7 | 状态流转、耗时、to_dict |
| `TestWarmupProgress` | 6 | 百分比、计数、recalculate |
| `TestOrchestratorBasicAPI` | 9 | run 创建、任务注册、异常场景 |
| `TestOrchestratorHappyPath` | 9 | 0任务/单任务/多独立任务/线性依赖/菱形依赖 |
| `TestOrchestratorFailureStrategies` | 5 | 三种失败策略场景 |
| `TestOrchestratorDependencyErrors` | 2 | 环依赖 + 缺失依赖 |
| `TestOrchestratorProgressQueries` | 4 | 进度快照隔离、结构化导出 |
| `TestOrchestratorIdempotency` | 2 | 成功/失败后重复调用 |
| `TestIntegrationScenarios` | 3 | 推荐管线、电商部分失败、自定义时钟耗时 |

**运行测试**：
```bash
python -m pytest tests/cache_warmup/ -v
```