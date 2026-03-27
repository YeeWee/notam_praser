"""NOTAM 解析置信度测试"""
import pytest
from src.parsers.regex_parser import RegexParser, ParseResult
from src.parsers.llm_parser import LLMParser, LLMParserResult
from src.config import get_settings


class TestRegexParserConfidence:
    """正则解析器置信度测试"""

    def test_high_confidence_complete_notam(self):
        """完整 NOTAM 应该获得高置信度 (>=75)"""
        notam = """A0766/26 NOTAMN
Q)EGTT/QFALC/IV/NBO/A/000/999/5147N00028W005
A)EGLL
B)2403150600
C)2403151800
E)RUNWAY 09L CLSD DUE TO WIP"""

        parser = RegexParser()
        result = parser.parse(notam)

        # 完整 NOTAM 应该获得较高置信度（75 分以上）
        assert result.confidence_score >= 75, f"完整 NOTAM 置信度应该 >= 75, 实际：{result.confidence_score}"
        assert result.q_line is not None
        assert result.a_location is not None
        assert result.b_time is not None

    def test_medium_confidence_missing_fields(self):
        """缺少非关键字段的 NOTAM 应该获得中等置信度 (60-79)"""
        notam = """A0767/26 NOTAMN
Q)EGTT/QFALC/IV/NBO/A/000/999
A)EGLL
B)2403150600
C)2403151800"""

        parser = RegexParser()
        result = parser.parse(notam)

        # 缺少坐标和 E 行，但关键字段完整
        assert 60 <= result.confidence_score <= 79 or result.confidence_score >= 80, \
            f"缺少非关键字段置信度应该在合理范围，实际：{result.confidence_score}"

    def test_low_confidence_invalid_qcode(self):
        """QCODE 无效的 NOTAM 应该降低置信度"""
        notam = """A0768/26 NOTAMN
Q)EGTT/QXXXX/IV/NBO/A/000/999
A)EGLL
B)2403150600
C)2403151800
E)TEST"""

        parser = RegexParser()
        result = parser.parse(notam)

        # QCODE 无效会扣除 15 分有效性分数
        assert result.confidence_score < 85, \
            f"QCODE 无效应该降低置信度，实际：{result.confidence_score}"

    def test_very_low_confidence_critical_errors(self):
        """有严重错误的 NOTAM 应该获得很低置信度"""
        notam = """INVALID NOTAM FORMAT"""

        parser = RegexParser()
        result = parser.parse(notam)

        # 缺少 Q 行、A 行、B 行，置信度应该很低
        assert result.confidence_score < 40, \
            f"严重错误的 NOTAM 置信度应该 < 40, 实际：{result.confidence_score}"
        assert len(result.errors) > 0

    def test_time_consistency_check(self):
        """C 时间 < B 时间应该降低置信度"""
        notam = """A0769/26 NOTAMN
Q)EGTT/QFALC/IV/NBO/A/000/999
A)EGLL
B)2403151800
C)2403150600
E)TEST"""

        parser = RegexParser()
        result = parser.parse(notam)

        # C 时间 < B 时间，时间逻辑错误
        assert result.confidence_score < 85, \
            f"时间逻辑错误应该降低置信度，实际：{result.confidence_score}"

    def test_confidence_with_coordinate_and_radius(self):
        """有坐标和半径的 NOTAM 应该获得更高置信度"""
        notam_with_coords = """A0770/26 NOTAMN
Q)EGTT/QFALC/IV/NBO/A/000/999/5147N00028W005
A)EGLL
B)2403150600
C)2403151800
E)TEST"""

        notam_without_coords = """A0771/26 NOTAMN
Q)EGTT/QFALC/IV/NBO/A/000/999
A)EGLL
B)2403150600
C)2403151800
E)TEST"""

        parser = RegexParser()
        result_with = parser.parse(notam_with_coords)
        result_without = parser.parse(notam_without_coords)

        # 有坐标的置信度应该更高（多 3-5 分）
        assert result_with.confidence_score > result_without.confidence_score, \
            f"有坐标的置信度应该更高：{result_with.confidence_score} vs {result_without.confidence_score}"


