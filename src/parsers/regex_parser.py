"""NOTAM 正则解析器

解析 NOTAM 的标准格式字段：Q 行、A 行、B 行、C 行、D 行、F 行、G 行
"""
import re
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field


@dataclass
class CoordinatesResult:
    """坐标解析结果"""
    latitude: Optional[float] = None  # 纬度 (度)
    longitude: Optional[float] = None  # 经度 (度)
    raw: Optional[str] = None  # 原始字符串


@dataclass
class RadiusResult:
    """半径解析结果"""
    value: Optional[int] = None  # 半径值
    unit: str = "NM"  # 单位 (海里)
    raw: Optional[str] = None  # 原始字符串


@dataclass
class TimeScheduleResult:
    """D 行时间段解析结果"""
    start: Optional[datetime] = None  # 开始时间
    end: Optional[datetime] = None  # 结束时间
    recurrence: Optional[str] = None  # 重复规则
    raw: Optional[str] = None  # 原始 D 行文本


@dataclass
class AltitudeRangeResult:
    """高度范围解析结果（F/G 行）"""
    lower: Optional[str] = None  # 下层高度
    upper: Optional[str] = None  # 上层高度
    lower_source: str = "F"  # 来源
    upper_source: str = "G"  # 来源

from .qcode_database import get_qcode_description, get_fir_description


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
    # C 行标记
    c_is_est: bool = False
    c_is_perm: bool = False
    # D 行：时间段/重复性
    d_schedule: Optional[str] = None
    # D 行结构化解析
    d_schedules: List[TimeScheduleResult] = field(default_factory=list)
    # F/G 行：高度范围
    altitude_range: Optional[AltitudeRangeResult] = None
    # F 行原始文本
    f_line_raw: Optional[str] = None
    # G 行原始文本
    g_line_raw: Optional[str] = None
    # E 行：原始文本
    e_raw: Optional[str] = None
    # NOTAMR 替换关系
    notam_replaces: Optional[str] = None
    # 警告列表
    warnings: List[str] = field(default_factory=list)
    # 解析错误
    errors: List[str] = field(default_factory=list)
    # 置信度评分
    confidence_score: float = 0.0


