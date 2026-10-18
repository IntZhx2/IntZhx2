"""
智能旅游规划 MCP 工具集 (Travel Agent Tools)
汇集并导出旅游攻略规划的核心工具：天气与防护、交通与换乘规划、景点深度情报与美食打卡、行程归档导出。
"""

from typing import List
from smart_agent.tools.base import BaseTool
from smart_agent.tools.weather_tool import WeatherQueryTool
from smart_agent.tools.traffic_tool import TrafficTransitTool
from smart_agent.tools.attraction_tool import AttractionInfoTool
from smart_agent.tools.itinerary_tool import ItinerarySaveTool, ItineraryListTool


def create_default_tools() -> List[BaseTool]:
    """实例化并返回所有专属旅游规划 MCP 工具"""
    return [
        WeatherQueryTool(),
        TrafficTransitTool(),
        AttractionInfoTool(),
        ItinerarySaveTool(),
        ItineraryListTool(),
    ]
