# TravelAgent: 能说会做的一站式旅游规划智能体

[![Language](https://img.shields.io/badge/Language-Python%203.9+-blue.svg)](https://www.python.org/)
[![Protocol](https://img.shields.io/badge/Protocol-Model%20Context%20Protocol%20(MCP)-orange.svg)](https://modelcontextprotocol.io/)
[![Course](https://img.shields.io/badge/Course-软件工程-brightgreen.svg)](https://edu.cnblogs.com/campus/gdgy/Class56-Grade2024-CS/)
[![Homework](https://img.shields.io/badge/Homework-构建能说会做的智能体16760-purple.svg)](https://edu.cnblogs.com/campus/gdgy/Class56-Grade2024-CS/homework/16760)
[![Tests](https://img.shields.io/badge/Tests-38%20Passed-success.svg)](tests/)

本项目为 **广东工业大学计算机学院 2024 级软件工程课程**【作业 16760：构建一个能说会做的智能体】的专属场景落地实现。聚焦于**旅游规划专属垂直领域**，全面落地开源的 **Model Context Protocol (MCP)** 行业标准，**强制接入真实云端大语言模型**（彻底关闭伪离线兜底），根据用户输入的【地点】、【交通方式】及【指定时间点在什么地方】等硬性约束，自动调度百度地图原生 WebService 工具链生成包含【景点门票】、【交通接驳】、【当季气象穿衣】与【老字号美食】的一条龙深度定制攻略。

---

## 👥 团队成员与分工

| 成员姓名 | 学号 | 班级 | Git 提交身份 | 核心项目分工 | 贡献占比 |
| :--- | :--- | :--- | :--- | :--- | :---: |
| **赵海翔** | 3124004113 | 24 计科 6班 | `IntZhx2` | 系统总架构、智能体内核 (SmartAgent)、ReAct 约束求解循环、多轮会话持久化与跨模型上下文自愈机制、真实大模型接入验证 | 35% |
| **何卓文** | 3124004132 | 24 计科 6班 | `reminderxxx` / `Traewen Ho` | MCP Server 服务端 (JSON-RPC 2.0)、百度地图 WebService 原生接入与 QPS 限流保护、SafeKeyVault 混淆安全保险箱与 38 项全套单元测试 | 35% |
| **吴与同** | 3124004018 | 24 计科 6班 | `FLC-niko` | 莫兰迪自然美学 Web UI 设计、侧边栏会话历史无感接续与 Markdown 导出、Web Speech API 语音录入 (STT) 与 朗读 (TTS)、多模态交互体验 | 30% |

---

## 🌟 核心特色与工程亮点

1. **深度专注垂直场景：一条龙旅游规划**：
   - 绝非大而无当的泛化功能堆砌，专注于为旅行者解决真实痛点：串联实时天气与穿衣指数、换乘路线耗时、景点预约规则与老字号招牌菜，给出精准时间线规划；
   - **严格响应硬性时间约束**：用户提出“周六下午 15:00 必须到广州塔登塔”、“早上 9:00 在酒店大堂集合”，智能体自动倒推通勤时间与前置游览节奏，拒绝脱节排期。
2. **纯真大模型驱动与跨模型自愈机制**：
   - 全面关闭伪离线模板规则，所有推理思考与规划均由**云端真实大语言模型实时生成**（支持通义千问、DeepSeek 官方、Google Gemini、OpenAI 等兼容端点）；
   - 独创 **`compact_last_turn` 上下文自愈机制**，在多轮对话中自动剥离中间工具调度帧，保证长程历史为纯净的 `user <-> assistant` 轮次，并在滑动窗口截断时强制首条消息为 `user`，彻底解决 DeepSeek 与 Gemini 报 400 校验异常的痛点。
3. **百度地图原生 WebService 接入与安全凭据保险箱**：
   - 接入 DirectionLite 公交地铁规划、百度天气与原生穿衣指数 (`chuanyi`)、Place POI 检索；
   - 内置 **`SafeKeyVault` 高熵动态混淆加密安全引擎**，杜绝明文 Key 上传公开代码仓库；
   - 引入滑动时间戳限流与多级内存缓存，有效保护开发者个人配额（3 QPS），避免并发报错。
4. **多轮对话持久化与无缝接续**：
   - 会话历史自动落盘存储于本地，网页侧边栏支持秒级无感检索、无缝接续追问；
   - 支持将完整会话及工具执行轨迹一键导出排版精美的 Markdown 电子文档随时查阅。
5. **多模态语音交互 (STT / TTS)**：
   - 集成浏览器原生 **Web Speech API**，支持自然语音录入旅行需求，并以清晰自然的中文语音朗读生成的行程方案。
6. **莫兰迪白底极简现代界面**：
   - 纯白底为主，融合莫兰迪低饱和度温润色谱（鼠尾草绿、灰暮蓝、灰陶红），界面清爽简洁，侧边栏作为统一整体自然顺畅纵向滚动。

---

## 🚀 快速启动与使用指南

### 1. 运行自动化测试套件
```bash
python3 smart_agent/main.py --test
```
*执行 38 项全覆盖自动化测试（涵盖 MCP 协议、百度地图、SafeKeyVault、会话持久化与 Web REST），1.8 秒内 100% 绿灯通过。*

### 2. 启动 Web 交互前端（推荐）
```bash
python3 smart_agent/main.py --web
```
控制台将输出服务启动信息，在浏览器中访问：
```
👉 http://127.0.0.1:8000
```
- 首次打开若未配置 API Key，将弹出配置窗口（支持填入通义千问、DeepSeek、Gemini、OpenAI 等兼容端点）；
- 在左侧选择或输入地点、天数、交通方式及【关键时间点约束】，点击【生成定制行程】即可实时获得一条龙图文攻略；
- 点击左侧【对话历史记录】中的任意条目，即可随时无缝接续多轮对话，或点击下载图标导出完整 Markdown 记录。

### 3. 运行微基准性能压测
```bash
python3 smart_agent/tests/benchmark_profile.py
```
*测试 MCP JSON-RPC 序列化、SafeKeyVault 密钥解密、百度地图内存缓存检索与上下文自愈压缩吞吐量。*

### 4. 命令行交互模式 (CLI)
```bash
python3 smart_agent/main.py --cli
```

---

## 📂 模块代码目录结构

```text
smart_agent/
├── main.py                     # 主程序入口：支持 --web, --cli, --test 运行模式
├── config.py                   # 全局配置管理（模型端点、API Key、System Prompt）
├── agent/                      # 旅游智能体认知内核
│   ├── core.py                 # TravelAgent 核心控制器：ReAct 倒推约束求解循环
│   ├── memory.py               # 多轮对话记忆：滑动窗口裁剪、compact_last_turn 自愈压缩
│   ├── session_manager.py      # 会话持久化管理器：多轮轮次增量落盘与 Markdown 导出
│   └── llm_client.py           # 真实大模型客户端：强制 API Key 校验与模型别名映射
├── security/                   # 安全凭据与密钥管理
│   ├── __init__.py             # 安全包导出
│   └── key_vault.py            # SafeKeyVault 高熵动态混淆加密与运行时解密引擎
├── utils/                      # 基础辅助与工具库
│   ├── __init__.py             # 工具包导出
│   ├── security.py             # 密钥混淆加密/解密底层实现与 SafeKeyVault 类
│   └── encrypt_key.py          # 百度地图 AK 加密生成命令行工具
├── mcp/                        # Model Context Protocol 标准协议实现
│   ├── protocol.py             # JSON-RPC 2.0 协议规范、数据实体与错误码
│   ├── server.py               # MCP Server：旅游专属工具注册、initialize 握手与请求路由
│   └── client.py               # MCP Client：拉取工具清单并适配大模型 Function Calling
├── tools/                      # 旅游专属 MCP 工具集与外部生态
│   ├── __init__.py             # 工具包导出 (create_default_tools)
│   ├── base.py                 # 工具基类与 Schema 解析
│   ├── baidu_map.py            # 百度地图 WebService 原生客户端（DirectionLite/POI/限流缓存）
│   ├── weather_tool.py         # 目的地气象与穿衣出行决策工具 (weather_query，百度天气API)
│   ├── traffic_tool.py         # 交通接驳与通勤换乘规划工具 (traffic_transit)
│   ├── attraction_tool.py      # 景点门票预约与周边美食情报工具 (attraction_info)
│   └── itinerary_tool.py       # 行程归档与导出工具 (itinerary_save / itinerary_list)
├── web/                        # Web 服务与莫兰迪响应式界面
│   ├── __init__.py             # Web 服务包导出
│   ├── server.py               # 原生多线程 HTTP 服务器、SSE 流式回显与 RESTful/MCP 路由
│   └── static/
│       ├── index.html          # 莫兰迪自然美学 SPA 界面 (快捷组合、会话历史、聊天视窗)
│       ├── app.js              # 前端交互、API 配置、多轮无缝接续与时间线攻略渲染
│       ├── speech.js           # Web Speech API 语音录入 (STT) 与 朗读 (TTS)
│       └── style.css           # 纯白底为主 + 莫兰迪低饱和度优雅样式表
├── docs/                       # 系统工程文档与白皮书
│   ├── architecture.md         # MCP 架构设计与技术白皮书
│   ├── PSP.md                  # 三人团队 PSP 2.1 任务耗时与工程效能度量表
│   └── performance.md          # 系统效能度量与基准压测白皮书
└── tests/                      # 38 项全覆盖自动化测试套件
    ├── test_agent.py           # ReAct 倒推求解、滑动窗口与上下文自愈测试 (6项)
    ├── test_baidu_map.py       # 百度地图地理编码、路线规划与 POI 检索测试 (4项)
    ├── test_mcp.py             # MCP 协议、initialize 与服务端通信测试 (8项)
    ├── test_security.py        # SafeKeyVault 凭据加解密与容错安全性测试 (4项)
    ├── test_session_manager.py # 会话生命周期、多轮增量落盘与标题保护测试 (3项)
    ├── test_tools.py           # 气象穿衣/交通/景点/归档工具集测试 (5项)
    ├── test_web.py             # Web HTTP API、MCP 端点与多轮接续测试 (8项)
    └── benchmark_profile.py    # 核心组件微基准压测脚本 (吞吐量与耗时剖析)
```