class RegexParser:
    """NOTAM 正则解析器"""

    # NOTAM 行首标识
    NOTAM_ID_PATTERN = re.compile(r'^([A-Z]{2})/(\d{4})\s*\((\w+)\)')

    # NOTAMR 替换模式：K0832/26 NOTAMR K0769/26
    NOTAM_REPLACES_PATTERN = re.compile(r'NOTAMR\s+([A-Z]\d{4}/\d{2})')

    # Q 行模式：Q)EGTT/QFALC/IV/NBO/A/000/999/5147N00028W005
    # 注意：traffic 可以是 I/V/K/IV 等组合
    # 坐标和半径之间没有/分隔，半径是坐标末尾的 3 位数字
    # 支持///表示空字段的情况
    Q_LINE_PATTERN = re.compile(
        r'^Q\)\s*(?P<fir>[A-Z]{2,4})/'  # 飞行情报区
        r'(?P<code>[A-Z]{5})/'  # NOTAM 代码
        r'(?P<traffic>[IVK]*|/)/*'  # 交通类型（支持 I/V/K/IV/空）
        r'(?P<purpose>[NBOM]*|/)/*'  # 目的（支持 N/B/O/M/空）
        r'(?P<scope>[AEWK]*|/)/*'  # 范围（支持 A/E/W/K/空）
        r'(?P<lower>\d{3})/'  # 下限高度
        r'(?P<upper>\d{3})'  # 上限高度
        r'(?:/(?P<coord_base>[A-Z0-9]+[NS][A-Z0-9]+[EW]))?'  # 坐标基础部分
        r'(?P<coord_radius>\d{3})?'  # 半径（可选，直接跟在坐标后）
    )

    # A 行模式：A) EGLL EGGW
    A_LINE_PATTERN = re.compile(r'^A\)\s*([A-Z]{4}(?:\s+[A-Z]{4})*)')

    # B 行模式：B) 2403150600 (10 位或 12 位时间格式)
    B_LINE_PATTERN = re.compile(r'^B\)\s*(\d{10,12})')

    # C 行模式：C) 2403151800 EST (10 位或 12 位时间格式)
    C_LINE_PATTERN = re.compile(r'^C\)\s*(\d{10,12})(?:\s+(EST|PERM))?')

    # D 行模式：D) MAR 15-17 0600-1800
    D_LINE_PATTERN = re.compile(r'^D\)\s*(.+?)(?=\n[EZ]|$)', re.MULTILINE)

    # F 行模式：F) 2500FT AMSL (后面可能跟 G 行)
    F_LINE_PATTERN = re.compile(r'\nF\)\s*([^\nG]+)')

    # G 行模式：G) FL125
    G_LINE_PATTERN = re.compile(r'\nG\)\s*([^\n]+)')

    # E 行模式：E) ... (直到 Z) 行或结束
    E_LINE_PATTERN = re.compile(r'^E\)\s*(.+?)(?=\n[FZ]\)|\n\n|$)', re.MULTILINE | re.DOTALL)

    # 时间格式：YYMMDDHHMM
    TIME_FORMAT = "%y%m%d%H%M"

    # 坐标解析模式：5147N00028W
    COORDINATE_PATTERN = re.compile(r'^(\d{2,4})([NS])(\d{3,5})([EW])$')

    def parse(self, notam_text: str) -> ParseResult:
        """解析完整的 NOTAM 文本"""
        result = ParseResult()
        lines = notam_text.strip().split('\n')

        # 提取 NOTAMR 替换关系
        notamr_match = self.NOTAM_REPLACES_PATTERN.search(notam_text)
        if notamr_match:
            result.notam_replaces = notamr_match.group(1)

        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue

            # 处理同一行上可能有多个字段的情况 (如 A)OEJD B)2603121818 C)2603132359)
            # 使用正则查找所有字段
            self._parse_line_fields(line_stripped, result, notam_text)

        # 提取 F 行和 G 行（可能不在单行中）
        self._parse_f_g_lines(notam_text, result)

        # 解析 D 行结构化时间表
        if result.d_schedule:
            result.d_schedules = self._parse_d_schedule(result.d_schedule)

        # 验证必填字段
        if result.q_line is None:
            result.errors.append("缺少 Q 行")
        if result.a_location is None:
            result.errors.append("缺少 A 行")
        if result.b_time is None:
            result.errors.append("缺少 B 行")

        # 计算置信度分数
        result.confidence_score = self._calculate_confidence(result)

        return result

    def _calculate_confidence(self, result: ParseResult) -> float:
        """计算置信度分数 (0-100)

        评分模型:
        - 必填字段完整性 (40 分)
        - 字段有效性验证 (35 分)
        - 错误惩罚

        Returns:
            置信度分数 (0-100)
        """
        score = 0.0

        # 第一层：必填字段完整性 (40 分)
        # Q 行存在且可解析 (15 分)
        if result.q_line:
            score += 15.0

        # A 行存在 (10 分)
        if result.a_location:
            score += 10.0
        else:
            score -= 5.0  # 扣 5 分

        # B 行存在且时间有效 (10 分)
        if result.b_time:
            score += 10.0
        else:
            score -= 5.0  # 扣 5 分

        # E 行存在 (5 分)
        if result.e_raw:
            score += 5.0

        # 第二层：字段有效性验证 (35 分)
        if result.q_line:
            # QCODE 在数据库中 (15 分)
            if result.q_line.notam_code:
                qcode_desc = get_qcode_description(result.q_line.notam_code)
                if qcode_desc:
                    score += 15.0

            # FIR 在数据库中 (10 分)
            if result.q_line.fir:
                fir_desc = get_fir_description(result.q_line.fir)
                if fir_desc:
                    score += 10.0

            # 坐标格式有效 (3 分)
            if result.q_line.coordinates:
                score += 3.0

            # 半径格式有效 (2 分)
            if result.q_line.radius:
                score += 2.0

        # C 时间 >= B 时间 (5 分)
        if result.b_time and result.c_time:
            if result.c_time >= result.b_time:
                score += 5.0
            else:
                score -= 2.5  # 时间逻辑错误扣半分
        elif result.b_time or result.c_is_perm:
            score += 5.0

        # 错误惩罚：每个错误扣 5 分，每个警告扣 2 分
        # 注意：由于上面已经计算了完整性分数，这里只计算额外错误
        # 必填字段缺失已经在完整性中扣分了，不要再重复扣

        return max(0.0, min(100.0, score))

    def _parse_line_fields(self, line: str, result: ParseResult, notam_text: str):
        """解析单行中的所有字段（支持多字段同行）"""
        # 查找 Q 行 - 修改提取逻辑，支持完整的 Q 行格式
        if 'Q)' in line or line.startswith('Q)'):
            # 更精确的 Q 行提取：支持///空字段
            q_match = re.search(r'Q\)\s*([A-Z]{2,4}/[A-Z]{5}/[IVK]*/[NBOM]*/[AEWK]*/\d{3}/\d{3}(?:/[A-Z0-9]+[NS][A-Z0-9]+[EW]\d{3})?)', line)
            if q_match:
                q_line_full = 'Q)' + q_match.group(1)
                result.q_line = self._parse_q_line(q_line_full)

        # 查找 A 行
        a_match = re.search(r'A\)\s*([A-Z]{4}(?:\s+[A-Z]{4})*)', line)
        if a_match:
            result.a_location = self._parse_a_line('A)' + a_match.group(1))

        # 查找 B 行
        b_match = re.search(r'B\)\s*(\d{10,12})', line)
        if b_match:
            result.b_time = self._parse_time_line('B)' + b_match.group(1), self.B_LINE_PATTERN)

        # 查找 C 行
        c_match = re.search(r'C\)\s*(\d{10,12})(?:\s+(EST|PERM))?', line)
        if c_match:
            result.c_time = self._parse_time_line('C)' + c_match.group(1), self.C_LINE_PATTERN)
            # 提取 EST/PERM 标记
            full_c = line[c_match.start():c_match.end()]
            if ' EST' in full_c or full_c.endswith('EST'):
                result.c_is_est = True
            if ' PERM' in full_c or full_c.endswith('PERM'):
                result.c_is_perm = True

        # 查找 D 行 - 使用多行正则从完整 NOTAM 文本提取
        d_match = re.search(r'D\)\s*(.+?)(?=\n[EZ]\)|$)', notam_text, re.IGNORECASE | re.DOTALL)
        if d_match:
            d_text = d_match.group(1).strip()
            # 将换行符替换为多个空格（表示时间段分隔）
            d_text = re.sub(r'\n\s*', '  ', d_text)
            result.d_schedule = d_text

        # 查找 E 行（只处理行首的 E)）
        if line.startswith('E)'):
            result.e_raw = self._parse_e_line(notam_text)

    def _parse_q_line(self, line: str) -> QLineResult:
        """解析 Q 行"""
        result = QLineResult(raw=line)
        match = self.Q_LINE_PATTERN.match(line)

        if not match:
            # 尝试宽松匹配
            return self._parse_q_line_relaxed(line, result)

        result.fir = match.group('fir')
        result.notam_code = match.group('code')

        # 处理空字段（/// 或空字符串）
        traffic = match.group('traffic')
        result.traffic = traffic if traffic and traffic != '/' else None

        purpose = match.group('purpose')
        result.purpose = purpose if purpose and purpose != '/' else None

        scope = match.group('scope')
        result.scope = scope if scope and scope != '/' else None

        result.lower_altitude = match.group('lower')
        result.upper_altitude = match.group('upper')

        # 处理坐标和半径（半径直接跟在坐标后）
        coord_base = match.group('coord_base')
        coord_radius = match.group('coord_radius')

        if coord_base:
            if coord_radius:
                # 坐标 + 半径连在一起
                result.coordinates = coord_base
                result.radius = coord_radius
            else:
                # 只有坐标
                result.coordinates = coord_base
                result.radius = None

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
        # 尝试多行匹配（支持 D 行跨越多行）
        match = re.search(r'D\)\s*(.+?)(?=\n[EZ]\)|$)', line, re.IGNORECASE | re.DOTALL)
        if match:
            # 清理并合并多行内容
            d_text = match.group(1).strip()
            # 将换行符替换为多个空格（表示时间段分隔）
            d_text = re.sub(r'\n\s*', '  ', d_text)
            return d_text
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
            stripped = line.strip()
            if stripped.startswith('E)'):
                in_e_section = True
                content = line.replace('E)', '').replace('E) ', '').strip()
                if content:
                    e_lines.append(content)
            elif in_e_section:
                # E 行结束于 NNNN、Z) 或下一个字段行
                if stripped.startswith(('NNNN', 'Z)')):
                    break
                # 检查是否是新的 NOTAM 块（以引号或 NOTAM ID 开头）
                if stripped.startswith('"') or re.match(r'^[A-Z]\d{4}/\d{2}', stripped):
                    break
                if stripped and not stripped.startswith(('A)', 'B)', 'C)', 'D)', 'Q)')):
                    e_lines.append(stripped)

        return ' '.join(e_lines)

    @staticmethod
    def load_notam_from_csv(csv_path: str) -> List[str]:
        """从 CSV 文件加载 NOTAM 文本列表

        支持多行 NOTAM 格式（以 NNNN 分隔）

        Args:
            csv_path: CSV 文件路径

        Returns:
            NOTAM 文本列表
        """
        with open(csv_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 移除 BOM
        content = content.replace('\ufeff', '')

        # NOTAM 之间用 NNNN 分隔
        notam_blocks = content.split('NNNN')
        notams = []

        for block in notam_blocks:
            block = block.strip().strip('"').strip()
            if block:
                notams.append(block)

        return notams

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
        return get_fir_description(fir) if fir else None

    def _decode_notam_code(self, code: Optional[str]) -> Optional[str]:
        """解码 NOTAM 代码（QCODE 格式）

        使用完整的 ICAO QCODE 数据库进行解码，支持 176 种 QCODE。

        Args:
            code: 5 位 QCODE（如 QFALC）或 4 位代码（如 FALC）

        Returns:
            QCODE 的中文描述，如无匹配则返回代码本身
        """
        if not code:
            return None

        # 使用 QCODE 数据库进行解码
        description = get_qcode_description(code)

        if description:
            return description

        # 如果数据库中没有，尝试前缀匹配
        actual_code = code[1:] if code.startswith('Q') and len(code) == 5 else code

        # 类别级描述（根据 QCODE 结构）
        category_descriptions = {
            'QA': '航路信息服务',
            'QC': '通信',
            'QF': '机场',
            'QG': 'GNSS',
            'QI': '仪表着陆系统 (ILS)',
            'QL': '灯光',
            'QM': '气象服务',
            'QN': '导航设施',
            'QO': '机场其他设施',
            'QP': '跑道',
            'QR': '限制空域',
            'QS': '滑行道',
            'QW': '警告',
            'QX': '特殊/未分类',
        }

        if len(actual_code) >= 2:
            prefix = actual_code[:2]
            if prefix in category_descriptions:
                return f"{category_descriptions[prefix]} (代码：{code})"

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

    def _parse_f_g_lines(self, notam_text: str, result: ParseResult):
        """解析 F 行和 G 行（高度范围）

        支持格式:
        - F)SFC G)UNL (同一行)
        - F) 2500FT AMSL
          G) FL125 (分开行)
        """
        # 尝试匹配 F) 和 G) 在同一行的情况
        fg_combined = re.search(r'\nF\)\s*(\S+)\s*G\)\s*(\S+)', notam_text, re.IGNORECASE)
        if fg_combined:
            result.f_line_raw = fg_combined.group(1)
            result.g_line_raw = fg_combined.group(2)
        else:
            # 分开匹配
            f_match = re.search(r'\nF\)\s*(\S+)', notam_text, re.IGNORECASE)
            if f_match:
                result.f_line_raw = f_match.group(1)

            g_match = re.search(r'\nG\)\s*(\S+)', notam_text, re.IGNORECASE)
            if g_match:
                result.g_line_raw = g_match.group(1)

        # 构建高度范围
        if result.f_line_raw or result.g_line_raw:
            result.altitude_range = AltitudeRangeResult(
                lower=result.f_line_raw,
                upper=result.g_line_raw,
                lower_source="F",
                upper_source="G",
            )

    def _parse_d_schedule(self, d_text: str) -> List[TimeScheduleResult]:
        """解析 D 行结构化时间表

        支持格式:
        - DAILY 0200-0400
        - 2604010330 TO 2604011330    2604020330 TO 2604021330
        - MAR 15-17 0600-1800
        """
        schedules = []
        d_text = d_text.strip()

        # 检测重复规则前缀
        recurrence = None
        recurrence_patterns = [
            (r'^(DAILY)\s+', 'DAILY'),
            (r'^(MON-FRI)\s+', 'MON-FRI'),
            (r'^(MON-SUN)\s+', 'MON-SUN'),
            (r'^(WEEKLY)\s+', 'WEEKLY'),
        ]
        for pattern, rec in recurrence_patterns:
            match = re.match(pattern, d_text, re.IGNORECASE)
            if match:
                recurrence = rec
                d_text = re.sub(pattern, '', d_text).strip()
                break

        # 分割多个时间段（空格或制表符分隔）
        time_segments = re.split(r'\s{2,}|\t+', d_text)

        for segment in time_segments:
            segment = segment.strip()
            if not segment:
                continue

            schedule = TimeScheduleResult(raw=segment, recurrence=recurrence)

            # 尝试解析 "YYYYMMDDHHMM TO YYYYMMDDHHMM" 格式
            to_match = re.search(r'(\d{10,12})\s+TO\s+(\d{10,12})', segment)
            if to_match:
                start_str = to_match.group(1)
                end_str = to_match.group(2)
                schedule.start = self._parse_datetime_str(start_str)
                schedule.end = self._parse_datetime_str(end_str)
            else:
                # 尝试解析 "MMDD-HHMM" 或 "DD-HHMM" 格式
                time_range_match = re.search(r'(\d{2})-(\d{4})', segment)
                if time_range_match:
                    # 这种情况需要结合 B/C 行时间，暂时只记录原始文本
                    schedule.raw = segment

            schedules.append(schedule)

        # 如果没有解析出具体时间但有原始文本，至少保留原始文本
        if not schedules and d_text:
            schedules.append(TimeScheduleResult(raw=d_text, recurrence=recurrence))

        return schedules

    def _parse_datetime_str(self, time_str: str) -> Optional[datetime]:
        """解析时间字符串（支持 10 位和 12 位格式）"""
        formats = ["%y%m%d%H%M", "%y%m%d%H%M%S"]
        for fmt in formats:
            try:
                return datetime.strptime(time_str, fmt)
            except ValueError:
                continue
        return None

    def parse_coordinate(self, coord_str: str) -> Optional[CoordinatesResult]:
        """解析坐标字符串

        支持格式:
        - 5147N00028W (DDMM(M)N/SDDDMM(M)E/W)
        - 3253S15141E

        返回:
            CoordinatesResult 包含十进制度数
        """
        match = self.COORDINATE_PATTERN.match(coord_str.upper())
        if not match:
            return None

        lat_str = match.group(1)
        lat_dir = match.group(2)
        lon_str = match.group(3)
        lon_dir = match.group(4)

        # 解析纬度
        latitude = self._parse_coordinate_part(lat_str, lat_dir)
        # 解析经度
        longitude = self._parse_coordinate_part(lon_str, lon_dir)

        if latitude is None or longitude is None:
            return None

        return CoordinatesResult(
            latitude=latitude,
            longitude=longitude,
            raw=coord_str,
        )

    def _parse_coordinate_part(self, value_str: str, direction: str) -> Optional[float]:
        """解析坐标分量（纬度或经度）

        Args:
            value_str: 数字部分（如 5147 或 00028）
            direction: 方向（N/S/E/W）

        Returns:
            十进制度数，失败返回 None

        格式说明:
        - 纬度范围 0-90，格式为 DDMM (4 位) 或 DDMMM (5 位，前导零)
        - 经度范围 0-180，格式为 DDDMM (5 位) 或 DDDMMM (6 位)
        """
        try:
            # 根据长度判断格式
            if len(value_str) == 4:  # DDMM (纬度标准格式)
                degrees = int(value_str[:2])
                minutes = int(value_str[2:])
                if degrees > 90:  # 无效的纬度
                    return None
                decimal = degrees + minutes / 60.0
            elif len(value_str) == 5:  # 可能是 DDMMM 或 DDDMM
                # 根据方向判断：E/W 一定是经度
                if direction in ['E', 'W']:
                    # DDDMM (经度)
                    degrees = int(value_str[:3])
                    minutes = int(value_str[3:])
                    decimal = degrees + minutes / 60.0
                else:
                    # DDMMM (纬度，前导零)
                    degrees = int(value_str[:2])
                    minutes = int(value_str[2:])
                    decimal = degrees + minutes / 60.0
            elif len(value_str) == 6:  # DDDMMM (经度标准格式)
                degrees = int(value_str[:3])
                minutes = int(value_str[3:])
                decimal = degrees + minutes / 60.0
            elif len(value_str) == 3:  # DDD (只有度数)
                decimal = float(value_str)
            else:
                return None

            # 处理方向
            if direction in ['S', 'W']:
                decimal = -decimal

            return decimal
        except (ValueError, IndexError):
            return None

    def parse_radius(self, radius_str: str) -> Optional[RadiusResult]:
        """解析半径字符串

        支持格式:
        - 005 (3 位数字，单位为海里)

        返回:
            RadiusResult 包含解析后的值和单位
        """
        # 标准 3 位数字格式
        match = re.match(r'^(\d{3})$', radius_str.strip())
        if match:
            value = int(match.group(1))
            return RadiusResult(
                value=value,
                unit="NM",
                raw=radius_str,
            )
        return None
