# TravelAgent 架构设计与技术实现白皮书

本文档详细记录 **广东工业大学 24 计科 6班三人团队（赵海翔、何卓文、吴与同）** 构建的 **TravelAgent 智能旅游规划系统** 的系统架构、Model Context Protocol (MCP) 标准协议、ReAct 倒推约束求解循环、会话持久化与跨模型上下文自愈机制。

---

## 一、 系统总体架构设计

TravelAgent 专注于**智能出行与一条龙旅游规划专属垂直领域**，坚持“高内聚、低耦合”的软件工程分层原则：

```mermaid
flowchart TB
    subgraph Presentation["1. 交互表现层 (莫兰迪白底极简 SPA)"]
        WebUI["单页应用 SPA (莫兰迪温润色系 + 纯白底为主)"]
        TravelGuideForm["行程要素快捷组合向导 (地点/天数/交通方式/时间点)"]
        SessionSidebar["会话管理中枢 (历史记录无感检索/无缝接续/Markdown导出)"]
        VoiceSTT["语音录入 STT (Web Speech API)"]
        VoiceTTS["语音合成 TTS (SpeechSynthesis API)"]
    end

    subgraph Cognitive["2. 认知规划内核 (TravelAgent Cognitive Core)"]
        AgentCore["TravelAgent 核心控制器 (core.py)"]
        ReActLoop["ReAct 倒推约束求解: 时间硬约束 -> 气象/交通/景点调度 -> 一条龙规划"]
        Memory["滑动窗口上下文记忆管理器 (memory.py)"]
        SessionMgr["多轮会话持久化存储引擎 (session_manager.py)"]
        ContextHealer["跨模型上下文自愈与压缩机制 (compact_last_turn)"]
        MandatoryLLM["真实在线云端大语言模型 (DeepSeek / Gemini / 通义千问 / GPT)"]
    end

    subgraph Security["3. 安全凭据与存储中枢 (Security Vault)"]
        KeyVault["SafeKeyVault 高熵动态混淆加密引擎"]
        RateLimiter["百度地图 API QPS 平滑限流保护与 POI 内存缓存"]
    end

    subgraph Protocol["4. MCP 协议总线层 (Model Context Protocol)"]
        MCPClient["MCP 客户端适配器 (client.py)"]
        JSONRPC["JSON-RPC 2.0 序列化与错误分发通道 (protocol.py)"]
        MCPServer["MCP 服务端路由中心 (server.py, tools/call, initialize, /api/mcp)"]
    end

    subgraph ToolsLayer["5. 真实旅游专属工具生态层 (Tools Ecosystem)"]
        BaiduClient["百度地图 WebService 原生客户端 (baidu_map.py)"]
        WeatherTool["实时天气与穿衣出行指数 (weather_query)"]
        TrafficTool["交通接驳换乘与通勤预估 (traffic_transit)"]
        AttractionTool["景点门票实名预约与老字号美食 (attraction_info)"]
        ItineraryTool["Markdown 攻略导出与归档清单 (itinerary_save / itinerary_list)"]
    end

    Presentation --> Cognitive
    Cognitive --> Security
    Cognitive --> Protocol
    MCPClient <-->|JSON-RPC 2.0| MCPServer
    MCPServer --> ToolsLayer
    ToolsLayer --> BaiduClient
    BaiduClient --> RateLimiter
    BaiduClient --> KeyVault
```

---

## 二、 核心约束求解与 ReAct 执行时序

针对用户提出的【地点】、【交通方式】及【特定时间点在什么地方】的复合需求，智能体执行精准的倒推规划：

