"""
智能体工具集合包
汇总并导出所有符合 MCP 标准的工具类。
"""

from typing import List
from smart_agent.tools.base import BaseTool
from smart_agent.tools.todo_tool import (
    TodoAddTool,
    TodoListTool,
    TodoUpdateTool,
    TodoDeleteTool,
    SQLQueryTool,
)
from smart_agent.tools.file_tool import (
    FileReadTool,
    FileWriteTool,
    FileListTool,
)
from smart_agent.tools.weather_tool import (
    WeatherQueryTool,
    TravelPlanTool,
)
from smart_agent.tools.math_tool import CalculateTool


def create_default_tools() -> List[BaseTool]:
    """实例化并返回所有默认系统工具"""
    return [
        TodoAddTool(),
        TodoListTool(),
        TodoUpdateTool(),
        TodoDeleteTool(),
        SQLQueryTool(),
        FileReadTool(),
        FileWriteTool(),
        FileListTool(),
        WeatherQueryTool(),
        TravelPlanTool(),
        CalculateTool(),
    ]
