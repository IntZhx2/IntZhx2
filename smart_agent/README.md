# TravelAgent: 能说会做的一站式旅游规划智能体

[![Language](https://img.shields.io/badge/Language-Python%203.9+-blue.svg)](https://www.python.org/)
[![Protocol](https://img.shields.io/badge/Protocol-Model%20Context%20Protocol%20(MCP)-orange.svg)](https://modelcontextprotocol.io/)
[![Course](https://img.shields.io/badge/Course-软件工程-brightgreen.svg)](https://edu.cnblogs.com/campus/gdgy/Class56-Grade2024-CS/)
[![Homework](https://img.shields.io/badge/Homework-构建能说会做的智能体16760-purple.svg)](https://edu.cnblogs.com/campus/gdgy/Class56-Grade2024-CS/homework/16760)
[![Tests](https://img.shields.io/badge/Tests-19%20Passed-success.svg)](tests/)

本项目为 **广东工业大学计算机学院 2024 级软件工程课程**【作业 16760：构建一个能说会做的智能体】的专属场景落地实现。聚焦于**专属旅游定制场景**，严格遵循 **Model Context Protocol (MCP)** 行业标准，**强制接入真实大语言模型**（全面关闭伪离线兜底），根据用户输入的【地点】、【交通方式】及【指定时间点在什么地方】等硬性约束，自动调度工具生成包含【景点】、【交通】与【美食】的一条龙深度旅游攻略。

---

## 👥 团队成员与分工

| 成员姓名 | 学号 | 班级 | Git 提交身份 | 核心项目分工 | 贡献占比 |
| :--- | :--- | :--- | :--- | :--- | :---: |
| **赵海翔** | 3124004113 | 24 计科 6班 | `IntZhx2` | 系统总架构、智能体内核 (TravelAgent)、ReAct 约束求解循环、多轮记忆管理与真实 LLM 强制接入验证 | 35% |
| **何卓文** | 3124004132 | 24 计科 6班 | `reminderxxx` | MCP Server 服务端 (JSON-RPC 2.0)、气象穿衣/交通接驳/景点预约/攻略归档 MCP 工具生态与单元测试 | 35% |
| **吴与同** | 3124004018 | 24 计科 6班 | `FLC-niko` | 莫兰迪自然美学 Web UI 设计、Web Speech API 语音录入 (STT) 与 朗读 (TTS)、演示示例整理与交互测试 | 30% |

---

## 🌟 核心特色与加分项达成

1. **专注深度场景：一条龙旅游规划**：
   - 绝非杂糅泛泛功能，专注于为旅行者解决真实痛点：结合实时天气、换乘路线耗时、景点预约规则与老字号美食，给出精准时间线规划；
   - **严格响应硬性时间约束**：例如用户要求“周六下午 15:00 必须到广州塔登塔”、“早上 9:00 在酒店大堂集合”，智能体自动倒推通勤时间与前置游览节奏，拒绝脱节排期。
2. **纯真大模型驱动（强制配置 API Key）**：
   - 全面关闭伪离线模板规则，所有思考推理、逻辑调度与攻略撰写均由**云端真实大语言模型实时生成**（支持通义千问百炼、DeepSeek、智谱、OpenAI 等兼容端点）；
   - 网页右上角集成可视化 **API 配置弹窗**，一键切换服务商预设并动态生效。
3. **加分项 1：多轮对话记忆系统**：
   - 滑动窗口机制维护上下文预算，支持在多轮对话中动态追加或微调约束条件（如：“把第二天晚上的火锅换成清淡海鲜”）。
4. **加分项 2：多模态语音输入/输出 (STT/TTS)**：
   - 集成浏览器原生 **Web Speech API**，支持自然语音录入旅行需求，并以清晰自然的中文语音朗读生成的行程方案。
5. **加分项 3：外部 API 与 MCP 专属工具链交互**：
   - 挂载 `weather_query` (气象穿衣)、`traffic_transit` (交通接驳耗时)、`attraction_info` (景点预约与招牌菜)、`itinerary_save` (保存方案至 Markdown 文档)。
6. **加分项 4：莫兰迪白底极简现代界面**：
   - 视觉以**纯白底为主**，辅以**莫兰迪低饱和度温润色系**（鼠尾草绿、灰暮蓝、灰陶红、暖灰褐），带来清新舒适的阅读感与呼吸感。

---

## 🚀 快速启动与使用指南

### 1. 运行自动化测试套件
```bash
python3 main.py --test
```
*执行 19 项全覆盖自动化测试，涵盖 MCP 协议标准序列化、真实 API 强制校验、气象交通景点专属工具与 Web REST 模拟。*

### 2. 启动 Web 交互前端（推荐）
```bash
python3 main.py --web
```
控制台将输出启动信息，在浏览器中访问：
```
👉 http://127.0.0.1:8000
```
1. 首次打开如果未配置 API Key，将弹出配置窗口；
2. 填入您的 API Key（如阿里云百炼、DeepSeek、智谱等）；
3. 在左侧向导选择地点、天数、交通方式及【关键时间点约束】，点击【一键生成一条龙攻略】，即可看到大模型调用 MCP 工具并输出精美图文攻略！

### 3. 命令行交互模式 (CLI)
```bash
python3 main.py --cli
```

---

## 📂 模块代码目录结构

```text
smart_agent/
├── main.py                     # 主程序入口：支持 --web, --cli, --test 运行模式
├── config.py                   # 全局配置管理（模型端点、API Key、System Prompt）
├── agent/                      # 旅游智能体认知内核
│   ├── core.py                 # TravelAgent 核心：ReAct 约束求解循环
│   ├── memory.py               # 多轮对话记忆：滑动窗口裁剪与持久化
│   └── llm_client.py           # 真实大模型客户端（强制 API Key 校验）
├── mcp/                        # Model Context Protocol 标准协议实现
│   ├── protocol.py             # JSON-RPC 2.0 协议规范、数据实体与错误码
│   ├── server.py               # MCP Server：旅游专属工具注册与请求路由
│   └── client.py               # MCP Client：拉取工具清单并适配大模型 Function Calling
├── tools/                      # 旅游专属 MCP 工具集
│   ├── base.py                 # 工具基类与 Schema 解析
│   ├── weather_tool.py         # 目的地气象与穿衣出行决策工具 (weather_query)
│   ├── traffic_tool.py         # 交通接驳与通勤换乘规划工具 (traffic_transit)
│   ├── attraction_tool.py      # 景点门票预约与周边美食情报工具 (attraction_info)
│   └── itinerary_tool.py       # 行程归档与导出工具 (itinerary_save / itinerary_list)
├── web/                        # Web 服务与莫兰迪响应式界面
│   ├── server.py               # 原生多线程 HTTP 服务器与 RESTful API 路由
│   └── static/
│       ├── index.html          # 莫兰迪自然美学 SPA 界面 (向导表单、聊天视窗)
│       ├── app.js              # 前端交互、API 配置与时间线攻略渲染
│       ├── speech.js           # Web Speech API 语音录入 (STT) 与 朗读 (TTS)
│       └── style.css           # 纯白底为主 + 莫兰迪低饱和度优雅样式表
├── tests/                      # 自动化测试套件
│   ├── test_mcp.py             # MCP 协议与服务端通信测试
│   ├── test_tools.py           # 气象/交通/景点/归档工具集测试
│   ├── test_agent.py           # ReAct 约束求解与强制 Key 校验测试
│   └── test_web.py             # Web HTTP API 接口集成测试
├── docs/                       # 工程文档
│   ├── architecture.md         # 架构设计与 MCP 规范技术白皮书
│   └── PSP.md                  # 三人小组 PSP 2.1 任务耗时度量表
├── README.md                   # 本说明文件
└── BLOG.md                     # 按照 homework/15692 规范撰写的完整作业博文
```
