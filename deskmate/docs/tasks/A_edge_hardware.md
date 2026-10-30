# 任务卡 A —— 硬件与 Windows 边缘端（负责人：赵海翔 / 成员 A）

> **工作目录**：`edge/` 及 `docs/hardware/`  
> **运行环境**：个人 Windows 10/11 笔记本电脑（与米家智能设备处于同一局域网 Wi-Fi）  
> **AI 开发规范**：开工前必须完整阅读 `AGENTS.md`、`docs/CONTRACTS.md`（特别是 §1~§3 与 §7），以及 `docs/PRD.md` 中的场景 1、2、3。  
> **状态标记**：⬜ 未开始 / 🟡 进行中 / ✅ 完成

---

## 0. 演示与开发硬件清单（全在成员 A 手中）

| 逻辑设备 | 真实硬件型号 | 接入通道 | 在 DeskMate 中的核心作用 |
|---|---|---|---|
| `lamp` | 米家台灯 1S | Wi-Fi（米家/HA） | 专注冷白光（4000K/80%）、伴眠暖光（2600K/10%）、10秒呼吸律动（L1 疲劳干预） |
| `ac` | 宿舍/书房空调 | **红外遥控（经由小爱音箱 IR）** | 智能降温（制冷 26℃）、自动温控联动、支持语音调温 |
| `plug` | 米家智能插座 3 | Wi-Fi（米家/HA） | 工位外设供电联动（可外接桌面小风扇/显示器挂灯），人离座节能关断 |
| `motion` | 小米人体传感器 2 | BLE 蓝牙（经小爱网关上云） | 监测工位是否有人移动、环境环境光照强弱（配合防误判在座融合算法） |
| `climate` | 米家智能温湿度计 3 | BLE 蓝牙（经小爱网关上云） | 实时回传工位温度与湿度，驱动闷热疲劳加权与空调开启判定 |
| `speaker` | 小爱音箱 Play 增强版（L05C） | Wi-Fi / 红外 / 蓝牙 Mesh 网关 | 语音输入监听桥、TTS 关键语音播报、执行红外控制空调指令、充当低功耗蓝牙网关 |
| `pc` | Windows 笔记本 | 本地系统内核 | 窗口编排（VS Code/浏览器分屏）、键鼠活动率统计（无摄像头疲劳特征）、截图与代码剪贴板 |

---

## 1. 第一次作业阶段（10/26 – 11/08）：技术可行性探针（Spike）

**目标**：打通关键硬件调用链路，产出一段 30~60 秒的 Windows 真机实操演示录像（答辩核心亮点，击碎“画大饼”质疑）。

### A-01 Windows 环境 Home Assistant 部署与米家设备接入 ✅（已完成）
- **操作步骤**：
  1. Windows 安装 Docker Desktop（启用 WSL2 后端）；
  2. 启动容器：`docker run -d --name homeassistant --restart unless-stopped -p 8123:8123 -v C:\ha_config:/config -e TZ=Asia/Shanghai ghcr.io/home-assistant/home-assistant:stable`；
  3. 配置 `ha_xiaomi_home` 小米官方集成，扫码/账号登录绑定“学校”或“家”中的 5 款硬件设备；
  4. 生成长期访问令牌（Long-Lived Access Token），写入 `edge/.env` 中的 `HA_TOKEN`。
- **交付产物**：`docs/hardware/entities.md`（详细记录台灯、温湿度计、传感器、插座在 HA 中的 `entity_id`、属性名称及调用参数示例）。
- **验收标准**：
  - [x] 终端使用 PowerShell/Python 脚本能直接请求 HA REST API 调整台灯亮度与色温；
  - [x] 设备实体全量录入 `docs/hardware/entities.md` 与 `edge/config/devices.yaml`。
- **实际实现说明**：
  在 Windows Docker 部署 HA 并集成 `ha_xiaomi_home`。查出米家台灯 1S（yeelink.light.lamp4）MIoT 色温有效区间为 2600K~5000K。编写无依赖验证脚本 `edge/spikes/test_lamp.py`，实体验证 4000K 专注光与 2600K 伴眠光切换成功，全部 5 款实体已映射。

### A-02 小爱音箱语音对话桥与红外控制空调验证 ✅（已完成）
- **参考工具**：基于 `MiService` / `xiaogpt` 与小米官方云端对话流接口；
- **探针脚本编写**：`edge/spikes/voice_listener_spike.py`、`edge/spikes/test_speaker_ha.py`
  1. 验证获取小爱音箱 Play 增强版（L05C）的 `deviceId`（`f91bfdb1-8b3a-427b-8a47-ce85269c6ca1`）；
  2. 轮询对话历史接口（`userprofile.mina.mi.com/device_profile/v2/conversation`），成功在 1.2 秒内抓取到对小爱说出的“我要开始写作业了”；
  3. 拦截测试：检测到关键词后立即触发小爱执行自定义 TTS 播报（经由 HA 官方通道）；
  4. 红外遥控测试：调用小爱下发文本指令（`notify.xiaomi_..._execute_text_directive`），成功触发实体空调响应。
