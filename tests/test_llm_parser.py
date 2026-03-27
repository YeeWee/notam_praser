"""LLM 解析器单元测试

使用真实 API 调用进行测试
"""
import pytest
import json
import os

from src.parsers.llm_parser import LLMParser, LLMParserResult, parse_notam_e_line
from src.config import get_settings


@pytest.fixture
def parser():
    """创建使用真实 API 配置的 LLM 解析器"""
    settings = get_settings()
    return LLMParser(
        api_key=settings.openai_api_key,
        api_base=settings.openai_api_base,
        model=settings.openai_model
    )


@pytest.fixture
def parser_with_test_key():
    """创建使用测试 API Key 的解析器（用于不需要实际调用的测试）"""
    return LLMParser(api_key="test-key")


class TestLLMParserInit:
    """LLM 解析器初始化测试"""

    def test_init_with_api_key(self):
        """带 API Key 初始化"""
        parser = LLMParser(api_key="test-key")

        assert parser.api_key == "test-key"
        assert parser.model == "gpt-4o-mini"

    def test_init_with_custom_model(self):
        """自定义模型"""
        parser = LLMParser(model="gpt-4-turbo")

        assert parser.model == "gpt-4-turbo"

    def test_init_with_api_base(self):
        """自定义 API Base"""
        parser = LLMParser(api_base="https://custom.api.com/v1")

        assert parser.api_base == "https://custom.api.com/v1"


class TestPromptBuilding:
    """Prompt 构建测试"""

    def setup_method(self):
        self.parser = LLMParser(api_key="test-key")

    def test_build_prompt_basic(self):
        """基础 Prompt"""
        e_text = "RUNWAY 09L CLSD"
        prompt = self.parser._build_prompt(e_text)

        assert "RUNWAY 09L CLSD" in prompt
        assert "E 行内容" in prompt
        assert "summary" in prompt
        assert "translation" in prompt
        assert "category" in prompt

    def test_build_prompt_with_context(self):
        """带上下文的 Prompt"""
        e_text = "RUNWAY 09L CLSD"
        context = {
            "q_line": {
                "fir": "EGTT",
                "notam_code": "QFALC"
            }
        }
        prompt = self.parser._build_prompt(e_text, context)

        assert "EGTT" in prompt
        assert "QFALC" in prompt
        assert "FIR" in prompt


class TestResponseParsing:
    """响应解析测试"""

    def setup_method(self):
        self.parser = LLMParser(api_key="test-key")

    def test_parse_clean_json(self):
        """解析干净的 JSON"""
        response = json.dumps({
            "summary": "跑道关闭",
            "translation": "跑道 09L 关闭",
            "category": "RUNWAY",
            "terminology": [],
            "restricted_areas": []
        })

        result = self.parser._parse_response(response, "RUNWAY 09L CLSD")

        assert result.summary == "跑道关闭"
        assert result.translation == "跑道 09L 关闭"
        assert result.category == "跑道相关"

    def test_parse_markdown_json(self):
        """解析 Markdown 代码块中的 JSON"""
        response = """```json
{
    "summary": "跑道关闭",
    "translation": "跑道 09L 关闭",
    "category": "RUNWAY",
    "terminology": [],
    "restricted_areas": []
}
```"""

        result = self.parser._parse_response(response, "RUNWAY 09L CLSD")

        assert result.summary == "跑道关闭"
        assert result.translation == "跑道 09L 关闭"

    def test_parse_invalid_json(self):
        """解析无效 JSON（降级处理）"""
        response = "{ invalid json }"

        result = self.parser._parse_response(response, "RUNWAY 09L CLSD")

        assert "解析失败" in result.summary
        assert result.translation == "RUNWAY 09L CLSD"
        assert result.category == "OTHER"

    def test_parse_partial_json(self):
        """解析部分字段缺失的 JSON"""
        response = json.dumps({
            "summary": "跑道关闭"
        })

        result = self.parser._parse_response(response, "RUNWAY 09L CLSD")

        assert result.summary == "跑道关闭"
        assert result.translation is None
        assert result.terminology == []


class TestCategoryDecoding:
    """分类解码测试"""

    def setup_method(self):
        self.parser = LLMParser(api_key="test-key")

    def test_decode_known_category(self):
        """已知分类"""
        assert self.parser._decode_category("RUNWAY") == "跑道相关"
        assert self.parser._decode_category("TAXIWAY") == "滑行道相关"
        assert self.parser._decode_category("AIRSPACE") == "空域限制"

    def test_decode_unknown_category(self):
        """未知分类"""
        assert self.parser._decode_category("UNKNOWN") == "UNKNOWN"

    def test_decode_none(self):
        """None 分类"""
        assert self.parser._decode_category(None) == "未分类"

    def test_decode_case_insensitive(self):
        """大小写不敏感"""
        assert self.parser._decode_category("runway") == "跑道相关"
        assert self.parser._decode_category("Runway") == "跑道相关"


