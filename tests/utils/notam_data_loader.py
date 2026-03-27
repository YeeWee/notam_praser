"""测试工具包 - NOTAM 数据加载器

提供从 datas/input_notams.csv 加载和处理真实 NOTAM 数据的功能。

使用示例:
    from tests.utils.notam_data_loader import load_all_notams, group_by_qcode

    notams = load_all_notams()
    qcode_groups = group_by_qcode(notams)
    rtca_samples = qcode_groups.get('QRTCA', [])
"""
import csv
import re
import random
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field


# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_FILE = PROJECT_ROOT / "datas" / "input_notams.csv"


@dataclass
class NotamFields:
    """NOTAM 字段解析结果"""
    raw: str
    identifier: Optional[str] = None  # A0766/26 NOTAMN
    q_line: Optional[str] = None
    qcode: Optional[str] = None
    a_line: Optional[str] = None
    b_line: Optional[str] = None
    c_line: Optional[str] = None
    d_line: Optional[str] = None
    e_line: Optional[str] = None
    f_line: Optional[str] = None
    g_line: Optional[str] = None


def load_all_notams(filepath: Optional[str] = None) -> List[str]:
    """加载所有 NOTAM 数据

    Args:
        filepath: CSV 文件路径，默认使用 datas/input_notams.csv

    Returns:
        NOTAM 文本列表
    """
    if filepath is None:
        filepath = str(DATA_FILE)

    notams = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                row_text = ''.join(row).strip()
                if row_text and 'Q)' in row_text:
                    notams.append(row_text)
    except FileNotFoundError:
        raise FileNotFoundError(f"NOTAM 数据文件未找到：{filepath}")

    return notams


def group_by_qcode(notams: List[str]) -> Dict[str, List[str]]:
    """按 QCODE 分组 NOTAM 数据

    Args:
        notams: NOTAM 文本列表

    Returns:
        {qcode: [notam_text, ...]}
    """
    groups = {}
    qcode_pattern = re.compile(r'Q\)[A-Z]{4}/([A-Z]{5})/')

    for notam in notams:
        match = qcode_pattern.search(notam)
        if match:
            qcode = match.group(1)
            if qcode not in groups:
                groups[qcode] = []
            groups[qcode].append(notam)

    return groups


def group_by_e_length(notams: List[str]) -> Dict[str, List[str]]:
    """按 E 行长度分组 NOTAM 数据

    Args:
        notams: NOTAM 文本列表

    Returns:
        {'short': [...], 'medium': [...], 'long': [...], 'very_long': [...]}
    """
    groups = {
        'short': [],      # <50 字符
        'medium': [],     # 50-200 字符
        'long': [],       # 200-500 字符
        'very_long': [],  # >500 字符
    }

    for notam in notams:
        e_line = extract_e_line(notam)
        length = len(e_line) if e_line else 0

        if length < 50:
            groups['short'].append(notam)
        elif length < 200:
            groups['medium'].append(notam)
        elif length < 500:
            groups['long'].append(notam)
        else:
            groups['very_long'].append(notam)

    return groups