- **验收标准**：
  - [x] 语音输入抓取延迟稳定在 ≤ 2 秒内；
  - [x] 成功使用代码触发空调红外开关与调温；
  - [x] 记录账号防风控与 Token 缓存机制（`.mi.token` 自动复用，无需重复输验证码）。
- **实际实现说明**：
  通过排查确定小爱云端接口在 Cookie 中必须传入音箱实体的 DeviceID（`f91bfdb1-...`），编写了全链路联动脚本 `edge/spikes/voice_listener_spike.py`。输入走云端高速轮询（~1.2s），输出与红外控制走 HA 官方 notify 端点，实现毫秒级双向语音互动与空调控制。

### A-03 答辩真机演示视频录制 🟡（待录像）
- 串联软硬件闭环动作：对小爱说“小爱，我要开始写作业了，帮我准备一下” → 台灯调至冷白专注光 → Windows 屏幕自动弹出 VS Code 与作业目录 → 小爱语音播报确认。代码链路已在 `edge/spikes/voice_listener_spike.py` 中全部打通，用户可随时拍摄 30~60 秒高清视频交给组员 C 插入答辩 PPT。

---

## 2. 工程实现阶段任务（Sprint 1 ~ Sprint 3）

### A-10 Edge 工程骨架与跨平台通信管道 ✅（已完成，P0，Sprint 1）
- **核心逻辑**：
  - 启动时调用 `SetProcessDpiAwareness(2)` 解决 Windows 高分屏缩放坐标偏移；
  - `ws_client.py` 维护长连接，启动即发送 `edge.hello` 注册 ToolSpec 清单；
  - 统一指令分发与 20 秒心跳保活、指数退避重连机制；
  - 平台抽象隔离层（`platform_win` 与 `platform_mock`），单测脱离硬件独立运行。
- **实际实现说明**：
  完成 `edge/pyproject.toml`、`deskmate_edge/protocol.py`、`tool_registry.py`、`ws_client.py` 及跨平台工厂 `platform_factory.py`，编写了 `tests/test_edge_core.py` 覆盖协议信封与工具校验。

### A-11 硬件与空调适配层 ✅（已完成，P0，Sprint 1）
- 对接 HA REST API 与通知端点，在 `edge/deskmate_edge/tools/device_tools.py` 中完整封装：
  - `lamp_set`（开关、亮度、2600~5000K 色温保护）；
  - `lamp_effect`（10 秒呼吸律动 L1 疲劳干预）；
  - `plug_set`（插座通断电）；
  - `ac_set`（红外指令控制空调）；
  - `speaker_tts`（≤60 字播报与打断）与 `speaker_exec_directive`。

### A-12 Windows 键鼠统计与在座活动采集（无摄像头方案） ✅（已完成，P0，Sprint 1~2）
- **实现文件**：`edge/deskmate_edge/platform_win/input_monitor.py`
  - 使用 `pynput.keyboard` 与 `pynput.mouse` 在后台线程监听敲击与移动；
  - **隐私底线**：严禁保存任何按键内容字符！仅维护内部自增计数器：`keys_count`、`clicks_count`、`scrolls_count`、`active_seconds`；
  - 每 60 秒汇总打包为标准 `InputMinute` 数据包，用于计算综合活跃率；
  - 使用 Windows API `GetForegroundWindow` / `GetWindowText` 提取前台进程名（如 `Code.exe`、`chrome.exe`）及分类（study/entertainment/other）。

### A-13 Windows 桌面与窗口编排工具集 ✅（已完成，P0，Sprint 2）
- **实现文件**：`edge/deskmate_edge/tools/desktop_tools.py` 与 `platform_win/platform_impl.py`
  - `open_app(name)`：校验白名单启动程序；
  - `open_folder(path, in_vscode=bool)`：支持资源管理器或 `code <path>`；
  - `arrange_windows(layout)`：实现 `code_left_browser_right`（VS Code 左 60% / 浏览器右 40% 分屏）与 `split_half`；
  - `take_screenshot(target)`：`mss` 屏幕截图与桌面最新图片自动缩放到长边 ≤ 1280px 并转 JPEG Base64；
  - `read_clipboard()` / `write_clipboard(text)`：剪贴板交互；
  - `show_win_toast(title, message)`：Windows 原生通知气泡。

### A-14 完整联调与现场演示准备 ⬜（Sprint 3）
- 编写一键启动脚本 `edge/scripts/start_edge.bat`；
- 执行附录 A 的 10 条全链路场景验证，记录平均响应延迟与稳定性报告；
- 准备离线/降级应急预案（如小爱网络波动时，利用本地快捷热键或前端语音输入兜底）。
