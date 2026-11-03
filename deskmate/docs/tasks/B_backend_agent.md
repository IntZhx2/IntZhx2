# 任务卡 B —— 后端平台与多智能体系统（负责人：成员 B）

> **工作目录**：`backend/` 及 `deploy/`  
> **运行环境**：云服务器（基于 Docker 与 Python 3.11）  
> **复用建议**：直接借鉴并改造原有项目 `smart_agent/agent/` 的 ReAct 循环、多轮会话管理、Prompt 与 OpenAI 标准客户端；工具适配层升级为支持多 Agent 分发与 Windows 动态 ToolSpec。  
> **AI 开发规范**：开工前必读 `AGENTS.md`、`docs/CONTRACTS.md`（§1~§7）与 `docs/ARCHITECTURE.md`（§2、§5、§7）。  
> **状态标记**：⬜ 未开始 / 🟡 进行中 / ✅ 完成

---

## 1. 第一次作业阶段（10/26 – 11/08）

### B-00 软件需求规格说明书（SRS）核心章节主笔 ✅
- 以 `docs/PRD.md`、`docs/ARCHITECTURE.md`、`docs/CONTRACTS.md` 为底座，输出符合国标《计算机软件需求规格说明规范（GB/T 9385）》的正式需求文档草稿；
- 重点绘制导出：
  1. 系统多智能体协同架构图；
  2. 核心状态机与类图（直接用 Mermaid 渲染高精度图表）；
  3. 附录 A 的 10 组端到端验收用例及评价指标。
- 参与答辩 PPT 制作：负责“智能体协同机制”、“系统架构设计”等核心页面的内容整理与图表设计。

**实际实现说明（2026-11-02）**
- `docs/assignment_b/SRS.md`、`SRS.html`、`DeskMate_SRS_B.pdf` 提供正式结构的需求评审草稿，PDF 17 页。
- `docs/assignment_b/figures/` 提供六张 Mermaid 源图、SVG 与高清 PNG，含架构、协同、两张状态机、类图和时序。
- SRS 附录 A 保留十组端到端用例、测量起止点、评价指标和待验状态，未虚构问卷或现场结果。
- `DEFENSE_TECH_PAGES.md` 提供 B 的两页正文讲稿及备查素材，交由 C 合入整套 PPT，未代做 C 的排版和调研。

---

## 2. 工程实现阶段任务（Sprint 1 ~ Sprint 3）

### B-01 后端工程骨架与基础服务 ✅（P0，Sprint 1）
- 采用 FastAPI + SQLModel（SQLite/PostgreSQL） + Pydantic v2 构建；
- 启动时自动完成数据库 Schema 迁移，预置 `admin` 用户与 `demo`（演示模式专用）账号；
- 按照 `docs/CONTRACTS.md` §5 完成设备、工作台、用户、日志相关 REST API 的基本 CRUD 路由与 JWT 鉴权保护；
- 编写统一的异步时钟模块 `Clock`，全系统禁用裸 `datetime.now()`，保证单元测试可随意注入时间。

**实际实现说明（2026-11-02）**
- `backend/app/main.py`、`config.py`、`db.py` 和 `schemas/contracts.py` 实现 FastAPI、SQLModel、Pydantic v2 与 v1 初始迁移。
- 自动幂等预置 admin/demo，密码只从环境读取并保存盐化哈希；REST 以 JWT 保护，工作台、设置、日志及会话按用户隔离。
- `backend/app/clock.py` 统一 UTC 时钟；`engine/focus.py` 持久化计时、暂停和顺延记录，整数微秒累计并支持跨本地午夜清零。
- `tests/test_api.py` 验证 CRUD、迁移重入、鉴权过期、配置即时生效和重启恢复；PostgreSQL 连接适配保留但未做外部集成实测。

### B-02 WebSocket Hub 与跨端 RPC 通信管道 ✅（P0，Sprint 1）
- **实现文件**：`backend/app/ws/edge_hub.py` 与 `backend/app/ws/web_hub.py`
  - `/ws/edge`：基于 `EDGE_TOKEN` 鉴权，负责维护 Edge 长连接。支持基于 `asyncio.Future` 的超时 RPC 工具调用（`EdgeHub.call(tool, args, timeout)`）；处理 `edge.hello` 注册工具与初始设备状态；
  - `/ws/web`：基于 JWT 认证，连接即下发 `state.snapshot`，并以 200ms 为单位合并节流广播增量 `state.patch` 与系统通知 `notify`。

**实际实现说明（2026-11-02）**
- `backend/app/ws/edge_hub.py` 维护单现场连接、动态 ToolSpec、Future 关联、工具默认超时及断线清理，执行中不重放。
- `web_hub.py` 提供首次快照、200ms 合并增量和有界发送队列；`envelope.py` 保持契约 v2。
- `main.py` 实现 Token/JWT、20s 心跳与 60s 无通信超时，并让接收循环持续读取反向 RPC 结果。
- `tests/test_websocket.py` 验证关联 ID、超时、断线、未知消息、真实 Edge 在线时 demo 隔离及 Python 3.11 关闭清理。

