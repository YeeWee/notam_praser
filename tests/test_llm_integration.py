"""LLM E 项解析集成测试

使用 datas/input_notams.csv 中的真实 NOTAM 数据进行测试：
1. 覆盖不同 QCODE 类型的 E 行解析
2. 测试边界情况（空 E 行、特殊字符、多语言等）
3. 验证 LLM 解析与 JSON Schema 的兼容性
4. 真实 LLM API 调用测试（需要配置 OPENAI_API_KEY）
"""
import pytest
import csv
import re
import os
from unittest.mock import patch, MagicMock
import json

from src.parsers.llm_parser import LLMParser, LLMParserResult
from src.parsers.regex_parser import RegexParser
from src.api.models import EParsedResponse
from tests.utils.notam_data_loader import (
    load_all_notams,
    group_by_qcode,
    get_top_qcodes,
    extract_e_line,
    extract_qcode,
    get_samples_by_top_qcodes,
)
from tests.utils.llm_test_helper import (
    is_llm_api_available,
    skip_if_no_llm_api,
    cached_llm_call,
)


# 使用统一的数据加载器
def load_notam_samples(filepath="datas/input_notams.csv", max_samples=20):
    """从 CSV 文件加载 NOTAM 样本（兼容旧接口）"""
    from tests.utils.notam_data_loader import load_all_notams, get_samples_by_top_qcodes

    notams = load_all_notams()
    return get_samples_by_top_qcodes(notams, top_n=max_samples, samples_per_qcode=1)


class TestELineExtraction:
    """E 行提取测试"""

    @pytest.fixture
    def samples(self):
        """加载样本"""
        return load_notam_samples()

    def test_extract_e_line_basic(self):
        """基础 E 行提取"""
        notam = '''Q)EGTT/QFALC/IV/NBO/A/000/999
A)EGLL
B)2403150600
E)RUNWAY 09L CLSD DUE TO WIP
NNNN'''
        e_line = extract_e_line(notam)
        assert "RUNWAY 09L CLSD" in e_line

    def test_extract_e_line_multiline(self):
        """多行 E 行提取"""
        notam = '''Q)YBBB/QAECA/IV/NBO/E/025/125
A)YBBB
E)  WILLIAMTOWN CTA C3 ACT
ACTIVATION OF THIS CLASS C AIRSPACE
VOLUME OVERRIDES ALL UNDERLYING
CIVILIAN AIRSPACE CLASS
NNNN'''
        e_line = extract_e_line(notam)
        assert "WILLIAMTOWN" in e_line
        assert "CLASS C AIRSPACE" in e_line

    def test_extract_e_line_with_trailing_space(self):
        """带前导空格的 E 行"""
        notam = '''Q)OEJD/QAFXX/IV/NBO/E/000/999
A)OEJD
E)  DEP TFC FM UNCONTROLLED AD SHALL OBTAIN ATC CLR
NNNN'''
        e_line = extract_e_line(notam)
        assert "DEP TFC" in e_line

    def test_extract_e_line_samples(self, samples):
        """真实样本的 E 行提取"""
        for sample in samples[:5]:
            e_line = extract_e_line(sample)
            # E 行不应该为空（对于有效 NOTAM）
            assert e_line is not None


