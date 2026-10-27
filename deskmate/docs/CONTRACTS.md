# CONTRACTS —— 接口契约（唯一真相源）

> **契约版本：2**  
> 变更说明：去除摄像头依赖，改为 Windows 平台；增加空调红外控制、工作台配置与窗口编排、键鼠活跃度统计（InputMinute）、多智能体协同协议及 Wellbeing 模块内部接口。
> 修改流程见 `AGENTS.md` §2。字段名一律 `snake_case`。时间一律 ISO 8601 带时区（如 `2026-11-20T21:30:00+08:00`）。

---

## §1 WebSocket 通用信封

所有 WebSocket 消息（edge ↔ backend、web ↔ backend）统一采用如下 JSON 结构：

```json
{
  "v": 2,
  "type": "event | cmd | result | ping | pong",
  "id": "uuid4-string",
  "ts": "2026-11-20T21:30:00+08:00",
  "name": "消息名，如 device.state / tool.call",
  "payload": {}
}
```

- `type="cmd"` 的消息，接收方必须回复 `type="result"`，`name="tool.result"`，并在 payload 中携带 `call_id` = 原 cmd 的 `id`。
- 心跳：任一方每 20 秒发 `ping`，对方回复 `pong`；若 60 秒未收到任何消息，判定为断线，客户端执行指数退避重连（1, 2, 4, 8, 16, 30... 秒）。
- 接收到未知 `name` 的消息必须记录 warning 日志并安全忽略，禁止抛出未捕获异常导致崩溃。

---

## §2 共享数据结构与设备模型

### 2.1 DeviceState（按逻辑设备名归一化）

```jsonc
// lamp 米家台灯 1S
{ "online": true, "on": true, "brightness": 80, "color_temp": 4000 } // brightness: 1-100; color_temp 单位 K (2500-4800)

// plug 米家智能插座 3
{ "online": true, "on": true, "power_w": 12.5 } // power_w 可为 null

// ac 空调（小爱红外遥控）
{ "online": true, "on": true, "mode": "cool", "temperature": 26, "inferred": true } // mode: "cool" | "heat" | "fan" | "dry"; inferred: true 表示为红外无状态回传推测态

// motion 小米人体传感器 2
{ "online": true, "last_motion_at": "2026-11-20T21:29:40+08:00", "illuminance": "weak" } // illuminance: "strong" | "weak" | null

// climate 米家智能温湿度计 3
{ "online": true, "temperature": 26.7, "humidity": 57.0, "updated_at": "2026-11-20T21:30:00+08:00" }

// speaker 小爱音箱 Play 增强版
{ "online": true, "voice_bridge_ok": true, "ir_supported": true }
```

### 2.2 运行时状态对象

#### PresenceState（在座状态）
```json
{
  "present": true,
  "since": "2026-11-20T20:30:00+08:00",
  "sources": { "motion": true, "keyboard_mouse": true, "screen_locked": false }
}
```

#### FocusState（专注状态）
```json
{
  "state": "idle | focusing | short_break | paused",
  "session_id": 12,
  "workspace_name": "软工大作业",
  "goal": "完成第3节类图绘制",
  "phase_started_at": "2026-11-20T20:30:00+08:00",
  "phase_ends_at": "2026-11-20T21:15:00+08:00",
  "remaining_seconds": 900,
  "pomodoro_index": 1,
  "flow_extensions": 0,
  "focus_seconds_today": 2700
}
```

#### FatigueState（疲劳与心流状态）
```json
{
  "level": 1,
  "score": 48.0,
  "in_flow": false,
  "reasons": ["long_presence", "typing_rate_drop", "hot_room"],
  "updated_at": "2026-11-20T21:30:00+08:00"
}
```
`reasons` 枚举值：
- `long_presence`: 连续在座超过设定阈值
- `typing_rate_drop`: 键鼠活跃度低于个人基线 50% 以上
- `idle_presence`: 人在座但持续无键鼠输入（发呆）
- `hot_room`: 室内温度高于预警阈值（如 ≥ 27.5℃）
- `late_night`: 深夜学习时段（如 23:30 后）

