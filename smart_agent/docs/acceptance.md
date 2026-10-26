# 2026-10-24 修复验收记录

修复前基线：6446bf2d8c2a1dff89323397f2e271bf639d166e。

## 本地验证结果

- Python 3.13.3：115 项测试通过，补充本地地图配置后的完整测试运行耗时 1.359 秒。
- Node.js 24.11.1：38 项前端渲染及交互测试通过。
- JavaScript 语法检查、Python 编译检查及 git diff --check 通过。
- 使用两个临时本机 HTTP 服务，跑通首页 Cookie、未鉴权拒绝、跨站拒绝、模型连接测试、工具调用、SSE 轨迹、同一会话追问和 Markdown 下载。
- 使用独立 stdio 子进程，跑通 initialize、initialized 通知、tools/list、tools/call 和 JSON 解析错误。此项验证工具消息子集，不代表所有 MCP 客户端互通。
- 模型、地图响应使用测试替身；HTTP 集成测试使用本地模拟模型，没有消耗真实模型或地图配额。
- 最终完整测试设置外部网络拦截，非本机请求尝试次数为 0。
- 新增 7 项地图本地配置测试，覆盖自动加载、优先级、显式参数、旧配置兼容、损坏文件和新客户端重载；测试只使用临时文件和假 AK，不读取真实本地凭据。
- 本机已将原 AK 迁移至被 Git 忽略的 maps_config.json，文件权限 0600，内部比对确认自动读取值与原值一致；未调用百度接口验证其有效性或配额。

## 问题与修复对照

| 原问题 | 修复方式 | 回归证据 |
| --- | --- | --- |
| 内置可恢复 AK | 公开源码不带实际凭据；支持环境和自动读取本地配置，保留已有 AK 的使用方式 | test_no_embedded_credential_defaults、TestLocalMapConfiguration |
| 写出工作区/覆盖文件 | 纯文件名校验、拒绝链接、独占创建 | TestItinerarySafety，含 8 线程同名竞争 |
| 配置变更转发旧 Key | API 访问令牌、Host/Origin 检查、改地址重填 Key、禁跳转 | test_endpoint_change_requires_new_key_and_does_not_mutate、test_foreign_origin_and_host_are_rejected |
| 会话串话 | 每会话独立上下文；未知 ID 拒绝；同会话互斥 | test_sessions_are_isolated_and_get_is_read_only、test_same_session_busy_returns_conflict |
| 六轮工具丢上下文 | 保留活动轮，按完整历史轮次裁剪，失败回滚 | test_six_tool_rounds_preserve_original_and_all_results_for_synthesis |
| MCP 握手/通知缺陷 | 实现握手与无响应通知；补独立 stdio 传输 | test_client_handshake_precedes_list_and_call_and_runs_once、TestStdioTransport |
| 错误类型中断执行 | 工具 schema 校验、执行异常封装、HTTP 类型/长度校验 | TestMCPExecutionRegressions、test_invalid_json_and_types_are_errors |
| 步行返回地铁 | 移除错误本地路线兜底；严格传递交通方式 | TestTrafficSafety |
| 测试受外网影响 | 天气/地图分别模拟成功失败，临时目录隔离 | TestWeatherSafety、test_weather_query_tool |
| Markdown/模型名注入 | 纯渲染器转义与协议白名单、textContent、CSP | 38 项前端测试 |
| 保存即显示已连接 | 保存和真实连接测试分离，状态可重置 | test_config_saved_is_not_connected、前端状态测试 |
| 并发限流失效 | 单调时钟加请求锁，重新检查提前唤醒 | TestMapPacingAndConfiguration |
| 并发删除后旧请求重建会话 | 取得执行锁后重新验证会话存在 | test_delete_between_lookup_and_lock_does_not_recreate_session |
| 落盘失败留下不可见对话 | 保存失败恢复执行前的上下文快照 | test_persistence_failure_rolls_back_invisible_turn |
| 错误环境地址阻止网页修正 | 旧地址无效时允许提供新地址与新 Key | test_invalid_initial_endpoint_can_be_corrected |

## 提交前需要真人完成的验收

1. 现有地图 AK 可以继续使用，程序自动读取 data/maps_config.json，无需重新申请或每次填写。该文件不入库；换电脑时需私下复制获授权的配置。旧公开历史仍可恢复 AK，由所有者决定是否轮换，本次不撤销凭据。
2. 配置本人有权限使用的模型，点击模型连接测试；检查地图服务端 AK 的接口授权、白名单和配额。
3. 输入旅行需求，确认界面展示真实天气/地图结果或明确错误，不将模拟数据当作真实结果。
4. 追问修改行程、切换两个会话，确认内容不互相影响；保存文档后下载检查。
5. 在演示设备使用支持 Web Speech API 的浏览器，验证麦克风权限、语音识别和中文朗读。
6. 核对分工、学号、原 PSP 与成员心得，附本组真实截图，再将 BLOG.md 发布到博客园。

## 能力边界

本机单用户；没有多租户身份系统。天气只支持当前观测，静态资料不代表最新票价或预约状态。时间规划是模型建议，没有数学求解及准点保证。JSON 本地持久化不属于数据库。语音依赖浏览器及其服务。MCP 仅实现明确列出的工具消息子集，不提供完整 Streamable HTTP。

本次未验证真实服务商端到端成功，不将 115/38 项测试通过表述为 100% 覆盖率或生产可靠性。