class TestLLMParsingWithRealData:
    """使用真实数据的 LLM 解析测试"""

    @pytest.fixture
    def samples(self):
        """加载真实 NOTAM 样本"""
        return load_notam_samples()

    @pytest.fixture
    def parser(self):
        """创建 LLM 解析器（Mock）"""
        return LLMParser(api_key="test-key")

    @patch('src.parsers.llm_parser.LLMParser._call_llm')
    def test_parse_runway_closure(self, mock_call_llm, parser):
        """跑道关闭类 NOTAM 解析"""
        mock_response = json.dumps({
            "summary": "跑道关闭通知",
            "translation": "跑道 07R/25L 状态灯系统失效",
            "category": "RUNWAY",
            "terminology": [
                {"term": "RWY", "expansion": "Runway (跑道)", "category": "airport"},
                {"term": "U/S", "expansion": "Unserviceable (不可用)", "category": "status"},
            ],
            "restricted_areas": []
        })
        mock_call_llm.return_value = mock_response

        e_text = "LAX RWY 07R/25L RWY STATUS LGT SYSTEM U/S"
        result = parser.parse(e_text)

        assert result.summary is not None
        assert result.category is not None
        assert len(result.terminology) > 0

    @patch('src.parsers.llm_parser.LLMParser._call_llm')
    def test_parse_airspace_activation(self, mock_call_llm, parser):
        """空域激活类 NOTAM 解析"""
        mock_response = json.dumps({
            "summary": "C 类空域激活",
            "translation": "威廉敦 CTA C3 空域激活，此 C 类空域覆盖所有下方民用空域等级",
            "category": "AIRSPACE",
            "terminology": [
                {"term": "CTA", "expansion": "Control Area (管制区域)", "category": "airspace"},
                {"term": "ACT", "expansion": "Active (激活)", "category": "status"},
            ],
            "restricted_areas": []
        })
        mock_call_llm.return_value = mock_response

        e_text = """WILLIAMTOWN CTA C3 ACT
ACTIVATION OF THIS CLASS C AIRSPACE
VOLUME OVERRIDES ALL UNDERLYING
CIVILIAN AIRSPACE CLASS"""
        result = parser.parse(e_text)

        assert result.summary is not None
        assert result.category == "空域限制"

    @patch('src.parsers.llm_parser.LLMParser._call_llm')
    def test_parse_military_operations(self, mock_call_llm, parser):
        """军事行动类 NOTAM 解析"""
        mock_response = json.dumps({
            "summary": "军事直升机行动",
            "translation": "3 架 UH60M 直升机'JUSTICE'将在夜间进行行动",
            "category": "MILITARY",
            "terminology": [
                {"term": "MIL HEL", "expansion": "Military Helicopter (军用直升机)", "category": "military"},
                {"term": "UH60M", "expansion": "Black Hawk Helicopter (黑鹰直升机)", "category": "aircraft"},
            ],
            "restricted_areas": []
        })
        mock_call_llm.return_value = mock_response

        e_text = """MIL HEL OPS WILL TAKE PLACE
3X UH60M CS 'JUSTICE' WILL BE
CONDUCTING OPS BY NIGHT"""
        result = parser.parse(e_text)

        assert result.summary is not None
        assert result.category == "军事活动"

    @patch('src.parsers.llm_parser.LLMParser._call_llm')
    def test_parse_atc_instructions(self, mock_call_llm, parser):
        """ATC 指令类 NOTAM 解析"""
        mock_response = json.dumps({
            "summary": "ATC 指令要求",
            "translation": "由于 ATC 指定空域 MILU EAST，来自南方的 Honolulu 到达航班应按以下方式飞行计划",
            "category": "OTHER",
            "terminology": [
                {"term": "ATC", "expansion": "Air Traffic Control (空中交通管制)", "category": "service"},
                {"term": "FLT PLAN", "expansion": "Flight Plan (飞行计划)", "category": "procedure"},
            ],
            "restricted_areas": []
        })
        mock_call_llm.return_value = mock_response

        e_text = """DUE TO ATC ASSIGNED AIRSPACE MILU EAST, MELA SOUTH, HONOLULU ARR
FM THE S SHOULD FLT PLAN AS FOLLOWS"""
        result = parser.parse(e_text)

        assert result.summary is not None

    @patch('src.parsers.llm_parser.LLMParser._call_llm')
    def test_parse_real_samples(self, mock_call_llm, parser, samples):
        """真实样本批量解析测试"""
        mock_response = json.dumps({
            "summary": "测试摘要",
            "translation": "测试翻译",
            "category": "OTHER",
            "terminology": [],
            "restricted_areas": []
        })
        mock_call_llm.return_value = mock_response

        # 测试前 5 个不同 QCODE 的样本
        for sample in samples[:5]:
            e_line = extract_e_line(sample)
            if e_line:
                result = parser.parse(e_line)

                # 验证基本字段存在
                assert result.summary is not None or result.translation is not None
                # 验证结果可以转换为 EParsedResponse
                response = EParsedResponse(
                    summary=result.summary,
                    translation=result.translation,
                    category=result.category,
                    terminology=result.terminology,
                    restricted_areas=result.restricted_areas,
                )
                assert response is not None


