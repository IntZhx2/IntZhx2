# ARCHITECTURE —— 系统架构（v0.2）

## 1. 总体架构

```mermaid
flowchart LR
    subgraph Desk["书桌现场（成员A的 Windows 笔记本 + 米家设备）"]
        XA["小爱音箱 Play 增强版\n(语音 + 蓝牙网关 + 红外遥控)"]
        AC["空调（红外）"]
        DEV["台灯1S / 智能插座3 / 人体传感器2 / 温湿度计3"]
        HA["Home Assistant (Docker Desktop)\n+ 小米官方集成 ha_xiaomi_home"]
        EDGE["Edge Agent (Python, Windows)\n设备适配 / 语音桥 / 电脑工具 / 键鼠与窗口监测"]
    end
    subgraph Cloud["云服务器（Docker）"]
        NGINX["Nginx (HTTPS, 静态前端)"]
        API["Backend (FastAPI)\n多智能体 / 状态中心 / 规则引擎 / Wellbeing 引擎"]
        DB[("SQLite")]
        VE["VirtualEdge (演示模式)"]
    end
    WEB["浏览器 Web 控制台"]
    LLM["大模型 API\n文本 / 快速 / 多模态 / 联网搜索"]
    MICLOUD["小米云"]

    XA -. 红外 .-> AC
    DEV <--> MICLOUD
    XA <--> MICLOUD
    HA <--> MICLOUD
    EDGE <-->|REST + WebSocket| HA
    EDGE <-->|"MiService：对话轮询 / TTS / 执行文本指令"| MICLOUD
    EDGE <-->|"wss /ws/edge（edge 主动外连）"| API
    WEB <-->|"https + wss /ws/web"| NGINX --> API
    API --> DB
    API --> LLM
    VE -.替代真实 edge.-> API
```

**关键设计决策**
1. **Edge 主动外连云端 WebSocket**：宿舍无公网 IP，无需内网穿透。
2. **Home Assistant 做设备抽象层**：BLE 传感器只能经网关上小米云，小米官方 HA 集成统一提供状态推送与控制。HA 不可用时降级为 `mijiaAPI`（只改 edge 适配层）。
3. **空调走小爱红外**：小爱 Play 增强版自带红外遥控，空调在米家中是"红外虚拟设备"。首选方案是通过小爱"执行文本指令（静默）"下发自然语言（"把空调调到 26 度"），因为这一路径对所有红外设备通用；若 HA 能直接暴露该红外空调实体，则改用 HA 调用。红外无状态回传 → 后端维护"推测状态"。
4. **小爱语音输入用"对话记录轮询"**（参考 xiaogpt / mi-gpt / MiService），多轮确认通过"期待回复窗口"实现；兜底网页语音输入。
5. **大脑只在后端**：edge 只负责"感知上报 + 执行工具"，不做决策。
6. **工具由 edge 动态注册**：edge 连接时上报 ToolSpec（JSON Schema），后端按"所属 Agent"分组注册（沿用 TravelAgent 的 MCP 工具思想）。
7. **疲劳检测不用摄像头**：用"在座时长 + 键鼠节奏相对个人基线 + 发呆 + 环境 + 时段"多源融合，个人基线让判断因人而异，并能识别"心流"反向保护。
8. **演示模式**：VirtualEdge 与真实 edge 协议完全一致，满足"上线供老师检查"和 B/C 无硬件开发。

## 2. 多智能体设计（答辩重点）

```mermaid
flowchart TB
    IN["输入：小爱语音 / 网页对话 / 系统事件"] --> R{"语音路由器\n快速路径正则"}
    R -->|命中| FAST["快速路径执行器\n(无 LLM, ≤3s)"]
    R -->|未命中| O["协调者 Agent (Orchestrator)\n意图理解 · 任务分解 · 并行派发 · 汇总回应"]
    O -->|delegate_env| ENV["环境 Agent\n台灯/空调/插座/灯光场景"]
    O -->|delegate_pc| PC["电脑 Agent (ReAct)\n打开/编排窗口/搜索/截图分析/剪贴板"]
    O -->|start_work| WS["工作台执行器\n(确定性流程, 环境与电脑并行)"]
    O -->|get_status / report| WB["状态健康 Agent (Wellbeing)\n疲劳融合 · 心流保护 · 关心话术 · 复盘报告"]
    EVT["键鼠统计 / 传感器 / 温湿度"] --> WB
    WB -->|干预动作| ACT["动作接口\n呼吸灯 / 小爱播报 / Windows 通知 / 切换休息"]
    PC --> VL["多模态模型\n截图分析"]
    PC --> SR["联网搜索"]
```

