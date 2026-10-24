# TravelAgent：旅游规划智能体

本项目对应[软件工程作业 16760](https://edu.cnblogs.com/campus/gdgy/Class56-Grade2024-CS/homework/16760)。用户可以通过自然语言规划行程、继续追问，并让模型调用天气、路线、景点和文档工具。

成员：赵海翔（3124004113）、何卓文（3124004132）、吴与同（3124004018）。

## 启动

Python 3.9 及以上，后端仅使用标准库。以下命令在仓库根目录执行：

```bash
python3 smart_agent/main.py --web
```

打开 http://127.0.0.1:8000 。首次访问首页会设置 HttpOnly、SameSite=Strict 的访问 Cookie；接口只接受本机同源请求。当前版本定位为本机单用户应用，不支持直接绑定 0.0.0.0 对外提供服务。

在右上角「API 设置」填写服务商的 OpenAI 兼容接口地址、模型名和自己的 Key：
- 默认地址示例：https://api.deepseek.com/v1，模型名 deepseek-chat。
- 点击保存仅表示配置写入成功；点击「测试连接」才会发起一次实际模型请求，可能产生少量模型费用。
- 切换模型服务地址时必须重新填写对应 Key，不会把旧 Key 自动发送给新服务。
- 第三方服务可保留自身路径，例如 /compatible-mode/v1 或 /api/paas/v4；模型名按服务商文档原样填写。
- 远程接口要求 HTTPS；本机开发服务可以使用 http://127.0.0.1:端口/v1。

CLI 可以通过环境变量配置（也支持网页配置，但 CLI 使用环境变量而不读取网页保存的配置）：

```bash
export OPENAI_BASE_URL="https://api.deepseek.com/v1"
export OPENAI_API_KEY="你的模型Key"
export AGENT_MODEL="deepseek-chat"
export BAIDU_MAPS_AK="你自己的百度地图服务端AK"
python3 smart_agent/main.py --cli
```

网页保存的模型配置位于 data/llm_config.json，是受文件权限限制的本地明文文件，并已被 Git 忽略。它不是加密保险箱。会话保存在 data/sessions/，行程文档保存在 data/workspace/。不要提交或分享这些实际数据。

## 工具与数据边界

| 工具 | 行为 |
| --- | --- |
| weather_query | 查询当前天气，百度失败时尝试 wttr.in；不是指定旅行日的天气预报 |
| traffic_transit | 查询指定交通方式的地图路线；无可用数据时返回错误，不使用手写地铁线路兜底 |
| attraction_info | 获取 POI，部分广州景点有明确标注的本地静态参考信息 |
| itinerary_save | 仅在工作区创建纯文件名的 Markdown/TXT 文件，拒绝越界、符号链接及覆盖已有文件 |
| itinerary_list | 列出已保存行程；网页可下载文档 |

百度工具需要自己配置 BAIDU_MAPS_AK，并在控制台开启相应接口权限；仓库不附带可用凭据。旧版 ENCRYPTED_BAIDU_AK 仅为兼容环境配置，不提供安全保密能力。旧版本曾包含可恢复的内置 AK，如该 AK 属于你的真实应用，应在控制台撤销或轮换；删除最新源码不能撤回已公开的历史。

到达时间、费用和游玩安排是基于已知数据的建议，未实现数学约束求解器，不能保证准点。票价、预约与营业状态应以官方最新信息为准。

## MCP 接口范围

实现 MCP 2024-11-05 的 initialize/initialized、tools/list、tools/call、ping 消息子集。内置 Agent 使用进程内适配器，也提供独立的换行 JSON stdio 服务：

```bash
python3 smart_agent/main.py --mcp-stdio
```

可在支持自定义 stdio 工具服务的客户端中配置 Python 可执行文件与该脚本的绝对路径。协议互通已用独立进程测试，尚未对所有第三方客户端做兼容测试；不支持 resources、prompts 或完整 Streamable HTTP。网页 /api/mcp 是受同源访问控制保护的自定义调试入口，不应当作完整标准 HTTP 传输。

## 验证

```bash
python3 smart_agent/main.py --test
node --test smart_agent/tests/test_frontend_security.js
python3 smart_agent/tests/benchmark_profile.py
```

Python 测试包含真实本机 HTTP 服务与本地模拟模型的工具循环，不访问付费模型。前端安全测试需要 Node.js 18 或以上，应用运行本身不依赖 Node。

测试覆盖路径隔离、参数类型、MCP 握手、六轮工具记忆保留、失败回滚、会话隔离、Cookie/Origin 校验、SSE、导出、限流及 Markdown 安全。测试通过不等于真实模型、地图配额或麦克风在你的机器上已验证，提交前请按 docs/acceptance.md 操作。

## 文档

- BLOG.md：符合课程格式的博客草稿，个人心得和真实演示需成员确认。
- docs/architecture.md：业务流、模块和访问边界。
- docs/acceptance.md：修复清单和提交前验收步骤。
- docs/performance.md：基准方法及结果的适用范围。
- docs/PSP.md：保留原团队时间记录，数值需由成员核对。