### B-03 VirtualEdge 虚拟边缘运行环境 ✅（P0，Sprint 1，**第一优先级**）
- **目标**：在没有物理硬件和 Windows 设备连接时，100% 模拟真实 Edge 的全部行为，解除前端与后端在开发测试期的硬件依赖；
- **模拟能力**：
  - 自动向 StateStore 注册默认虚拟硬件（台灯、插座、空调、温湿度计、人体传感器）；
  - 支持虚拟执行全部 ToolSpec，例如调用 `lamp_set`、`ac_set` 时实时修改内存中设备状态，调用 `speaker_tts` 时将播报文本通过 WebSocket 转换为前端可感知的 `notify` 消息提示；
  - 响应 `POST /api/demo/inject`：支持动态注入按键活跃频率（`typing_rate`）、人员离座（`leave`）、锁屏（`lock`）、温度跳变及语音模拟输入。

**实际实现说明（2026-11-02）**
- `backend/app/sim/virtual_edge.py` 注册六种逻辑设备，覆盖全部 21 个契约工具，灯光和空调修改实时状态、TTS 转为 notify。
- 电脑窗口、剪贴板、笔记均只在内存模拟，截图是明确标识的协议占位图，不冒充真机报错。
- `runtime.py` 实现 motion/leave/lock/temperature/typing_rate/voice 注入及分钟活动序列，demo 与 admin 运行环境独立。
- `tests/test_runtime.py` 参数化覆盖全部工具和注入范围，`test_websocket.py` 验证真实连接在线时演示控制不外泄。

### B-04 工作台配置管理与并行协同执行器（场景 1 核心） ✅（P0，Sprint 1~2）
- **实现文件**：`backend/app/agent/workspace_exec.py`
  - 管理 `WorkspaceProfile`（支持预设与自定义）；
  - 当收到协调者派发的 `start_work(workspace)` 时，触发确定性并发执行器：
    - **并行环境动作**：通过 EdgeHub 调用 `lamp_set(80%, 4000K)`；若当前环境温度 ≥ 27.5℃ 且设置为 auto，调用 `ac_set(mode="cool", temp=26)`；
    - **并行电脑动作**：调用 EdgeHub 顺序或并发执行 `open_folder`、`open_url`、`open_app`，并在全部启动完成后调用 `arrange_windows("code_left_browser_right")`；
    - **会话与播报生成**：创建 `FocusSession` 记录，汇总各执行分支耗时与状态，生成小爱口语化回应：“工作台已为你配置完毕，台灯切入专注模式，已自动打开作业目录，预计专注 45 分钟，加油！”。

**实际实现说明（2026-11-02）**
- `backend/app/agent/workspace_exec.py` 并行执行环境与电脑分支，启动项完成后才编排窗口，逐项记录成功、失败和耗时。
- 使用契约 27.5℃ 自动空调阈值，支持 auto/ask/off；灯光、时长和启动项来自工作台配置。
- 创建 FocusSession 并汇总真实分支状态，部分失败不阻塞其他操作；在离座状态启动时仍暂停计时并保持伴眠灯光。
- `tests/test_runtime.py` 验证实际并发、阈值边界和单项失败；`test_agents.py` 验证未知目录搜索后三十秒确认。

### B-05 多智能体协调者与语音路由系统 ✅（P0，Sprint 2）
- **实现文件**：`backend/app/agent/orchestrator.py` 与 `backend/app/agent/voice_router.py`
  - **快速路径（Fast Path）**：严格按照 CONTRACTS §7 的正则清单进行前置匹配，命中后在 ≤ 3 秒内直接分发控制指令，完全规避 LLM API 延迟与 Token 开销；
  - **协调者 Agent（Orchestrator）**：使用主大模型（Function Calling），负责多轮上下文维护、复杂任务分解，并向环境 Agent、电脑 Agent 分派任务；
  - **电脑 Agent（PC Copilot）**：负责场景 2 的开放式电脑操作与图文分析（Dijkstra 时间复杂度搜索、报错截图多模态分析、写代码至剪贴板等）；
  - **超时优雅兜底**：若大模型推理耗时预判超过 2 秒，系统先通过 `speaker_tts` 播报“好的，正在为你处理，稍等片刻”，避免小爱长时间静音导致用户重复发问。

**实际实现说明（2026-11-02）**
- `voice_router.py` 严格匹配 §7 的十一条正则，快速控制不调用模型，长工作台任务后台执行；确认窗口优先处理。
- `orchestrator.py`、`llm.py` 实现用户级多轮上下文、流式 Function Calling、环境/电脑委派及每次最多六步工具调用和六轮规划。
- `services.py` 支持 Bocha/提供商内建搜索与内存多模态通道，结果推 assist.result，代码可写剪贴板；工具白名单和参数双重校验。
- 两秒确认播报、总超时、忙碌保护及 VoiceLog 已实现；`tests/test_agents.py` 使用受控模型验证，真实 LLM/搜索延迟需配置密钥后联验。

