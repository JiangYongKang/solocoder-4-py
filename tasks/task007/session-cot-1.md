让我先探索当前项目的结构，了解项目的组织方式和现有代码风格。

        
            
toolName: view_folder
            
status: success
          
c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py
          

        
            
toolName: file_search
            
status: success
          
file_pattern: src/**/*.py
          

        
            
toolName: file_search
            
status: success
          
file_pattern: tests/**/*.py
          
让我查看现有模块的代码风格，特别关注 `cache_warmup` 模块（包含拓扑排序相关逻辑）和其他模块的模式。


        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_warmup\__init__.py
          

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_warmup\exceptions.py
          

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_warmup\constants.py
          

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_warmup\topology.py
          

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\cache_warmup\README.md
          

        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\cache_warmup\test_cache_warmup.py
          
让我查看项目配置文件，然后创建任务规划。


        
            
toolName: view_files
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\pyproject.toml
          
现在我对项目的结构和代码风格有了全面了解。让我创建任务规划并开始实现。




        
            
toolName: todo_write
            
status: success
          
Todos updated: 9 items
          

        
            
toolName: todo_write
            
status: success
          
Todos updated: 9 items
          
首先创建所有核心源代码文件。我会按照项目的现有代码风格编写。



        
            
toolName: Write
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\module_init_graph\__init__.py
          
changes: undefined
          

        
            
toolName: Write
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\module_init_graph\constants.py
          
changes: undefined
          

        
            
toolName: Write
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\module_init_graph\exceptions.py
          
changes: undefined
          

        
            
toolName: Write
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\module_init_graph\module.py
          
changes: undefined
          

        
            
toolName: todo_write
            
status: success
          
Todos updated: 9 items
          

        
            
toolName: Write
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\module_init_graph\topology.py
          
changes: undefined
          
现在实现核心的初始化编排器 `initializer.py`：





        
            
toolName: todo_write
            
status: success
          
Todos updated: 9 items
          

        
            
toolName: Write
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\module_init_graph\initializer.py
          
changes: undefined
          
现在创建测试文件和 README.md：






        
            
toolName: todo_write
            
status: success
          
Todos updated: 9 items
          

        
            
toolName: Write
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\module_init_graph\__init__.py
          
changes: undefined
          

        
            
toolName: Write
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\tests\module_init_graph\test_module_init_graph.py
          
changes: undefined
          

        
            
toolName: todo_write
            
status: success
          
Todos updated: 9 items
          

        
            
toolName: Write
            
status: success
          
            
filePath: c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py\src\solocoder_4_py\module_init_graph\README.md
          
changes: undefined
          
现在运行测试验证实现的正确性：







        
            
toolName: todo_write
            
status: success
          
Todos updated: 9 items
          

        
            
toolName: run_command
            
status: success
          
command: cd c:\Users\vince\GoletaLab\SoloCoder-4\solocoder-4-py ; python -m pytest tests/module_init_graph/ -v --tb=short undefined
          
全部 80 个测试通过！让我更新任务状态并完成收尾。







        
            
toolName: todo_write
            
status: success
          
Todos updated: 9 items
          
## 任务完成总结

已完整实现**模块初始化依赖图**功能模块，所有 **80 个单元测试全部通过**（100%）。

### 一、创建的文件结构

**源代码包**：[`src/solocoder_4_py/module_init_graph/`](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/module_init_graph)

| 文件 | 核心职责 |
|------|---------|
| [`__init__.py`](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/module_init_graph/__init__.py) | 公共 API 导出 |
| [`constants.py`](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/module_init_graph/constants.py) | `ModuleState` / `InitState` 状态枚举 + 终态集合 |
| [`exceptions.py`](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/module_init_graph/exceptions.py) | 异常类层级（含带 `cycles` 字段的循环依赖异常） |
| [`module.py`](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/module_init_graph/module.py) | `ModuleNode` 数据模型（依赖声明、回调、`max_retries` 等） |
| [`topology.py`](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/module_init_graph/topology.py) | `TopologyAnalyzer` + `CycleReport`：拓扑排序、**多环检测**、上下游分析、层级计算 |
| [`initializer.py`](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/module_init_graph/initializer.py) | `ModuleProgress` / `InitProgress` / **`ModuleInitializer`**：核心编排器，含失败隔离 + 级联重试 |
| [`README.md`](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/src/solocoder_4_py/module_init_graph/README.md) | 完整功能文档、算法说明、6 个使用示例 |

**测试目录**：[`tests/module_init_graph/`](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/tests/module_init_graph)
- [`__init__.py`](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/tests/module_init_graph/__init__.py)
- [`test_module_init_graph.py`](file:///c:/Users/vince/GoletaLab/SoloCoder-4/solocoder-4-py/tests/module_init_graph/test_module_init_graph.py)（**80 个测试用例**）

---

### 二、三大核心功能实现要点

#### 1. 依赖解析 + 循环依赖检测（带详细报告）
- **拓扑排序**：`TopologyAnalyzer.sort()` 使用 Kahn 算法
- **循环检测**：基于 DFS 的环查找，找出**所有简单环**（支持多环）
- **结构化报告**：`CycleReport.cycles` 保存所有环的路径列表；`format_report()` 生成可读报告；异常 `CircularDependencyError` 中携带 `cycles` 字段

#### 2. 失败隔离（最小影响范围）
- 某模块失败后，通过 `get_all_downstream()` 获取**传递闭包下游**
- 仅标记真正依赖失败模块的下游为 `ISOLATED`
- 独立子图（无依赖关系）的模块正常初始化
- 自动构建隔离原因（如 "依赖模块失败: db_pool; 依赖模块被隔离: redis"）

#### 3. 局部重试 + 级联恢复
- **内置重试**：`ModuleNode(max_retries=N)`，首次初始化自动重试 N+1 次
- **`retry_module(module_id)`**：对失败/隔离模块重试
- **级联恢复**：重试成功后自动递归尝试下游中仅因本模块被隔离的模块（检查上游是否全部就绪后才执行，避免无效调用）
- **`retry_all_failed()`**：按拓扑升序批量重试所有失败/隔离模块