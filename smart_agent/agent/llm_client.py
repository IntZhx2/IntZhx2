"""
大语言模型客户端与离线智能语义推理引擎 (LLM & Semantic Engine)
支持标准 OpenAI 格式的大模型接口，并在无 API Key 或离线断网环境下自动无缝切换为内置规则语义引擎。
"""

import json
import re
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional
import logging
from smart_agent.config import API_BASE, API_KEY, DEFAULT_MODEL

logger = logging.getLogger("agent.llm")


class LLMClient:
    """LLM 统一客户端"""

    def __init__(
        self,
        api_base: str = API_BASE,
        api_key: str = API_KEY,
        model: str = DEFAULT_MODEL,
    ):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.model = model

    def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """向 LLM 端点发送对话请求或使用本地智能引擎"""
        # 如果配置了有效 API Key，则尝试通过 HTTP 请求大模型 API
        if self.api_key and len(self.api_key.strip()) > 5:
            try:
                return self._call_remote_api(messages, tools)
            except Exception as e:
                logger.warning(f"远程大模型 API 调用失败 ({e})，降级回退至本地离线智能推理引擎。")

        # 默认或降级：使用内置语义规则与意图规划引擎
        return self._local_semantic_engine(messages, tools)

    def _call_remote_api(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """使用 Python 标准库调用 OpenAI 兼容接口"""
        url = f"{self.api_base}/chat/completions"
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.3,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "SmartAgent/1.0",
        }

        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=30.0) as resp:
            resp_body = resp.read().decode("utf-8")
            result = json.loads(resp_body)
            choice = result["choices"][0]["message"]
            return choice

    def _local_semantic_engine(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """内置高鲁棒性语义意图分析与工具决策引擎 (ReAct 规划)"""
        last_msg = messages[-1]

        # 1. 如果上一条是 tool 执行结果，说明工具调用已完成，综合生成最终自然语言回复
        if last_msg.get("role") == "tool":
            tool_content = last_msg.get("content", "")
            tool_name = last_msg.get("name", "tool")

            # 找到最近一条用户提问以作对齐
            user_question = ""
            for m in reversed(messages):
                if m.get("role") == "user":
                    user_question = m.get("content", "")
                    break

            answer = self._synthesize_final_answer(user_question, tool_name, tool_content)
            return {"role": "assistant", "content": answer, "tool_calls": None}

        # 2. 如果是用户输入，分析意图是否需要触发 MCP 工具
        user_text = last_msg.get("content", "").strip()

        # 检查是否触发待办事项相关工具
        todo_call = self._detect_todo_intent(user_text)
        if todo_call:
            return {
                "role": "assistant",
                "content": f"好的，我正在通过 MCP 协议为您调用待办管理工具处理：'{user_text}'...",
                "tool_calls": [todo_call],
            }

        # 检查是否触发天气或旅游规划工具
        weather_call = self._detect_weather_intent(user_text)
        if weather_call:
            return {
                "role": "assistant",
                "content": "正在为您查询气象情报与出行指南...",
                "tool_calls": [weather_call],
            }

        # 检查是否触发数学计算
        calc_call = self._detect_calc_intent(user_text)
        if calc_call:
            return {
                "role": "assistant",
                "content": "正在为您进行精确数学运算...",
                "tool_calls": [calc_call],
            }

        # 检查是否触发文件操作
        file_call = self._detect_file_intent(user_text)
        if file_call:
            return {
                "role": "assistant",
                "content": "正在为您执行文件读写与工作区管理...",
                "tool_calls": [file_call],
            }

        # 3. 纯语言对话与意图答复（能说）
        return {
            "role": "assistant",
            "content": self._handle_chit_chat(user_text, messages),
            "tool_calls": None,
        }

    def _detect_todo_intent(self, text: str) -> Optional[Dict[str, Any]]:
        # 添加待办
        match_add = re.search(r"(?:添加|记一下|新增|新建|提醒我|记录)(?:待办|任务|日程)?[:：\s]*(.+)", text)
        if ("待办" in text or "任务" in text or "提醒" in text) and any(kw in text for kw in ["添加", "新增", "新建", "建一个", "买", "完成"]):
            title = text
            if match_add:
                title = match_add.group(1).strip()
            # 清除前后多余字词
            title = re.sub(r"^(待办|任务|日程)[:：\s]*", "", title).strip()
            priority = "high" if any(w in text for w in ["紧急", "尽快", "高", "重要"]) else "medium"
            category = "study" if any(w in text for w in ["学习", "作业", "复习", "实验", "考试"]) else "work"
            return {
                "id": "call_todo_add_1",
                "type": "function",
                "function": {
                    "name": "todo_add",
                    "arguments": json.dumps({"title": title, "priority": priority, "category": category}, ensure_ascii=False),
                },
            }

        # 查看待办
        if any(kw in text for kw in ["查看待办", "列出待办", "待办清单", "我的任务", "有什么任务", "任务列表", "待办列表", "查询待办"]):
            status = "pending" if "未完成" in text or "待办" in text else "all"
            if "已完成" in text:
                status = "completed"
            return {
                "id": "call_todo_list_1",
                "type": "function",
                "function": {
                    "name": "todo_list",
                    "arguments": json.dumps({"status": status}, ensure_ascii=False),
                },
            }

        # 完成或更新待办
        match_done = re.search(r"(?:完成|做完|搞定|已完成).*?(\d+)", text)
        if match_done:
            task_id = int(match_done.group(1))
            return {
                "id": "call_todo_update_1",
                "type": "function",
                "function": {
                    "name": "todo_update",
                    "arguments": json.dumps({"task_id": task_id, "status": "completed"}, ensure_ascii=False),
                },
            }

        # 删除待办
        match_del = re.search(r"(?:删除|移除|删掉).*?(\d+)", text)
        if match_del:
            task_id = int(match_del.group(1))
            return {
                "id": "call_todo_del_1",
                "type": "function",
                "function": {
                    "name": "todo_delete",
                    "arguments": json.dumps({"task_id": task_id}, ensure_ascii=False),
                },
            }

        return None

    def _detect_weather_intent(self, text: str) -> Optional[Dict[str, Any]]:
        if "旅游" in text or "攻略" in text or "行程" in text or "计划去" in text:
            # 提取城市
            city = "广州"
            for c in ["广州", "深圳", "北京", "上海", "杭州", "成都", "武汉", "南京"]:
                if c in text:
                    city = c
                    break
            days = 2
            match_days = re.search(r"(\d+)天", text)
            if match_days:
                days = int(match_days.group(1))
            return {
                "id": "call_travel_1",
                "type": "function",
                "function": {
                    "name": "travel_plan",
                    "arguments": json.dumps({"destination": city, "days": days}, ensure_ascii=False),
                },
            }

        if "天气" in text or "气温" in text or "下雨" in text or "穿什么" in text:
            city = "广州"
            for c in ["广州", "深圳", "北京", "上海", "杭州", "成都", "武汉", "南京"]:
                if c in text:
                    city = c
                    break
            return {
                "id": "call_weather_1",
                "type": "function",
                "function": {
                    "name": "weather_query",
                    "arguments": json.dumps({"city": city}, ensure_ascii=False),
                },
            }
        return None

    def _detect_calc_intent(self, text: str) -> Optional[Dict[str, Any]]:
        # 寻找算式模式，例如 12 + 34 * 5 或 计算 sqrt(100)
        match_calc = re.search(r"(?:计算|算一下|求值|等于多少)?\s*([0-9\.\+\-\*\/\(\)\s\^\%]+|[a-z]+\([0-9\.\,\s]+\))", text)
        if any(op in text for op in ["+", "-", "*", "/", "sqrt", "计算", "算一下"]) and re.search(r"\d", text):
            expr = text
            if "计算" in expr or "算一下" in expr or "等于多少" in expr:
                expr = re.sub(r"(计算|算一下|等于多少|\?|？|求)", "", expr).strip()
            # 过滤只保留合法的表达式字符
            clean_expr = re.sub(r"[^\d\+\-\*\/\(\)\.\s\^]", "", expr).strip()
            if clean_expr and any(op in clean_expr for op in ["+", "-", "*", "/"]):
                return {
                    "id": "call_calc_1",
                    "type": "function",
                    "function": {
                        "name": "calculate",
                        "arguments": json.dumps({"expression": clean_expr}, ensure_ascii=False),
                    },
                }
        return None

    def _detect_file_intent(self, text: str) -> Optional[Dict[str, Any]]:
        if any(kw in text for kw in ["查看文件", "列出文件", "有哪些文件", "工作区文件", "文件列表"]):
            return {
                "id": "call_file_list_1",
                "type": "function",
                "function": {
                    "name": "file_list",
                    "arguments": "{}",
                },
            }

        match_write = re.search(r"(?:写入|保存到|创建文件)\s*([a-zA-Z0-9_\-\.]+)\s*[:：\s]*(.*)", text)
        if match_write:
            fname = match_write.group(1).strip()
            content = match_write.group(2).strip() or "这是智能体自动创建的文件内容。"
            return {
                "id": "call_file_write_1",
                "type": "function",
                "function": {
                    "name": "file_write",
                    "arguments": json.dumps({"filepath": fname, "content": content}, ensure_ascii=False),
                },
            }

        match_read = re.search(r"(?:读取|查看|打开文件)\s*([a-zA-Z0-9_\-\.]+)", text)
        if match_read:
            fname = match_read.group(1).strip()
            return {
                "id": "call_file_read_1",
                "type": "function",
                "function": {
                    "name": "file_read",
                    "arguments": json.dumps({"filepath": fname}, ensure_ascii=False),
                },
            }
        return None

    def _synthesize_final_answer(self, user_question: str, tool_name: str, tool_result: str) -> str:
        """根据工具执行结果组织最终自然语言回复"""
        if "todo_add" in tool_name:
            return f"任务已经成功记录到您的待办数据库中了！\n\n{tool_result}\n\n您可以随时对我说“查看待办事项”来核对您近期的任务清单。"
        elif "todo_list" in tool_name:
            return f"为您检索到以下待办事项明细：\n\n{tool_result}\n\n若某项任务已完成，可告诉我“完成任务 [ID]”进行状态标记。"
        elif "todo_update" in tool_name:
            return f"状态更新成功！\n\n{tool_result}"
        elif "todo_delete" in tool_name:
            return f"待办事项已移除！\n\n{tool_result}"
        elif "weather_query" in tool_name:
            return f"已为您查询到最新气象动态：\n\n{tool_result}\n\n出行请根据天气状况携带相应装备，注意身体健康！"
        elif "travel_plan" in tool_name:
            return f"根据您的偏好，我为您生成了详细的出行方案：\n\n{tool_result}\n\n如果需要将此行程保存为本地文件，只需告诉我“保存为 travel_plan.txt”即可！"
        elif "calculate" in tool_name:
            return f"数学运算已完成：\n\n{tool_result}"
        elif "file" in tool_name:
            return f"工作区文件操作执行结果如下：\n\n{tool_result}"
        else:
            return f"工具执行完毕：\n\n{tool_result}"

    def _handle_chit_chat(self, text: str, messages: List[Dict[str, Any]]) -> str:
        """处理问答、自我介绍及多轮记忆延续"""
        if any(w in text.lower() for w in ["你好", "hello", "hi", "你是谁", "介绍一下你自己", "功能"]):
            return (
                "👋 您好！我是 **SmartAgent**，一个具备“能说会做”能力的高级智能助理。\n\n"
                "基于 Model Context Protocol (MCP) 架构，我不仅能与您自然流利地交流，还能主动调度各种外部工具为您解决问题：\n"
                "- 📋 **待办事项管家**：添加任务、按优先级与分类查询、更新状态（SQLite 数据库持久化）\n"
                "- 🌤️ **气象与出行规划**：实时天气查询、穿衣指数与多日定制旅游计划\n"
                "- 🔢 **精确科学计算**：支持复合加减乘除、乘方与数学函数无误差求值\n"
                "- 📁 **文件与办公助手**：在安全沙箱内创建、读写与管理文档\n"
                "- 🎙️ **多模态语音交互**：支持语音输入 (STT) 与实时语音朗读 (TTS)\n\n"
                "请问今天有什么我可以协助您的吗？"
            )

        if "学号" in text or "组队" in text or "队员" in text or "作者" in text:
            return (
                "🎓 本智能体由广东工业大学 24 计科 6班三人团队共同构建：\n"
                "- **赵海翔**（学号：3124004113，架构设计与智能体内核）\n"
                "- **何卓文**（学号：3124004132，MCP 服务端与工具生态）\n"
                "- **吴与同**（学号：3124004018，Web 界面与多模态语音工程）"
            )

        # 检查多轮记忆关联
        user_history_count = sum(1 for m in messages if m.get("role") == "user")
        if user_history_count > 1:
            return (
                f"我理解您说的：“{text}”。\n"
                f"我已经记住我们前面的 {user_history_count} 轮对话上下文。\n"
                "如果需要我执行具体操作（例如记录待办、查询天气、计算数据或写入文件），您可以直接用自然语言对我下达指令！"
            )

        return (
            f"收到您的消息：“{text}”。\n"
            "我可以帮您管理待办清单（存入 SQLite 数据库）、查询天气与行程、做精确算术计算或管理工作空间文件。\n"
            "例如您可以试着对我说：\n"
            "- “提醒我明天下午两点提交软件工程智能体作业，优先级高”\n"
            "- “查询广州现在的天气如何，适不适合出行”\n"
            "- “帮我算一下 (128 * 45) + 300 / 12”\n"
            "- “帮我把今天的学习计划写进 plan.txt 文件里”"
        )
