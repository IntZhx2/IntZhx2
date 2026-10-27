# 任务卡 A —— 硬件与 Windows 边缘端（负责人：赵海翔 / 成员 A）

> **工作目录**：`edge/` 及 `docs/hardware/`  
> **运行环境**：个人 Windows 10/11 笔记本电脑（与米家智能设备处于同一局域网 Wi-Fi）  
> **AI 开发规范**：开工前必须完整阅读 `AGENTS.md`、`docs/CONTRACTS.md`（特别是 §1~§3 与 §7），以及 `docs/PRD.md` 中的场景 1、2、3。  
> **状态标记**：⬜ 未开始 / 🟡 进行中 / ✅ 完成

---

## 0. 演示与开发硬件清单（全在成员 A 手中）

| 逻辑设备 | 真实硬件型号 | 接入通道 | 在 DeskMate 中的核心作用 |
|---|---|---|---|
| `lamp` | 米家台灯 1S | Wi-Fi（米家/HA） | 专注冷白光（4000K/80%）、伴眠暖光（2500K/10%）、10秒呼吸律动（L1 疲劳干预） |
| `ac` | 宿舍/书房空调 | **红外遥控（经由小爱音箱 IR）** | 智能降温（制冷 26℃）、自动温控联动、支持语音调温 |
| `plug` | 米家智能插座 3 | Wi-Fi（米家/HA） | 工位外设供电联动（可外接桌面小风扇/显示器挂灯），人离座节能关断 |
| `motion` | 小米人体传感器 2 | BLE 蓝牙（经小爱网关上云） | 监测工位是否有人移动、环境环境光照强弱（配合防误判在座融合算法） |
| `climate` | 米家智能温湿度计 3 | BLE 蓝牙（经小爱网关上云） | 实时回传工位温度与湿度，驱动闷热疲劳加权与空调开启判定 |
| `speaker` | 小爱音箱 Play 增强版（L05C） | Wi-Fi / 红外 / 蓝牙 Mesh 网关 | 语音输入监听桥、TTS 关键语音播报、执行红外控制空调指令、充当低功耗蓝牙网关 |
| `pc` | Windows 笔记本 | 本地系统内核 | 窗口编排（VS Code/浏览器分屏）、键鼠活动率统计（无摄像头疲劳特征）、截图与代码剪贴板 |

---

## 1. 第一次作业阶段（10/26 – 11/08）：技术可行性探针（Spike）

**目标**：打通关键硬件调用链路，产出一段 30~60 秒的 Windows 真机实操演示录像（答辩核心亮点，击碎“画大饼”质疑）。

### A-01 Windows 环境 Home Assistant 部署与米家设备接入 ⬜（预计 2.5h）
- **操作步骤**：
  1. Windows 安装 Docker Desktop（启用 WSL2 后端）；
  2. 启动容器：`docker run -d --name homeassistant --restart unless-stopped -p 8123:8123 -v C:\ha_config:/config -e TZ=Asia/Shanghai ghcr.io/home-assistant/home-assistant:stable`；
  3. 配置 `ha_xiaomi_home` 小米官方集成，扫码/账号登录绑定“学校”或“家”中的 5 款硬件设备；
  4. 生成长期访问令牌（Long-Lived Access Token），写入 `edge/.env` 中的 `HA_TOKEN`。
- **交付产物**：`docs/hardware/entities.md`（详细记录台灯、温湿度计、传感器、插座在 HA 中的 `entity_id`、属性名称及调用参数示例）。
- **验收标准**：
  - [ ] 终端使用 PowerShell/curl 能直接请求 HA REST API 调整台灯亮度与色温；
  - [ ] 走到人体传感器前，HA 界面或日志中 `motion` 状态在 10 秒内产生变化。

### A-02 小爱音箱语音对话桥与红外控制空调验证 ⬜（预计 3h，**高优先级**）
- **参考工具**：基于 `MiService` / `xiaogpt` 开源核心逻辑；
- **探针脚本编写**：`edge/spikes/voice_ir_spike.py`
  1. 使用小米账号鉴权并获取小爱音箱 Play 增强版（L05C）的 `deviceId`；
  2. 轮询对话历史接口（`userprofile.mina.mi.com/device_profile/v2/conversation`），验证能否在 1~2 秒内抓取到对小爱说出的“我要写作业了”、“空调调到26度”；
  3. 拦截测试：检测到关键词后立即触发 `player_pause`，并让小爱执行自定义 TTS 播报；
  4. 红外遥控测试：调用小爱“执行文本指令”接口（`text_to_speech` 或静默 directive），模拟下发“把空调调到26度”，观察实体空调是否有滴答响应。
- **验收标准**：
  - [ ] 语音输入抓取延迟稳定在 ≤ 2 秒内；
  - [ ] 成功使用代码触发空调红外开关与调温（录像记录备用）；
  - [ ] 记录账号防风控注意事项（若遇风控提取 `passToken` 备用）。

