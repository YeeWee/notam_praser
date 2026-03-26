"""NOTAM 正则解析器

解析 NOTAM 的标准格式字段：Q 行、A 行、B 行、C 行、D 行
"""
import re
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field


@dataclass
class QLineResult:
    """Q 行解析结果"""
    fir: Optional[str] = None  # 飞行情报区
    notam_code: Optional[str] = None  # NOTAM 代码
    traffic: Optional[str] = None  # 交通类型 (I/V/K)
    purpose: Optional[str] = None  # 目的 (N/B/O/M)
    scope: Optional[str] = None  # 范围 (A/E/W/K)
    lower_altitude: Optional[str] = None  # 下限高度
    upper_altitude: Optional[str] = None  # 上限高度
    coordinates: Optional[str] = None  # 坐标
    radius: Optional[str] = None  # 半径
    raw: Optional[str] = None  # 原始 Q 行文本


@dataclass
class ParseResult:
    """NOTAM 解析结果"""
    # Q 行
    q_line: Optional[QLineResult] = None
    # A 行：适用机场/空域
    a_location: Optional[List[str]] = None
    # B 行：生效时间
    b_time: Optional[datetime] = None
    # C 行：结束时间
    c_time: Optional[datetime] = None
    # D 行：时间段/重复性
    d_schedule: Optional[str] = None
    # E 行：原始文本
    e_raw: Optional[str] = None
    # 警告列表
    warnings: List[str] = field(default_factory=list)
    # 解析错误
    errors: List[str] = field(default_factory=list)