| Agent | 实现方式 | 模型 | 工具 |
|---|---|---|---|
| 协调者 | function calling，单轮可并行发出多个工具调用（`asyncio.gather` 执行） | `LLM_MODEL` | `start_work`、`stop_work`、`delegate_env`、`delegate_pc`、`get_status`、`get_today_summary`、`set_reminder`、`save_workspace`(P1) |
| 环境 Agent | 简单请求走规则映射；复杂请求（"灯光弄温馨点""有点闷"）用快速模型选工具 | `LLM_FAST_MODEL` | `lamp_set`、`lamp_effect`、`ac_set`、`plug_set` |
| 电脑 Agent | ReAct，最多 6 步 | `LLM_MODEL` + `LLM_VL_MODEL` | edge 电脑工具 + 后端 `web_search`、`analyze_image` |
| 状态健康 Agent | **规则打分（确定性）+ 快速模型生成话术与报告点评** | `LLM_FAST_MODEL` | 通过动作接口执行干预（CONTRACTS §8） |

设计原则：**需要可靠的地方用确定性代码，需要理解与表达的地方用大模型**。工作台执行、疲劳打分、规则联动是确定性的；意图理解、开放任务规划、话术、复盘由 LLM 完成。

## 3. 后端模块与所有权

```
backend/app/
  main.py config.py db.py clock.py          (B)
  schemas/contracts.py                      (B) 契约 pydantic 模型
  ws/ edge_hub.py web_hub.py envelope.py    (B)
  api/ ...                                  (B) 除 reports/timeline 外的 REST
  engine/ state_store.py presence.py rules.py focus.py scheduler.py   (B)
  agent/ llm.py orchestrator.py env_agent.py pc_agent.py workspace_exec.py
         voice_router.py tools.py search.py vision.py prompts.py      (B)
  sim/virtual_edge.py                       (B)
  wellbeing/                                (C)
    models.py        InputMinute / FatigueEvent / FlowExtension / DailyReport 表
    baseline.py      个人基线
    fatigue.py       疲劳打分与等级状态机
    flow.py          心流保护
    engine.py        WellbeingEngine（实现 CONTRACTS §8 接口）
    copywriter.py    关心话术（LLM + 模板兜底）
    report.py        日报/周报统计与 AI 点评
    router.py        /api/reports/* 与 /api/timeline
```

## 4. 疲劳等级状态机

```mermaid
stateDiagram-v2
    [*] --> L0
    L0 --> L1: score ≥ 40 持续 60s（心流中不触发）
    L1 --> L2: score ≥ 55 持续 60s 或 L1 持续 10min 未缓解
    L2 --> L3: score ≥ 75 持续 60s
    L1 --> L0: score < 30 持续 3min
    L2 --> L1: score < 45 持续 3min
    L3 --> L0: 休息结束
    L1 --> L0: 离座 ≥ 3min（视为休息，在座时长清零）
    L2 --> L0: 离座 ≥ 3min
```

## 5. 专注会话状态机

```mermaid
stateDiagram-v2
    [*] --> idle
    idle --> focusing: start_work / focus_start
    focusing --> focusing: 到点且处于心流 → 顺延10min（≤2次）
    focusing --> short_break: 到点 / L3
    short_break --> focusing: 休息结束
    focusing --> paused: 离座（锁屏或无人≥3min）
    paused --> focusing: 回座
    focusing --> idle: stop_work
    short_break --> idle: stop_work
    paused --> idle: stop_work / 离座 ≥ 60min
```

