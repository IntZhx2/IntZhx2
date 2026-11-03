# DeskMate 部署与本地验收

本轮按用户指示只验证 localhost，不进行公网交互。后端可直接用 Python 启动，容器配置也已提供。C 的前端尚未交付，所以 Nginx 根路径跳转到 `/docs`，不另外制作一个替代控制台。

## 本地容器启动

先按 `../backend/README.md` 生成 `.env`，启动 Docker Desktop 或服务器 Docker 引擎，然后在 `deskmate/deploy` 执行：

```bash
docker compose config --quiet
docker compose up -d --build
docker compose ps
```

访问 <http://127.0.0.1:8080/docs>，健康检查为 <http://127.0.0.1:8080/api/health>。在 backend 目录运行 `.venv/bin/python scripts/smoke_local.py --base-url http://127.0.0.1:8080` 验证反代后的 HTTP、SSE 和 WebSocket。Nginx 关闭 SSE 缓冲，转发 Upgrade，读取超时 120 秒。默认端口只绑定环回地址。

后端镜像使用 Python 3.11 和非 root UID 10001，校验完整 requirements.txt 哈希，运行单 worker。命名卷 `backend_data` 保留 SQLite。Docker 构建不包含 `.env`、本地数据库或测试。`docker compose down` 保留数据卷，禁止在需要数据时使用 `down -v`。

## 后续 HTTPS 配置

待团队指定服务器、域名和证书后，把完整证书链与私钥分别放在被忽略的 `certs/fullchain.pem`、`certs/privkey.pem`，私钥设为本地可读，按服务器实际域名更新 nginx/https.conf 的 server_name。不要提交证书私钥。

```bash
docker compose -f docker-compose.yml -f docker-compose.https.yml config --quiet
docker compose -f docker-compose.yml -f docker-compose.https.yml up -d --build
```

覆盖配置增加 443；基础文件的 127.0.0.1:8080 仍保留供本机诊断。容器内 80 跳转 HTTPS。公网 DNS、证书链、WSS、JWT 和实际模型连通性需现场验证。本轮没有执行这一步，也没有声称已上线。

## 接入 C 的前端

由 C 交付 frontend/dist 后，再按共享部署计划配置 Nginx 静态文件路径与 SPA fallback，保留 `/api`、`/ws` 和 SSE 代理规则。B 本轮不生成 frontend 源码或静态假页面。当前 API 文档可供老师或组员检查后端接口，但不能替代三场景最终产品演示。

## 备份与回退

升级前保存当前镜像标签、代码版本及数据库快照。当前 v1 迁移不删列，但未来 Schema 更改应先在备份副本验证。

```bash
docker compose stop backend
docker compose cp backend:/app/data/deskmate.db ./deskmate-backup.db
docker compose start backend
```

备份文件包含用户和日志数据，只保存在本地受控位置，不加入 Git。停止后复制避免 SQLite 活跃写入不一致。回退时停止 backend，使用匹配旧版镜像和对应数据库备份恢复，确认卷内文件属主为 UID/GID 10001，再启动并运行冒烟脚本。不要把新 Schema 数据库直接交给更旧的镜像；应用会拒绝更高 SchemaVersion。

直接 Uvicorn 本地运行时，停止该进程后复制 `../backend/data/deskmate.db`，恢复同理。当前不存在自动操作云服务器、申请证书或发送第三方消息的脚本。

## 验证边界

本轮已启动本机 Docker Desktop，完成镜像构建、backend 健康检查、非 root 身份检查、Nginx 配置检查和 127.0.0.1:8080 HTTP/WS/SSE 冒烟。容器使用 Python 3.11.18，测试环境为 Python 3.11.16。HTTPS 覆盖配置通过 compose 结构校验，但没有提供证书或执行 TLS 握手，也未做公网部署。最终证据见 `../docs/assignment_b/VALIDATION.md`。