class RegexParser:
    """NOTAM 正则解析器"""

    # NOTAM 行首标识
    NOTAM_ID_PATTERN = re.compile(r'^([A-Z]{2})/(\d{4})\s*\((\w+)\)')

    # Q 行模式：Q)EGTT/QFALC/IV/NBO/A/000/999/5147N00028W005
    Q_LINE_PATTERN = re.compile(
        r'^Q\)\s*(?P<fir>[A-Z]{2,4})/'  # 飞行情报区
        r'(?P<code>[A-Z]{5})/'  # NOTAM 代码
        r'(?P<traffic>[IVK])/'  # 交通类型
        r'(?P<purpose>[NBOM]{1,4})/'  # 目的
        r'(?P<scope>[AEWK]{1,4})/'  # 范围
        r'(?P<lower>\d{3})/'  # 下限高度
        r'(?P<upper>\d{3})/'  # 上限高度
        r'(?:/(?P<coords>[A-Z0-9]+[NS][A-Z0-9]+[EW]))?'  # 坐标（可选，如 5147N00028W）
        r'(?:/(?P<radius>\d{3}))?'  # 半径（可选）
    )

    # A 行模式：A) EGLL EGGW
    A_LINE_PATTERN = re.compile(r'^A\)\s*([A-Z]{4}(?:\s+[A-Z]{4})*)')

    # B 行模式：B) 2403150600 (10 位或 12 位时间格式)
    B_LINE_PATTERN = re.compile(r'^B\)\s*(\d{10,12})')

    # C 行模式：C) 2403151800 EST (10 位或 12 位时间格式)
    C_LINE_PATTERN = re.compile(r'^C\)\s*(\d{10,12})(?:\s+(EST|PERM))?')

    # D 行模式：D) MAR 15-17 0600-1800
    D_LINE_PATTERN = re.compile(r'^D\)\s*(.+?)(?=\n[EZ]|$)', re.MULTILINE)

    # E 行模式：E) ... (直到 Z) 行或结束
    E_LINE_PATTERN = re.compile(r'^E\)\s*(.+?)(?=\n[ZD]\)|$)', re.MULTILINE | re.DOTALL)

    # 时间格式：YYMMDDHHMM
    TIME_FORMAT = "%y%m%d%H%M"

    def parse(self, notam_text: str) -> ParseResult:
        """解析完整的 NOTAM 文本"""
        result = ParseResult()
        lines = notam_text.strip().split('\n')

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 解析 Q 行
            if line.startswith('Q)'):
                result.q_line = self._parse_q_line(line)
            # 解析 A 行
            elif line.startswith('A)'):
                result.a_location = self._parse_a_line(line)
            # 解析 B 行
            elif line.startswith('B)'):
                result.b_time = self._parse_time_line(line, self.B_LINE_PATTERN)
            # 解析 C 行
            elif line.startswith('C)'):
                result.c_time = self._parse_time_line(line, self.C_LINE_PATTERN)
            # 解析 D 行
            elif line.startswith('D)'):
                result.d_schedule = self._parse_d_line(line)
            # 解析 E 行
            elif line.startswith('E)'):
                result.e_raw = self._parse_e_line(notam_text)

        # 验证必填字段
        if result.q_line is None:
            result.errors.append("缺少 Q 行")
        if result.a_location is None:
            result.errors.append("缺少 A 行")
        if result.b_time is None:
            result.errors.append("缺少 B 行")

        return result

    def _parse_q_line(self, line: str) -> QLineResult:
        """解析 Q 行"""
        result = QLineResult(raw=line)
        match = self.Q_LINE_PATTERN.match(line)

        if not match:
            # 尝试宽松匹配
            return self._parse_q_line_relaxed(line, result)

        result.fir = match.group('fir')
        result.notam_code = match.group('code')
        result.traffic = match.group('traffic')
        result.purpose = match.group('purpose')
        result.scope = match.group('scope')
        result.lower_altitude = match.group('lower')
        result.upper_altitude = match.group('upper')
        result.coordinates = match.group('coords')
        result.radius = match.group('radius')

        return result

    def _parse_q_line_relaxed(self, line: str, result: QLineResult) -> QLineResult:
        """宽松 Q 行解析（处理格式不规范的情况）"""
        # 移除 Q) 前缀
        content = line.replace('Q)', '').replace('Q) ', '').strip()
        parts = content.split('/')

        if len(parts) >= 2:
            result.fir = parts[0] if len(parts) > 0 else None
            result.notam_code = parts[1] if len(parts) > 1 else None
        if len(parts) >= 3:
            result.traffic = parts[2][0] if parts[2] else None
        if len(parts) >= 4:
            result.purpose = parts[3] if len(parts) > 3 else None
        if len(parts) >= 5:
            result.scope = parts[4] if len(parts) > 4 else None
        if len(parts) >= 6:
            result.lower_altitude = parts[5] if len(parts) > 5 else None
        if len(parts) >= 7:
            result.upper_altitude = parts[6] if len(parts) > 6 else None

        result.warnings = ["Q 行格式不规范，使用宽松解析"]
        return result

    def _parse_a_line(self, line: str) -> List[str]:
        """解析 A 行（适用机场/空域列表）"""
        match = self.A_LINE_PATTERN.match(line)
        if match:
            airports = match.group(1).split()
            return airports
        # 宽松解析
        content = line.replace('A)', '').strip()
        return content.split()

    def _parse_time_line(self, line: str, pattern: re.Pattern) -> Optional[datetime]:
        """解析 B 行或 C 行时间"""
        match = pattern.match(line)
        if match:
            time_str = match.group(1)
            # 支持 10 位 (YYMMDDHHMM) 和 12 位 (YYMMDDHHMM) 格式
            formats = ["%y%m%d%H%M", "%y%m%d%H%M%S"]
            for fmt in formats:
                try:
                    return datetime.strptime(time_str, fmt)
                except ValueError:
                    continue
        return None

    def _parse_d_line(self, line: str) -> str:
        """解析 D 行（时间段/重复性）"""
        match = self.D_LINE_PATTERN.search(line)
        if match:
            return match.group(1).strip()
        # 宽松解析
        content = line.replace('D)', '').strip()
        return content

    def _parse_e_line(self, notam_text: str) -> str:
        """解析 E 行（完整内容）"""
        # 从原始文本中提取 E 行内容
        match = self.E_LINE_PATTERN.search(notam_text)
        if match:
            return match.group(1).strip()

        # 如果正则失败，尝试行方式提取
        lines = notam_text.split('\n')
        e_lines = []
        in_e_section = False

        for line in lines:
            if line.strip().startswith('E)'):
                in_e_section = True
                content = line.replace('E)', '').strip()
                if content:
                    e_lines.append(content)
            elif in_e_section:
                # E 行结束于 Z) 或下一个字段行（但不是 continuation）
                stripped = line.strip()
                if stripped.startswith('Z)') or (stripped.startswith(('A)', 'B)', 'C)', 'D)')) and len(stripped) < 10):
                    break
                if stripped:
                    e_lines.append(stripped)

        return '\n'.join(e_lines)

    def decode_q_line(self, q_line: QLineResult) -> Dict[str, Any]:
        """解码 Q 行各字段的语义

        Returns:
            包含 Q 行各字段语义解释的字典
        """
        result = {
            "fir": q_line.fir,
            "fir_name": self._decode_fir(q_line.fir),
            "notam_code": q_line.notam_code,
            "code_description": self._decode_notam_code(q_line.notam_code),
            "traffic": self._decode_traffic(q_line.traffic),
            "purpose": self._decode_purpose(q_line.purpose),
            "scope": self._decode_scope(q_line.scope),
            "altitude": {
                "lower": q_line.lower_altitude,
                "upper": q_line.upper_altitude,
                "unit": "FL (Flight Level)"
            },
            "coordinates": q_line.coordinates,
            "radius": q_line.radius,
        }
        return result

    def _decode_fir(self, fir: Optional[str]) -> Optional[str]:
        """解码飞行情报区"""
        fir_names = {
            "EGTT": "London FIR (UK)",
            "EGTT": "London Flight Information Region",
            "ZBPE": "Beijing FIR (China)",
            "ZSHA": "Shanghai FIR (China)",
            "ZGZU": "Guangzhou FIR (China)",
            "ZPKM": "Kunming FIR (China)",
            "KZNY": "New York ARTCC (USA)",
            "KZLA": "Los Angeles ARTCC (USA)",
        }
        return fir_names.get(fir) if fir else None

    def _decode_notam_code(self, code: Optional[str]) -> Optional[str]:
        """解码 NOTAM 代码（5 位字母，格式为 QCODE）"""
        if not code:
            return None
        # NOTAM 代码格式：QCODE，实际代码是后 4 位
        actual_code = code[1:] if code.startswith('Q') and len(code) == 5 else code

        code_descriptions = {
            "FALC": "Aerodrome closed",
            "FA": "Aerodrome",
            "AD": "Aerodrome",
            "RW": "Runway",
            "TW": "Taxiway",
            "AP": "Apron",
            "NB": "Navigation",
            "NA": "Navigation aids",
        }
        # 先尝试精确匹配，再尝试前缀匹配
        if actual_code in code_descriptions:
            return code_descriptions[actual_code]
        for prefix, desc in code_descriptions.items():
            if actual_code.startswith(prefix):
                return desc
        return f"NOTAM Code: {code}"

    def _decode_traffic(self, traffic: Optional[str]) -> str:
        """解码交通类型"""
        traffic_map = {
            "I": "IFR (仪表飞行规则)",
            "V": "VFR (目视飞行规则)",
            "K": "检查单 (Checklist)",
        }
        return traffic_map.get(traffic, f"未知 ({traffic})") if traffic else "未指定"

    def _decode_purpose(self, purpose: Optional[str]) -> str:
        """解码发布目的"""
        purpose_map = {
            "N": "立即注意 (Note)",
            "B": "飞行前简报 (Briefing)",
            "O": "运控重要 (Operations)",
            "M": "杂项 (Miscellaneous)",
        }
        if not purpose:
            return "未指定"
        return " | ".join([purpose_map.get(p, p) for p in purpose])

    def _decode_scope(self, scope: Optional[str]) -> str:
        """解码适用范围"""
        scope_map = {
            "A": "机场区域 (Aerodrome)",
            "E": "航路 (En-route)",
            "W": "警告 (Warning)",
            "K": "检查单 (Checklist)",
        }
        if not scope:
            return "未指定"
        return " | ".join([scope_map.get(s, s) for s in scope])