## 6. 数据模型（需求文档类图）

```mermaid
classDiagram
    class User {
        +int id
        +str username
        +str password_hash
        +bool is_demo
    }
    class Settings {
        +int user_id
        +json values
    }
    class WorkspaceProfile {
        +int id
        +int user_id
        +str name
        +list aliases
        +int focus_minutes
        +json lamp
        +list items
        +str layout
        +json custom_layout
    }
    class FocusSession {
        +int id
        +int user_id
        +int workspace_id
        +datetime started_at
        +datetime ended_at
        +str goal
        +int focus_seconds
        +int pomodoros_done
        +int pause_count
        +int flow_extensions
        +str end_reason
    }
    class InputMinute {
        +datetime minute
        +int keys
        +int clicks
        +int scrolls
        +int active_seconds
        +int app_switches
        +str top_category
        +float activity_rate
    }
    class FatigueEvent {
        +int id
        +int session_id
        +datetime at
        +int level
        +float score
        +list reasons
        +str action_taken
    }
    class PresenceEvent {
        +datetime at
        +bool present
        +str trigger
    }
    class EnvReading {
        +datetime at
        +float temperature
        +float humidity
    }
    class VoiceLog {
        +datetime at
        +str text
        +str route
        +json trace
        +str reply
        +int latency_ms
        +bool ok
    }
    class DailyReport {
        +date day
        +json stats
        +str ai_comment
    }
    User "1" --> "1" Settings
    User "1" --> "*" WorkspaceProfile
    User "1" --> "*" FocusSession
    WorkspaceProfile "1" --> "*" FocusSession
    FocusSession "1" --> "*" FatigueEvent
    User "1" --> "*" DailyReport
```

运行时对象（不落库）：`DeviceState`、`PresenceState`、`FocusState`、`FatigueState`、`PcActivity`，字段见 CONTRACTS §2。

## 7. 典型时序：场景 1

```mermaid
sequenceDiagram
    participant U as 用户
    participant X as 小爱
    participant E as Edge
    participant O as 协调者
    participant W as 工作台执行器
    participant L as LLM
    U->>X: 我要开始写软工大作业了，帮我准备一下
    X-->>E: 对话记录（轮询 ≤1s）
    E->>X: 打断原生回答
    E->>O: voice.heard
    O->>L: 意图解析（带工作台列表）
    L-->>O: start_work{workspace:"软工大作业"}
    O->>W: start_work
    par 环境动作
        W->>E: lamp_set(80%,4000K)
        W->>E: ac_set(cool,26)（室温≥27）
    and 电脑动作
        W->>E: open_folder(vscode) / open_folder(explorer) / open_url
        W->>E: arrange_windows(code_left_browser_right)
    end
    W->>W: 创建 FocusSession(45min)
    W-->>O: 各动作结果
    O->>E: speaker_tts("工作台已为你配置好……加油！")
```

## 8. 典型时序：场景 3

```mermaid
sequenceDiagram
    participant E as Edge
    participant WB as Wellbeing 引擎
    participant B as 动作接口(B实现)
    E->>WB: pc.input_stats（每60s）
    WB->>WB: 更新基线/打分：在座60min+节奏降70%+27℃ → 50
    WB->>B: L1 → lamp_effect(breathe,10s)
    Note over WB: L1 持续 10min 未缓解
    WB->>B: L2 → speak(LLM话术) + expect_reply(30s)
    E->>B: voice.heard("好")
    B->>E: ac_set(temperature-1)
    E->>B: pc.session(locked=true)
    B->>B: 番茄钟暂停 + lamp 伴眠光(10%,2700K)
```

## 9. 部署

- 云服务器 2C2G；`deploy/docker-compose.yml`：`backend` + `nginx`（托管 `frontend/dist`，反代 `/api`、`/ws`，SSE 关闭缓冲）。
- HTTPS 推荐（JWT 安全、wss）。国内域名需 ICP 备案（1~3 周），第一周就办；来不及用香港区服务器。
- 现场：Windows 笔记本运行 Docker Desktop（HA）+ `python -m deskmate_edge`。
