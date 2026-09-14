# 论文查重系统（个人项目）

- **学号**：3124004113
- **课程**：广东工业大学 2026 计算机学院软件工程课程
- **作业要求链接**：[广东工业大学 2024 级软工个人项目作业要求](https://edu.cnblogs.com/campus/gdgy/Class56-Grade2024-CS/homework/15693)
- **作业博客链接**：[博客园作业文章](https://www.cnblogs.com/IntZhx2)

---

## 🌟 项目简介

本程序是基于 Python 3 实现的高效、鲁棒的中文论文查重系统。算法结合 **2-gram 字符滑动窗口切片**、**64 位加权 SimHash 指纹** 与 **向量余弦相似度**，能够精准衡量文本在增、删、改、乱序及段落重构等各种抄袭改写场景下的重复率。

### 核心特性

- **零外部第三方库依赖**：纯 Python 标准库原生实现（内置 `hashlib`、`collections`、`unicodedata`），不需要安装 `jieba` 或其他三方依赖，避免在评测机因缺少依赖引发 `ModuleNotFoundError`。
- **全编码自适应容错**：自动识别 UTF-8（含 BOM）、GBK、GB18030、Big5、UTF-16 编码，避免乱码；内置 HTML 标签清洗容错能力。
- **高性能**：37 万字大文本查重端到端耗时仅约 **0.37 秒**，远低于 5 秒限时要求。
- **高测试覆盖率**：内置 22 项单元测试，覆盖常规场景、极端边界（空文本、纯标点、单字符）与异常处理（参数不足、文件缺失、目录输入等）。

---

## 🚀 运行方法

### 命令行调用规范

程序严格遵从课程要求，接收三个**绝对路径**参数：

```bash
python3 main.py <原文文件绝对路径> <抄袭版论文文件绝对路径> <答案文件绝对路径>
```

#### 运行示例

```bash
# 切换到项目目录
cd 3124004113

# 运行查重测试（参数支持相对路径与绝对路径，程序内部自动转为绝对路径）
python3 main.py samples/orig.txt samples/orig_0.8_add.txt ans.txt

# 查看生成的答案文件
cat ans.txt
# 输出示例：0.87
```

答案文件中输出的查重率为浮点型，精确到小数点后两位（`0.00` ~ `1.00`）。

---

## 🧪 单元测试

项目包含 22 个单元测试用例，覆盖全部算法逻辑与异常场景：

```bash
cd 3124004113
python3 -m unittest discover -s tests -p "test_*.py" -v
```

所有测试均可一键通过。

---

## 📊 性能分析 (cProfile)

使用 Python 内置的 `cProfile` 工具对超大文本进行 CPU 采样剖析：

```bash
cd 3124004113
# 执行性能测试基准
python3 profile/benchmark_profile.py

# 生成详细性能分析报告
python3 profile/profile_analysis.py
cat profile/profile_report.txt
```

---

## 📁 目录结构

```text
3124004113/
├── main.py                     # 命令行主入口：绝对路径参数解析、异常捕获、非零退出码管理
├── text_processor.py           # 文本处理模块：编码自适应识别、BOM清除、文本清洗归一化
├── similarity_checker.py       # 核心算法模块：2-gram 特征提取、SimHash 降维与余弦相似度融合
├── samples/                    # 课程下发的官方测试文本集（orig.txt, orig_0.8_add.txt 等）
├── tests/
│   ├── __init__.py
│   └── test_checker.py         # 22 个全覆盖单元测试
├── profile/
│   ├── benchmark_profile.py    # 37 万字大规模文本压测基准脚本
│   ├── profile_analysis.py     # cProfile 报告解析与优化对比生成脚本
│   └── profile_report.txt      # 性能测试详细输出报告
├── PSP.md                      # PSP 2.1 任务耗时估算与实际耗时对比表
├── BLOG.md                     # 符合老师要求的博客园 7 大模块完整长文草稿
└── README.md                   # 本文档
```
