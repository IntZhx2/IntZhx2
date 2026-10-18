# TravelAgent 架构设计与协议技术白皮书

本文档详细记录 **广东工业大学 24 计科 6班三人团队** 构建的 **TravelAgent 智能旅游规划系统** 的总体架构、Model Context Protocol (MCP) 规范落地、ReAct 约束求解循环及莫兰迪白底美学工程设计。

---

## 一、 系统总体架构设计

TravelAgent 专注于**旅游定制专属垂直领域**，杜绝无意义的功能杂糅，建立在严密的软件工程分层体系之上：

```mermaid
flowchart TB
    subgraph Presentation["1. 交互表现层 (莫兰迪极简白底美学)"]
        WebUI["响应式单页应用 SPA (莫兰迪低饱和度色系 + 白底为主)"]
        TravelGuideForm["行程要素快捷组合向导 (地点/天数/交通方式/时间点约束)"]
        VoiceSTT["语音录入 STT (Web Speech API)"]
        VoiceTTS["语音合成 TTS (SpeechSynthesis API)"]
    end

    subgraph Cognitive["2. 认知规划内核 (TravelAgent Cognitive Core)"]
        AgentCore["TravelAgent 核心控制器 (core.py)"]
        ReActLoop["ReAct 约束求解循环: 用户约束 -> 气象/交通/景点工具调度 -> 归纳一条龙攻略"]
        Memory["多轮对话记忆管理器 (memory.py - 滑动窗口机制)"]
        MandatoryLLM["强制云端大模型引擎 (OpenAI 兼容 / 通义千问 / DeepSeek / 智谱)"]
    end

    subgraph Protocol["3. MCP 协议总线层 (Model Context Protocol)"]
        MCPClient["MCP 客户端适配器 (client.py)"]
        JSONRPC["JSON-RPC 2.0 序列化通道 (protocol.py)"]
        MCPServer["MCP 服务端路由分发中心 (server.py)"]
    end

    subgraph ToolsLayer["4. 旅游专属工具生态层 (Travel Tools Ecosystem)"]
        WeatherTool["实时天气与穿衣出行防护工具 (weather_query)"]
        TrafficTool["交通接驳换乘与通勤预估工具 (traffic_transit)"]
        AttractionTool["景点预约规则与周边老字号美食工具 (attraction_info)"]
        ItineraryTool["Markdown 攻略归档与导出工具 (itinerary_save / list)"]
    end

    Presentation --> Cognitive
    AgentCore --> Memory
    AgentCore --> MandatoryLLM
    AgentCore --> MCPClient
    MCPClient <-->|JSON-RPC 2.0| MCPServer
    MCPServer --> ToolsLayer
```

---

## 二、 核心约束求解与 ReAct 执行时序

针对用户提出的【地点】、【交通方式】及【特定时间点必须在什么地方】的复合需求，智能体执行精准的倒推规划：

```mermaid
sequenceDiagram
    autonumber
    actor User as 用户 (旅行者)
    participant Web as 莫兰迪前端 (Web UI)
    participant Agent as 旅游智能体 (TravelAgent)
    participant LLM as 真实大模型 (Qwen/DeepSeek/GPT)
    participant MCP as MCP 协议总线 (Client/Server)
    participant Tool as 专属工具 (Weather/Traffic/Attraction)

    User->>Web: 提出定制需求（例如：广州2日游，地铁出行，周六15:00必须到广州塔登塔）
    Web->>Agent: POST /api/chat
    Agent->>Agent: 写入多轮记忆 ConversationMemory
    
    rect rgb(245, 244, 239)
        Note over Agent,LLM: ReAct 约束求解第一轮：气象与环境感知
        Agent->>LLM: 提交系统指令 + 用户需求 + 可用 MCP 工具
        LLM-->>Agent: Thought: 优先确认目的地气温与降雨 -> Call: weather_query(city='广州')
        Agent->>MCP: 调度 tools/call
        MCP->>Tool: 执行 WeatherQueryTool
        Tool-->>MCP: 返回 24~29℃、多云微风、穿衣指数
        MCP-->>Agent: Observation 注入上下文
    end

    rect rgb(245, 244, 239)
        Note over Agent,LLM: ReAct 约束求解第二轮：硬性时间点逆推与交通换乘
        Agent->>LLM: 提交包含天气上下文的最新消息
        LLM-->>Agent: Thought: 用户要求 15:00 必须到广州塔，需核算前序换乘 -> Call: traffic_transit(...)
        Agent->>MCP: 调度 tools/call
        MCP->>Tool: 执行 TrafficTransitTool
        Tool-->>MCP: 返回地铁换乘路线、预估30分钟、高峰防拥堵贴士
        MCP-->>Agent: Observation 注入上下文
    end

    rect rgb(245, 244, 239)
        Note over Agent,LLM: ReAct 约束求解第三轮：景点预约与招牌美食
        Agent->>LLM: 提交包含交通方案的上下文
        LLM-->>Agent: Thought: 确认广州塔与西关周边必吃老字号 -> Call: attraction_info(...)
        Agent->>MCP: 调度 tools/call
        MCP->>Tool: 执行 AttractionInfoTool
        Tool-->>MCP: 返回分时段门票预约规则、周边炳胜粤菜与老字号早茶
        MCP-->>Agent: Observation 注入上下文
    end

    Agent->>LLM: 综合所有客观真实数据，编写结构化时间线攻略
    LLM-->>Agent: 生成包含景点、换乘耗时、老字号餐厅的一条龙完整方案
    Agent-->>Web: 渲染 ReAct 思考卡片与 Markdown 美学排版
    Web-->>User: 展现攻略并触发 Web Speech API 语音朗读 (TTS)
```

---

## 三、 强制接入真实在线大模型的安全规范

1. **彻底杜绝伪离线欺骗**：
   在 `llm_client.py` 中移除任何预设死数据的规则模板，当 `api_key` 为空或无效时，系统直接以结构化 HTTP 400 拦截请求并给出引导，确保智能体的生成富有创造力、温度和真实逻辑推理能力。
2. **零泄漏安全存储**：
   用户填入的 API Key 仅保存在当前运行服务内存与本地浏览器 Session 中，绝不回传任何第三方，且前端界面展示时统一做脱敏遮蔽（如 `sk-***abcd`）。
