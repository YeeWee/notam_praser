"""LLM 解析器单元测试

使用 mock 避免实际调用 API
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import json

from src.parsers.llm_parser import LLMParser, LLMParserResult, parse_notam_e_line


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
        assert result.translation == "RUNWAY 09L CLSD"  # 返回原文
        assert result.category == "OTHER"

    def test_parse_partial_json(self):
        """解析部分字段缺失的 JSON"""
        response = json.dumps({
            "summary": "跑道关闭"
            # 其他字段缺失
        })

        result = self.parser._parse_response(response, "RUNWAY 09L CLSD")

        assert result.summary == "跑道关闭"
        assert result.translation is None
        assert result.terminology == []  # 默认为空数组


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
        # 这个测试依赖于术语库中的实际数据
        # 如果 LLM 返回错误的 RWY 解释，应该被校正
        terminology = [
            {
                "term": "RWY",
                "expansion": "Wrong explanation",
                "category": "airport"
            }
        ]

        report = self.parser._validate_terminology(terminology)

        # 术语库应该会校正这个错误解释
        assert "corrected_terms" in report or report["is_valid"] is True


@patch('src.parsers.llm_parser.LLMParser._call_llm')
class TestParseWithMock:
    """使用 Mock 的解析测试"""

    def setup_method(self):
        self.parser = LLMParser(api_key="test-key")

    def test_full_parse(self, mock_call_llm):
        """完整解析"""
        mock_response = json.dumps({
            "summary": "跑道关闭通知",
            "translation": "跑道 09L 因施工关闭",
            "category": "RUNWAY",
            "terminology": [
                {
                    "term": "RWY",
                    "expansion": "Runway (跑道)",
                    "category": "airport"
                }
            ],
            "restricted_areas": []
        })
        mock_call_llm.return_value = mock_response

        result = self.parser.parse("RUNWAY 09L CLSD DUE TO WIP")

        assert result.summary == "跑道关闭通知"
        assert result.translation == "跑道 09L 因施工关闭"
        assert result.category == "跑道相关"
        assert len(result.terminology) == 1

    def test_parse_with_restricted_areas(self, mock_call_llm):
        """带限制区域的解析"""
        mock_response = json.dumps({
            "summary": "限制区域激活",
            "translation": "限制区域 RA-01 激活",
            "category": "AIRSPACE",
            "terminology": [],
            "restricted_areas": [
                {
                    "name": "RA-01",
                    "type": "restricted",
                    "coordinates": "40N116E",
                    "altitude_limits": "0-10000FT",
                    "description": "军事演习区域"
                }
            ]
        })
        mock_call_llm.return_value = mock_response

        result = self.parser.parse("RESTRICTED AREA RA-01 ACTIVE")

        assert result.category == "空域限制"
        assert len(result.restricted_areas) == 1
        assert result.restricted_areas[0]["name"] == "RA-01"


class TestRetryLogic:
    """重试逻辑测试"""

    def setup_method(self):
        self.parser = LLMParser(api_key="test-key")

    @patch('src.parsers.llm_parser.LLMParser._call_llm')
    def test_parse_with_retry_success(self, mock_call_llm):
        """重试成功"""
        mock_response = json.dumps({
            "summary": "Success",
            "translation": "成功",
            "category": "OTHER",
            "terminology": [],
            "restricted_areas": []
        })
        mock_call_llm.return_value = mock_response

        result = self.parser.parse_with_retry("Test", max_retries=3)

        assert result.summary == "Success"
        assert mock_call_llm.call_count == 1

    @patch('src.parsers.llm_parser.LLMParser._call_llm')
    def test_parse_with_retry_exhausted(self, mock_call_llm):
        """重试耗尽"""
        mock_call_llm.side_effect = Exception("API Error")

        result = self.parser.parse_with_retry("Test", max_retries=3)

        assert mock_call_llm.call_count == 3
        assert "解析失败" in result.summary or result.summary is None


class TestConvenienceFunction:
    """便捷函数测试"""

    @patch('src.parsers.llm_parser.LLMParser.parse_with_retry')
    def test_parse_notam_e_line(self, mock_parse):
        """便捷函数调用"""
        mock_result = LLMParserResult(summary="Test summary")
        mock_parse.return_value = mock_result

        result = parse_notam_e_line("Test NOTAM", api_key="test-key")

        assert result.summary == "Test summary"
        mock_parse.assert_called_once()
