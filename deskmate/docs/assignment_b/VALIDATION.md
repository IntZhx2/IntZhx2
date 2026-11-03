# DeskMate 成员 B 验证记录

核查日期为 2026 年 11 月 2 日，执行环境为 macOS arm64。本文只记录本轮实际执行的检查，需求指标与真实端到端结果在 SRS 附录中分开管理。用户已将本轮 B-07 调整为 localhost 验证，不进行公网交互。

## 代码与自动化测试

运行目录为 `deskmate/backend`，本地 `.venv` 使用 CPython 3.11.16。生产依赖由 requirements.txt 固定版本及哈希，Docker 内为 CPython 3.11.18。执行：

```bash
.venv/bin/ruff check app tests scripts
.venv/bin/ruff format --check app tests scripts
.venv/bin/pytest -q --cov=app --cov-report=term --cov-report=json:data/coverage.json --cov-fail-under=70
```

| 检查 | 实际结果 |
| --- | --- |
| pytest | 84 passed，10.48s |
| 总语句覆盖率 | 89.85%，1843 条语句，187 条未覆盖 |
| 核心状态引擎覆盖率 | 超过 95%，FocusEngine 97%，PresenceEngine 91%，StateStore 100% |
| ruff check | All checks passed |
| ruff format | 35 files already formatted |
| Git 空白检查 | git diff --check 通过 |
| 依赖警告 | 一条 Starlette TestClient 对 httpx 的弃用警告，不影响测试结果 |

测试使用临时数据库和受控模型响应，没有调用外部模型或真实硬件。已覆盖登录过期与越权、Schema 幂等启动、工作台 CRUD、配置范围与即时生效、全部 21 个模拟工具、用户隔离、WS 快照和 200ms 合并、RPC 关联/超时/断线清理、模型工具拒绝、六步限制、二秒确认、未知目录确认、离座阶梯、失败重试、滚动阅读、重启暂停、小数秒计时及本地午夜日计数。Python 3.11 正常断开时的取消清理和倒计时提前到点问题已通过回归测试修正。

## 实际 localhost 访问

先通过临时 Uvicorn 的 `127.0.0.1:8000` 端口运行冒烟，再构建容器并通过 Nginx 的 `127.0.0.1:8080` 重复验证。临时 Uvicorn 已停止，当前保留容器入口供查看。执行：

```bash
.venv/bin/python scripts/smoke_local.py --base-url http://127.0.0.1:8080
```

实际输出的状态为：

```json
{
  "base_url": "http://127.0.0.1:8080",
  "health": "ok",
  "login": "ok",
  "websocket": "ok",
  "focus_pause_resume": "ok",
  "sse_fast_path": "ok",
  "demo_mode": true,
  "api_docs": "ok",
  "c_module": "not_installed"
}
```

脚本从被忽略的本地 .env 读取 demo 密码，未打印凭据。验证内容包括实际端口登录、WS 首次快照和增量、一分钟专注、锁屏暂停与伴眠光、解锁恢复、SSE 空调调到 25℃、结束会话以及 C 未接入时报告 503。这里验证的是后端 API 文档和虚拟设备，不是 C 的正式页面或真实音箱。

## 容器与代理

在仓库根目录执行：

```bash
docker compose -f deskmate/deploy/docker-compose.yml config --quiet
docker compose -f deskmate/deploy/docker-compose.yml up -d --build
docker compose -f deskmate/deploy/docker-compose.yml exec -T backend python --version
docker compose -f deskmate/deploy/docker-compose.yml exec -T backend id
docker compose -f deskmate/deploy/docker-compose.yml exec -T nginx nginx -t
docker compose -f deskmate/deploy/docker-compose.yml ps
```

镜像构建成功并完成哈希校验安装。backend 为 healthy，Nginx 正在运行，端口为 `127.0.0.1:8080->80/tcp`。容器 Python 为 3.11.18，执行身份为 `uid=10001(deskmate) gid=10001(deskmate)`。`nginx -t` 返回 syntax is ok 和 test is successful。最终容器包含最后的计时边界修正，HTTP/WS/SSE 冒烟再次通过。

