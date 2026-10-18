#!/usr/bin/env python3
"""
SmartAgent 智能体主程序入口
支持以 Web 现代前端交互界面或 CLI 终端交互模式运行，完全兼容 MCP 协议规范。

开发团队（广东工业大学 24 计科 6班）：
- 赵海翔（3124004113，架构设计与智能体内核）
- 何卓文（3124004132，MCP 服务端与工具生态）
- 吴与同（3124004018，Web 界面与多模态交互）
"""

import sys
import argparse
import unittest
from pathlib import Path

# 确保 smart_agent 可以作为顶层包或直接执行
current_dir = Path(__file__).resolve().parent
parent_dir = current_dir.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from smart_agent.config import SERVER_HOST, SERVER_PORT
from smart_agent.mcp.server import MCPServer
from smart_agent.mcp.client import MCPClient
from smart_agent.agent.memory import ConversationMemory
from smart_agent.agent.llm_client import LLMClient
from smart_agent.agent.core import SmartAgent
from smart_agent.tools import create_default_tools
from smart_agent.web.server import run_server


def run_cli_mode():
    """终端交互模式"""
    print("=" * 65)
    print("🤖 欢迎进入 SmartAgent 命令行交互终端！")
    print("👥 开发团队: 赵海翔 (3124004113) · 何卓文 (3124004132) · 吴与同 (3124004018)")
    print("💡 模式特性: 已挂载 MCP 工具集，支持多轮记忆与自然语言指令执行")
    print("输入 'exit' 或 'quit' 退出，输入 'clear' 重置上下文记忆")
    print("=" * 65)

    # 初始化 MCP Server 与工具集
    mcp_server = MCPServer(name="SmartAgent-CLI")
    for tool in create_default_tools():
        mcp_server.register_tool(tool)

    mcp_client = MCPClient(mcp_server)
    llm_client = LLMClient()
    memory = ConversationMemory(session_id="cli_session")
    agent = SmartAgent(memory=memory, mcp_client=mcp_client, llm_client=llm_client)

    print(f"🛠️ 已成功就绪 {len(mcp_client.get_tools())} 个 MCP 旅游专属工具！")
    if not llm_client.has_valid_key():
        print("⚠️  当前未配置大模型 API Key（系统已关闭伪离线模式，必须接入真实大模型）。")
        prompt_key = input("👉 请输入您的大模型 API Key (如阿里云百炼/DeepSeek sk-xxx): ").strip()
        if prompt_key:
            llm_client.api_key = prompt_key
            print("✅ API Key 已设定！\n")
        else:
            print("❌ 未提供 API Key，您也可以通过 --web 在网页端进行可视化配置。\n")

    while True:
        try:
            user_input = input("\n👤 您: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit", "q"):
                print("👋 再见！期待下次与您合作！")
                break
            if user_input.lower() == "clear":
                memory.clear()
                print("🧹 上下文记忆已清空。")
                continue

            print("\n🤖 SmartAgent 正在思考与执行...", flush=True)

            def print_step(trace):
                if trace.step_type == "thought":
                    print(f"  🧠 [思考] {trace.content}")
                elif trace.step_type == "tool_call":
                    tool = trace.details.get("tool", "")
                    args = trace.details.get("arguments", {})
                    print(f"  🛠️ [MCP 调用] {tool}({args})")
                elif trace.step_type == "tool_result":
                    print(f"  👁️ [工具反馈] {trace.content.strip()}")

            result = agent.run(user_input, on_step_callback=print_step)
            print(f"\n💬 SmartAgent 回复:\n{result.answer}")

        except (KeyboardInterrupt, EOFError):
            print("\n👋 交互已终止。")
            break


def run_tests():
    """运行全套单元与集成测试"""
    print("🚀 开始执行 SmartAgent 自动化测试套件...")
    loader = unittest.TestLoader()
    start_dir = str(current_dir / "tests")
    suite = loader.discover(start_dir, pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=2)
    res = runner.run(suite)
    sys.exit(0 if res.wasSuccessful() else 1)


def main():
    parser = argparse.ArgumentParser(
        description="SmartAgent: 具备自然语言交互与工具执行能力的多功能智能体系统"
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="启动 Web 交互前端与 REST 服务（默认推荐）",
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        help="以命令行终端交互模式运行",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="运行系统全量自动化测试套件",
    )
    parser.add_argument(
        "--host",
        default=SERVER_HOST,
        help=f"Web 服务监听地址 (默认: {SERVER_HOST})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=SERVER_PORT,
        help=f"Web 服务监听端口 (默认: {SERVER_PORT})",
    )

    args = parser.parse_args()

    if args.test:
        run_tests()
    elif args.cli:
        run_cli_mode()
    else:
        # 默认启动 Web 模式
        run_server(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