class TestTerminologyValidation:
    """术语校验测试"""

    def setup_method(self):
        self.parser = LLMParser(api_key="test-key")

    def test_validate_empty(self):
        """空术语列表"""
        report = self.parser._validate_terminology([])

        assert report["is_valid"] is True
        assert len(report["warnings"]) == 0

    def test_validate_with_corrections(self):
        """带校正的术语"""
        terminology = [
            {
                "term": "RWY",
                "expansion": "Wrong explanation",
                "category": "airport"
            }
        ]

        report = self.parser._validate_terminology(terminology)

        assert "corrected_terms" in report or report["is_valid"] is True


class TestRealAPIParsing:
    """真实 API 解析测试（需要有效的 API Key）"""

    def setup_method(self):
        settings = get_settings()
        self.parser = LLMParser(
            api_key=settings.openai_api_key,
            api_base=settings.openai_api_base,
            model=settings.openai_model
        )

    def test_parse_runway_closure(self, parser):
        """跑道关闭 NOTAM 真实解析"""
        result = parser.parse("RUNWAY 09L CLSD DUE TO WIP")

        assert result.summary is not None
        assert result.translation is not None
        assert result.category is not None
        assert len(result.terminology) > 0

    def test_parse_airspace_activation(self, parser):
        """空域激活 NOTAM 真实解析"""
        result = parser.parse("WILLIAMTOWN CTA C3 ACT ACTIVATION OF THIS CLASS C AIRSPACE")

        assert result.summary is not None
        assert result.category == "空域限制"

    def test_parse_military_operations(self, parser):
        """军事行动 NOTAM 真实解析"""
        result = parser.parse("MIL HEL OPS WILL TAKE PLACE 3X UH60M CS JUSTICE")

        assert result.summary is not None
        assert result.category == "军事活动"

    def test_parse_atc_instructions(self, parser):
        """ATC 指令 NOTAM 真实解析"""
        result = parser.parse("DUE TO ATC ASSIGNED AIRSPACE MILU EAST MELA SOUTH")

        assert result.summary is not None


class TestRealAPIEdgeCases:
    """真实 API 边界情况测试"""

    def setup_method(self):
        settings = get_settings()
        self.parser = LLMParser(
            api_key=settings.openai_api_key,
            api_base=settings.openai_api_base,
            model=settings.openai_model
        )

    def test_empty_e_line(self, parser):
        """空 E 行处理"""
        result = parser.parse("")

        assert result.summary is None
        assert result.translation is None

    def test_whitespace_only_e_line(self, parser):
        """纯空白 E 行处理"""
        result = parser.parse("   \n\n  ")

        assert result.summary is None

    def test_special_characters(self, parser):
        """特殊字符处理"""
        result = parser.parse("TEST NOTAM WITH SPECIAL CHARS")

        assert result is not None

    def test_very_long_e_line(self, parser):
        """超长 E 行处理"""
        e_text = "TEST " * 50
        result = parser.parse(e_text)

        assert result is not None

    def test_mixed_language(self, parser):
        """多语言混合处理"""
        result = parser.parse("RUNWAY 关闭 due to WIP 施工中")

        assert result is not None


class TestRetryLogic:
    """重试逻辑测试（使用真实 API）"""

    def setup_method(self):
        settings = get_settings()
        self.parser = LLMParser(
            api_key=settings.openai_api_key,
            api_base=settings.openai_api_base,
            model=settings.openai_model
        )

    def test_parse_with_retry_success(self, parser):
        """重试成功"""
        result = parser.parse_with_retry("RUNWAY CLSD", max_retries=3)

        assert result.summary is not None

    def test_parse_with_retry_exhausted(self, parser):
        """重试耗尽（使用无效 key 测试）"""
        invalid_parser = LLMParser(api_key="invalid-key")
        result = invalid_parser.parse_with_retry("TEST", max_retries=1)

        # 应该有某种降级结果或错误信息
        assert result is not None


class TestConvenienceFunction:
    """便捷函数测试（真实 API 调用）"""

    def test_parse_notam_e_line(self, parser):
        """便捷函数调用"""
        result = parse_notam_e_line(
            "RUNWAY 09L CLSD",
            api_key=get_settings().openai_api_key,
            api_base=get_settings().openai_api_base,
            model=get_settings().openai_model
        )

        assert result.summary is not None


class TestConfidenceCalculation:
    """置信度计算测试"""

    def setup_method(self):
        self.parser = LLMParser(api_key="test-key")

    def test_confidence_with_valid_result(self):
        """有效结果的置信度"""
        result = LLMParserResult(
            summary="跑道关闭",
            translation="跑道因施工关闭",
            category="跑道相关",
            terminology=[{"term": "RWY", "expansion": "Runway"}],
            raw_llm_response='{"summary": "test"}',
            validation_report={"is_valid": True}
        )

        score = self.parser._calculate_confidence(result)
        assert score > 0

    def test_confidence_with_empty_result(self):
        """空结果的置信度"""
        result = LLMParserResult()

        score = self.parser._calculate_confidence(result)
        assert score == 0.0
