"""
main.py
命令行接口主程序：
接收三个命令行绝对路径参数：
  sys.argv[1]: 原文文件绝对路径
  sys.argv[2]: 抄袭版论文文件绝对路径
  sys.argv[3]: 答案输出文件绝对路径
计算重复率并写入答案文件，保留两位小数
"""
import os
import sys

# 兼容当前脚本目录导入
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from text_processor import TextProcessor
from similarity_checker import SimilarityChecker

def run_plagiarism_check(orig_path: str, suspect_path: str, ans_path: str) -> float:
    """执行完整的论文查重流水线"""
    orig_abs = os.path.abspath(orig_path)
    suspect_abs = os.path.abspath(suspect_path)
    ans_abs = os.path.abspath(ans_path)

    if not os.path.isfile(orig_abs):
        raise FileNotFoundError(f"原文文件不存在或不是普通文件: {orig_abs}")
    if not os.path.isfile(suspect_abs):
        raise FileNotFoundError(f"抄袭版论文文件不存在或不是普通文件: {suspect_abs}")

    raw_orig = TextProcessor.read_file(orig_abs)
    raw_suspect = TextProcessor.read_file(suspect_abs)

    norm_orig = TextProcessor.normalize(raw_orig)
    norm_suspect = TextProcessor.normalize(raw_suspect)

    checker = SimilarityChecker()
    score = checker.calculate_similarity(norm_orig, norm_suspect)

    ans_dir = os.path.dirname(ans_abs)
    if ans_dir and not os.path.exists(ans_dir):
        os.makedirs(ans_dir, exist_ok=True)

    with open(ans_abs, 'w', encoding='utf-8') as f:
        f.write(f"{score:.2f}\n")

    return score

def main():
    if len(sys.argv) != 4:
        print("错误：参数数量不正确！", file=sys.stderr)
        print("用法：python3 main.py <原文文件绝对路径> <抄袭版论文文件绝对路径> <答案文件绝对路径>", file=sys.stderr)
        sys.exit(2)

    orig_path = sys.argv[1]
    suspect_path = sys.argv[2]
    ans_path = sys.argv[3]

    try:
        score = run_plagiarism_check(orig_path, suspect_path, ans_path)
        print(f"查重完成！重复率: {score:.2f}，结果已保存至: {os.path.abspath(ans_path)}")
        sys.exit(0)
    except FileNotFoundError as e:
        print(f"文件未找到错误: {e}", file=sys.stderr)
        sys.exit(1)
    except IsADirectoryError as e:
        print(f"路径类型错误: {e}", file=sys.stderr)
        sys.exit(1)
    except PermissionError as e:
        print(f"权限错误: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"运行发生异常: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
