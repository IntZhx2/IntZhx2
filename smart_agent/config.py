"""
全局配置模块 (Global Configuration)
管理智能体运行环境、MCP 服务配置、大模型端点及本地存储路径。
"""

import os
from pathlib import Path

# 项目路径定义
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
WORKSPACE_DIR = DATA_DIR / "workspace"
DB_PATH = DATA_DIR / "agent_data.db"

# 自动创建必要数据目录
DATA_DIR.mkdir(parents=True, exist_ok=True)
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

# Web 服务配置
SERVER_HOST = os.environ.get("AGENT_HOST", "127.0.0.1")
SERVER_PORT = int(os.environ.get("AGENT_PORT", "8000"))

# LLM 与推理后端配置
# 支持兼容 OpenAI 接口标准的 API（如 通义千问百炼、DeepSeek、Ollama 等）
# 若未提供 API_KEY，系统将自动无缝切换至高质量本地语义规则推理引擎，确保评测与教学展示零门槛开箱即用
API_BASE = os.environ.get("OPENAI_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
API_KEY = os.environ.get("OPENAI_API_KEY", "")
DEFAULT_MODEL = os.environ.get("AGENT_MODEL", "qwen-plus")

# 智能体 ReAct 循环与记忆预算
MAX_REACT_TURNS = 6
MEMORY_WINDOW_SIZE = 12

# 系统通用提示词
SYSTEM_PROMPT = """你是一个具备“能说会做”能力的高级智能助理（SmartAgent）。
你通过 Model Context Protocol (MCP) 标准协议连接并调用工具来解决用户的问题。

你的核心原则与行为准则：
1. 【能说】：以清晰、友好、自然的中文与用户进行多轮对话，具备良好的上下文理解和记忆能力。
2. 【会做】：当用户的需求需要获取实时数据、管理待办事项、执行复杂数学计算或读写文件时，必须主动且准确地调用对应的 MCP 工具。
3. 【知行合一】：在调用工具前先简要说明意图，工具执行返回结果后，必须根据观察到的真实数据进行归纳、总结和回复，严禁臆造外部信息。
4. 【安全严谨】：在文件读写和命令执行时保持安全性，遇到异常或不合理输入时给出友好解释和改进建议。
"""
