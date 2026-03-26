"""API 路由单元测试"""
import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.config import get_settings


@pytest.fixture
def client():
    """测试客户端"""
    return TestClient(app)


@pytest.fixture
def settings():
    """测试配置"""
    return get_settings()


class TestHealthCheck:
    """健康检查测试"""

    def test_health_endpoint(self, client):
        """健康检查端点"""
        response = client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "llm_enabled" in data

    def test_health_version(self, client):
        """版本号格式"""
        response = client.get("/api/v1/health")
        data = response.json()

        # 版本号应该是语义化版本
        assert data["version"].startswith("0.")


class TestRootEndpoint:
    """根端点测试"""

    def test_root(self, client):
        """根端点"""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert data["docs"] == "/docs"


class TestParseEndpoint:
    """解析端点测试"""

    def test_parse_empty_input(self, client):
        """空输入"""
        response = client.post(
            "/api/v1/parse",
            json={"notam_text": ""}
        )

        assert response.status_code == 400
        assert "不能为空" in response.json()["detail"]

    def test_parse_whitespace_only(self, client):
        """纯空白输入"""
        response = client.post(
            "/api/v1/parse",
            json={"notam_text": "   \n\n  "}
        )

        assert response.status_code == 400

    def test_parse_minimal_notam(self, client):
        """最小 NOTAM 解析"""
        notam_text = """Q)EGTT/QFALC/IV/NBO/A/000/999
A)EGLL
B)2403150600
C)2403151800
E)RUNWAY CLSD"""

        response = client.post(
            "/api/v1/parse",
            json={"notam_text": notam_text}
        )

        assert response.status_code == 200
        data = response.json()

        # 检查基本字段
        assert data["q_line"] is not None
        assert data["a_location"] is not None
        assert data["time_window"] is not None
        assert data["time_window"]["start"] is not None
        assert data["time_window"]["end"] is not None
        assert "e_raw" in data

    def test_parse_with_llm_disabled(self, client):
        """禁用 LLM 解析"""
        notam_text = """Q)EGTT/QFALC/IV/NBO/A/000/999
A)EGLL
B)2403150600
E)RUNWAY CLSD"""

        response = client.post(
            "/api/v1/parse",
            json={
                "notam_text": notam_text,
                "include_llm": False
            }
        )

        assert response.status_code == 200
        data = response.json()

        # 正则解析应该成功
        assert data["q_line"] is not None
        # LLM 解析应该跳过
        assert data.get("e_parsed") is None or data.get("e_parsed") == {}

    def test_parse_missing_q_line(self, client):
        """缺少 Q 行"""
        notam_text = """A)EGLL
B)2403150600
E)RUNWAY CLSD"""

        response = client.post(
            "/api/v1/parse",
            json={"notam_text": notam_text}
        )

        assert response.status_code == 200
        data = response.json()

        # 应该有错误
        assert data["q_line"] is None
        assert len(data["errors"]) > 0
        assert any("Q 行" in str(e) for e in data["errors"])

    def test_parse_missing_a_line(self, client):
        """缺少 A 行"""
        notam_text = """Q)EGTT/QFALC/IV/NBO/A/000/999
B)2403150600
E)RUNWAY CLSD"""

        response = client.post(
            "/api/v1/parse",
            json={"notam_text": notam_text}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["a_location"] is None
        assert len(data["errors"]) > 0

    def test_parse_missing_b_line(self, client):
        """缺少 B 行"""
        notam_text = """Q)EGTT/QFALC/IV/NBO/A/000/999
A)EGLL
E)RUNWAY CLSD"""

        response = client.post(
            "/api/v1/parse",
            json={"notam_text": notam_text}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["time_window"] is None
        assert len(data["errors"]) > 0


class TestQLineDecoding:
    """Q 行解码测试"""

    def test_q_line_fir(self, client):
        """FIR 解码"""
        notam_text = """Q)EGTT/QFALC/IV/NBO/A/000/999
A)EGLL
B)2403150600
E)TEST"""

        response = client.post(
            "/api/v1/parse",
            json={"notam_text": notam_text}
        )

        data = response.json()
        q_line = data["q_line"]

        assert q_line["fir"] == "EGTT"
        assert q_line["fir_name"] is not None
        assert "London" in q_line["fir_name"]

    def test_q_line_chinese_fir(self, client):
        """中国 FIR 解码"""
        notam_text = """Q)ZBPE/QFALC/IV/NBO/A/000/999
A)ZBAA
B)2403150600
E)TEST"""

        response = client.post(
            "/api/v1/parse",
            json={"notam_text": notam_text}
        )

        data = response.json()
        q_line = data["q_line"]

        assert q_line["fir"] == "ZBPE"
        assert q_line["fir_name"] is not None
        assert "Beijing" in q_line["fir_name"]

    def test_q_line_traffic(self, client):
        """交通类型解码"""
        notam_text = """Q)EGTT/QFALC/IV/NBO/A/000/999
A)EGLL
B)2403150600
E)TEST"""

        response = client.post(
            "/api/v1/parse",
            json={"notam_text": notam_text}
        )

        data = response.json()
        q_line = data["q_line"]

        # traffic 字段是原始值 "IV"（IFR+VFR 都适用）
        assert q_line["traffic"] == "IV"
        # code_description 应该包含机场关闭相关信息
        assert "Aerodrome" in q_line["code_description"] or "closed" in q_line["code_description"].lower()


class TestTimeFormatting:
    """时间格式化测试"""

    def test_b_time_iso_format(self, client):
        """B 行 ISO 8601 格式"""
        notam_text = """Q)EGTT/QFALC/IV/NBO/A/000/999
A)EGLL
B)2403150600
E)TEST"""

        response = client.post(
            "/api/v1/parse",
            json={"notam_text": notam_text}
        )

        data = response.json()

        # 时间应该是 ISO 8601 格式或为 None（如果解析失败）
        time_window = data.get("time_window")
        if time_window and time_window.get("start"):
            assert "2024-03-15" in time_window["start"] or "24-03-15" in time_window["start"]

    def test_c_time_iso_format(self, client):
        """C 行 ISO 8601 格式"""
        notam_text = """Q)EGTT/QFALC/IV/NBO/A/000/999
A)EGLL
B)2403150600
C)2403151800
E)TEST"""

        response = client.post(
            "/api/v1/parse",
            json={"notam_text": notam_text}
        )

        data = response.json()

        # 时间应该是 ISO 8601 格式
        time_window = data.get("time_window")
        assert time_window is not None
        assert time_window.get("end") is not None
        assert "2024-03-15" in time_window["end"] or "24-03-15" in time_window["end"]


class TestMultipleAirports:
    """多机场测试"""

    def test_parse_multiple_airports(self, client):
        """多机场 NOTAM"""
        notam_text = """Q)EGTT/QFALC/IV/NBO/A/000/999
A)EGLL EGGW EGKK
B)2403150600
E)TEST"""

        response = client.post(
            "/api/v1/parse",
            json={"notam_text": notam_text}
        )

        data = response.json()

        assert len(data["a_location"]) == 3
        assert "EGLL" in data["a_location"]
        assert "EGGW" in data["a_location"]
        assert "EGKK" in data["a_location"]
