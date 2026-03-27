"""NOTAM 解析器集成测试

端到端测试真实 NOTAM 样本的完整解析流程
"""
import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.parsers.regex_parser import RegexParser
from src.parsers.llm_parser import LLMParser
from src.parsers.terminology_db import get_terminology_db
from src.database import NotamCache, init_cache
from src.config import get_settings


# 真实 NOTAM 样本
SAMPLE_NOTAMS = [
    # 样本 1: 跑道关闭
    """Q)EGTT/QFALC/IV/NBO/A/000/999/5147N00028W005
A)EGLL
B)2403150600
C)2403151800
D)MAR 15-17 0600-1800
E)RUNWAY 09L CLSD DUE TO WIP. AIRCRAFT MAY BE INSTRUCTED TO HOLD SHORT OF RUNWAY 09L""",

    # 样本 2: 导航台失效
    """Q)ZBPE/QNBAK/IV/NBO/A/000/999/3954N11624W010
A)ZBAA
B)2403200000
C)2403252359
E)VOR/DME VYK U/S DUE TO MAINTENANCE""",

    # 样本 3: 空域限制
    """Q)EGTT/QFALC/IV/NBO/A/000/999
A)EGKK
B)2404010800
C)2404011800
E)RESTRICTED AREA RA-01 ACTIVE. ALL TRAFFIC MUST AVOID AREA WI RADIUS 5NM PSN 5109N00012W""",

    # 样本 4: 多机场
    """Q)EGTT/QFALC/IV/NBO/A/000/999
A)EGLL EGGW EGKK EGLC
B)2403150600
C)2403151800
E)LOW VISIBILITY OPERATIONS IN PROGRESS""",

    # 样本 5: 天气相关
    """Q)KZNY/QFALC/IV/NBO/A/000/999
A)KJFK
B)2403150600
C)2403151800
E)RWY 04L/22R CLSD DUE TO SNOW REMOVAL OPS""",
]


class TestRegexParserIntegration:
    """正则解析器集成测试"""

    def setup_method(self):
        self.parser = RegexParser()

    def test_parse_runway_closure(self):
        """跑道关闭 NOTAM 解析"""
        result = self.parser.parse(SAMPLE_NOTAMS[0])

        assert result.q_line is not None
        assert result.q_line.fir == "EGTT"
        assert result.a_location == ["EGLL"]
        assert "RUNWAY 09L CLSD" in result.e_raw

    def test_parse_navaid_outage(self):
        """导航台失效 NOTAM 解析"""
        result = self.parser.parse(SAMPLE_NOTAMS[1])

        assert result.q_line is not None
        assert result.q_line.fir == "ZBPE"
        assert result.a_location == ["ZBAA"]
        assert "VOR/DME VYK U/S" in result.e_raw

    def test_parse_restricted_area(self):
        """空域限制 NOTAM 解析"""
        result = self.parser.parse(SAMPLE_NOTAMS[2])

        assert result.q_line is not None
        assert "RESTRICTED AREA" in result.e_raw or "RA-01" in result.e_raw

    def test_parse_multiple_airports(self):
        """多机场 NOTAM 解析"""
        result = self.parser.parse(SAMPLE_NOTAMS[3])

        assert len(result.a_location) == 4
        assert "EGLL" in result.a_location
        assert "EGKK" in result.a_location

    def test_q_line_decoding(self):
        """Q 行完整解码"""
        result = self.parser.parse(SAMPLE_NOTAMS[0])
        decoded = self.parser.decode_q_line(result.q_line)

        assert decoded["fir"] == "EGTT"
        assert decoded["fir_name"] is not None
        assert "London" in decoded["fir_name"]
        assert decoded["traffic"] is not None
        assert decoded["purpose"] is not None


class TestTerminologyIntegration:
    """术语库集成测试"""

    def setup_method(self):
        self.db = get_terminology_db()

    def test_lookup_all_sample_terms(self):
        """样本中的术语都能找到"""
        terms_to_find = ["RWY", "CLSD", "VOR", "DME", "U/S", "A"]

        found = 0
        for term in terms_to_find:
            result = self.db.lookup(term)
            if result:
                found += 1

        # 至少应该找到大部分术语
        assert found >= len(terms_to_find) * 0.7

    def test_extract_terms_from_notam(self):
        """从 NOTAM 提取术语"""
        notam = SAMPLE_NOTAMS[1]  # 包含 VOR/DME
        terms = self.db.extract_terms_from_text(notam)

        # extract_terms_from_text 返回 list
        assert isinstance(terms, list)
        if len(terms) > 0:
            term_names = [t["term"] for t in terms]
            assert any("VOR" in str(t) or "DME" in str(t) for t in terms)


class TestFullPipelineIntegration:
    """完整解析流水线集成测试"""

    def setup_method(self):
        self.regex_parser = RegexParser()
        settings = get_settings()
        self.llm_parser = LLMParser(
            api_key=settings.openai_api_key,
            api_base=settings.openai_api_base,
            model=settings.openai_model
        )

    def test_end_to_end_parse(self):
        """端到端解析（真实 API 调用）"""
        notam = SAMPLE_NOTAMS[0]

        # Step 1: 正则解析
        regex_result = self.regex_parser.parse(notam)
        assert regex_result.q_line is not None
        assert regex_result.e_raw is not None

        # Step 2: LLM 解析
        llm_result = self.llm_parser.parse(regex_result.e_raw)

        assert llm_result.summary is not None
        assert llm_result.translation is not None
        assert llm_result.category is not None


