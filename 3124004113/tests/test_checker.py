"""
test_checker.py
单元测试套件：覆盖论文查重核心算法、预处理、边界情况、文件异常与命令行接口
共包含 22 个单元测试用例
"""
import os
import sys
import shutil
import tempfile
import subprocess
import unittest

# 确保能导入待测模块
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from text_processor import TextProcessor
from similarity_checker import SimilarityChecker
from main import run_plagiarism_check

class TestPlagiarismChecker(unittest.TestCase):
    """单元测试类"""

    @classmethod
    def setUpClass(cls):
        cls.checker = SimilarityChecker()
        cls.samples_dir = os.path.join(parent_dir, 'samples')

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # ---------------- 算法与预处理测试 ----------------

    def test_01_identical_text(self):
        """测试完全相同的文本返回 1.00"""
        text = "今天是星期天，天气晴朗，今天晚上我要去看电影。"
        norm = TextProcessor.normalize(text)
        score = self.checker.calculate_similarity(norm, norm)
        self.assertAlmostEqual(score, 1.00, places=2)

    def test_02_completely_different(self):
        """测试完全不相干的文本返回接近 0.00"""
        t1 = TextProcessor.normalize("量子纠缠与广义相对论的引力奇点假说")
        t2 = TextProcessor.normalize("红烧排骨的做法是将肉洗净后焯水爆炒至金黄色")
        score = self.checker.calculate_similarity(t1, t2)
        self.assertLess(score, 0.20)

    def test_03_both_empty(self):
        """测试双方均为空文本时返回 1.00"""
        score = self.checker.calculate_similarity("", "")
        self.assertEqual(score, 1.00)

    def test_04_one_empty_orig(self):
        """测试原文为空时返回 0.00"""
        t2 = TextProcessor.normalize("只有疑似抄袭版有内容")
        score = self.checker.calculate_similarity("", t2)
        self.assertEqual(score, 0.00)

    def test_05_one_empty_suspect(self):
        """测试抄袭文本为空时返回 0.00"""
        t1 = TextProcessor.normalize("原文有丰富的内容")
        score = self.checker.calculate_similarity(t1, "")
        self.assertEqual(score, 0.00)

    def test_06_punctuation_only(self):
        """测试纯标点符号清洗后视为空文本"""
        t1 = "！！！？？？，，，。。。"
        t2 = "，，，！！！"
        norm1 = TextProcessor.normalize(t1)
        norm2 = TextProcessor.normalize(t2)
        self.assertEqual(norm1, "")
        self.assertEqual(norm2, "")
        score = self.checker.calculate_similarity(norm1, norm2)
        self.assertEqual(score, 1.00)

    def test_07_whitespace_and_newlines(self):
        """测试空格与换行不影响查重结果"""
        t1 = "软件 工程 实践 开发"
        t2 = "软件\n工程\t\t实践\r\n开发"
        norm1 = TextProcessor.normalize(t1)
        norm2 = TextProcessor.normalize(t2)
        self.assertEqual(norm1, norm2)
        score = self.checker.calculate_similarity(norm1, norm2)
        self.assertEqual(score, 1.00)

    def test_08_fullwidth_halfwidth(self):
        """测试全角与半角字符归一化"""
        t1 = "１２３４５６ ＡＢＣＤＥ"
        t2 = "123456 abcde"
        norm1 = TextProcessor.normalize(t1)
        norm2 = TextProcessor.normalize(t2)
        self.assertEqual(norm1, norm2)

    def test_09_case_insensitivity(self):
        """测试英文字母大小写无关性"""
        t1 = "Python Software Engineering"
        t2 = "python software engineering"
        norm1 = TextProcessor.normalize(t1)
        norm2 = TextProcessor.normalize(t2)
        self.assertEqual(norm1, norm2)

    def test_10_short_text_fallback(self):
        """测试超短文本（少于 2 个字符）能平滑回退"""
        score = self.checker.calculate_similarity("我", "我")
        self.assertEqual(score, 1.00)
        score_diff = self.checker.calculate_similarity("甲", "乙")
        self.assertEqual(score_diff, 0.00)

    # ---------------- 官方测试集样本验证 ----------------

    def test_11_sample_orig_add(self):
        """测试官方增字样本 orig_0.8_add.txt"""
        f1 = os.path.join(self.samples_dir, 'orig.txt')
        f2 = os.path.join(self.samples_dir, 'orig_0.8_add.txt')
        if os.path.exists(f1) and os.path.exists(f2):
            t1 = TextProcessor.normalize(TextProcessor.read_file(f1))
            t2 = TextProcessor.normalize(TextProcessor.read_file(f2))
            score = self.checker.calculate_similarity(t1, t2)
            self.assertTrue(0.70 <= score <= 0.98, f"Score: {score}")

    def test_12_sample_orig_del(self):
        """测试官方删字样本 orig_0.8_del.txt"""
        f1 = os.path.join(self.samples_dir, 'orig.txt')
        f2 = os.path.join(self.samples_dir, 'orig_0.8_del.txt')
        if os.path.exists(f1) and os.path.exists(f2):
            t1 = TextProcessor.normalize(TextProcessor.read_file(f1))
            t2 = TextProcessor.normalize(TextProcessor.read_file(f2))
            score = self.checker.calculate_similarity(t1, t2)
            self.assertTrue(0.70 <= score <= 0.98, f"Score: {score}")

    def test_13_sample_orig_dis_1(self):
        """测试官方距离-1 样本 orig_0.8_dis_1.txt"""
        f1 = os.path.join(self.samples_dir, 'orig.txt')
        f2 = os.path.join(self.samples_dir, 'orig_0.8_dis_1.txt')
        if os.path.exists(f1) and os.path.exists(f2):
            t1 = TextProcessor.normalize(TextProcessor.read_file(f1))
            t2 = TextProcessor.normalize(TextProcessor.read_file(f2))
            score = self.checker.calculate_similarity(t1, t2)
            self.assertTrue(0.85 <= score <= 1.00, f"Score: {score}")

    def test_14_sample_orig_dis_10(self):
        """测试官方距离-10 样本 orig_0.8_dis_10.txt"""
        f1 = os.path.join(self.samples_dir, 'orig.txt')
        f2 = os.path.join(self.samples_dir, 'orig_0.8_dis_10.txt')
        if os.path.exists(f1) and os.path.exists(f2):
            t1 = TextProcessor.normalize(TextProcessor.read_file(f1))
            t2 = TextProcessor.normalize(TextProcessor.read_file(f2))
            score = self.checker.calculate_similarity(t1, t2)
            self.assertTrue(0.75 <= score <= 0.98, f"Score: {score}")

    def test_15_sample_orig_dis_15(self):
        """测试官方距离-15 样本 orig_0.8_dis_15.txt"""
        f1 = os.path.join(self.samples_dir, 'orig.txt')
        f2 = os.path.join(self.samples_dir, 'orig_0.8_dis_15.txt')
        if os.path.exists(f1) and os.path.exists(f2):
            t1 = TextProcessor.normalize(TextProcessor.read_file(f1))
            t2 = TextProcessor.normalize(TextProcessor.read_file(f2))
            score = self.checker.calculate_similarity(t1, t2)
            self.assertTrue(0.65 <= score <= 0.95, f"Score: {score}")

    # ---------------- 编码与文件兼容测试 ----------------

    def test_16_utf8_bom_handling(self):
        """测试 UTF-8 带 BOM 文件读取"""
        path = os.path.join(self.temp_dir, 'bom.txt')
        with open(path, 'wb') as f:
            f.write('\ufeff测试BOM文件正文内容'.encode('utf-8'))
        read_text = TextProcessor.read_file(path)
        self.assertFalse(read_text.startswith('\ufeff'))
        self.assertIn('测试BOM文件正文内容', read_text)

    def test_17_gbk_encoding(self):
        """测试 GBK 编码文件读取"""
        path = os.path.join(self.temp_dir, 'gbk.txt')
        with open(path, 'wb') as f:
            f.write('广东工业大学软件工程课程'.encode('gbk'))
        read_text = TextProcessor.read_file(path)
        self.assertEqual(read_text, '广东工业大学软件工程课程')

    def test_18_simhash_deterministic(self):
        """测试算法计算的完全确定性"""
        t1 = TextProcessor.normalize("这是一段用来测试哈希确定性的文本内容，反复计算不应有变动。")
        t2 = TextProcessor.normalize("这是一段用来测试哈希确定性的疑似文本，反复计算不应变动。")
        s1 = self.checker.calculate_similarity(t1, t2)
        s2 = self.checker.calculate_similarity(t1, t2)
        self.assertEqual(s1, s2)

    # ---------------- 命令行与接口异常测试 ----------------

    def test_19_cli_correct_usage(self):
        """测试命令行端到端调用：成功返回 0，答案精确写入两位小数"""
        f1 = os.path.join(self.temp_dir, 'f1.txt')
        f2 = os.path.join(self.temp_dir, 'f2.txt')
        ans = os.path.join(self.temp_dir, 'ans.txt')
        with open(f1, 'w', encoding='utf-8') as f:
            f.write('今天天气真好，去图书馆自习。')
        with open(f2, 'w', encoding='utf-8') as f:
            f.write('今天天气很好，去图书馆自习。')

        cmd = [sys.executable, os.path.join(parent_dir, 'main.py'), f1, f2, ans]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertTrue(os.path.exists(ans))
        with open(ans, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        val = float(content)
        self.assertTrue(0.0 <= val <= 1.0)
        self.assertRegex(content, r'^\d+\.\d{2}$')

    def test_20_cli_wrong_arg_count(self):
        """测试命令行参数不足时退出码为 2 并打印提示"""
        cmd = [sys.executable, os.path.join(parent_dir, 'main.py'), 'only_one_param']
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 2)
        self.assertIn('参数数量不正确', res.stderr)

    def test_21_cli_file_not_found(self):
        """测试输入文件不存在时退出码为 1"""
        ans = os.path.join(self.temp_dir, 'ans_not_exist.txt')
        cmd = [sys.executable, os.path.join(parent_dir, 'main.py'), 'non_existent_1.txt', 'non_existent_2.txt', ans]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 1)
        self.assertFalse(os.path.exists(ans))

    def test_22_cli_directory_input_error(self):
        """测试输入路径为目录时退出码为 1"""
        ans = os.path.join(self.temp_dir, 'ans_dir.txt')
        cmd = [sys.executable, os.path.join(parent_dir, 'main.py'), self.temp_dir, self.temp_dir, ans]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 1)

if __name__ == '__main__':
    unittest.main()