HTTPS 覆盖文件通过 `docker compose -f ... -f ... config --quiet` 结构校验；没有生成或安装证书，没有执行 TLS 握手，没有公网地址验收。数据保存在 Docker 命名卷，直接 Python 运行时的数据库与容器卷分别独立。

## 作业文档与图表

`DeskMate_SRS_B.pdf` 共 17 页，A4，未加密，已用 Poppler 渲染逐页检查文字、图表、表格、页码和中文字体。PDF 的字体已嵌入，文本可提取，附录含 A01～A10 十组用例。需求目标与待确认项均有明确标签，不预填真机成功率或调研数据。

六张图均从 Mermaid 源渲染，SVG 可缩放，PNG 尺寸如下：

| 图 | PNG 尺寸 |
| --- | --- |
| 系统架构 | 2700 × 1580 |
| 多智能体协同 | 2700 × 2192 |
| 专注状态机 | 2700 × 1748 |
| 在座阶梯状态机 | 2700 × 2777 |
| 类图 | 2700 × 2075 |
| 工作台时序 | 2700 × 1791 |

`DEFENSE_TECH_PAGES.md` 是 B 的技术页内容和讲稿，供 C 放入整套 PPT，没有交付或声称已完成 C 的整套排版。SRS 使用任务卡要求的规范结构，属于评审草稿，具体标准版本条文仍需课程评审复核。

## 范围与未验证项

仅新增 backend、deploy 和 B 的 docs 材料，更新 B 任务卡；未修改 edge、C 任务卡、frontend 或 app/wellbeing，未修改 CONTRACTS v2；首次核查时尚未提交或推送 Git，后续整理见文末说明。

真实模型密钥未配置，所以外部 Function Calling、Bocha/内建联网、多模态识别质量及云端响应时延尚未实测。Windows 应用启动、150% DPI 窗口误差、小爱语音桥和红外空调需要 A/B 联验。疲劳基线、评分、心流决策、报告统计和前端页面需要 C 接入；默认 fatigue 零值是占位，报告未接入明确返回 503。

环境文件权限确认为 0600，.env、数据库、虚拟环境、文档工具 node_modules 和 QA 渲染文件均已被忽略。公开提交只含 .env.example 与可重建的源码、锁文件和最终文档，不包含真实凭据或现场数据。

## 2026 年 11 月 3 日恢复复核

会话中断后，本机 Docker 没有运行，先前位于临时目录的 Python 解释器也已清理。本次已恢复 Docker Desktop 与原有 backend/nginx 容器，并将本地 Python 3.11.16 安装到项目内 `.runtime/`，重建 `.venv`，不再引用临时目录。`.runtime/` 同时加入 Git 和 Docker 忽略规则，未纳入源码、镜像上下文或作业素材包。

恢复后重新执行相同的完整测试，结果为 **84 passed，9.93s，总覆盖率 89.85%**，一条相同的 TestClient 弃用警告。`ruff check app tests scripts` 通过，`ruff format --check app tests scripts` 返回 34 files already formatted。localhost:8080 的 HTTP/WS/SSE 冒烟和 `nginx -t` 均再次通过，backend 保持 healthy，未改变公网暂缓及 C 模块不实现的范围。

SRS PDF 仍为已逐页检查的 17 页版本。新增 `DeskMate_B00_materials.zip` 便于交付文档和图表，压缩包只包含明确列出的作业素材与导出源码，排除 .env、数据库、虚拟环境、.runtime、node_modules 和 QA 中间文件。


## Git 分阶段整理说明

2026 年 11 月 3 日按功能依赖把本轮已完成的本地改动整理为七个提交：基础服务、WebSocket 与 VirtualEdge、工作台与状态引擎、多智能体、API 与测试、容器部署、作业文档。所有提交使用整理时的真实时间，不回填作者或提交日期，不修改原有 A 的提交历史。

这些提交用于审阅和追踪功能边界，不代表代码按提交间隔从零逐步开发，也不能用来证明此前数日的连续开发节奏。原始实现与验证日期以本文件各次检查记录为准。推送目标为已有 origin/main，即 https://github.com/IntZhx2/IntZhx2 的 main 分支；本节编写时尚未推送，后续是否完成需核对远端分支 HEAD，不能仅凭本地提交记录判断。
