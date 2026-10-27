# AGENTS.md —— 给 AI 编码助手的项目说明（每次开工前必读）

> 你（AI）正在参与 **DeskMate 桌伴** 团队项目的开发。本文件是你的入口。
> 动手写任何代码前，按顺序阅读：
> 1. 本文件
> 2. `docs/PRD.md`（要做什么、三大场景、验收标准）
> 3. `docs/ARCHITECTURE.md`（系统分层、多智能体设计、数据模型）
> 4. `docs/CONTRACTS.md`（**唯一的接口真相源**：WebSocket 消息、REST API、工具清单、内部模块接口、默认配置）
> 5. 你被分配的任务卡：`docs/tasks/A_edge_hardware.md` / `B_backend_agent.md` / `C_frontend_wellbeing.md`

---

## 1. 项目一句话

桌面版"贾维斯"：一个**能理解复杂意图、会规划、能操作 Windows 电脑并联动米家设备**的桌面智能体（Desktop OS Copilot）。
用户坐下说一句话，台灯、电脑窗口、番茄钟一起进入工作状态；写作业时隔空声控电脑查资料、分析报错截图；
系统融合在座时长、键鼠节奏、温湿度判断疲劳，用"呼吸灯 → 语音关心"渐进干预，离座自动暂停并切换伴眠暖光。

**明确不做**：不使用摄像头；不记录键盘输入内容（只统计次数）。

## 2. 子工程与所有权（严禁越界修改）

| 目录 | 负责人 | 运行位置 | 技术栈 |
|---|---|---|---|
| `edge/` | 成员 A（硬件负责人） | 演示用 **Windows 10/11 笔记本**（与米家设备同一 Wi-Fi） | Python 3.11、websockets、httpx、pywin32、psutil、pynput、mss、Pillow、pyperclip、pycaw、MiService；Home Assistant（Docker Desktop/WSL2） |
| `backend/`（除 `app/wellbeing/`） | 成员 B（平台/智能体） | 云服务器（Docker） | Python 3.11、FastAPI、SQLModel + SQLite、OpenAI 兼容 LLM 接口 |
| `backend/app/wellbeing/` | 成员 C | 随后端运行 | Python 3.11（疲劳融合、心流保护、学习报告） |
| `frontend/` | 成员 C | 浏览器（Nginx 静态部署） | Vue 3 + Vite + TypeScript + Pinia + Element Plus + ECharts |
| `deploy/` | 成员 B | 云服务器 | docker compose、Nginx、HTTPS |
| `docs/` | 全员 | — | Markdown |

规则：
- 只修改当前任务卡所属目录。需要别人配合时，在**自己任务卡末尾"跨组请求"**写需求，不直接改对方代码。
- `docs/CONTRACTS.md` 是共同契约。修改必须：①更新 CONTRACTS.md 并把 `契约版本` +1；②在其末尾变更日志写清改动；③提交信息以 `contract:` 开头。
- 子工程之间只通过 CONTRACTS.md 定义的 WebSocket / REST / 内部 Python 接口（§8）交互。

## 3. 关键约定

1. **没有硬件也能开发**：后端内置 `VirtualEdge`（任务 B-03），在 `DEMO_MODE=true` 或真实 edge 未连接时模拟全部设备、键鼠节奏与语音事件。B、C 开发一律对接 VirtualEdge。
2. **设备只用逻辑名**：`lamp`、`plug`、`motion`、`climate`、`speaker`。HA 真实 entity_id 只出现在 `edge/config/devices.yaml`。
3. **时间**：带时区 ISO 8601（`2026-11-20T21:30:00+08:00`），后端存 UTC；所有引擎通过注入的 `Clock` 取时间，便于测试。
4. **阈值**全部放 settings（默认值见 CONTRACTS §6），禁止写死。
5. **密钥**只从环境变量读取，只提交 `.env.example`。
6. **小爱播报文本 ≤ 60 个汉字**、口语化、无 Markdown；详细内容推网页（`assist.result`），代码类结果写入剪贴板。
7. **Windows 路径**一律用 `pathlib`，支持中文路径；edge 进程启动时设置 DPI 感知（`SetProcessDpiAwareness(2)`），窗口坐标按物理像素计算。

## 4. 编码规范

- Python：必须类型标注；`ruff` 格式化；异步优先；`logging` 记日志（logger 名 = 模块路径）；每个模块顶部中文 docstring 说明职责。
- 调用 Windows 专用库（pywin32、pynput、pycaw）的代码集中在 `edge/deskmate_edge/platform_win/`，并提供同接口的 `platform_mock/` 实现，使 edge 单测可在 macOS/Linux CI 上运行。
- TypeScript：`strict: true`；`<script setup lang="ts">`；契约类型集中在 `frontend/src/types/contracts.ts`，字段名与 CONTRACTS.md 完全一致（snake_case）。
- 测试：`pytest` + `pytest-asyncio`；前端 `vitest`。任务卡的每条验收标准至少对应一个自动化测试或一段写在 PR 描述里的可复现手动步骤。
- 提交信息：`feat(edge): ...` / `fix(backend): ...` / `docs: ...` / `contract: ...`。
- 不引入任务卡未提及的大型依赖；确需引入时在任务卡备注说明。

## 5. 环境变量（`.env.example` 中必须列全）

```
# backend
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1   # 任意 OpenAI 兼容接口
LLM_API_KEY=
LLM_MODEL=qwen-plus            # 协调者/电脑 Agent（需支持 function calling）
LLM_FAST_MODEL=qwen-turbo      # 意图解析、关心话术、短回复
LLM_VL_MODEL=qwen-vl-plus      # 截图/屏幕分析
SEARCH_PROVIDER=llm_builtin    # llm_builtin（如 DashScope enable_search）| bocha
BOCHA_API_KEY=
EDGE_TOKEN=change-me
JWT_SECRET=change-me
DEMO_MODE=false
DATABASE_URL=sqlite:///./data/deskmate.db
TZ=Asia/Shanghai

# edge (Windows)
BACKEND_WS_URL=wss://<你的域名>/ws/edge
EDGE_TOKEN=change-me
HA_URL=http://127.0.0.1:8123
HA_TOKEN=
MI_USER=
MI_PASS=
MI_PASS_TOKEN=                 # 账号密码登录被风控时使用
SPEAKER_HARDWARE=L05C          # 小爱音箱 Play 增强版
```

## 6. 完成一个任务必须交付

1. 代码 + 测试；
2. 任务卡中该任务状态改为 `✅`，填写"实际实现说明"（3~5 行，含关键文件路径）；
3. 若改了契约，按 §2 流程更新；
4. 写出 5 分钟内可复现的手动验证步骤。

## 7. 禁止事项

- 不实现任务卡之外的"顺手功能"。
- 不给 LLM 暴露：任意 shell 执行、删除/移动文件、发送消息给第三方、修改系统设置的工具。
- 不记录、不上传键盘按键内容；键鼠监听只累加计数。
- 截图只在内存中转发给多模态模型，后端不落盘。
- 业务代码不直接调用 Home Assistant 或 MiService —— 只能在 `edge/` 适配层调用。