### B-06 在座规则引擎与离座级联响应 ✅（P0，Sprint 2）
- 依据人体传感器移动时间戳、Windows 键鼠最近活跃时间与系统锁屏状态，实时计算 `PresenceState`；
- **离座阶梯控制**：
  - 离开工位（锁屏或无活动持续 ≥ 3 分钟）→ 自动暂停当前专注计时，台灯切换至微弱暖光（10%, 2500K）伴眠模式；
  - 持续离开 ≥ 15 分钟 → 自动关断台灯与外设插座；
  - 持续离开 ≥ 30 分钟 → 自动执行 `ac_set(on=false)` 关闭空调；
  - 人员返回工位 → 唤醒台灯恢复原有专注亮度色温，小爱语音播报“欢迎回来，番茄钟继续，还剩 X 分钟”。

**实际实现说明（2026-11-02）**
- `backend/app/engine/presence.py` 融合移动、键鼠空闲与锁屏；锁屏立即离座，静默信号达到设置阈值后确认。
- 暂停会话、10%/2500K 伴眠、十五分钟关灯插座、三十分钟关空调及回座恢复均使用配置和注入 Clock。
- 设备动作失败不标记完成，之后调度重试；滚动阅读视为活动，回座恢复原阶段剩余秒数而不计入离座时间。
- `tests/test_runtime.py` 和 `test_api.py` 验证级联、临界值、失败重试和恢复；只接线 C 的接口，不实现疲劳打分或报告。

### B-07 云端容器化部署与公网交付 ✅（本轮按用户要求完成 localhost 验收，公网暂缓）
- 编写 `deploy/docker-compose.yml`，打通云服务器 Nginx 反向代理、HTTPS 证书配置及 FastAPI 容器；
- 确保公网访问演示环境顺畅无阻，满足课程“上线运行供老师助教检查”的硬性考核指标。

**实际实现说明（2026-11-02）**
- 用户本轮明确“先不做公网交互，localhost 先验证访问就好”，因此公网、域名和证书签发均不执行。
- `backend/Dockerfile`、哈希锁定 `requirements.txt`、`deploy/docker-compose.yml` 提供非 root Python 3.11、SQLite 命名卷和健康检查。
- `deploy/nginx/` 提供 SSE/WS 反代及 HTTPS 覆盖模板，`backend/scripts/smoke_local.py` 已通过直接 localhost HTTP/WS/SSE。
- 容器构建、健康检查、非 root 身份、Nginx 配置及 8080 端口 HTTP/WS/SSE 冒烟均通过，记录见 `docs/assignment_b/VALIDATION.md`；不将本机验证写成公网已上线。

---

## 三 五分钟内手动复现

前提为 Python 3.11 与依赖已准备好，初次下载依赖不计入操作时间。

1. 在 backend 中运行 `python scripts/init_env.py`（仅首次），再运行 `.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log`。
2. 浏览器访问 `http://127.0.0.1:8000/docs`，另开终端执行 `.venv/bin/python scripts/smoke_local.py`，一并验证 B-01/02/03/04/06 和快速语音。
3. B-05 复杂链路执行 `.venv/bin/pytest -q tests/test_agents.py`；真实服务需先在本地 .env 配置模型与搜索密钥，不打印密钥。
4. B-00 打开 `docs/assignment_b/DeskMate_SRS_B.pdf`，检查图 1～6、附录 A 十组用例，并阅读技术页讲稿。
5. B-07 在 deploy 运行 `docker compose up -d --build`，准备好镜像后以 `smoke_local.py --base-url http://127.0.0.1:8080` 复现；完整命令见 deploy/README.md。

## 四 跨组请求与契约待确认

- 给 A：提供 Windows 真机的 DPI/窗口矩形、语音桥、红外静默和六类设备验收证据，按 v2 edge.hello 与工具结果对接；B 未修改 edge/。
- 给 C：通过 `create_app(wellbeing_factory=..., wellbeing_router=...)` 按用户接入 §8 接口和报告路由；确认疲劳状态发布、C 自有数据写入和闷热追问参数。B 只完成平台接线，不实现 C 算法与页面。
- 给 C：整套 PPT 可取 `assignment_b/DEFENSE_TECH_PAGES.md` 的两页技术正文、讲稿和六张矢量图，C 的问卷、品牌、UI 原型及博客仍由 C 负责。
- 共同契约未修改，版本维持 2。空调采用 27.5℃、伴眠采用 2500K；现有正则不覆盖部分口语和带空格温度。用户 CRUD 与离座六十分钟结束未定义在现行契约，不另造接口或阈值。
- 除已在任务卡提及的框架外，新增轻量 PyJWT、jsonschema、AnyIO 分别承担 JWT、动态 Schema 校验与取消清理；Mermaid CLI 只用于文档导出，不进入后端运行镜像。