#### InputMinute（每分钟键鼠及系统活动）
```json
{
  "minute": "2026-11-20T21:30:00+08:00",
  "keys": 120,
  "clicks": 35,
  "scrolls": 12,
  "active_seconds": 45,
  "app_switches": 4,
  "front_process": "Code.exe",
  "front_title_category": "study",
  "activity_rate": 167.0
}
```
*注：严禁上报按键字符内容，仅统计敲击计数值。*

#### WorkspaceProfile（工作台配置）
```json
{
  "id": 1,
  "name": "软工大作业",
  "aliases": ["软工", "大作业", "软件工程项目"],
  "focus_minutes": 45,
  "lamp": { "brightness": 80, "color_temp": 4000 },
  "ac": { "auto_on": true, "temperature": 26 },
  "items": [
    { "type": "vscode", "path": "D:\\Projects\\DeskMate" },
    { "type": "folder", "path": "D:\\University\\Course\\SoftwareEng" },
    { "type": "url", "url": "https://edu.cnblogs.com/campus/gdgy/Class56-Grade2024-CS" },
    { "type": "app", "name": "Chrome" }
  ],
  "layout": "code_left_browser_right",
  "custom_layout": null
}
```

---

## §3 Edge ↔ Backend 协议（`wss://<host>/ws/edge`）

Edge 客户端连接时带 URL Query 参数 `?token=<EDGE_TOKEN>`。认证失败由后端以 HTTP 4401 关闭。

### 3.1 Edge → Backend 事件清单（type="event"）

| event name | payload | 说明 |
|---|---|---|
| `edge.hello` | 见下方详细格式 | 连接成功后发送的第一条握手包，上报设备初始态与工具能力 |
| `device.state` | `{ "device": "lamp", "state": DeviceState }` | 任一受控设备发生状态变化时全量推送该设备状态 |
| `voice.heard` | `{ "text": "帮我查一下Dijkstra算法", "heard_at": "...", "handled_by_edge": false }` | 语音桥检测到用户对小爱发出的自然语言并决定由 DeskMate 接管 |
| `pc.input_stats` | `InputMinute` | **每 60 秒**定时上报过去一分钟的键鼠综合活动计数 |
| `pc.session` | `{ "locked": bool, "active": bool, "idle_seconds": int }` | 锁屏/解锁即时上报，或空闲状态变化时上报 |
| `edge.log` | `{ "level": "warning" \| "error", "message": "..." }` | 硬件适配或工具执行中的严重异常日志 |

#### `edge.hello` payload 规范：
```json
{
  "edge_version": "0.2.0",
  "platform": "windows",
  "dpi_scale": 1.5,
  "devices": {
    "lamp": { "online": true, "on": true, "brightness": 80, "color_temp": 4000 },
    "plug": { "online": true, "on": true, "power_w": 0.0 },
    "ac": { "online": true, "on": false, "mode": "cool", "temperature": 26, "inferred": true },
    "motion": { "online": true, "last_motion_at": "...", "illuminance": "weak" },
    "climate": { "online": true, "temperature": 26.5, "humidity": 55.0, "updated_at": "..." },
    "speaker": { "online": true, "voice_bridge_ok": true, "ir_supported": true }
  },
  "capabilities": {
    "lamp": { "color_temp_min": 2500, "color_temp_max": 4800 },
    "ac": { "temp_min": 16, "temp_max": 30, "modes": ["cool", "heat", "fan", "dry"] }
  },
  "tools": [ /* ToolSpec 清单，见 §3.3 */ ]
}
```

### 3.2 Backend → Edge 指令（type="cmd"）

```json
{
  "type": "cmd",
  "id": "cmd-uuid-4",
  "name": "tool.call",
  "payload": {
    "tool": "lamp_set",
    "args": { "brightness": 80, "color_temp": 4000 }
  }
}
```

Edge 收到后必须在规定超时时间内执行并回复：
```json
{
  "type": "result",
  "id": "res-uuid-4",
  "name": "tool.result",
  "payload": {
    "call_id": "cmd-uuid-4",
    "ok": true,
    "data": {},
    "error": null
  }
}
```
错误码规范：`BAD_ARGS`、`DEVICE_OFFLINE`、`NOT_ALLOWED`、`PERMISSION_DENIED`、`TIMEOUT`、`INTERNAL`。

### 3.3 Edge 必须提供的工具集（ToolSpec）

