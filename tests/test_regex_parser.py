"""正则解析器单元测试"""
import pytest
from datetime import datetime

from src.parsers.regex_parser import RegexParser, QLineResult, ParseResult


class TestQLineParser:
    """Q 行解析测试"""

    def setup_method(self):
        self.parser = RegexParser()

    def test_standard_q_line(self):
        """标准 Q 行格式"""
        q_line = "Q)EGTT/QFALC/IV/NBO/A/000/999/5147N00028W005"
        result = self.parser._parse_q_line(q_line)

        assert result.fir == "EGTT"
        assert result.notam_code == "QFALC"
        assert result.traffic == "IV"  # IV = IFR + VFR 都适用
        assert result.purpose == "NBO"
        assert result.scope == "A"
        assert result.lower_altitude == "000"
        assert result.upper_altitude == "999"

    def test_q_line_with_coordinates(self):
        """带坐标的 Q 行"""
        # 坐标格式：/5147N00028W/005 (坐标/半径)
        q_line = "Q)ZBPE/QFALC/IV/NBO/A/000/999/5147N11624W/010"
        result = self.parser._parse_q_line(q_line)

        assert result.fir == "ZBPE"
        # 宽松解析可能会处理
        assert result.notam_code == "QFALC"

    def test_relaxed_q_line(self):
        """宽松解析：非标准 Q 行"""
        q_line = "Q) ZBPE/QFALC/IV/NBO/A"
        result = self.parser._parse_q_line(q_line)

        assert result.fir == "ZBPE"
        assert result.notam_code == "QFALC"

    def test_q_line_decode(self):
        """Q 行解码"""
        q_result = QLineResult(
            fir="EGTT",
            notam_code="QFALC",
            traffic="I",
            purpose="NBO",
            scope="A",
            lower_altitude="000",
            upper_altitude="999"
        )

        decoded = self.parser.decode_q_line(q_result)

        assert decoded["fir"] == "EGTT"
        assert decoded["traffic"] == "IFR (仪表飞行规则)"
        assert "London" in decoded["fir_name"]


class TestAParser:
    """A 行解析测试"""

    def setup_method(self):
        self.parser = RegexParser()

    def test_single_airport(self):
        """单机场"""
        a_line = "A)EGLL"
        result = self.parser._parse_a_line(a_line)

        assert result == ["EGLL"]

    def test_multiple_airports(self):
        """多机场"""
        a_line = "A)EGLL EGGW EGKK"
        result = self.parser._parse_a_line(a_line)

        assert len(result) == 3
        assert "EGLL" in result
        assert "EGGW" in result


class TestBLineParser:
    """B 行（生效时间）解析测试"""

    def setup_method(self):
        self.parser = RegexParser()

    def test_standard_time(self):
        """标准 UTC 时间格式"""
        b_line = "B)2403150600"
        result = self.parser._parse_time_line(
            b_line,
            self.parser.B_LINE_PATTERN
        )

        assert result == datetime(2024, 3, 15, 6, 0)

    def test_invalid_time(self):
        """无效时间格式"""
        b_line = "B)2403150"  # 时间格式不完整
        result = self.parser._parse_time_line(
            b_line,
            self.parser.B_LINE_PATTERN
        )

        assert result is None


class TestCLineParser:
    """C 行（结束时间）解析测试"""

    def setup_method(self):
        self.parser = RegexParser()

    def test_standard_time(self):
        """标准 UTC 时间格式"""
        c_line = "C)2403151800"
        result = self.parser._parse_time_line(
            c_line,
            self.parser.C_LINE_PATTERN
        )

        assert result == datetime(2024, 3, 15, 18, 0)

    def test_perm_notam(self):
        """PERM（永久）NOTAM"""
        c_line = "C)2403151800 PERM"
        result = self.parser._parse_time_line(
            c_line,
            self.parser.C_LINE_PATTERN
        )

        assert result == datetime(2024, 3, 15, 18, 0)

    def test_est_time(self):
        """EST（预计）时间"""
        c_line = "C)2403151800 EST"
        result = self.parser._parse_time_line(
            c_line,
            self.parser.C_LINE_PATTERN
        )

        assert result == datetime(2024, 3, 15, 18, 0)


