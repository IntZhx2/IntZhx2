"""
工具集完整单元测试 (Todo, File, Weather, Math)
"""

import unittest
from pathlib import Path
from smart_agent.tools.todo_tool import (
    TodoAddTool,
    TodoListTool,
    TodoUpdateTool,
    TodoDeleteTool,
    SQLQueryTool,
    _db_manager,
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
from smart_agent.config import WORKSPACE_DIR


class TestToolsSuite(unittest.TestCase):
    def setUp(self):
        # 清空测试数据库表
        with _db_manager.get_connection() as conn:
            conn.execute("DELETE FROM todos")
            conn.commit()

    def test_todo_crud_flow(self):
        add_tool = TodoAddTool()
        list_tool = TodoListTool()
        update_tool = TodoUpdateTool()
        del_tool = TodoDeleteTool()
        sql_tool = SQLQueryTool()

        # 1. 添加任务
        r1 = add_tool.execute(title="完成软工作业", priority="high", category="study")
        self.assertFalse(r1.is_error)
        self.assertIn("成功创建待办事项", r1.get_text())

        # 获取刚插入的任务 ID
        with _db_manager.get_connection() as conn:
            task_id = conn.execute("SELECT id FROM todos WHERE title = '完成软工作业'").fetchone()[0]

        r2 = add_tool.execute(title="准备组队汇报", priority="medium", category="work")
        self.assertFalse(r2.is_error)

        # 2. 查询任务
        list_res = list_tool.execute(status="pending")
        self.assertFalse(list_res.is_error)
        self.assertIn("完成软工作业", list_res.get_text())
        self.assertIn("准备组队汇报", list_res.get_text())

        # 3. 更新状态
        up_res = update_tool.execute(task_id=task_id, status="completed")
        self.assertFalse(up_res.is_error)
        self.assertIn("completed", up_res.get_text())

        # 4. 统计查询 (SQL)
        sql_res = sql_tool.execute(query="SELECT count(*) as total FROM todos")
        self.assertFalse(sql_res.is_error)
        self.assertIn('"total": 2', sql_res.get_text())

        # 5. 删除任务
        del_res = del_tool.execute(task_id=task_id)
        self.assertFalse(del_res.is_error)
        self.assertIn("已成功删除", del_res.get_text())

    def test_file_operations(self):
        write_tool = FileWriteTool()
        read_tool = FileReadTool()
        list_tool = FileListTool()

        test_file = "test_doc.txt"
        test_content = "Hello, SmartAgent File Tool!"

        # 写入
        w_res = write_tool.execute(filepath=test_file, content=test_content)
        self.assertFalse(w_res.is_error)
        self.assertIn("成功写入", w_res.get_text())

        # 读取
        r_res = read_tool.execute(filepath=test_file)
        self.assertFalse(r_res.is_error)
        self.assertIn(test_content, r_res.get_text())

        # 列表
        l_res = list_tool.execute()
        self.assertFalse(l_res.is_error)
        self.assertIn(test_file, l_res.get_text())

    def test_weather_and_travel(self):
        weather_tool = WeatherQueryTool()
        travel_tool = TravelPlanTool()

        # 天气查询
        w_res = weather_tool.execute(city="广州")
        self.assertFalse(w_res.is_error)
        self.assertIn("广州", w_res.get_text())
        self.assertIn("气温", w_res.get_text())

        # 旅游规划
        t_res = travel_tool.execute(destination="广州", days=2)
        self.assertFalse(t_res.is_error)
        self.assertIn("深度出行计划", t_res.get_text())
        self.assertIn("广州塔", t_res.get_text())

    def test_math_calculate(self):
        calc_tool = CalculateTool()

        # 基础四则
        r1 = calc_tool.execute(expression="25 * 4 + 100 / 5")
        self.assertFalse(r1.is_error)
        self.assertIn("120", r1.get_text())

        # 括号与函数
        r2 = calc_tool.execute(expression="sqrt(144) + 8")
        self.assertFalse(r2.is_error)
        self.assertIn("20", r2.get_text())

        # 除以零异常捕获
        r3 = calc_tool.execute(expression="10 / 0")
        self.assertTrue(r3.is_error)
        self.assertIn("除数不能为 0", r3.get_text())


if __name__ == "__main__":
    unittest.main()