| tool | 参数（args） | 成功返回（data） | 所属智能体 / 权限 | 默认超时 |
|---|---|---|---|---|
| `lamp_set` | `on?: bool, brightness?: int, color_temp?: int` | 最新 lamp `DeviceState` | 环境 Agent (公开) | 5s |
| `lamp_effect` | `effect: "breathe" \| "blink", duration_s?: int` | `{}` | 环境 Agent (内部) | 15s |
| `ac_set` | `on?: bool, mode?: "cool"\|"heat"\|"fan"\|"dry", temperature?: int` | 最新 ac `DeviceState` | 环境 Agent (公开) | 8s |
| `plug_set` | `on: bool` | 最新 plug `DeviceState` | 环境 Agent (公开) | 5s |
| `speaker_tts` | `text: str, interrupt?: bool = true` | `{}` | 内部指令 (截断 ≤ 60字) | 6s |
| `speaker_stop` | — | `{}` | 内部指令 (打断播放) | 3s |
| `speaker_exec_directive` | `directive: str`（如"把空调调到26度"） | `{}` | 内部红外遥控通道 | 8s |
| `voice_expect_reply` | `seconds: int = 30` | `{}` | 语音桥开启连续对话窗口 | 3s |
| `open_app` | `name: str` | `{ "opened": str }` | 电脑 Agent (白名单) | 8s |
| `open_folder` | `path: str, in_vscode?: bool = false` | `{ "opened": str }` | 电脑 Agent | 8s |
| `open_url` | `url: str` | `{}` | 电脑 Agent | 5s |
| `find_files` | `keyword: str, directory?: str, limit?: int = 5` | `{ "files": [{"path": str, "name": str, "is_dir": bool}] }` | 电脑 Agent | 10s |
| `arrange_windows` | `layout: "code_left_browser_right" \| "maximize" \| "split_half" \| "custom", custom?: dict` | `{ "arranged_count": int }` | 电脑 Agent / 工作台 | 10s |
| `get_open_windows` | — | `{ "windows": [{"title": str, "process": str, "rect": [x, y, w, h]}] }` | 电脑 Agent | 5s |
| `read_clipboard` | — | `{ "text": str }`（截断至 8000 字） | 电脑 Agent | 3s |
| `write_clipboard` | `text: str` | `{}` | 电脑 Agent | 3s |
| `get_selected_text` | — | `{ "text": str }` | 电脑 Agent | 3s |
| `take_screenshot` | `target?: "screen" \| "latest_desktop_file", max_side?: int = 1280` | `{ "image_b64": str, "mime": "image/jpeg" }` | 内部多模态通道 | 10s |
| `create_note` | `title: str, content: str` | `{ "path": str }` | 电脑 Agent | 5s |
| `show_win_toast` | `title: str, message: str` | `{}` | 内部通知工具 | 4s |
| `edge_config_update` | `{ app_whitelist, study_apps, entertainment_apps, voice_takeover_prefixes }` | `{}` | 后端同步配置 | 5s |

---

## §4 Web ↔ Backend 协议（`wss://<host>/ws/web?token=<JWT>`）

### 4.1 Backend → Web 实时事件（type="event"）

| event name | payload 内容 | 触发时机 |
|---|---|---|
| `state.snapshot` | 完整系统快照：`{ edge_online, demo_mode, devices, presence, focus, fatigue, current_input_stats }` | 前端建立连接成功后立即推送一次 |
| `state.patch` | 部分状态增量更新对象（前端浅合并） | 状态发生变化时合并节流（200ms）推送 |
| `notify` | `{ "level": "info" \| "warn" \| "alert", "title": str, "text": str, "action": "none" \| "rest_overlay" }` | 疲劳介入、系统提醒或小爱语音播报同步气泡 |
| `voice.log` | 单条 `VoiceLog` 结构 | 每次语音或智能体响应结束 |
| `assist.result` | `{ "kind": "code_clip" \| "screen_explain" \| "search_summary", "title": str, "markdown": str }` | 声控电脑产生完整图文/代码时推送到右侧抽屉 |

### 4.2 Web → Backend 交互指令（type="event"）

| event name | payload 内容 | 说明 |
|---|---|---|
| `rest.skip` | `{}` | 用户在前端全屏强制休息倒计时上点击跳过 |

---

## §5 RESTful API 规范

所有需要认证的端点请求头均需附带：`Authorization: Bearer <JWT>`。