class TestLLMEdgeCases:
    """LLM 解析边界情况测试"""

    @pytest.fixture
    def parser(self):
        """创建 LLM 解析器"""
        return LLMParser(api_key="test-key")

    @patch('src.parsers.llm_parser.LLMParser._call_llm')
    def test_empty_e_line(self, mock_call_llm, parser):
        """空 E 行处理"""
        result = parser.parse("")

        # 空输入应该返回空结果
        assert result.summary is None
        assert result.translation is None

    @patch('src.parsers.llm_parser.LLMParser._call_llm')
    def test_whitespace_only_e_line(self, mock_call_llm, parser):
        """纯空白 E 行处理"""
        result = parser.parse("   \n\n  ")

        assert result.summary is None

    @patch('src.parsers.llm_parser.LLMParser._call_llm')
    def test_special_characters(self, mock_call_llm, parser):
        """特殊字符处理"""
        mock_response = json.dumps({
            "summary": "特殊字符测试",
            "translation": "测试特殊字符",
            "category": "OTHER",
            "terminology": [],
            "restricted_areas": []
        })
        mock_call_llm.return_value = mock_response

        e_text = "TEST @#$%^&*() 特殊字符 ñoño 日本語"
        result = parser.parse(e_text)

        assert result is not None

    @patch('src.parsers.llm_parser.LLMParser._call_llm')
    def test_very_long_e_line(self, mock_call_llm, parser):
        """超长 E 行处理"""
        mock_response = json.dumps({
            "summary": "长文本摘要",
            "translation": "长文本翻译",
            "category": "OTHER",
            "terminology": [],
            "restricted_areas": []
        })
        mock_call_llm.return_value = mock_response

        # 创建超长文本
        e_text = "TEST " * 200  # 1000 个字符
        result = parser.parse(e_text)

        assert result is not None

    @patch('src.parsers.llm_parser.LLMParser._call_llm')
    def test_mixed_language(self, mock_call_llm, parser):
        """多语言混合处理"""
        mock_response = json.dumps({
            "summary": "多语言测试",
            "translation": "多语言混合测试",
            "category": "OTHER",
            "terminology": [
                {"term": "RWY", "expansion": "跑道", "category": "airport"},
            ],
            "restricted_areas": []
        })
        mock_call_llm.return_value = mock_response

        e_text = "RUNWAY 关闭 due to WIP 施工中"
        result = parser.parse(e_text)

        assert result is not None

    @patch('src.parsers.llm_parser.LLMParser._call_llm')
    def test_invalid_json_response(self, mock_call_llm, parser):
        """LLM 返回无效 JSON 的处理"""
        mock_call_llm.return_value = "{ invalid json }"

        e_text = "RUNWAY 09L CLSD"
        result = parser.parse(e_text)

        # 应该有降级处理
        assert result.summary is not None
        assert "解析失败" in result.summary

    @patch('src.parsers.llm_parser.LLMParser._call_llm')
    def test_partial_json_response(self, mock_call_llm, parser):
        """LLM 返回部分 JSON 的处理"""
        mock_call_llm.return_value = json.dumps({
            "summary": "部分响应",
            # 其他字段缺失
        })

        e_text = "RUNWAY 09L CLSD"
        result = parser.parse(e_text)

        # 应该有默认值
        assert result.summary == "部分响应"
        assert result.translation is None
        assert result.terminology == []

    @patch('src.parsers.llm_parser.LLMParser._call_llm')
    def test_markdown_json_response(self, mock_call_llm, parser):
        """LLM 返回 Markdown 代码块 JSON 的处理"""
        mock_call_llm.return_value = """```json
{
    "summary": "Markdown JSON 测试",
    "translation": "测试翻译",
    "category": "OTHER",
    "terminology": [],
    "restricted_areas": []
}
```"""

        e_text = "TEST NOTAM"
        result = parser.parse(e_text)

        assert result.summary == "Markdown JSON 测试"
        assert result.translation == "测试翻译"


class TestEParsedResponseCompatibility:
    """EParsedResponse 与 LLM 解析结果兼容性测试"""

    def test_llm_result_to_response(self):
        """LLM 结果转换为 EParsedResponse"""
        llm_result = LLMParserResult(
            summary="测试摘要",
            translation="测试翻译",
            category="跑道相关",
            terminology=[{"term": "RWY", "expansion": "跑道"}],
            restricted_areas=[],
            validation_report={"is_valid": True},
            raw_llm_response='{"summary": "..."}',
        )

        response = EParsedResponse(
            summary=llm_result.summary,
            translation=llm_result.translation,
            category=llm_result.category,
            terminology=llm_result.terminology,
            restricted_areas=llm_result.restricted_areas,
            validation_report=llm_result.validation_report,
            raw_llm_response=llm_result.raw_llm_response,
        )

        assert response.summary == "测试摘要"
        assert response.translation == "测试翻译"
        assert len(response.terminology) == 1

    def test_llm_result_empty_fields(self):
        """LLM 结果空字段处理"""
        llm_result = LLMParserResult()

        response = EParsedResponse(
            summary=llm_result.summary,
            translation=llm_result.translation,
            category=llm_result.category,
            terminology=llm_result.terminology,
            restricted_areas=llm_result.restricted_areas,
        )

        assert response.summary is None
        assert response.terminology == []
        assert response.restricted_areas == []