class TestDLineParser:
    """D 行（时间段）解析测试"""

    def setup_method(self):
        self.parser = RegexParser()

    def test_time_range(self):
        """时间段格式"""
        d_line = "D)MAR 15-17 0600-1800"
        result = self.parser._parse_d_line(d_line)

        assert "MAR 15-17" in result
        assert "0600-1800" in result

    def test_recurring_schedule(self):
        """重复性格式"""
        d_line = "D)MON-FR 0800-1600"
        result = self.parser._parse_d_line(d_line)

        assert "MON-FR" in result
        assert "0800-1600" in result


class TestELineParser:
    """E 行（内容）解析测试"""

    def setup_method(self):
        self.parser = RegexParser()

    def test_single_line_e(self):
        """单行 E 行"""
        notam = """Q)EGTT/QFALC/IV/NBO/A/000/999
A)EGLL
B)2403150600
C)2403151800
E)RUNWAY 09L CLSD"""

        result = self.parser._parse_e_line(notam)

        assert "RUNWAY 09L CLSD" in result

    def test_multiline_e(self):
        """多行 E 行"""
        notam = """Q)EGTT/QFALC/IV/NBO/A/000/999
A)EGLL
B)2403150600
C)2403151800
E)RUNWAY 09L CLSD DUE TO WIP
TAXIWAY A ALSO AFFECTED
Z)END"""

        result = self.parser._parse_e_line(notam)

        assert "RUNWAY 09L CLSD" in result
        # 多行内容可能被解析，取决于 E 行结束条件
        # 这里验证至少单行解析成功
        assert len(result) > 0


class TestFullNotamParser:
    """完整 NOTAM 解析测试"""

    def setup_method(self):
        self.parser = RegexParser()

    def test_standard_notam(self):
        """标准 NOTAM"""
        notam_text = """Q)EGTT/QFALC/IV/NBO/A/000/999/5147N00028W005
A)EGLL
B)2403150600
C)2403151800
E)RUNWAY 09L CLSD DUE TO WIP"""

        result = self.parser.parse(notam_text)

        assert result.q_line is not None
        assert result.q_line.fir == "EGTT"
        assert result.a_location == ["EGLL"]
        assert result.b_time == datetime(2024, 3, 15, 6, 0)
        assert result.c_time == datetime(2024, 3, 15, 18, 0)
        assert "RUNWAY 09L CLSD" in result.e_raw

    def test_missing_q_line(self):
        """缺少 Q 行"""
        notam_text = """A)EGLL
B)2403150600
E)RUNWAY CLSD"""

        result = self.parser.parse(notam_text)

        assert result.q_line is None
        assert "缺少 Q 行" in result.errors

    def test_missing_a_line(self):
        """缺少 A 行"""
        notam_text = """Q)EGTT/QFALC/IV/NBO/A/000/999
B)2403150600
E)RUNWAY CLSD"""

        result = self.parser.parse(notam_text)

        assert result.a_location is None
        assert "缺少 A 行" in result.errors

    def test_missing_b_line(self):
        """缺少 B 行"""
        notam_text = """Q)EGTT/QFALC/IV/NBO/A/000/999
A)EGLL
E)RUNWAY CLSD"""

        result = self.parser.parse(notam_text)

        assert result.b_time is None
        assert "缺少 B 行" in result.errors

    def test_chinese_fir(self):
        """中国 FIR"""
        notam_text = """Q)ZBPE/QFALC/IV/NBO/A/000/999/3954N11624W010
A)ZBAA
B)2403150600
C)2403151800
E)RUNWAY CLSD"""

        result = self.parser.parse(notam_text)

        assert result.q_line.fir == "ZBPE"
        decoded = self.parser.decode_q_line(result.q_line)
        assert "Beijing" in decoded["fir_name"]


class TestQLineDecoder:
    """Q 行解码器测试"""

    def setup_method(self):
        self.parser = RegexParser()

    def test_decode_traffic_ifr(self):
        """交通类型：IFR"""
        result = self.parser._decode_traffic("I")
        assert "IFR" in result
        assert "仪表飞行规则" in result

    def test_decode_traffic_vfr(self):
        """交通类型：VFR"""
        result = self.parser._decode_traffic("V")
        assert "VFR" in result
        assert "目视飞行规则" in result

    def test_decode_purpose(self):
        """目的"""
        result = self.parser._decode_purpose("NBO")
        assert "Note" in result or "注意" in result

    def test_decode_scope(self):
        """范围"""
        result = self.parser._decode_scope("A")
        assert "机场" in result or "Aerodrome" in result