### 5.1 基础与设备控制
- `GET /api/health` → `{ "ok": true, "edge_online": bool, "demo_mode": bool }`
- `POST /api/auth/login` → 入参 `{ "username", "password" }`，返回 `{ "token", "user": { "id", "username", "is_demo" } }`
- `GET /api/state` → 返回当前 `state.snapshot`
- `POST /api/devices/{device}/command`
  - `lamp`: `{ "on"?: bool, "brightness"?: int, "color_temp"?: int }`
  - `ac`: `{ "on"?: bool, "mode"?: str, "temperature"?: int }`
  - `plug`: `{ "on": bool }`
  - 返回 `{ "ok": true, "state": DeviceState }`

### 5.2 工作台与专注会话
- `GET /api/workspaces` → 返回 `[WorkspaceProfile]`
- `POST /api/workspaces` → 创建工作台配置
- `PUT /api/workspaces/{id}` → 更新工作台配置
- `DELETE /api/workspaces/{id}` → 删除工作台配置
- `POST /api/focus/start` → 入参 `{ "workspace_id"?: int, "goal"?: str, "minutes"?: int }`，返回 `FocusState`
- `POST /api/focus/stop` → 返回 `{ "session": FocusSession }`
- `GET /api/focus/sessions` → Query `?from=YYYY-MM-DD&to=YYYY-MM-DD`，返回 `[FocusSession]`

### 5.3 健康、时序曲线与报告
- `GET /api/reports/daily` → Query `?date=YYYY-MM-DD`，返回 `DailyReport`
- `POST /api/reports/daily/generate` → 入参 `{ "date": "YYYY-MM-DD" }`，强制重新生成 AI 日报
- `GET /api/reports/weekly` → Query `?week_start=YYYY-MM-DD`，返回周汇总与趋势点评
- `GET /api/timeline` → Query `?date=YYYY-MM-DD`，返回当日时序曲线数据：
  ```json
  {
    "date": "2026-11-20",
    "inputs": [ { "minute": "...", "activity_rate": 140, "top_category": "study" } ],
    "env": [ { "at": "...", "temperature": 26.5, "humidity": 55 } ],
    "fatigue_events": [ FatigueEvent ],
    "focus_spans": [ { "started_at": "...", "ended_at": "...", "workspace": "软工大作业" } ]
  }
  ```

### 5.4 智能体对话与日志
- `POST /api/chat` → 入参 `{ "message": str, "conversation_id"?: str }`，**SSE 流式响应**：
  ```
  event: delta   data: {"text": "正在为你配置软工大作业工作台..."}
  event: tool    data: {"agent": "orchestrator", "tool": "start_work", "args": {...}, "status": "running|ok|error"}
  event: done    data: {"reply": "完整回应", "conversation_id": "..."}
  event: error   data: {"message": "..."}
  ```
- `GET /api/logs/voice` → Query `?limit=50`，返回最近语音与对话交互日志 `[VoiceLog]`
- `GET /api/settings` → 返回当前配置项
- `PUT /api/settings` → 更新配置项（持久化并即时生效）

### 5.5 线上演示注入端点（仅 DEMO 账号可用）
- `POST /api/demo/inject`
  - 格式：`{ "kind": str, "value": any }`
  - `kind="motion"`: 模拟人体传感器被触发
  - `kind="leave"`: 模拟人员离开座位
  - `kind="lock"`: 模拟系统锁屏/解锁（`value: true|false`）
  - `kind="temperature"`: 模拟环境温度变动（`value: 28.5`）
  - `kind="typing_rate"`: 模拟键盘鼠标活跃速率（`value: 20` 代表疲劳暴跌，`value: 180` 代表心流敲击）
  - `kind="voice"`: 模拟小爱听到的语音句子（`value: "我要开始写软工大作业了，帮我准备一下"`）

---

## §6 系统默认配置表（Settings）