class TestQCodeCoverage:
    """QCODE 覆盖测试"""

    @pytest.fixture
    def qcode_samples(self):
        """加载不同 QCODE 的样本"""
        samples = {}
        try:
            with open("datas/input_notams.csv", 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    row_text = ''.join(row)
                    qcode_match = re.search(r'Q\)[A-Z]{4}/([A-Z]{5})/', row_text)
                    if qcode_match:
                        qcode = qcode_match.group(1)
                        if qcode not in samples:
                            samples[qcode] = row_text
                    if len(samples) >= 10:  # 限制样本数
                        break
        except FileNotFoundError:
            pytest.skip("数据文件未找到")

        return samples

    @patch('src.parsers.llm_parser.LLMParser._call_llm')
    def test_multiple_qcode_parsing(self, mock_call_llm, qcode_samples):
        """测试多种 QCODE 的 E 行解析"""
        mock_response = json.dumps({
            "summary": "测试摘要",
            "translation": "测试翻译",
            "category": "OTHER",
            "terminology": [],
            "restricted_areas": []
        })
        mock_call_llm.return_value = mock_response

        parser = LLMParser(api_key="test-key")

        for qcode, sample in qcode_samples.items():
            e_line = extract_e_line(sample)
            if e_line:
                result = parser.parse(e_line)

                # 验证可以转换为 EParsedResponse
                response = EParsedResponse(
                    summary=result.summary,
                    translation=result.translation,
                    category=result.category,
                    terminology=result.terminology,
                    restricted_areas=result.restricted_areas,
                )

                assert response is not None, f"QCODE {qcode} 解析失败"


class TestRetryLogic:
    """重试逻辑测试"""

    @pytest.fixture
    def parser(self):
        """创建 LLM 解析器"""
        return LLMParser(api_key="test-key")

    @patch('src.parsers.llm_parser.LLMParser._call_llm')
    def test_retry_on_exception(self, mock_call_llm, parser):
        """异常时重试"""
        # 前两次调用失败，第三次成功
        mock_call_llm.side_effect = [
            Exception("API Error 1"),
            Exception("API Error 2"),
            json.dumps({
                "summary": "成功",
                "translation": "成功翻译",
                "category": "OTHER",
                "terminology": [],
                "restricted_areas": []
            })
        ]

        result = parser.parse_with_retry("TEST", max_retries=3)

        assert mock_call_llm.call_count == 3
        assert result.summary == "成功"

    @patch('src.parsers.llm_parser.LLMParser._call_llm')
    def test_retry_exhausted(self, mock_call_llm, parser):
        """重试耗尽"""
        mock_call_llm.side_effect = Exception("Persistent Error")

        result = parser.parse_with_retry("TEST", max_retries=3)

        assert mock_call_llm.call_count == 3
        # 应该有某种降级结果
        assert result is not None


class TestTerminologyValidation:
    """术语验证测试"""

    @pytest.fixture
    def parser(self):
        """创建 LLM 解析器"""
        return LLMParser(api_key="test-key")

    @patch('src.parsers.llm_parser.LLMParser._call_llm')
    def test_valid_terminology(self, mock_call_llm, parser):
        """有效术语"""
        mock_response = json.dumps({
            "summary": "跑道关闭",
            "translation": "跑道关闭",
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

        result = parser.parse("RWY CLSD")

        assert result.validation_report is not None
        assert result.validation_report.get("is_valid", True) is True

    @patch('src.parsers.llm_parser.LLMParser._call_llm')
    def test_empty_terminology(self, mock_call_llm, parser):
        """空术语列表"""
        mock_response = json.dumps({
            "summary": "测试",
            "translation": "测试",
            "category": "OTHER",
            "terminology": [],
            "restricted_areas": []
        })
        mock_call_llm.return_value = mock_response

        result = parser.parse("TEST NOTAM")

        assert result.validation_report is not None
        assert result.validation_report.get("is_valid", True) is True


class TestContextBuilding:
    """上下文构建测试"""

    @pytest.fixture
    def parser(self):
        """创建 LLM 解析器"""
        return LLMParser(api_key="test-key")

    @patch('src.parsers.llm_parser.LLMParser._call_llm')
    def test_parse_with_q_line_context(self, mock_call_llm, parser):
        """带 Q 行上下文的解析"""
        mock_call_llm.return_value = json.dumps({
            "summary": "上下文测试",
            "translation": "上下文测试翻译",
            "category": "OTHER",
            "terminology": [],
            "restricted_areas": []
        })

        context = {
            "q_line": {
                "fir": "EGTT",
                "notam_code": "QFALC",
            }
        }

        result = parser.parse("RUNWAY CLSD", context=context)

        # 验证 _call_llm 被调用（表明上下文被使用）
        assert mock_call_llm.called

        # 验证结果
        assert result.summary == "上下文测试"

    def test_build_prompt_includes_context(self):
        """验证 Prompt 包含上下文"""
        parser = LLMParser(api_key="test-key")

        context = {
            "q_line": {
                "fir": "EGTT",
                "notam_code": "QFALC",
            }
        }

        prompt = parser._build_prompt("TEST", context)

        assert "EGTT" in prompt
        assert "QFALC" in prompt


# =============================================================================
# 真实 LLM API 调用测试
# =============================================================================

@pytest.mark.real_llm
class TestLLMParsingWithRealAPI:
    """使用真实 LLM API 的解析测试

    需要配置 OPENAI_API_KEY 在 .env 文件中
    """

    @pytest.fixture
    def parser(self, openai_api_key, openai_api_base, openai_model):
        """创建使用真实 API 的解析器"""
        return LLMParser(
            api_key=openai_api_key,
            api_base=openai_api_base,
            model=openai_model,
        )

    @pytest.fixture
    def real_notam_samples(self):
        """加载真实 NOTAM 样本"""
        notams = load_all_notams()
        return get_samples_by_top_qcodes(notams, top_n=10, samples_per_qcode=2)

    def test_real_api_parse_single_notam(self, parser, real_notam_samples):
        """真实 API 解析单个 NOTAM"""
        if not is_llm_api_available():
            pytest.skip("OPENAI_API_KEY not configured")

        sample = real_notam_samples[0]
        e_line = extract_e_line(sample)

        if not e_line:
            pytest.skip("E 行为空")

        result = parser.parse(e_line)

        # 验证基本字段
        assert result.summary is not None, "LLM 摘要生成失败"

        # 验证可以转换为 EParsedResponse
        response = EParsedResponse(
            summary=result.summary,
            translation=result.translation,
            category=result.category,
            terminology=result.terminology,
            restricted_areas=result.restricted_areas,
        )
        assert response is not None

    @pytest.mark.slow
    def test_real_api_parse_multiple_notams(self, parser, real_notam_samples):
        """真实 API 解析多个 NOTAM（慢速测试）"""
        if not is_llm_api_available():
            pytest.skip("OPENAI_API_KEY not configured")

        results = []
        failed = []
        processed = 0

        for sample in real_notam_samples:
            e_line = extract_e_line(sample)
            if not e_line:
                continue

            processed += 1
            try:
                result = parser.parse(e_line)
                if result.summary:
                    results.append({
                        'qcode': extract_qcode(sample),
                        'summary': result.summary,
                    })
                else:
                    failed.append(sample[:100])
            except Exception as e:
                failed.append(str(e))

        print(f"\n真实 API 解析统计:")
        print(f"  处理：{processed}")
        print(f"  成功：{len(results)}")
        print(f"  失败：{len(failed)}")

        # 至少 60% 应该成功（基于实际处理的数量）
        assert len(results) >= processed * 0.6, \
            f"真实 API 解析成功率过低：{len(results)}/{processed}"

    def test_real_api_category_decoding(self, parser, real_notam_samples):
        """真实 API 分类解码测试"""
        if not is_llm_api_available():
            pytest.skip("OPENAI_API_KEY not configured")

        categories = set()

        for sample in real_notam_samples[:5]:
            e_line = extract_e_line(sample)
            if not e_line:
                continue

            result = parser.parse(e_line)
            if result.category:
                categories.add(result.category)

        print(f"\n解析到的分类：{categories}")
        # 应该能解析出多种分类
        assert len(categories) >= 1, "未能解析出任何分类"

    def test_real_api_terminology_validation(self, parser, real_notam_samples):
        """真实 API 术语验证测试"""
        if not is_llm_api_available():
            pytest.skip("OPENAI_API_KEY not configured")

        sample = real_notam_samples[0]
        e_line = extract_e_line(sample)

        if not e_line:
            pytest.skip("E 行为空")

        result = parser.parse(e_line)

        # 验证术语校验报告存在
        assert result.validation_report is not None, "缺少术语校验报告"

        # 验证报告结构
        if result.terminology:
            assert 'is_valid' in result.validation_report or \
                   'terminology_corrected' in result.validation_report
