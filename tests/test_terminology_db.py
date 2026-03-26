"""术语库单元测试"""
import pytest

from src.parsers.terminology_db import (
    TerminologyDatabase,
    get_terminology_db,
    TerminologyMatch,
    ValidationReport
)


class TestTerminologyLookup:
    """术语查找测试"""

    def setup_method(self):
        self.db = TerminologyDatabase()

    def test_lookup_airport_term(self):
        """机场术语查找"""
        result = self.db.lookup("RWY")

        assert result is not None
        assert "Runway" in result["expansion"]
        assert "跑道" in result["expansion"]

    def test_lookup_navigation_term(self):
        """导航术语查找"""
        result = self.db.lookup("VOR")

        assert result is not None
        assert "VHF Omnidirectional Range" in result["expansion"]

    def test_lookup_status_term(self):
        """状态术语查找"""
        result = self.db.lookup("CLSD")

        assert result is not None
        assert "Closed" in result["expansion"]
        assert "关闭" in result["expansion"]

    def test_lookup_weather_term(self):
        """天气术语查找"""
        result = self.db.lookup("TS")

        assert result is not None
        assert "Thunderstorm" in result["expansion"]

    def test_lookup_not_found(self):
        """术语不存在"""
        result = self.db.lookup("UNKNOWN")

        assert result is None

    def test_lookup_with_punctuation(self):
        """带标点的术语"""
        result = self.db.lookup("RWY.")

        assert result is not None
        assert "Runway" in result["expansion"]

    def test_lookup_case_insensitive(self):
        """大小写不敏感"""
        result_upper = self.db.lookup("RWY")
        result_lower = self.db.lookup("rwy")

        assert result_upper is not None
        assert result_lower is not None
        assert result_upper["expansion"] == result_lower["expansion"]


class TestTermCategory:
    """术语分类测试"""

    def setup_method(self):
        self.db = TerminologyDatabase()

    def test_airport_category(self):
        """机场分类"""
        assert self.db._categorize_term("RWY") == "airport"
        assert self.db._categorize_term("TWY") == "airport"

    def test_navigation_category(self):
        """导航分类"""
        assert self.db._categorize_term("VOR") == "navigation"
        assert self.db._categorize_term("ILS") == "navigation"

    def test_airspace_category(self):
        """空域分类"""
        assert self.db._categorize_term("FIR") == "airspace"
        assert self.db._categorize_term("CTR") == "airspace"

    def test_weather_category(self):
        """天气分类"""
        assert self.db._categorize_term("TS") == "weather"
        assert self.db._categorize_term("SN") == "weather"

    def test_unknown_category(self):
        """未知分类"""
        # 术语库中没有的术语返回 general
        assert self.db._categorize_term("UNKNOWN") == "general"


class TestLLMValidation:
    """LLM 输出校验测试"""

    def setup_method(self):
        self.db = TerminologyDatabase()

    def test_valid_terminology(self):
        """术语解释正确"""
        llm_terms = [
            {
                "term": "RWY",
                "expansion": "Runway (跑道)",
                "category": "airport"
            }
        ]

        report = self.db.validate_llm_output(llm_terms)

        assert report.is_valid is True
        assert len(report.errors) == 0

    def test_corrected_terminology(self):
        """术语解释需要校正"""
        llm_terms = [
            {
                "term": "RWY",
                "expansion": "Random Wrong Explanation",
                "category": "airport"
            }
        ]

        report = self.db.validate_llm_output(llm_terms)

        assert len(report.terminology_corrected) > 0
        assert report.terminology_corrected[0].term == "RWY"
        assert "Runway" in report.terminology_corrected[0].expansion

    def test_unknown_term(self):
        """术语库中没有的术语"""
        llm_terms = [
            {
                "term": "CUSTOM",
                "expansion": "Custom Explanation",
                "category": "general"
            }
        ]

        report = self.db.validate_llm_output(llm_terms)

        # 术语库中没有，应该产生警告但不报错
        assert any("CUSTOM" in w for w in report.warnings)

    def test_empty_terminology(self):
        """空术语列表"""
        report = self.db.validate_llm_output([])

        assert report.is_valid is True
        assert len(report.warnings) == 0
        assert len(report.errors) == 0


class TestExtractTermsFromText:
    """从文本提取术语测试"""

    def setup_method(self):
        self.db = TerminologyDatabase()

    def test_extract_single_term(self):
        """提取单个术语"""
        text = "RWY 09L CLSD"
        terms = self.db.extract_terms_from_text(text)

        assert len(terms) > 0
        assert any(t["term"] == "RWY" for t in terms)
        assert any(t["term"] == "CLSD" for t in terms)

    def test_extract_multiple_terms(self):
        """提取多个术语"""
        text = "VOR DME U/S. ILS APPROACH NOT AVBL"
        terms = self.db.extract_terms_from_text(text)

        assert len(terms) >= 2
        term_names = [t["term"] for t in terms]
        assert "VOR" in term_names
        assert "DME" in term_names
        assert "U/S" in term_names
        assert "ILS" in term_names

    def test_extract_no_terms(self):
        """没有已知术语"""
        text = "This is plain English text"
        terms = self.db.extract_terms_from_text(text)

        assert len(terms) == 0


class TestGlobalInstance:
    """全局实例测试"""

    def test_get_terminology_db(self):
        """获取全局术语库实例"""
        db1 = get_terminology_db()
        db2 = get_terminology_db()

        # 应该是同一个实例
        assert db1 is db2

    def test_singleton_terms(self):
        """全局实例包含术语"""
        db = get_terminology_db()
        result = db.lookup("NOTAM")

        assert result is not None
        assert "Notice to Airmen" in result["expansion"]


class TestValidationReport:
    """校验报告测试"""

    def test_report_structure(self):
        """报告结构"""
        report = ValidationReport(is_valid=True)

        assert report.is_valid is True
        assert isinstance(report.terminology_corrected, list)
        assert isinstance(report.warnings, list)
        assert isinstance(report.errors, list)

    def test_report_with_corrections(self):
        """带校正的报告"""
        match = TerminologyMatch(
            term="RWY",
            expansion="Runway (跑道)",
            category="airport",
            source="terminology_db"
        )

        report = ValidationReport(
            is_valid=True,
            terminology_corrected=[match],
            warnings=["Term corrected"],
            errors=[]
        )

        assert len(report.terminology_corrected) == 1
        assert report.terminology_corrected[0].term == "RWY"
        assert report.terminology_corrected[0].source == "terminology_db"
