# 广东工业大学 2026 软件工程课程作业与项目仓库

[![Language](https://img.shields.io/badge/Language-Python-blue.svg)](https://github.com/)
[![Course](https://img.shields.io/badge/Course-软件工程-brightgreen.svg)](https://edu.cnblogs.com/campus/gdgy/Class56-Grade2024-CS/)
[![Blog](https://img.shields.io/badge/Blog-博客园-orange.svg)](https://www.cnblogs.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

本项目为 **广东工业大学计算机学院 2024 级软件工程课程** 专属实践代码与项目沉淀仓库。记录大学期间在个人开发、结对协作及团队项目中的代码演进、测试用例与工程文档。

---

## 👨‍💻 作者与课程信息

- **学校**：广东工业大学（GDUT）
- **专业班级**：24 计科 6班
- **学号**：3124004113
- **博客园主页**：[点击访问我的博客园主页](https://www.cnblogs.com/IntZhx2)
- **班级课程链接**：[Class56-Grade2024-CS](https://edu.cnblogs.com/campus/gdgy/Class56-Grade2024-CS/)

---

## 📂 项目目录导航

- [3124004113 - 个人项目：论文查重系统](3124004113/README.md)
  - 核心模块：`main.py`、`text_processor.py`、`similarity_checker.py`
  - 测试套件：22 个全覆盖单元测试 `tests/test_checker.py`
  - 性能分析：cProfile 基准与报告 `profile/`
  - 课程博客：[完整作业博文](3124004113/BLOG.md)
  - 任务耗时：[PSP 2.1 记录表](3124004113/PSP.md)

- [结对项目 - 小学四则运算题目生成器与批改系统](pair_project/README.md)
  - 成员：赵海翔（3124004113）、何卓文（3124004132）
  - 核心模块：`main.py`、`expression.py`、`generator.py`、`renderer.py`、`parser.py`、`grader.py`
  - 测试套件：44 个全覆盖自动化测试 `tests/test_arithmetic.py`
  - 性能剖析：10000 题规模 cProfile 报告与图表 `profile/`（生成 0.686 秒，批改 0.241 秒）
  - 结对博客：[完整结对作业博文](pair_project/BLOG.md)
  - 任务耗时：[PSP 2.1 记录表](pair_project/docs/PSP.md)
  - 效能报告：[性能分析与优化](pair_project/docs/performance.md)