### A-03 答辩真机演示视频录制 ⬜（预计 1.5h）
- 串联软硬件闭环动作：对小爱说“小爱，我要开始写软工大作业了，帮我准备一下” → 台灯调至冷白专注光 → Windows 屏幕自动弹出 VS Code 与作业目录 → 小爱语音播报确认。录制 30~60 秒高清视频交给组员 C 插入答辩 PPT。

---

## 2. 工程实现阶段任务（Sprint 1 ~ Sprint 3）

### A-10 Edge 工程骨架与跨平台通信管道 ⬜（P0，Sprint 1）
- **目录结构**：
  ```
  edge/
    pyproject.toml            # 依赖：websockets, httpx, pydantic, pywin32, psutil, pynput, mss, Pillow, pyperclip, pycaw, miservice
    .env.example
    deskmate_edge/
      __main__.py             # 启动入口：python -m deskmate_edge [--mock]
      config.py               # 加载 .env 与 devices.yaml
      ws_client.py            # 连接云端 /ws/edge、握手 edge.hello、自动心跳与指数退避重连
      tool_registry.py        # 工具注册中心、自动生成 ToolSpec、入参 Pydantic 校验、超时防护
      platform_win/           # Windows 原生实现（win32gui, pynput, mss 等）
      platform_mock/          # 虚拟降级实现（使非 Windows 环境也能通过全量测试）
  ```
- **核心逻辑**：启动时调用 `ctypes.windll.shcore.SetProcessDpiAwareness(2)` 解决 Windows 高分屏缩放坐标偏移；向后端发送 `edge.hello` 注册所有 ToolSpec。

### A-11 硬件与空调适配层 ⬜（P0，Sprint 1）
- 对接 HA WebSocket / REST，实现 `lamp_set`、`lamp_effect`（呼吸律动）、`plug_set`；
- 对接 MiService 红外指令通道，封装 `ac_set` 工具：下发红外指令控制空调开关、模式、风速与目标温度；
- 监听 HA 的温湿度与人体传感器事件，转换为标准 `device.state` 推送给后端。

### A-12 Windows 键鼠统计与在座活动采集（无摄像头方案） ⬜（P0，Sprint 1~2）
- **实现文件**：`edge/deskmate_edge/platform_win/input_monitor.py`
  - 使用 `pynput.keyboard` 与 `pynput.mouse` 在后台线程监听敲击与移动；
  - **隐私底线**：严禁保存任何按键内容字符！仅维护内部自增计数器：`keys_count`、`clicks_count`、`scrolls_count`、`active_seconds`；
  - 每 60 秒汇总打包为标准 `InputMinute` 数据包，通过 WebSocket 发送 `pc.input_stats`；
  - 使用 Windows API `GetForegroundWindow` / `GetWindowText` 提取前台进程名（如 `Code.exe`、`chrome.exe`）及分类（study/entertainment/other）；
  - 监听 Windows 锁屏/解锁会话事件（`WM_WTSSESSION_CHANGE`），立即发送 `pc.session{locked: true/false}`。

### A-13 Windows 桌面与窗口编排工具集 ⬜（P0，Sprint 2）
- **实现文件**：`edge/deskmate_edge/platform_win/desktop_tools.py`
  - `open_app(name)`：校验白名单，使用 `subprocess.Popen` 或 `os.startfile` 启动；
  - `open_folder(path, in_vscode=bool)`：支持资源管理器打开，或直接执行 `code <path>`；
  - `arrange_windows(layout)`：
    - `code_left_browser_right` 模式：遍历可见窗口句柄，匹配 VS Code 窗口调整至屏幕左侧 60% 物理区域，匹配 Chrome/Edge 浏览器调整至右侧 40% 区域，自动居前呈现；
  - `take_screenshot(target)`：
    - `target="screen"`：使用 `mss` 抓取主屏幕，Pillow 等比缩放到长边 ≤ 1280px，返回 JPEG base64；
    - `target="latest_desktop_file"`：检索桌面（`Desktop` 目录）最新 10 分钟内创建的图片文件；
  - `read_clipboard()` / `write_clipboard(text)`：使用 `pyperclip` 或 win32clipboard 进行交互；
  - `show_win_toast(title, message)`：在 Windows 系统右下角弹出原生通知（如“参考代码已自动复制到剪贴板”）。

### A-14 完整联调与现场演示准备 ⬜（Sprint 3）
- 编写一键启动脚本 `edge/scripts/start_edge.bat`；
- 执行附录 A 的 10 条全链路场景验证，记录平均响应延迟与稳定性报告；
- 准备离线/降级应急预案（如小爱网络波动时，利用本地快捷热键或前端语音输入兜底）。
