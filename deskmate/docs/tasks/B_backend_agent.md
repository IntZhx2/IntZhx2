# 任务卡 B —— 后端平台与多智能体系统（负责人：成员 B）

> **工作目录**：`backend/` 及 `deploy/`  
> **运行环境**：云服务器（基于 Docker 与 Python 3.11）  
> **复用建议**：直接借鉴并改造原有项目 `smart_agent/agent/` 的 ReAct 循环、多轮会话管理、Prompt 与 OpenAI 标准客户端；工具适配层升级为支持多 Agent 分发与 Windows 动态 ToolSpec。  
> **AI 开发规范**：开工前必读 `AGENTS.md`、`docs/CONTRACTS.md`（§1~§7）与 `docs/ARCHITECTURE.md`（§2、§5、§7）。  
> **状态标记**：⬜ 未开始 / 🟡 进行中 / ✅ 完成

---

## 1. 第一次作业阶段（10/26 – 11/08）

### B-00 软件需求规格说明书（SRS）核心章节主笔 ⬜
- 以 `docs/PRD.md`、`docs/ARCHITECTURE.md`、`docs/CONTRACTS.md` 为底座，输出符合国标《计算机软件需求规格说明规范（GB/T 9385）》的正式需求文档草稿；
- 重点绘制导出：
  1. 系统多智能体协同架构图；
  2. 核心状态机与类图（直接用 Mermaid 渲染高精度图表）；
  3. 附录 A 的 10 组端到端验收用例及评价指标。
- 参与答辩 PPT 制作：负责“智能体协同机制”、“系统架构设计”等核心页面的内容整理与图表设计。

---

## 2. 工程实现阶段任务（Sprint 1 ~ Sprint 3）

### B-01 后端工程骨架与基础服务 ⬜（P0，Sprint 1）
- 采用 FastAPI + SQLModel（SQLite/PostgreSQL） + Pydantic v2 构建；
- 启动时自动完成数据库 Schema 迁移，预置 `admin` 用户与 `demo`（演示模式专用）账号；
- 按照 `docs/CONTRACTS.md` §5 完成设备、工作台、用户、日志相关 REST API 的基本 CRUD 路由与 JWT 鉴权保护；
- 编写统一的异步时钟模块 `Clock`，全系统禁用裸 `datetime.now()`，保证单元测试可随意注入时间。

### B-02 WebSocket Hub 与跨端 RPC 通信管道 ⬜（P0，Sprint 1）
- **实现文件**：`backend/app/ws/edge_hub.py` 与 `backend/app/ws/web_hub.py`
  - `/ws/edge`：基于 `EDGE_TOKEN` 鉴权，负责维护 Edge 长连接。支持基于 `asyncio.Future` 的超时 RPC 工具调用（`EdgeHub.call(tool, args, timeout)`）；处理 `edge.hello` 注册工具与初始设备状态；
  - `/ws/web`：基于 JWT 认证，连接即下发 `state.snapshot`，并以 200ms 为单位合并节流广播增量 `state.patch` 与系统通知 `notify`。

### B-03 VirtualEdge 虚拟边缘运行环境 ⬜（P0，Sprint 1，**第一优先级**）
- **目标**：在没有物理硬件和 Windows 设备连接时，100% 模拟真实 Edge 的全部行为，解除前端与后端在开发测试期的硬件依赖；
- **模拟能力**：
  - 自动向 StateStore 注册默认虚拟硬件（台灯、插座、空调、温湿度计、人体传感器）；
  - 支持虚拟执行全部 ToolSpec，例如调用 `lamp_set`、`ac_set` 时实时修改内存中设备状态，调用 `speaker_tts` 时将播报文本通过 WebSocket 转换为前端可感知的 `notify` 消息提示；
  - 响应 `POST /api/demo/inject`：支持动态注入按键活跃频率（`typing_rate`）、人员离座（`leave`）、锁屏（`lock`）、温度跳变及语音模拟输入。

### B-04 工作台配置管理与并行协同执行器（场景 1 核心） ⬜（P0，Sprint 1~2）
- **实现文件**：`backend/app/agent/workspace_exec.py`
  - 管理 `WorkspaceProfile`（支持预设与自定义）；
  - 当收到协调者派发的 `start_work(workspace)` 时，触发确定性并发执行器：
    - **并行环境动作**：通过 EdgeHub 调用 `lamp_set(80%, 4000K)`；若当前环境温度 ≥ 27.5℃ 且设置为 auto，调用 `ac_set(mode="cool", temp=26)`；
    - **并行电脑动作**：调用 EdgeHub 顺序或并发执行 `open_folder`、`open_url`、`open_app`，并在全部启动完成后调用 `arrange_windows("code_left_browser_right")`；
    - **会话与播报生成**：创建 `FocusSession` 记录，汇总各执行分支耗时与状态，生成小爱口语化回应：“工作台已为你配置完毕，台灯切入专注模式，已自动打开作业目录，预计专注 45 分钟，加油！”。

### B-05 多智能体协调者与语音路由系统 ⬜（P0，Sprint 2）
- **实现文件**：`backend/app/agent/orchestrator.py` 与 `backend/app/agent/voice_router.py`
  - **快速路径（Fast Path）**：严格按照 CONTRACTS §7 的正则清单进行前置匹配，命中后在 ≤ 3 秒内直接分发控制指令，完全规避 LLM API 延迟与 Token 开销；
  - **协调者 Agent（Orchestrator）**：使用主大模型（Function Calling），负责多轮上下文维护、复杂任务分解，并向环境 Agent、电脑 Agent 分派任务；
  - **电脑 Agent（PC Copilot）**：负责场景 2 的开放式电脑操作与图文分析（Dijkstra 时间复杂度搜索、报错截图多模态分析、写代码至剪贴板等）；
  - **超时优雅兜底**：若大模型推理耗时预判超过 2 秒，系统先通过 `speaker_tts` 播报“好的，正在为你处理，稍等片刻”，避免小爱长时间静音导致用户重复发问。

### B-06 在座规则引擎与离座级联响应 ⬜（P0，Sprint 2）
- 依据人体传感器移动时间戳、Windows 键鼠最近活跃时间与系统锁屏状态，实时计算 `PresenceState`；
- **离座阶梯控制**：
  - 离开工位（锁屏或无活动持续 ≥ 3 分钟）→ 自动暂停当前专注计时，台灯切换至微弱暖光（10%, 2500K）伴眠模式；
  - 持续离开 ≥ 15 分钟 → 自动关断台灯与外设插座；
  - 持续离开 ≥ 30 分钟 → 自动执行 `ac_set(on=false)` 关闭空调；
  - 人员返回工位 → 唤醒台灯恢复原有专注亮度色温，小爱语音播报“欢迎回来，番茄钟继续，还剩 X 分钟”。

### B-07 云端容器化部署与公网交付 ⬜（P0，Sprint 2~3）
- 编写 `deploy/docker-compose.yml`，打通云服务器 Nginx 反向代理、HTTPS 证书配置及 FastAPI 容器；
- 确保公网访问演示环境顺畅无阻，满足课程“上线运行供老师助教检查”的硬性考核指标。