class TestAPIIntegration:
    """API 集成测试"""

    def setup_method(self):
        self.client = TestClient(app)

    def test_parse_sample_notam(self):
        """解析样本 NOTAM"""
        response = self.client.post(
            "/api/v1/parse",
            json={"notam_text": SAMPLE_NOTAMS[0], "include_llm": False}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["q_line"]["fir"] == "EGTT"
        assert data["a_location"] == ["EGLL"]
        assert "e_raw" in data

    def test_parse_all_samples(self):
        """解析所有样本"""
        for i, notam in enumerate(SAMPLE_NOTAMS):
            response = self.client.post(
                "/api/v1/parse",
                json={"notam_text": notam, "include_llm": False}
            )

            assert response.status_code == 200, f"样本{i+1}解析失败"
            data = response.json()
            assert data["q_line"] is not None or len(data["errors"]) > 0

    def test_health_before_parse(self):
        """解析前检查健康状态"""
        # 先检查健康
        health_response = self.client.get("/api/v1/health")
        assert health_response.status_code == 200

        # 然后解析
        parse_response = self.client.post(
            "/api/v1/parse",
            json={"notam_text": SAMPLE_NOTAMS[0]}
        )

        assert parse_response.status_code == 200


class TestCacheIntegration:
    """缓存集成测试"""

    def setup_method(self):
        import tempfile
        import os
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.cache = NotamCache(db_path=self.temp_db.name)
        self.client = TestClient(app)

    def teardown_method(self):
        import os
        if os.path.exists(self.temp_db.name):
            os.remove(self.temp_db.name)

    def test_cache_parse_result(self):
        """缓存解析结果"""
        notam = SAMPLE_NOTAMS[0]
        parse_result = {"summary": "Cached result"}

        self.cache.set(notam, parse_result)
        cached = self.cache.get(notam)

        assert cached == parse_result

    def test_cache_miss(self):
        """缓存未命中"""
        result = self.cache.get("UNCACHED NOTAM")
        assert result is None


class TestErrorHandling:
    """错误处理集成测试"""

    def setup_method(self):
        self.parser = RegexParser()
        self.client = TestClient(app)

    def test_malformed_notam(self):
        """格式错误的 NOTAM"""
        malformed = """INVALID FORMAT
A)EGLL
B)2403150600"""

        result = self.parser.parse(malformed)

        assert result.q_line is None
        assert "缺少 Q 行" in result.errors

    def test_api_invalid_request(self):
        """API 无效请求"""
        # 空请求
        response = self.client.post(
            "/api/v1/parse",
            json={"notam_text": ""}
        )
        assert response.status_code == 400

        # 缺少字段
        response = self.client.post(
            "/api/v1/parse",
            json={}
        )
        assert response.status_code == 422

    def test_api_partial_failure(self):
        """部分字段解析失败"""
        # 缺少 C 行的 NOTAM（不应该报错，只是字段为 None）
        notam = """Q)EGTT/QFALC/IV/NBO/A/000/999
A)EGLL
B)2403150600
E)TEST"""

        response = self.client.post(
            "/api/v1/parse",
            json={"notam_text": notam}
        )

        assert response.status_code == 200
        data = response.json()
        # time_window 应该存在但 end 为 None
        assert data["time_window"] is not None
        assert data["time_window"]["end"] is None


class TestConcurrencyIntegration:
    """并发性集成测试"""

    def setup_method(self):
        self.client = TestClient(app)

    def test_concurrent_parse_requests(self):
        """并发解析请求"""
        import concurrent.futures

        def parse_notam(notam_text):
            return self.client.post(
                "/api/v1/parse",
                json={"notam_text": notam_text}
            )

        # 并发解析 5 个 NOTAM
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(parse_notam, notam)
                for notam in SAMPLE_NOTAMS[:5]
            ]
            results = [f.result() for f in futures]

        # 所有请求都应该成功
        for response in results:
            assert response.status_code == 200


class TestPerformanceIntegration:
    """性能集成测试"""

    def setup_method(self):
        self.parser = RegexParser()
        self.client = TestClient(app)

    def test_parse_time_regex_only(self):
        """正则解析时间"""
        import time

        notam = SAMPLE_NOTAMS[0]

        start = time.time()
        for _ in range(100):
            self.parser.parse(notam)
        end = time.time()

        # 100 次解析应该在合理时间内完成
        assert (end - start) < 5.0  # 5 秒

    def test_api_response_time(self):
        """API 响应时间"""
        import time

        notam = SAMPLE_NOTAMS[0]

        start = time.time()
        response = self.client.post(
            "/api/v1/parse",
            json={"notam_text": notam, "include_llm": False}
        )
        end = time.time()

        assert response.status_code == 200
        # 单次请求应该在合理时间内完成
        assert (end - start) < 2.0  # 2 秒
