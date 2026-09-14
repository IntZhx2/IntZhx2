| 这个作业属于哪个课程 | [广东工业大学计算机学院 2024 级软件工程](https://edu.cnblogs.com/campus/gdgy/Class56-Grade2024-CS) |
| :--- | :--- |
| 这个作业要求在哪里 | [软件工程个人项目作业要求 - 论文查重](https://edu.cnblogs.com/campus/gdgy/Class56-Grade2024-CS/homework/15693) |
| 这个作业的目标 | 熟练掌握现代软件工程开发流程，设计高鲁棒性论文查重系统，践行 PSP 流程、代码规范、单元测试、性能调优及 Git 版本控制 |
| 作业的 GitHub 链接 | [IntZhx2/IntZhx2 - 3124004113](https://github.com/IntZhx2/IntZhx2/tree/main/3124004113) |

---

# 软件工程个人项目：论文查重系统设计与实现

## 一、PSP 2.1 表格（预估阶段）

在正式开始编码与设计之前，我根据任务要求，对软件工程开发全生命周期各阶段所需耗时进行了客观预估：

| PSP 2.1 | Personal Software Process Stages | 预估耗时（分钟） | 实际耗时（分钟） |
| :--- | :--- | :--- | :--- |
| **Planning** | **计划** | **30** | **25** |
| · Estimate | · 估计这个任务需要多少时间 | 30 | 25 |
| **Development** | **开发** | **385** | **350** |
| · Analysis | · 需求分析（包括学习新技术与算法调研） | 45 | 40 |
| · Design Spec | · 生成设计文档（模块划分与接口定义） | 30 | 25 |
| · Design Review | · 设计复审（确认输入输出规范与编码自适应） | 15 | 15 |
| · Coding Standard | · 代码规范（PEP 8 命名与格式约定） | 15 | 10 |
| · Design | · 具体设计（SimHash 与 Cosine 融合算法设计） | 40 | 35 |
| · Coding | · 具体编码（数据处理、算法实现与 CLI 入口） | 100 | 95 |
| · Code Review | · 代码复审（代码审查与潜在异常排查） | 30 | 25 |
| · Test | · 测试（单元测试编写、边界排查与修复） | 110 | 105 |
| **Reporting** | **报告** | **115** | **105** |
| · Test Report | · 测试报告与覆盖率分析 | 40 | 35 |
| · Size Measurement | · 计算工作量（代码行数与测试覆盖统计） | 15 | 15 |
| · Postmortem & Process Improvement Plan | · 事后总结并提出过程改进计划 | 60 | 55 |
| **合计** |  | **530** | **480** |

---

## 二、计算模块接口的设计与实现过程

### 2.1 模块架构划分与职责
本项目严格采用高内聚、低耦合的分层架构设计思想，代码组织清晰，职责明确：

```text
3124004113/
├── main.py                     # 命令行主入口：接收三个绝对路径、异常分流与答案文件写入
├── text_processor.py           # 文本处理模块：编码自适应识别、HTML 标签清洗、Unicode 归一化
├── similarity_checker.py       # 核心算法模块：2-gram 特征提取、64 位加权 SimHash 与余弦融合
└── tests/test_checker.py       # 测试模块：22 个覆盖常规、极端边界及异常场景的单元测试
```

- **`main.py`（命令行门面层）**：负责接收与校验命令行参数，调用底层模块，统一拦截各类 I/O 与业务异常，向标准错误输出友好中文提示，并把两位小数的浮点数写入指定答案文件。
- **`TextProcessor` 类（数据清洗与预处理层）**：专注于文件读取与字符规范化。自动识别各种常见编码，提供 HTML 标签剥离容错，执行 `Unicode NFKC` 归一化，剔除非字符噪音。
- **`SimilarityChecker` 类（核心计算层）**：纯内存算法接口，完全与文件 I/O 隔离。接收两份已归一化的纯文本，计算其 `[0.00, 1.00]` 范围内的重复率。

### 2.2 核心业务流程图

```text
接收命令行 3 个绝对路径参数
    │
    ▼
检查参数个数是否为 3 个（否则报错并以退出码 2 退出）
    │
    ▼
检查原文与抄袭版文件是否存在（否则报错并以退出码 1 退出）
    │
    ▼
读取两份文件内容（自动尝试 UTF-8、GBK 等编码，清除 BOM，剥离 HTML 标签）
    │
    ▼
文本清洗与归一化（NFKC 统一全角半角、英文转小写、过滤标点符号与空白）
    │
    ▼
短路快速判断（两份文本相同直接返回 1.00，任一文本为空返回 0.00）
    │
    ▼
提取 2-gram 字符滑动切片并统计词频 Counter
    │
    ▼
计算 64 位加权 SimHash 海明距离 与 共有特征余弦相似度
    │
    ▼
加权得出最终重复率，保留两位小数写入答案文件（正常退出码 0）
```

### 2.3 核心查重算法原理解析

在中文长文本查重领域，传统的结巴分词（`jieba`）依赖静态外部词典，在面对网络文本随机增删字、恶意改写、拼音同音替换时，极易导致分词破碎，且冷启动加载词典需要耗费近 1 秒。为此，本项目设计了基于 **字符级 2-gram 滑动窗口** 的 **加权 SimHash 与余弦相似度融合算法**：

1. **字符级 2-gram 特征抽取**：
   对清洗后的纯文本按相邻 2 个字符滑动切片（例如：“软件工程实践” 切分为 `['软件', '件工', '工程', '程实', '实践']`）。该方案无需词典即可精准刻画局部字序逻辑，对于文本增字、删字具有很强的鲁棒性。
2. **64 位加权 SimHash 指纹降维**：
   - 针对每一个 2-gram 切片特征，利用内置的 `hashlib.md5` 计算其 64 位确定性散列值；
   - 建立长度为 64 的向量，以特征在文本中出现的频次作为权重。若对应位为 1 则加上权重，为 0 则减去权重；
   - 最终向量大于 0 的位记为 1，其余记为 0，压缩为单个 64 位的二进制整数指纹。
3. **海明距离（Hamming Distance）计算**：
   计算原文指纹与抄袭版指纹异或后二进制中 1 的个数：
   海明距离 d = bin(指纹1 ^ 指纹2).count('1')
   SimHash 相似度 = 1.0 - (d / 64.0)
4. **多重集余弦相似度融合与阻尼**：
   利用两篇文本的切片频次 Counter 计算余弦夹角：
   余弦相似度 = 共有特征词频点积 / (原文特征向量模长 × 抄袭版特征向量模长)
   最终得分通过 `0.50 × SimHash相似度 + 0.50 × 余弦相似度` 线性融合，兼顾全局宏观主题分布与局部字词精确匹配。

### 2.4 独到之处

1. **零第三方库外部依赖（Zero-Dependency）**：全套算法仅依赖 Python 标准库（`hashlib`、`collections`、`unicodedata`），不需要通过 `pip` 安装任何第三方库，评测机秒级启动，免除依赖缺失风险。
2. **全编码自适应与 HTML 包装自动清洗**：自动兼容 UTF-8（含 BOM）、GBK、GB18030、Big5、UTF-16 等格式；针对从网页右键另存为带有 `<!DOCTYPE html>` 的文件，能够自动剥离标签提取纯正文。
3. **稀疏点积与交集优化**：在余弦相似度计算中，通过 Python 内置的高性能集合交集运算 `common_keys = c1.keys() & c2.keys()`，避免了传统遍历全量字典产生的无效计算，将算法点积复杂度优化至 O(共有特征数)。
4. **哈希确定性保证**：放弃 Python 默认带随机盐的内置 `hash()`，选用 `hashlib.md5`，确保在任何操作系统、不同进程重启后计算结果百分之百可复现。

---

## 三、计算模块接口部分的性能改进

### 3.1 性能测试环境与压测设定
为了验证算法在极端压力下的运行效率，专门编写了性能压测脚本 `profile/benchmark_profile.py`：
- **测试环境**：macOS (Apple Silicon M 系列芯片 / Python 3.9)
- **输入规模**：以官方测试文本为基准，构造包含随机增删改扰动的 **368,795 字符（近 37 万字）** 超大规模文本对。
- **分析工具**：Python 原生 `cProfile` 与 `pstats` 性能剖析套件。

### 3.2 性能分析采样数据与调用耗时

运行 `cProfile` 采集到的前 8 个热点函数如下表所示：

| 调用次数 (ncalls) | 函数净耗时 (tottime/s) | 累计耗时 (cumtime/s) | 涉及函数与代码行 | 耗时机理解析 |
| :--- | :--- | :--- | :--- | :--- |
| 1 | 0.004 | 0.206 | `similarity_checker.py:calculate_similarity` | 查重主控逻辑与调度 |
| 2 | 0.000 | 0.146 | `text_processor.py:normalize` | 文本 Unicode 归一化与清洗 |
| 2 | 0.101 | 0.106 | `similarity_checker.py:compute_simhash` | 64 位特征 MD5 哈希与权重向量累加 |
| 2 | 0.098 | 0.098 | `{built-in method unicodedata.normalize}` | C 底层 NFKC 字符标准化 |
| 2 | 0.000 | 0.094 | `similarity_checker.py:extract_ngrams` | 2-gram 切片与 Counter 频次构建 |
| 2 | 0.064 | 0.064 | `similarity_checker.py:<listcomp>` | 列表推导式生成切片子串 |
| 2 | 0.039 | 0.039 | `{method 'findall' of 're.Pattern'}` | 正则过滤非中英文及数字 |
| 2 | 0.028 | 0.028 | `{_collections._count_elements}` | C 底层 Counter 频次快速累加 |

### 3.3 性能耗时甘特图

各阶段耗时分布统计（总耗时约 0.372 秒）：

| 阶段步骤 | 核心操作 | 耗时 (毫秒) | 耗时占比 | 说明 |
| :--- | :--- | :---: | :---: | :--- |
| **阶段一：文本归一化** | Unicode NFKC 标准化、正则过滤标点符号 | 146 ms | 39.2% | 遍历近 37 万字符完成清洗 |
| **阶段二：特征工程** | 2-gram 字符滑动切片、Counter 频次统计 | 94 ms | 25.3% | 生成并聚合切片特征字典 |
| **阶段三：相似度计算** | 64 位 MD5 降维、特征交集点积计算 | 112 ms | 30.1% | 纯数学指纹与余弦向量计算 |
| **阶段四：调度与其他** | 函数调用调度、边界判断开销 | 20 ms | 5.4% | 运行环境准备与退出清理 |

从耗时分布可以看出，文本归一化与哈希计算是主要的 CPU 消耗环节，但在 Python 标准库 C 底层实现的支持下，整体处理 37 万字大文本仅需 0.37 秒，表现非常理想。

### 3.4 针对性优化措施与成效

1. **余弦计算的稀疏交集优化**：
   - **优化前**：早期方案直接对两篇文本的全量特征空间进行笛卡尔式对齐，当特征量达到数十万时，循环内部充斥着大量 `0 * 0` 的无效乘法。
   - **优化后**：先通过 `c1.keys() & c2.keys()` 获取两者共有切片键集，仅遍历该交集进行乘积累加，点积计算耗时从 0.08 秒骤降至 0.004 秒以下。
2. **底层 C 扩展代替纯 Python 统计**：
   - 提取 2-gram 时，直接使用列表推导式结合 `Counter` 的底层 C 实现 `_collections._count_elements`，比手动 `for` 循环操作字典提速 40% 以上。
3. **优化成果**：
   在单次高达 37 万字符的严苛压测下，全流程总耗时仅为 **0.372 秒**，相比作业要求的 5 秒时限，运行速度有超过 13 倍的充足性能余量。

---

## 四、计算模块部分单元测试展示

### 4.1 测试数据设计思路
测试用例依据等价类划分、边界值分析与白盒分支覆盖准则设计，在 `tests/test_checker.py` 中实现了 **22 个全自动化单元测试用例**：
1. **常规等价类**：完全相同文本（预期 1.00）、完全不相干文本（预期 0.00）、中英文混合文本。
2. **极端边界等价类**：双方均为空文本（1.00）、单方为空文本（0.00）、纯标点符号/空格文本（清洗后视为空）、超短单字符文本（1 字符回退机制）。
3. **编码与格式等价类**：全角半角转换（`１２３` vs `123`）、英文大小写无关性、UTF-8 带 BOM 文件读取、GBK 编码文件读取。
4. **官方测试集验证**：对官方下发的增字、删字、改字（距离 1、10、15）共 5 组样本设计专项测试，验证查重率落入合理区间。
5. **异常与健壮性等价类**：命令行参数不足（退出码 2）、输入文件不存在（退出码 1）、输入路径为目录（退出码 1）。

### 4.2 核心测试代码片段展示

```python
# 1. 验证完全不相干的两段文本（量子物理 vs 红烧排骨），断言相似度小于 0.20（实际为 0.00）
def test_02_completely_different(self):
    t1 = TextProcessor.normalize("量子纠缠与广义相对论的引力奇点假说")
    t2 = TextProcessor.normalize("红烧排骨的做法是将肉洗净后焯水爆炒至金黄色")
    score = self.checker.calculate_similarity(t1, t2)
    self.assertLess(score, 0.20)

# 2. 验证纯标点符号文本，清洗归一化后均为空串，判定为完全一致
def test_06_punctuation_only(self):
    t1 = "！！！？？？，，，。。。"
    t2 = "，，，！！！"
    norm1 = TextProcessor.normalize(t1)
    norm2 = TextProcessor.normalize(t2)
    self.assertEqual(norm1, "")
    self.assertEqual(norm2, "")
    score = self.checker.calculate_similarity(norm1, norm2)
    self.assertEqual(score, 1.00)

# 3. 验证官方增补样本测试 (orig.txt vs orig_0.8_add.txt)，查重率应在 0.70 到 0.98 之间
def test_11_sample_orig_add(self):
    f1 = os.path.join(self.samples_dir, 'orig.txt')
    f2 = os.path.join(self.samples_dir, 'orig_0.8_add.txt')
    t1 = TextProcessor.normalize(TextProcessor.read_file(f1))
    t2 = TextProcessor.normalize(TextProcessor.read_file(f2))
    score = self.checker.calculate_similarity(t1, t2)
    self.assertTrue(0.70 <= score <= 0.98, f"Score: {score}")

# 4. 验证命令行参数不足时返回非零退出码 2 并向 stderr 输出用法说明
def test_20_cli_wrong_arg_count(self):
    cmd = [sys.executable, os.path.join(parent_dir, 'main.py'), 'only_one_param']
    res = subprocess.run(cmd, capture_output=True, text=True)
    self.assertEqual(res.returncode, 2)
    self.assertIn('参数数量不正确', res.stderr)
```

### 4.3 单元测试运行结果与覆盖率展示

在终端执行 `python3 -m unittest discover -s tests -p "test_*.py" -v`，全部 22 项测试均一次性通过：

```text
test_01_identical_text (test_checker.TestPlagiarismChecker)
测试完全相同的文本返回 1.00 ... ok
test_02_completely_different (test_checker.TestPlagiarismChecker)
测试完全不相干的文本返回接近 0.00 ... ok
test_03_both_empty (test_checker.TestPlagiarismChecker)
测试双方均为空文本时返回 1.00 ... ok
test_04_one_empty_orig (test_checker.TestPlagiarismChecker)
测试原文为空时返回 0.00 ... ok
test_05_one_empty_suspect (test_checker.TestPlagiarismChecker)
测试抄袭文本为空时返回 0.00 ... ok
test_06_punctuation_only (test_checker.TestPlagiarismChecker)
测试纯标点符号清洗后视为空文本 ... ok
test_07_whitespace_and_newlines (test_checker.TestPlagiarismChecker)
测试空格与换行不影响查重结果 ... ok
test_08_fullwidth_halfwidth (test_checker.TestPlagiarismChecker)
测试全角与半角字符归一化 ... ok
test_09_case_insensitivity (test_checker.TestPlagiarismChecker)
测试英文字母大小写无关性 ... ok
test_10_short_text_fallback (test_checker.TestPlagiarismChecker)
测试超短文本（少于 2 个字符）能平滑回退 ... ok
test_11_sample_orig_add (test_checker.TestPlagiarismChecker)
测试官方增字样本 orig_0.8_add.txt ... ok
test_12_sample_orig_del (test_checker.TestPlagiarismChecker)
测试官方删字样本 orig_0.8_del.txt ... ok
test_13_sample_orig_dis_1 (test_checker.TestPlagiarismChecker)
测试官方距离-1 样本 orig_0.8_dis_1.txt ... ok
test_14_sample_orig_dis_10 (test_checker.TestPlagiarismChecker)
测试官方距离-10 样本 orig_0.8_dis_10.txt ... ok
test_15_sample_orig_dis_15 (test_checker.TestPlagiarismChecker)
测试官方距离-15 样本 orig_0.8_dis_15.txt ... ok
test_16_utf8_bom_handling (test_checker.TestPlagiarismChecker)
测试 UTF-8 带 BOM 文件读取 ... ok
test_17_gbk_encoding (test_checker.TestPlagiarismChecker)
测试 GBK 编码文件读取 ... ok
test_18_simhash_deterministic (test_checker.TestPlagiarismChecker)
测试算法计算的完全确定性 ... ok
test_19_cli_correct_usage (test_checker.TestPlagiarismChecker)
测试命令行端到端调用：成功返回 0，答案精确写入两位小数 ... ok
test_20_cli_wrong_arg_count (test_checker.TestPlagiarismChecker)
测试命令行参数不足时退出码为 2 并打印提示 ... ok
test_21_cli_file_not_found (test_checker.TestPlagiarismChecker)
测试输入文件不存在时退出码为 1 ... ok
test_22_cli_directory_input_error (test_checker.TestPlagiarismChecker)
测试输入路径为目录时退出码为 1 ... ok

----------------------------------------------------------------------
Ran 22 tests in 0.591s

OK
```

核心算法与业务处理代码的分支和语句覆盖率达到 **95% 以上**，达到了白盒测试与质量保障的要求。

---

## 五、计算模块部分异常处理说明

### 5.1 命令行参数数量异常（缺少或多传参数）
- **设计目标**：防止数组索引越界，向标准错误输出详细规范用法，返回退出码 2。
- **对应单元测试**：`test_20_cli_wrong_arg_count`，只传一个参数时，验证捕获退出码 2 且 `stderr` 打印错误提示。

### 5.2 输入文件不存在或为目录路径
- **设计目标**：传入不存在的文件名或目录路径时，给出明确错误提示，退出码置为 1，且**绝对不生成或污染答案文件**。
- **对应单元测试**：`test_21_cli_file_not_found` 与 `test_22_cli_directory_input_error`，验证断言答案文件未生成，进程以 1 退出。

### 5.3 编码未知与乱码兼容
- **设计目标**：中文环境下常见 GBK、GB18030、带 BOM 的 UTF-8 文件，直接按 UTF-8 解码会抛出 `UnicodeDecodeError` 崩溃。`TextProcessor.read_file` 采用编码梯次解码法，并提供安全替换容错。
- **对应单元测试**：`test_16_utf8_bom_handling` 与 `test_17_gbk_encoding`。

### 5.4 零长度与纯标点文本边界防护
- **设计目标**：清洗后文本长度可能为 0，若直接执行切片或计算分母模长会产生 `ZeroDivisionError`。算法设立短路防护分支：双方皆无正文返回 1.00，一方无正文返回 0.00。
- **对应单元测试**：`test_03_both_empty`、`test_04_one_empty_orig`、`test_06_punctuation_only`。

---

## 六、在开发过程中遇到的问题与解决记录

在整个项目的实际推进中，记录了两次具有代表性的调试经历与反思：

1. **官方测试样本文件包装问题**：
   - **问题现象**：在分析班级群下发的测试样本时，发现 `orig_0.8_del.txt` 以及部分 `dis` 样本的文件体积异常偏大，文本首行为 `<!DOCTYPE html>`。
   - **排查原因**：排查后确认是部分同学在 GitHub 网页上通过右键“另存为”下载了文件，将 GitHub 的整张代码浏览网页 HTML 下载了下来。
   - **解决策略**：在 `TextProcessor` 中加入了 HTML 结构检测。当文件含有 `<html` 标签时，自动提取内部代码行正文，使程序既能直接兼容纯文本，又能自动纠偏网页另存为文件，大幅增强了现实鲁棒性。
2. **纯随机散列与余弦阻尼调整**：
   - **问题现象**：在初版单元测试中，两段毫无关系的文本（量子物理 vs 红烧排骨）测出的相似度达到了 0.25 左右，未达到接近 0 的预期。
   - **排查原因**：纯 64 位 SimHash 在两个完全随机无关的特征向量之间，海明距离的数学期望值约为 32 位（即 50% 相似）。单纯线性加权会将这个噪声带入最终分数。
   - **解决策略**：在相似度算法中增加了特征交集检测。当两篇文本的共同切片集合为空时，直接确立相似度为 0.00；对于重合率极低的稀疏文本引入重合度阻尼系数，完美解决了无关文本的底噪误判。

---

## 七、PSP 表格（实际耗时对比与过程改进计划）

### 7.1 PSP 实际耗时对比

| PSP 2.1 | Personal Software Process Stages | 预估耗时（分钟） | 实际耗时（分钟） | 耗时偏差 |
| :--- | :--- | :--- | :--- | :--- |
| **Planning** | **计划** | **30** | **25** | -5 |
| · Estimate | · 估计这个任务需要多少时间 | 30 | 25 | -5 |
| **Development** | **开发** | **385** | **350** | -35 |
| · Analysis | · 需求分析（包括学习新技术与算法调研） | 45 | 40 | -5 |
| · Design Spec | · 生成设计文档（模块划分与接口定义） | 30 | 25 | -5 |
| · Design Review | · 设计复审（确认输入输出规范与编码自适应） | 15 | 15 | 0 |
| · Coding Standard | · 代码规范（PEP 8 命名与格式约定） | 15 | 10 | -5 |
| · Design | · 具体设计（SimHash 与 Cosine 融合算法设计） | 40 | 35 | -5 |
| · Coding | · 具体编码（数据处理、算法实现与 CLI 入口） | 100 | 95 | -5 |
| · Code Review | · 代码复审（代码审查与潜在异常排查） | 30 | 25 | -5 |
| · Test | · 测试（单元测试编写、边界排查与修复） | 110 | 105 | -5 |
| **Reporting** | **报告** | **115** | **105** | -10 |
| · Test Report | · 测试报告与覆盖率分析 | 40 | 35 | -5 |
| · Size Measurement | · 计算工作量（代码行数与测试覆盖统计） | 15 | 15 | 0 |
| · Postmortem & Process Improvement Plan | · 事后总结并提出过程改进计划 | 60 | 55 | -5 |
| **合计** |  | **530** | **480** | **-50 (-9.4%)** |

### 7.2 过程改进计划（Postmortem）

1. **测试驱动开发（TDD）实践**：在本次项目中，单元测试大多在编码完成后补齐，导致部分边界情况在测试时才被发现并进行回溯修改。在后续的结对项目和团队项目中，应当尝试先定义接口与测试用例，再行实现业务代码，降低重构成本。
2. **性能基准固化**：利用 cProfile 定位性能热点的做法非常直观有效。未来可以把性能基准测试与自动化测试集成到持续集成工作流中，当代码变更导致耗时回退时自动预警。
