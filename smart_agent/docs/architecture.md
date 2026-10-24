# TravelAgent 架构与接口边界

## 业务链路

用户输入 → 当前会话的 Agent → 模型选择工具 → 参数校验 → 工具执行 → 结果进入当前轮上下文 → 模型回答 → 会话原子保存。

SmartAgent 不保存跨会话状态。Web 服务按 session_id 保存 SessionContext，每个上下文包含独立的 ConversationMemory、Agent 和锁。同一会话并发请求返回 409；读取历史不会切换其他请求的上下文。不存在的会话 ID 返回 404。

## 工具层

BaseTool 描述参数；MCPServer 在执行前验证对象、必填字段、类型和枚举，把错误转换为结构化结果。MCPClient 在首次调用前完成 initialize 和 notifications/initialized。

实现范围为 MCP 2024-11-05 工具消息子集，既可进程内调用，也可通过 main.py --mcp-stdio 在独立进程中交换换行 JSON。通知不返回响应，错误 JSON 返回 -32700。未实现 resources、prompts、完整协议协商和标准 HTTP 传输，不宣称完整 MCP 兼容。

网页 /api/mcp 使用同样的分发器，但它是受保护的自定义 HTTP 入口。

## 记忆和失败恢复

执行中的原始用户消息、assistant tool_calls 和 tool 结果完整保留，即使暂时超过历史窗口。回答完成后，本轮压缩为 user/assistant，并按完整轮次移除更早历史。模型或工具链抛异常时恢复执行前快照，避免半轮工具消息污染重试。

历史窗口是消息预算，不是 token 级硬限制。用户输入上限 20000 字符，HTTP 请求体上限 1 MiB，模型响应上限 4 MiB。

## 访问控制

服务仅支持 127.0.0.1 或 localhost 本机监听。浏览器访问首页后获得随机 HttpOnly、SameSite=Strict Cookie，API 需要该 Cookie 或部署者显式配置的 AGENT_ACCESS_TOKEN Bearer 令牌。检查 Host、Origin 和 Fetch Metadata，不开放跨域 CORS。

这是本机单所有者的访问边界，不是多租户账号系统，也不用于保护同一操作系统账号下的恶意程序。网络部署需要独立设计 HTTPS、身份认证、用户数据归属和配额。

模型配置更新在锁内完成；每次 Agent 请求使用配置快照，避免地址和 Key 在并发更新时错配。变更地址要求重新提供 Key。禁止自动 HTTP 跳转，避免带凭据跟随重定向。

## 本地文件

行程仅接受纯文件名，拒绝绝对路径、目录分隔符、符号链接和覆盖。会话 ID 严格校验；JSON 写入使用 0600 临时文件并原子替换。模型配置同样是私有权限的本地明文文件。

地图客户端自动读取本地 data/maps_config.json 中的 baidu_maps_ak，环境配置优先。已有 AK 可继续使用，无需重新申请；网页、CLI 和 MCP 使用同一读取逻辑。实际文件被 Git 忽略，迁移时使用 0600 权限。客户端在创建时读取配置，改动后重启应用生效。

历史已公开凭据仍可被恢复；是否在服务商侧轮换由凭据拥有者决定。本次保留现有 AK，不执行撤销或轮换；本地文件并不能撤回已经公开的历史。

## 数据质量

路线失败直接返回错误，不使用无法核实的手写换乘库。当前天气不等于未来预报；景点本地数据为静态参考。时间、费用与预约建议不代表已订票或保证可行。

## 前端

安全 Markdown 渲染器转义文本、URL 属性并限制链接协议，代码块不参与行内语法重写；模型名以 textContent 显示。CSP 禁止内联脚本，所有接口使用同源 Cookie。语音依赖浏览器 Web Speech API 和麦克风权限。