def extract_e_line(notam_text: str) -> str:
    """从 NOTAM 文本提取 E 行内容

    Args:
        notam_text: NOTAM 完整文本

    Returns:
        E 行内容（不含 E) 标记）
    """
    # 匹配 E) 到下一个字段标记或结尾
    match = re.search(r'E\)\s*(.*?)(?:\n(?:[A-Z]\)|NNNN|$))', notam_text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return ""


def extract_qcode(notam_text: str) -> Optional[str]:
    """从 NOTAM 文本提取 QCODE

    Args:
        notam_text: NOTAM 完整文本

    Returns:
        QCODE（如 QFALC）或 None
    """
    match = re.search(r'Q\)[A-Z]{4}/([A-Z]{5})/', notam_text)
    return match.group(1) if match else None


def extract_fields(notam_text: str) -> NotamFields:
    """从 NOTAM 文本提取所有字段

    Args:
        notam_text: NOTAM 完整文本

    Returns:
        NotamFields 数据类
    """
    fields = NotamFields(raw=notam_text)

    # 提取标识符
    id_match = re.match(r'([A-Z]\d{4}/\d+\s+NOTAM[NC])', notam_text)
    if id_match:
        fields.identifier = id_match.group(1)

    # 提取 Q 行
    q_match = re.search(r'Q\)[^\n]+', notam_text)
    if q_match:
        fields.q_line = q_match.group(0)
        fields.qcode = extract_qcode(notam_text)

    # 提取其他单行字段
    for line_field in ['A', 'B', 'C', 'D', 'F', 'G']:
        pattern = rf'{line_field}\)[^\n]+'
        match = re.search(pattern, notam_text)
        if match:
            setattr(fields, f'{line_field.lower()}_line', match.group(0))

    # 提取 E 行
    fields.e_line = extract_e_line(notam_text)

    return fields


def get_random_samples(notams: List[str], count: int = 10) -> List[str]:
    """随机抽样 NOTAM

    Args:
        notams: NOTAM 文本列表
        count: 抽样数量

    Returns:
        随机样本列表
    """
    return random.sample(notams, min(count, len(notams)))


def get_qcode_statistics(notams: List[str]) -> Dict[str, Any]:
    """获取 QCODE 统计信息

    Args:
        notams: NOTAM 文本列表

    Returns:
        统计信息字典
    """
    groups = group_by_qcode(notams)

    return {
        'total_notams': len(notams),
        'unique_qcodes': len(groups),
        'top_qcodes': sorted(
            [(qcode, len(items)) for qcode, items in groups.items()],
            key=lambda x: -x[1]
        )[:20],
        'all_qcodes': list(groups.keys()),
    }


def get_e_length_statistics(notams: List[str]) -> Dict[str, Any]:
    """获取 E 行长度统计信息

    Args:
        notams: NOTAM 文本列表

    Returns:
        统计信息字典
    """
    groups = group_by_e_length(notams)
    lengths = [len(extract_e_line(n)) for n in notams]

    return {
        'total': len(notams),
        'by_category': {k: len(v) for k, v in groups.items()},
        'min_length': min(lengths) if lengths else 0,
        'max_length': max(lengths) if lengths else 0,
        'avg_length': sum(lengths) / len(lengths) if lengths else 0,
    }


def filter_by_qcode(notams: List[str], qcode: str) -> List[str]:
    """筛选指定 QCODE 的 NOTAM

    Args:
        notams: NOTAM 文本列表
        qcode: 目标 QCODE

    Returns:
        筛选后的 NOTAM 列表
    """
    return [n for n in notams if extract_qcode(n) == qcode]


def filter_by_e_length(
    notams: List[str],
    min_length: int = 0,
    max_length: Optional[int] = None
) -> List[str]:
    """按 E 行长度筛选 NOTAM

    Args:
        notams: NOTAM 文本列表
        min_length: 最小长度
        max_length: 最大长度（None 表示无上限）

    Returns:
        筛选后的 NOTAM 列表
    """
    filtered = []
    for notam in notams:
        e_len = len(extract_e_line(notam))
        if e_len < min_length:
            continue
        if max_length is not None and e_len > max_length:
            continue
        filtered.append(notam)
    return filtered


def get_top_qcodes(notams: List[str], top_n: int = 20) -> List[str]:
    """获取出现次数最多的 QCODE 列表

    Args:
        notams: NOTAM 文本列表
        top_n: 返回前 N 个

    Returns:
        QCODE 列表
    """
    groups = group_by_qcode(notams)
    sorted_qcodes = sorted(
        groups.items(),
        key=lambda x: -len(x[1])
    )
    return [qc for qc, _ in sorted_qcodes[:top_n]]


def get_samples_by_top_qcodes(
    notams: List[str],
    top_n: int = 20,
    samples_per_qcode: int = 3
) -> List[str]:
    """从 Top QCODE 中各取样本

    Args:
        notams: NOTAM 文本列表
        top_n: 取前 N 个 QCODE
        samples_per_qcode: 每个 QCODE 取多少个样本

    Returns:
        样本列表
    """
    top_qcodes = get_top_qcodes(notams, top_n)
    groups = group_by_qcode(notams)

    samples = []
    for qcode in top_qcodes:
        qcode_samples = groups.get(qcode, [])
        samples.extend(qcode_samples[:samples_per_qcode])

    return samples
