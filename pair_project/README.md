# 小学四则运算题目生成器（结对项目）

[![Language](https://img.shields.io/badge/Language-Python%203.11+-blue.svg)](https://www.python.org/)
[![Course](https://img.shields.io/badge/Course-软件工程-brightgreen.svg)](https://edu.cnblogs.com/campus/gdgy/Class56-Grade2024-CS/)
[![Homework](https://img.shields.io/badge/Homework-结对项目15694-orange.svg)](https://edu.cnblogs.com/campus/gdgy/Class56-Grade2024-CS/homework/15694)
[![Tests](https://img.shields.io/badge/Tests-38%20Passed-success.svg)](tests/test_arithmetic.py)

本项目为 **广东工业大学 2024 级计算机学院软件工程课程**【第三周结对项目：小学四则运算题目生成器】的完整实现。

- **项目成员**：
  - 赵海翔（学号：3124004113，GitHub: [IntZhx2](https://github.com/IntZhx2)，24 计科 6班）
  - 何卓文（学号：3124004132，GitHub: [reminderxxx](https://github.com/reminderxxx)，24 计科 6班）
- **作业要求**：[结对项目作业要求（homework/15694）](https://edu.cnblogs.com/campus/gdgy/Class56-Grade2024-CS/homework/15694)
- **博客规范**：[软件工程博客规范（homework/15692）](https://edu.cnblogs.com/campus/gdgy/Class56-Grade2024-CS/homework/15692)
- **作业博客**：[点击访问博客园结对项目博文](BLOG.md)

---

## 🌟 核心功能与亮点

1. **题目生成与自动求解**：
   - 随机生成包含 $1 \sim 3$ 个四则运算符（`+`、`−`、`×`、`÷`）的小学四则运算题目；
   - 支持自然数、真分数（如 `3/5`）与带分数（如 `1'1/2`）；
   - 输出题目文件 `Exercises.txt` 与对应标准答案文件 `Answers.txt`。
2. **作业自动批改**：
   - 支持读取指定的题目文件与答案文件；
   - 使用自定义递归下降解析器进行语法分析与高精度求值，杜绝使用危险的 `eval()`；
   - 自动对比并统计题目对错，输出规范的批改报告 `Grade.txt`。
3. **严格的算术约束**：
   - **减法非负**：计算过程中任何子表达式 $e_1 − e_2$ 均保证 $e_1 \ge e_2$；
   - **除法规范**：除数不为 0，且除法结果保证为正非整数有理数，大于 1 时自动转为带分数格式；
   - **等价题去重**：加法与乘法遵循交换律，基于表达式树递归构造规范化键（Canonical Key），单次运行绝无等价重复题目；
   - **高精度计算**：全部使用原生 `fractions.Fraction`，彻底避免浮点数舍入误差。
4. **极致性能**：
   - 生成 10,000 道有效题目与标准答案仅需 **0.65 秒**；
   - 全量批改 10,000 道题目仅需 **0.19 秒**；
   - 零第三方外部依赖，原生标准库即开即用。

---

## 🚀 命令行使用规范

### 1. 生成模式

```bash
# 生成 10 道题目，数值及分母上限为 10
python3 main.py -n 10 -r 10

# 生成 10000 道题目，数值及分母上限为 10
python3 main.py -n 10000 -r 10
```

- `-n`：生成题目的个数（支持正整数，默认 10）；
- `-r`：题目中数值（自然数、真分数和真分数分母）的数值上限（**必须提供**，否则程序报错退出）；
- 生成文件写入当前执行目录下的 `Exercises.txt` 与 `Answers.txt`。

#### 输出示例

`Exercises.txt`：
```text
1.  9 + 5 =
2.  2/9 ÷ (8’5/7 + 1) =
3.  0 × (2 + 5/8) =
```

`Answers.txt`：
```text
1.  14
2.  7/306
3.  0
```

---

### 2. 批改模式

```bash
# 读取题目与答案文件并进行自动化批改
python3 main.py -e Exercises.txt -a Answers.txt
```

- `-e`：题目文件路径；
- `-a`：答案文件路径；
- 批改结果写入当前目录下的 `Grade.txt`。

#### 输出示例

`Grade.txt`：
```text
Correct: 2 (1, 3)
Wrong: 1 (2)
```

---

## 🧪 自动化测试套件

项目包含 38 项单元测试，覆盖基础四则运算、带分数格式化、等价去重、递归下降解析器、批改引擎、边界值及命令行互斥异常：

```bash
cd pair_project
python3 -m unittest discover -s tests -p "test_*.py" -v
```

执行结果：
```text
Ran 38 tests in 0.162s
OK
```

---

## 📊 性能剖析与基准压测

使用内置 `cProfile` 工具进行 10,000 题的大规模性能测试：

```bash
cd pair_project
python3 profile/benchmark_10k.py
```

报告将保存至 `profile/profile_report.txt`，详见 [效能分析报告](docs/performance.md)。

---

## 📂 项目结构

```text
pair_project/
├── main.py                     # CLI 主入口：参数解析、模式分发与非零退出码管理
├── arithmetic/                 # 核心算法业务包
│   ├── __init__.py             # 包导出声明
│   ├── errors.py               # 自定义异常体系
│   ├── expression.py           # 表达式树、精确求值与规范化去重键
│   ├── generator.py            # 随机题目生成、单遍递归约束检查与去重引擎
│   ├── renderer.py             # 中缀表达式渲染、带分数与括号格式化
│   ├── parser.py               # 自定义递归下降表达式与答案解析器（不依赖 eval）
│   └── grader.py               # 答案批量比对与 Grade.txt 生成引擎
├── tests/                      # 自动化测试套件
│   ├── __init__.py
│   └── test_arithmetic.py      # 38 项单元测试
├── profile/                    # 性能剖析与基准压测
│   ├── benchmark_10k.py        # 10000 题压测基准脚本
│   └── profile_report.txt      # cProfile 采样分析报告
├── docs/                       # 工程文档
│   ├── PSP.md                  # PSP 2.1 任务耗时表
│   └── performance.md          # 详细效能分析与优化记录
├── BLOG.md                     # 严格符合 15692 规范的结对项目课程博文
└── README.md                   # 本文档
```