```mermaid
sequenceDiagram
    autonumber
    actor User as 用户 (旅行者)
    participant Web as 莫兰迪前端 (Web UI)
    participant Agent as 旅游智能体 (TravelAgent)
    participant Memory as 上下文与会话 (Memory & Session)
    participant LLM as 真实云端大模型 (DeepSeek/Gemini/Qwen)
    participant MCP as MCP 协议总线 (Client/Server)
    participant Baidu as 百度地图 WebService (API)

    User->>Web: 输入定制需求（如：广州2日游，地铁出行，周六15:00必须到广州塔）
    Web->>Agent: POST /api/chat (带 session_id)
    Agent->>Memory: 载入历史轮次并追加当前提问
    
    rect rgb(248, 247, 244)
        Note over Agent,LLM: ReAct 第一轮：目的地气象感知与穿衣指数
        Agent->>LLM: 提交系统指令 + 用户需求 + MCP 工具清单
        LLM-->>Agent: Thought: 优先确认目的地气温与穿衣 -> Call: weather_query(city='广州')
        Agent->>MCP: 调度 tools/call
        MCP->>Baidu: 查询百度天气与穿衣指数 (带 QPS 限流保护)
        Baidu-->>MCP: 返回 24~29℃、多云微风、舒适穿衣指南
        MCP-->>Agent: Observation 注入上下文
    end

    rect rgb(248, 247, 244)
        Note over Agent,LLM: ReAct 第二轮：硬性时间点逆推与交通换乘
        Agent->>LLM: 提交包含天气上下文的最新状态
        LLM-->>Agent: Thought: 用户指定15:00到达广州塔，需计算前序通勤 -> Call: traffic_transit(...)
        Agent->>MCP: 调度 tools/call
        MCP->>Baidu: 请求 DirectionLite 公共交通换乘规划
        Baidu-->>MCP: 返回地铁3号线路线、耗时28分钟、避堵建议
        MCP-->>Agent: Observation 注入上下文
    end

    rect rgb(248, 247, 244)
        Note over Agent,LLM: ReAct 第三轮：景点门票预约与地道老字号美食
        Agent->>LLM: 提交包含交通数据的最新状态
        LLM-->>Agent: Thought: 挖掘广州塔周边正宗粤菜老字号 -> Call: attraction_info(...)
        Agent->>MCP: 调度 tools/call
        MCP->>Baidu: 请求 Place POI 检索周边老字号
        Baidu-->>MCP: 返回分时段门票预约规则、炳胜品味脆皮叉烧
        MCP-->>Agent: Observation 注入上下文
    end

    Agent->>LLM: 综合所有客观真实数据，编写结构化时间线攻略
    LLM-->>Agent: 生成包含景点、换乘耗时、老字号餐厅的一条龙深度方案
    Agent->>Memory: 执行 compact_last_turn 纯净化，落盘会话 session.json
    Agent-->>Web: SSE 流式回显 / JSON 结构化渲染
    Web-->>User: 展现攻略排版并触发 Web Speech API 语音朗读 (TTS)
```

---

## 三、 多轮对话持久化与跨模型上下文自愈机制

在实际工程落地中，不同大模型服务商（如 OpenAI、DeepSeek、Google Gemini）对于历史上下文中的 `tool_calls` 和 `tool` 结果消息校验策略各不相同：
- **DeepSeek 校验约束**：严格要求多轮历史遵循 `user` 与 `assistant` 的严格交替，不允许在历史长文中残留无对应工具调用结果的悬空帧，且滑动窗口修剪后系统提示词后的第一条消息必须为 `user` 角色。
- **Gemini 校验约束**：严格要求 `tool_call` 与 `functionResponse` 成对闭环，否则报 400 校验异常。

### 上下文自愈与双轨压缩解决方案
1. **轻量轮次存储模型 (`SessionManager`)**：
   在持久化层将每一轮对话记录为高内聚的原子单元：
   ```json
   {
     "turn_id": 1,
     "timestamp": "2026-10-23 18:30:00",
     "user_prompt": "广州2日游，地铁出行，下午3点必须到广州塔",
     "step_traces": [...],
     "assistant_response": "..."
   }
   ```
2. **上下文自愈压缩 (`compact_last_turn`)**：
   在一轮 ReAct 推理结束后，智能体立即将该轮对话中的中间工具调度帧压缩，仅在长程记忆窗口中保留：
   - 原始用户的 `user` 输入；
   - 最终综合生成的 `assistant` 完整回复。
3. **安全恢复与首条 User 强制约束 (`load_from_turns` & `_trim_window`)**：
   当用户在侧边栏点击任意历史会话时，系统从持久化轮次直接重构上下文，并在滑动窗口裁剪后，自动修剪掉由于窗口截断导致的孤立 `assistant` 消息，确保第一条消息永远是 `user`，彻底杜绝所有云端大模型的 400 格式报错。

---

## 四、 百度地图 WebService 原生接入与 QPS 限流保护

针对外部气象与地图接口易受网络超时与配额上限限制的问题，系统深度集成了百度地图开放平台 WebService：

1. **多级平滑限流与并发防护**：
   个人开发者配额通常为 3 QPS。系统在 `BaiduMapClient` 中设计了基于时间戳差值的平滑限流器（`_rate_limit`）与多级内存缓存字典（`_geo_cache`、`_place_cache`），有效防止大模型并发调用时的额度耗尽报警。
2. **多维城市气象与穿衣出行指数**：
   直接对接百度天气开放接口，实时采集城市最高/最低气温、相对湿度、天气现象及专属穿衣指数（`chuanyi`），让智能体不仅能感知气象，还能输出体贴的出行着装建议。
3. **高熵凭据安全加密引擎 (`SafeKeyVault`)**：
   敏感的 API 凭据在代码库与配置文件中以高熵多轮异或与掩码混淆加密存储，系统启动时由安全保险箱在内存中解密使用，杜绝明文凭据上传公网导致的被盗刷风险。