```json
{
  "focus_lamp": { "brightness": 80, "color_temp": 4000 },
  "relax_lamp": { "brightness": 40, "color_temp": 2700 },
  "sleep_lamp": { "brightness": 10, "color_temp": 2500 },
  "auto_lamp_after": "18:00",
  "motion_window_min": 5,
  "absent_confirm_min": 3,
  "absent_lamp_sleep_min": 3,
  "absent_lamp_off_min": 15,
  "absent_ac_off_min": 30,
  "ac": {
    "auto_rule": "auto",
    "summer_temp": 26,
    "trigger_on_temp": 27.5,
    "high_humidity_trigger": 75.0
  },
  "wellbeing": {
    "l1_score": 40,
    "l2_score": 55,
    "l3_score": 75,
    "max_continuous_focus_min": 60,
    "cooldown_min": 15,
    "flow_extension_min": 10,
    "max_flow_extensions": 2
  },
  "app_whitelist": [
    "Code.exe", "devenv.exe", "idea64.exe", "pycharm64.exe",
    "chrome.exe", "msedge.exe", "firefox.exe",
    "notepad.exe", "explorer.exe", "Typora.exe", "Obsidian.exe",
    "WeChat.exe"
  ],
  "study_categories": ["Code.exe", "idea64.exe", "pycharm64.exe", "Typora.exe", "Obsidian.exe"],
  "entertainment_categories": ["bilibili.com", "douyin.com", "weibo.com", "Steam.exe", "CloudMusic.exe"],
  "voice_takeover_prefixes": ["帮我", "请", "桌伴", "准备一下", "查一下", "分析一下"]
}
```

---

## §7 语音快速响应词表（Fast Path，≤ 3s 无 LLM 消耗）

| 意图识别正则（按序匹配） | 关联动作与参数 |
|---|---|
| `^(我要开始(学习\|专注\|工作\|写作业)\|开始学习)` | 进入默认或上次使用的工作台专注模式 |
| `^(结束(学习\|专注\|工作)\|退出专注)` | 结束专注会话，计算本次小结播报 |
| `^(开灯\|把灯打开)` | `lamp_set(on=true)` |
| `^(关灯\|把灯关了)` | `lamp_set(on=false)` |
| `^(调亮\|亮一点)` | 台灯亮度 +20 |
| `^(调暗\|暗一点)` | 台灯亮度 -20 |
| `^(开空调\|把空调打开)` | `ac_set(on=true, temperature=26)` |
| `^(关空调\|把空调关了)` | `ac_set(on=false)` |
| `^(空调.*(?P<temp>\d{2})度)` | 提取温度数值并执行 `ac_set(temperature=int(temp))` |
| `^(现在多少度\|室内温湿度)` | 播报温湿度计当前指标 |
| `^(还剩多久\|学了多久)` | 播报当前番茄钟剩余时间或已专注时长 |

未命中以上正则的语句，统一转入**协调者 Agent（Orchestrator）**进行意图分解与多智能体分发。

---

## §8 Wellbeing 模块 Python 内部接口规范

该接口定义了成员 B（后端平台）与成员 C（健康引擎开发）在 Python 进程内的交互边界，由 `backend/app/wellbeing/engine.py` 实现并供系统调用：

```python
from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

class WellbeingAction(BaseModel):
    action_type: str  # "lamp_breathe" | "voice_care" | "force_break" | "flow_extended" | "none"
    level: int        # 0, 1, 2, 3
    speech_text: Optional[str] = None
    reason: List[str] = []

class IWellbeingEngine(ABC):
    @abstractmethod
    def on_minute_stats(self, stat: dict, current_focus: Optional[dict], env_temp: float) -> Optional[WellbeingAction]:
        """每分钟由 scheduler/state_store 传入最新 InputMinute 指标，计算疲劳度，返回触发的干预动作"""
        pass

    @abstractmethod
    def check_flow_extension(self, focus_session_id: int) -> bool:
        """番茄钟时间到时调用。若符合心流特征返回 True，自动顺延 10 分钟并记录"""
        pass

    @abstractmethod
    def on_user_left(self, is_locked: bool) -> None:
        """人员离座或系统锁屏时通知，重置在座计时与疲劳累计分"""
        pass

    @abstractmethod
    def generate_daily_report(self, date_str: str) -> dict:
        """生成指定日期的结构化统计数据与大模型建议点评"""
        pass
```

---

## 契约变更记录
- **v1 (2026-10-26)**: 初稿，包含基本设备、摄像头疲劳、REST 与 WS 基础定义。
- **v2 (2026-10-27)**: 架构升级：去除摄像头，采用键鼠活跃节奏分析；增加空调红外控制；支持工作台多窗口协同编排；升级多智能体分工与协调通信。
