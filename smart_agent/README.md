# SmartAgent: 能说会做的多功能智能体系统

[![Language](https://img.shields.io/badge/Language-Python%203.9+-blue.svg)](https://www.python.org/)
[![Protocol](https://img.shields.io/badge/Protocol-Model%20Context%20Protocol%20(MCP)-orange.svg)](https://modelcontextprotocol.io/)
[![Course](https://img.shields.io/badge/Course-软件工程-brightgreen.svg)](https://edu.cnblogs.com/campus/gdgy/Class56-Grade2024-CS/)
[![Homework](https://img.shields.io/badge/Homework-构建能说会做的智能体16760-purple.svg)](https://edu.cnblogs.com/campus/gdgy/Class56-Grade2024-CS/homework/16760)
[![Tests](https://img.shields.io/badge/Tests-18%20Passed-success.svg)](tests/)

本项目为 **广东工业大学计算机学院 2024 级软件工程课程**【作业 16760：构建一个能说会做的智能体】的完整实现。由三人小组协作完成，严格遵循 **Model Context Protocol (MCP)** 行业标准，具备**语言交互（能说）**与**行动执行（会做）**双重能力，并达成全部 4 项加分项。

---

## 👥 团队成员与分工

| 成员姓名 | 学号 | 班级 | Git 提交身份 / 昵称 | 核心项目分工 | 贡献占比 |
| :--- | :--- | :--- | :--- | :--- | :---: |
| **赵海翔** | 3124004113 | 24 计科 6班 | `IntZhx2` | 架构总览、智能体内核 (SmartAgent)、ReAct 认知规划循环、多轮记忆管理与双模推理引擎 | 35% |
| **何卓文** | 3124004132 | 24 计科 6班 | `reminderxxx` | MCP Server 服务端 (JSON-RPC 2.0)、SQLite 任务数据库、天气/文件/计算工具集与单元测试 | 35% |
| **吴与同** | 3124004018 | 24 计科 6班 | `FLC-niko` | Web 现代交互前端 (HTML5/Tailwind/JS)、Web Speech API 语音录入(STT)与朗读(TTS)、演示示例整理 | 30% |

---

## 🌟 核心特色与加分项全达成

1. **自然语言交互（能说）**：
   - 具备流畅自然的意图理解能力，支持自我介绍、任务调度、日程规划与闲聊；
   - 支持主流大模型接口（通义千问百炼、DeepSeek、OpenAI），同时内置高性能**离线语义规划规则引擎**，离线断网或未配置 API Key 时亦可开箱即用。
2. **行动执行与工具调度（会做）**：
   - 全面落地 **Model Context Protocol (MCP)** 标准，基于 JSON-RPC 2.0 实现工具发现与安全分发；
   - 包含待办事项管理、SQLite 关系型数据库、实时天气查询与出行规划、沙箱文件安全读写、AST 高精度数学运算等丰富工具。
3. **加分项 1：多轮对话记忆系统**：
   - 采用滑动窗口算法（Sliding Window Context Budgeting），动态维持上下文预算；
   - 支持跨轮次指代消解与会话持久化到磁盘。
4. **加分项 2：多模态语音输入/输出 (STT/TTS)**：
   - 集成浏览器原生 **Web Speech API**，提供低延迟连续语音指令识别；
   - 自动过滤 Markdown 语法，实现流利自然的中文文本语音朗读。
5. **加分项 3：外部 API 与 SQLite 数据库深度交互**：
   - 内置 SQLite 关系型数据库引擎（`agent_data.db`），支持任务增删改查与原生 SQL 查询；
   - 支持与公共气象站点接口实时查询气象指标与穿衣指数。
6. **加分项 4：现代响应式 Web 交互前端**：
   - 提供视觉极佳的现代深色流线交互界面，支持实时查看 ReAct 思考轨迹、工具调用入参和执行结果；
   - 侧边栏提供待办状态看板与 MCP 已注册工具动态清单。

---

## 🚀 快速启动指南

本项目基于 **Python 原生标准库** 实现核心服务与协议，**无需额外安装庞大的第三方 Python 依赖库**，下载即可直接运行：

### 1. 运行自动化测试套件
```bash
python3 main.py --test
```
*执行 18 项全覆盖单元测试，包括 MCP 协议序列化、SQLite 工具、文件安全沙箱、ReAct 规划循环及 Web REST 模拟。*

### 2. 启动现代 Web 交互前端（推荐）
```bash
python3 main.py --web
```
控制台将输出启动信息，在浏览器中打开：
```
👉 http://127.0.0.1:8000
```
- 点击麦克风图标 🎙️ 进行**语音输入**；
- 页面将自动进行**语音朗读**回复；
- 侧边栏可实时监控并双向同步 SQLite 待办事项状态！

### 3. 命令行交互模式 (CLI)
```bash
python3 main.py --cli
```
可在终端中直接与 SmartAgent 进行自然语言指令交互，终端将实时打印 ReAct 思考轨迹与 MCP 调用日志。

---

## 📂 模块代码目录结构

```text
smart_agent/
├── main.py                     # 主程序入口：支持 --web, --cli, --test 运行模式
├── config.py                   # 全局配置管理（模型配置、端口、数据路径、System Prompt）
├── agent/                      # 智能体决策内核
│   ├── core.py                 # SmartAgent 核心：ReAct (Thought-Action-Observation) 循环
│   ├── memory.py               # 多轮对话记忆：滑动窗口裁剪、上下文持久化
│   └── llm_client.py           # 大模型客户端与高质量离线语义意图规则引擎
├── mcp/                        # Model Context Protocol 标准实现
│   ├── protocol.py             # JSON-RPC 2.0 协议规范、数据实体与错误码
│   ├── server.py               # MCP Server：工具动态注册表与请求路由分发
│   └── client.py               # MCP Client：拉取工具清单并适配大模型 Function Schema
├── tools/                      # MCP 工具生态集
│   ├── base.py                 # 工具基类与装饰器定义
│   ├── todo_tool.py            # SQLite 数据库与待办任务工具 (增删改查与 SQL 执行)
│   ├── file_tool.py            # 沙箱文件读写与工作区管理工具
│   ├── weather_tool.py         # 实时气象查询与多日出行攻略工具
│   └── math_tool.py            # 基于 AST 语法树的高精度安全数学计算器
├── web/                        # Web 服务与现代前端
│   ├── server.py               # 原生多线程 HTTP 服务器与 RESTful API 路由
│   └── static/
│       ├── index.html          # 响应式 Web UI (工具展示、待办看板、聊天窗口)
│       ├── app.js              # 前端交互与 ReAct 轨迹卡片渲染
│       ├── speech.js           # Web Speech API 语音录入 (STT) 与 朗读 (TTS)
│       └── style.css           # 现代深色高质感样式
├── tests/                      # 自动化测试套件
│   ├── test_mcp.py             # MCP 协议与服务端通信测试
│   ├── test_tools.py           # 数据库/文件/天气/计算工具集测试
│   ├── test_agent.py           # ReAct 认知规划与多轮记忆测试
│   └── test_web.py             # Web HTTP API 接口集成测试
├── docs/                       # 工程文档
│   ├── architecture.md         # 架构设计与 MCP 规范技术白皮书
│   └── PSP.md                  # 三人小组 PSP 2.1 任务耗时度量表
├── README.md                   # 本说明文件
└── BLOG.md                     # 按照 homework/15692 规范撰写的完整作业博文
```

---

## 🛠️ MCP 协议已注册工具一览

| 工具标识 (`name`) | 功能简要说明 | 关联数据或外部环境 |
| :--- | :--- | :--- |
| `todo_add` | 向待办数据库新增一条任务（指定标题、优先级、分类与截止时间） | SQLite 数据库 `agent_data.db` |
| `todo_list` | 查询检索待办清单（支持按 `pending`/`completed` 或分类过滤） | SQLite 数据库 `agent_data.db` |
| `todo_update` | 更新指定任务状态（如标记为完成 `completed`） | SQLite 数据库 `agent_data.db` |
| `todo_delete` | 根据 ID 删除指定的待办事项 | SQLite 数据库 `agent_data.db` |
| `sql_query` | 在数据库中执行只读与统计分析类 SQL 查询 | SQLite 数据库 `agent_data.db` |
| `file_read` | 安全读取工作空间中的指定文本文件 | 沙箱工作目录 `data/workspace/` |
| `file_write` | 在工作空间创建或追加文本文件（可保存日志或攻略） | 沙箱工作目录 `data/workspace/` |
| `file_list` | 列出当前工作区中存在的所有文档与资源 | 沙箱工作目录 `data/workspace/` |
| `weather_query` | 查询指定城市的实时气象动态与穿衣指南 | 开放气象 API / 离线气象知识库 |
| `travel_plan` | 为指定目的地定制多日旅游/出行规划与路线建议 | 气象与出行攻略引擎 |
| `calculate` | 执行精确数学算术与科学函数求值（零代码执行风险） | Python AST 安全求值器 |
