# DeskMate 后端平台

B-00～B-07 的实现与验收入口。前端和 `app/wellbeing/` 属于成员 C，本目录没有实现 C 的页面、疲劳评分或学习报告。默认界面是 FastAPI 的接口文档，不能当成产品控制台。

## 五分钟本地验证

在 `deskmate/backend` 执行，使用 Python 3.11。首次下载依赖的时间取决于网络。

当前工作区已将 Python 3.11 安装到被 Git 和 Docker 忽略的 `.runtime/`，虚拟环境直接引用该目录，重启后不依赖 `/tmp`。若需按同样方式重建，可先执行 `UV_PYTHON_INSTALL_DIR="$PWD/.runtime" uv python install 3.11`，再执行 `uv venv --clear --python .runtime/cpython-3.11-macos-aarch64-none/bin/python3.11`。该路径适用于当前 macOS arm64；其他平台使用下面的通用安装命令。

```bash
uv venv --python 3.11
uv pip install -r requirements.txt -e '.[dev]'
.venv/bin/python scripts/init_env.py
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

`init_env.py` 只在 `.env` 不存在时执行；已有文件会拒绝覆盖。它生成随机密钥和 admin/demo 密码，文件权限 0600、被 Git 忽略。预置账号的密码只在数据库第一次初始化时读取，修改 `.env` 不会偷偷覆盖已有密码；需要重建演示数据库时先备份并明确删除本地演示数据。不要把 `.env` 发到聊天、截图或提交。

浏览器访问 <http://127.0.0.1:8000/docs>，健康检查为 <http://127.0.0.1:8000/api/health>。另开终端在同一目录执行：

```bash
.venv/bin/python scripts/smoke_local.py
```

脚本从本地 `.env` 读取 demo 密码，不打印凭据。它通过实际端口验证登录、WS 首次快照及增量、专注暂停恢复、SSE 快速控制、演示模式、API 文档和 C 未接入的 503 响应。脚本会创建一条一分钟演示会话并在完成时停止，不控制任何真实设备。

使用 API 文档时先调用 login，以本地 `.env` 中的 demo 密码登录，然后在 Authorize 中填入返回的 JWT。先 `POST /api/focus/start {"minutes":1}`，再调用 demo/inject 的 lock、temperature、typing_rate、voice。模型密钥为空时，简单快速口令可用，复杂任务明确返回未配置模型。

## 验证命令

```bash
.venv/bin/ruff check app tests scripts
.venv/bin/ruff format --check app tests scripts
.venv/bin/pytest -q --cov=app --cov-report=term-missing --cov-fail-under=70
```

测试使用临时 SQLite、手动时钟及受控模型，禁止外网模型请求。Python 3.11 的结果和 localhost 证据见 [VALIDATION.md](../docs/assignment_b/VALIDATION.md)。首次生成的数据目录和覆盖率文件均不提交。

## 模块关系

| 入口 | 职责 |
| --- | --- |
| `app/main.py` | 生命周期、JWT REST、SSE、双端 WS、请求上限 |
| `app/config.py` `clock.py` `db.py` | 环境配置、统一时钟、版本迁移与持久化 |
| `app/ws/` | 信封、Future RPC、心跳与 200ms Web 增量 |
| `app/sim/virtual_edge.py` | 全部 21 个工具的内存模拟 |
| `app/engine/` | 状态、专注计时、在座和离座阶梯 |
| `app/agent/` | 快速路径、协调者、子 Agent、工作台、搜索与视觉服务 |
| `app/integrations.py` | C 的内部接口类型，无评分算法 |

## 模型和搜索配置

在 `.env` 填写 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL`、`LLM_FAST_MODEL`、`LLM_VL_MODEL`。主模型需支持 OpenAI 兼容的流式 Function Calling，视觉模型需接受 image_url。所有 HTTP 请求均有超时，超过两秒先播报处理中，电脑工具调用和规划轮次各最多六步。

`SEARCH_PROVIDER=llm_builtin` 会发送 `enable_search=true`，需要提供商支持该扩展；OpenAI 兼容并不意味着一定支持内建联网。选 `bocha` 时必须填写 BOCHA_API_KEY。未配置或不支持时返回真实错误，不将模型记忆当作搜索证据。

截图从 Edge 内存转送多模态模型，不落盘、不写入工具日志或会话历史。VirtualEdge 返回协议占位图并明确无法分析真实桌面。虚拟剪贴板、笔记和窗口不操作本机，重启后丢失，这是有意的模拟边界。

## A 的联调入口

本地联调设置 `DEMO_MODE=false`，A 使用相同 EDGE_TOKEN 连接 `/ws/edge`，发送契约 v2 的 edge.hello。只接受已定义工具，按平台允许范围和注册 JSON Schema 双重校验，接入后同步白名单与语音接管前缀。demo 账号仍固定使用隔离的 VirtualEdge。

若真实 Edge 离线，admin 会显示 demo_mode=true 并使用模拟器；已发出的 RPC 断线时失败，不自动重放。离线回退会重置模拟设备，不代表真实灯光或空调的状态。真实 Windows、DPI、小米云和语音时延需要 A/B 联验。当前没有替 A 修改任何文件。

## C 的接入入口

使用 `create_app(wellbeing_factory=..., wellbeing_router=...)`。factory 接收 user_id，返回实现 CONTRACTS §8 的实例，避免不同用户共享算法状态。B 在分钟统计、到点、离座和摘要请求处调用四个接口，并执行返回动作。C 的 router 可替换预留的 `/api/reports/*` 与 `/api/timeline`。

当前未接入 C，报告路由返回 503，fatigue 的默认零值仅为契约占位，不表示已经检测健康。疲劳快照发布、C 自有表落库和闷热确认的参数细节仍需双方按任务卡末尾跨组请求联调。B 不创建或修改 `app/wellbeing/`。

## 数据库与部署

v1 迁移创建 SchemaVersion、User、UserSettings、WorkspaceProfile、FocusSession、FocusCheckpoint 和 VoiceLog。重复启动不覆盖用户数据，遇到更高版本拒绝启动。以后增加列必须写显式迁移，不能只调用 create_all。服务关闭及异常重启后，会话保守恢复为 paused，避免把停机时间计作有效专注。

SQLite 默认使用 `./data/deskmate.db`。如需 PostgreSQL，安装 `.[postgres]` 并配置 `postgresql+psycopg://...`；本轮未连接 PostgreSQL，不声称已做数据库兼容实测。进程内 Hub 与状态中心要求 `--workers 1`。容器、HTTPS 模板、备份与回退见 [部署说明](../deploy/README.md)。

## 当前边界

原始共享契约未改动，信封保持 v2。快速路径严格使用 §7 正则，带空格的温度口令、“把灯调亮一点”等未命中时走协调者。用户管理 CRUD、P1 收工复盘、六十分钟离座自动结束未加入本轮实现。当前交付不包含公网部署、真实模型或硬件通过的声明。