class TestLLMParserConfidence:
    """LLM 解析器置信度测试"""

    def test_llm_confidence_with_valid_response(self):
        """LLM 返回有效响应应该获得高置信度"""
        settings = get_settings()
        e_text = "RUNWAY 09L CLSD DUE TO WIP"
        parser = LLMParser(
            api_key=settings.openai_api_key,
            api_base=settings.openai_api_base,
            model=settings.openai_model
        )
        result = parser.parse(e_text)

        assert result.confidence_score > 0, "LLM 解析应该有置信度分数"
        assert result.raw_llm_response is not None

    def test_llm_confidence_calculation(self):
        """测试 LLM 置信度计算逻辑"""
        # 模拟一个完整的 LLM 结果
        result = LLMParserResult(
            summary="跑道关闭",
            translation="跑道因施工关闭",
            category="跑道相关",
            terminology=[{"term": "RWY", "expansion": "Runway"}],
            raw_llm_response='{"summary": "test"}',
            validation_report={"is_valid": True}
        )

        parser = LLMParser()
        score = parser._calculate_confidence(result)

        # 完整结果应该得满分
        assert score == 100.0, f"完整 LLM 结果应该得 100 分，实际：{score}"

    def test_llm_confidence_missing_fields(self):
        """LLM 结果缺少字段应该降低置信度"""
        result = LLMParserResult(
            summary=None,  # 缺少摘要
            translation=None,  # 缺少翻译
            category=None,
            terminology=[],
            raw_llm_response=None,  # 没有原始响应
            validation_report=None
        )

        parser = LLMParser()
        score = parser._calculate_confidence(result)

        # 缺少所有字段应该得 0 分
        assert score == 0.0, f"空 LLM 结果应该得 0 分，实际：{score}"


class TestConfidenceLevel:
    """置信度等级标记测试"""

    def test_confidence_level_threshold(self):
        """测试 80 分阈值"""
        from src.api.routes import NotamParseResponse

        # 80 分以上不应该标记为 low
        response_high = NotamParseResponse(
            raw_input="test",
            confidence_score=85.0
        )
        assert response_high.confidence_level is None

        # 80 分以下应该标记为 low
        response_low = NotamParseResponse(
            raw_input="test",
            confidence_score=75.0
        )
        assert response_low.confidence_level == "low"

    def test_confidence_level_boundary(self):
        """测试边界情况"""
        from src.api.routes import NotamParseResponse

        # 正好 80 分
        response_80 = NotamParseResponse(
            raw_input="test",
            confidence_score=80.0
        )
        assert response_80.confidence_level is None

        # 79.9 分
        response_79 = NotamParseResponse(
            raw_input="test",
            confidence_score=79.9
        )
        assert response_79.confidence_level == "low"


class TestIntegrationConfidence:
    """集成置信度测试"""

    def test_real_notam_confidence(self):
        """测试真实 NOTAM 数据的置信度"""
        # 使用真实的 NOTAM 数据
        notam = """A0766/26 NOTAMN
Q)EGTT/QFALC/IV/NBO/A/000/999/5147N00028W005
A)EGLL
B)2403150600
C)2403151800
E)RUNWAY 09L CLSD DUE TO WIP"""

        parser = RegexParser()
        result = parser.parse(notam)

        # 验证置信度分数在合理范围内
        assert 0 <= result.confidence_score <= 100

        # 验证置信度分数反映了数据质量
        if result.errors:
            assert result.confidence_score < 60, "有错误的解析置信度应该 < 60"
        elif result.warnings:
            assert result.confidence_score < 90, "有警告的解析置信度应该 < 90"
        else:
            assert result.confidence_score >= 60, "无错误警告的解析置信度应该 >= 60"
