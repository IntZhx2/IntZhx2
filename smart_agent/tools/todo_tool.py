"""
SQLite 关系型数据库与待办事项 (Todo) 工具集
提供结构化持久存储、任务状态流转及统计分析能力，满足作业要求中的外部数据库交互。
"""

import sqlite3
from typing import Any, Dict, List, Optional
from pathlib import Path
from smart_agent.config import DB_PATH
from smart_agent.tools.base import BaseTool
from smart_agent.mcp.protocol import ToolCallResult


class DatabaseManager:
    """SQLite 数据库底层管理类"""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                priority TEXT DEFAULT 'medium', -- low, medium, high
                category TEXT DEFAULT 'general', -- study, work, life
                due_date TEXT,
                status TEXT DEFAULT 'pending', -- pending, in_progress, completed, cancelled
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)
            conn.commit()


# 全局单例数据库实例
_db_manager = DatabaseManager()


class TodoAddTool(BaseTool):
    @property
    def name(self) -> str:
        return "todo_add"

    @property
    def description(self) -> str:
        return "向待办事项数据库添加一条新任务，支持指定优先级、类别和截止日期。"

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "任务具体内容与名称"},
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                    "default": "medium",
                    "description": "优先级：low(低), medium(中), high(高)",
                },
                "category": {
                    "type": "string",
                    "default": "general",
                    "description": "任务类别，如 work, study, life 等",
                },
                "due_date": {"type": "string", "description": "截止日期，例如 2026-10-25 18:00"},
            },
            "required": ["title"],
        }

    def execute(self, **kwargs) -> ToolCallResult:
        title = kwargs.get("title", "").strip()
        if not title:
            return ToolCallResult.text("错误: 任务名称 (title) 不能为空", is_error=True)

        priority = kwargs.get("priority", "medium")
        category = kwargs.get("category", "general")
        due_date = kwargs.get("due_date", "")

        try:
            with _db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO todos (title, priority, category, due_date, status) VALUES (?, ?, ?, ?, 'pending')",
                    (title, priority, category, due_date),
                )
                conn.commit()
                task_id = cursor.lastrowid

            return ToolCallResult.text(
                f"✅ 成功创建待办事项！ID: {task_id}, 标题: '{title}', 优先级: {priority}, 分类: {category}"
            )
        except Exception as e:
            return ToolCallResult.text(f"添加待办事项失败: {str(e)}", is_error=True)


class TodoListTool(BaseTool):
    @property
    def name(self) -> str:
        return "todo_list"

    @property
    def description(self) -> str:
        return "查询数据库中的待办事项清单，可按状态（pending/completed/all）或分类过滤。"

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["all", "pending", "in_progress", "completed"],
                    "default": "all",
                    "description": "过滤状态：all(全部), pending(待处理), completed(已完成)",
                },
                "category": {"type": "string", "description": "按分类过滤，留空则不限分类"},
            },
        }

    def execute(self, **kwargs) -> ToolCallResult:
        status = kwargs.get("status", "all")
        category = kwargs.get("category")

        try:
            with _db_manager.get_connection() as conn:
                cursor = conn.cursor()
                sql = "SELECT id, title, priority, category, due_date, status, created_at FROM todos WHERE 1=1"
                params: List[Any] = []

                if status and status != "all":
                    sql += " AND status = ?"
                    params.append(status)

                if category:
                    sql += " AND category = ?"
                    params.append(category)

                sql += " ORDER BY CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, id ASC"

                cursor.execute(sql, params)
                rows = cursor.fetchall()

            if not rows:
                return ToolCallResult.text("当前没有任何匹配的待办事项。")

            lines = [f"📋 共检索到 {len(rows)} 条待办事项："]
            for r in rows:
                status_icon = "✅" if r["status"] == "completed" else "⏳"
                pri_icon = "🔥" if r["priority"] == "high" else ("⚡" if r["priority"] == "medium" else "☕")
                due = f" (截止: {r['due_date']})" if r["due_date"] else ""
                lines.append(
                    f"- [{status_icon} ID {r['id']}] {pri_icon} [{r['category']}] {r['title']} | 状态: {r['status']}{due}"
                )

            return ToolCallResult.text("\n".join(lines))
        except Exception as e:
            return ToolCallResult.text(f"查询待办列表失败: {str(e)}", is_error=True)


class TodoUpdateTool(BaseTool):
    @property
    def name(self) -> str:
        return "todo_update"

    @property
    def description(self) -> str:
        return "更新指定待办事项的状态（如标记为完成 completed、进行中 in_progress 等）。"

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer", "description": "待修改的任务 ID"},
                "status": {
                    "type": "string",
                    "enum": ["pending", "in_progress", "completed", "cancelled"],
                    "description": "新状态",
                },
            },
            "required": ["task_id", "status"],
        }

    def execute(self, **kwargs) -> ToolCallResult:
        task_id = kwargs.get("task_id")
        status = kwargs.get("status")

        if not task_id or not status:
            return ToolCallResult.text("错误: 缺少 task_id 或 status 参数", is_error=True)

        try:
            with _db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE todos SET status = ? WHERE id = ?", (status, task_id))
                conn.commit()
                if cursor.rowcount == 0:
                    return ToolCallResult.text(f"未找到 ID 为 {task_id} 的待办事项", is_error=True)

            return ToolCallResult.text(f"✅ 已成功将待办事项 [ID {task_id}] 状态更新为: {status}")
        except Exception as e:
            return ToolCallResult.text(f"更新待办事项失败: {str(e)}", is_error=True)


class TodoDeleteTool(BaseTool):
    @property
    def name(self) -> str:
        return "todo_delete"

    @property
    def description(self) -> str:
        return "根据 ID 从数据库中删除指定的待办事项。"

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer", "description": "需要删除的任务 ID"},
            },
            "required": ["task_id"],
        }

    def execute(self, **kwargs) -> ToolCallResult:
        task_id = kwargs.get("task_id")
        if not task_id:
            return ToolCallResult.text("错误: 缺少 task_id 参数", is_error=True)

        try:
            with _db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM todos WHERE id = ?", (task_id,))
                conn.commit()
                if cursor.rowcount == 0:
                    return ToolCallResult.text(f"未找到 ID 为 {task_id} 的待办事项", is_error=True)

            return ToolCallResult.text(f"🗑️ 已成功删除待办事项 [ID {task_id}]")
        except Exception as e:
            return ToolCallResult.text(f"删除待办事项失败: {str(e)}", is_error=True)


class SQLQueryTool(BaseTool):
    @property
    def name(self) -> str:
        return "sql_query"

    @property
    def description(self) -> str:
        return "在 SQLite 数据库中执行只读或统计类 SQL 查询，返回结构化分析数据。"

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "SELECT 开头的 SQL 查询语句"},
            },
            "required": ["query"],
        }

    def execute(self, **kwargs) -> ToolCallResult:
        query = kwargs.get("query", "").strip()
        if not query:
            return ToolCallResult.text("错误: query 不能为空", is_error=True)

        if not query.lower().startswith("select"):
            return ToolCallResult.text("安全限制: 为保护数据完整性，sql_query 仅允许执行 SELECT 查询", is_error=True)

        try:
            with _db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query)
                rows = cursor.fetchall()
                if not rows:
                    return ToolCallResult.text("查询结果为空。")

                cols = [desc[0] for desc in cursor.description]
                result_list = [dict(zip(cols, row)) for row in rows]
                import json
                return ToolCallResult.text(json.dumps(result_list, ensure_ascii=False, indent=2))
        except Exception as e:
            return ToolCallResult.text(f"SQL 执行失败: {str(e)}", is_error=True)
