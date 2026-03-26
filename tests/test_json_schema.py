"""JSON Schema 验证测试

验证 Pydantic 模型的 JSON Schema 生成和验证逻辑：
1. 所有响应模型能生成有效的 JSON Schema
2. 字段约束和类型校验正确
3. 模型验证逻辑符合预期
"""
import pytest
from pydantic import ValidationError
from typing import get_args
import json

from src.api.models import (
    NotamParseResponse,
    NotamParseRequest,
    NotamIdentifier,
    QLineResponse,
    TimeWindow,
    TimeSchedule,
    AltitudeRange,
    Coordinates,
    Radius,
    EParsedResponse,
    HealthResponse,
    BatchParseRequest,
    BatchParseResponse,
    BatchParseResult,
    TerminologyItem,
    RestrictedArea,
    NotamType,
)


class TestNotamType:
    """NOTAM 类型枚举测试"""

    def test_notam_type_values(self):
        """NOTAM 类型值"""
        assert NotamType.NEW.value == "NOTAMN"
        assert NotamType.REPLACE.value == "NOTAMR"
        assert NotamType.CANCEL.value == "NOTAMC"

    def test_notam_type_from_string(self):
        """字符串转换为 NOTAM 类型"""
        assert NotamType("NOTAMN") == NotamType.NEW
        assert NotamType("NOTAMR") == NotamType.REPLACE
        assert NotamType("NOTAMC") == NotamType.CANCEL


class TestNotamIdentifier:
    """NOTAM 标识符模型测试"""

    def test_valid_identifier(self):
        """有效标识符"""
        identifier = NotamIdentifier(
            series="A",
            number="0766",
            year="26",
            type=NotamType.NEW,
            full_id="A0766/26 NOTAMN",
        )
        assert identifier.series == "A"
        assert identifier.number == "0766"
        assert identifier.year == "26"

    def test_optional_fields(self):
        """可选字段"""
        identifier = NotamIdentifier()
        assert identifier.series is None
        assert identifier.number is None

    def test_replaces_field(self):
        """NOTAMR 替换关系"""
        identifier = NotamIdentifier(
            series="K",
            number="0832",
            year="26",
            type=NotamType.REPLACE,
            replaces="K0769/26",
        )
        assert identifier.replaces == "K0769/26"


class TestCoordinates:
    """坐标模型测试"""

    def test_valid_coordinates(self):
        """有效坐标"""
        coords = Coordinates(
            latitude=51.4775,
            longitude=-0.4614,
            raw="5147N00028W",
        )
        assert coords.latitude == 51.4775
        assert coords.longitude == -0.4614

    def test_invalid_latitude_range(self):
        """纬度超出范围（Pydantic v2 不会自动验证范围，除非使用 Field 约束）"""
        # 这个测试验证模型接受数据 - 实际范围验证在解析逻辑中
        coords = Coordinates(
            latitude=91.0,  # 超出范围，但 Pydantic 会接受
            longitude=0.0,
            raw="INVALID",
        )
        assert coords.latitude == 91.0

    def test_coordinates_required_fields(self):
        """必填字段验证"""
        with pytest.raises(ValidationError):
            Coordinates()  # 缺少必填字段


class TestRadius:
    """半径模型测试"""

    def test_valid_radius(self):
        """有效半径"""
        radius = Radius(value=5, unit="NM", raw="005")
        assert radius.value == 5
        assert radius.unit == "NM"

    def test_radius_default_unit(self):
        """默认单位"""
        radius = Radius(value=10, raw="010")
        assert radius.unit == "NM"


class TestAltitudeRange:
    """高度范围模型测试"""

    def test_valid_altitude_range(self):
        """有效高度范围"""
        altitude = AltitudeRange(
            lower="2500FT",
            upper="FL125",
            lower_source="F",
            upper_source="G",
        )
        assert altitude.lower == "2500FT"
        assert altitude.upper == "FL125"

    def test_optional_altitude(self):
        """可选高度"""
        altitude = AltitudeRange(lower="SFC", upper="UNL")
        assert altitude.lower == "SFC"
        assert altitude.upper == "UNL"

    def test_default_source(self):
        """默认来源字段"""
        altitude = AltitudeRange()
        assert altitude.lower_source == "F"
        assert altitude.upper_source == "G"


class TestTimeSchedule:
    """时间表模型测试"""

    def test_valid_schedule(self):
        """有效时间表"""
        schedule = TimeSchedule(
            start="2024-03-15T06:00:00Z",
            end="2024-03-15T18:00:00Z",
            recurrence="DAILY",
            raw="MAR 15-17 0600-1800",
        )
        assert schedule.start == "2024-03-15T06:00:00Z"
        assert schedule.recurrence == "DAILY"

    def test_optional_recurrence(self):
        """可选重复规则"""
        schedule = TimeSchedule(raw="MAR 15 0600-1800")
        assert schedule.recurrence is None


class TestTimeWindow:
    """时间窗口模型测试"""

    def test_valid_time_window(self):
        """有效时间窗口"""
        window = TimeWindow(
            start="2024-03-15T06:00:00Z",
            end="2024-03-15T18:00:00Z",
            is_permanent=False,
            is_estimated=False,
        )
        assert window.start == "2024-03-15T06:00:00Z"
        assert not window.is_permanent

    def test_permanent_notam(self):
        """永久生效 NOTAM"""
        window = TimeWindow(
            start="2024-03-15T06:00:00Z",
            is_permanent=True,
            raw="PERM",
        )
        assert window.is_permanent is True
        assert window.end is None

    def test_empty_schedules(self):
        """默认空时间表列表"""
        window = TimeWindow()
        assert window.schedules == []


class TestQLineResponse:
    """Q 行响应模型测试"""

    def test_minimal_q_line(self):
        """最小 Q 行"""
        q_line = QLineResponse(fir="EGTT")
        assert q_line.fir == "EGTT"
        assert q_line.notam_code is None

    def test_full_q_line(self):
        """完整 Q 行"""
        q_line = QLineResponse(
            fir="EGTT",
            fir_name="London FIR",
            notam_code="QFALC",
            code_description="Aerodrome closed",
            traffic="IV",
            traffic_decoded="IFR and VFR",
            purpose="NBO",
            scope="A",
            lower_altitude="000",
            upper_altitude="999",
            coordinates="5147N00028W",
            radius="005",
            raw="Q)EGTT/QFALC/IV/NBO/A/000/999/5147N00028W005",
        )
        assert q_line.notam_code == "QFALC"
        assert "London" in q_line.fir_name

    def test_q_line_with_parsed_coordinates(self):
        """带解析后坐标的 Q 行"""
        coords = Coordinates(latitude=51.4775, longitude=-0.4614, raw="5147N00028W")
        q_line = QLineResponse(
            fir="EGTT",
            coordinates="5147N00028W",
            coordinates_parsed=coords,
        )
        assert q_line.coordinates_parsed.latitude == 51.4775


class TestEParsedResponse:
    """E 行 LLM 解析结果模型测试"""

    def test_full_llm_response(self):
        """完整 LLM 响应"""
        e_parsed = EParsedResponse(
            summary="跑道关闭通知",
            translation="跑道 09L 因施工关闭",
            category="跑道相关",
            terminology=[
                {
                    "term": "RWY",
                    "expansion": "Runway (跑道)",
                    "category": "airport",
                }
            ],
            restricted_areas=[],
            validation_report={"is_valid": True},
            raw_llm_response='{"summary": "..."}',
        )
        assert e_parsed.summary == "跑道关闭通知"
        assert len(e_parsed.terminology) == 1

    def test_empty_llm_response(self):
        """空 LLM 响应"""
        e_parsed = EParsedResponse()
        assert e_parsed.summary is None
        assert e_parsed.terminology == []
        assert e_parsed.restricted_areas == []

    def test_terminology_with_dict(self):
        """术语列表支持字典"""
        e_parsed = EParsedResponse(
            terminology=[
                {"term": "RWY", "expansion": "Runway", "category": "airport"},
                {"term": "CLSD", "expansion": "Closed", "category": "status"},
            ]
        )
        assert len(e_parsed.terminology) == 2


class TestTerminologyItem:
    """术语项模型测试"""

    def test_valid_terminology_item(self):
        """有效术语项"""
        item = TerminologyItem(
            term="RWY",
            expansion="Runway (跑道)",
            category="airport",
        )
        assert item.term == "RWY"
        assert item.category == "airport"

    def test_optional_category(self):
        """可选分类"""
        item = TerminologyItem(term="TEST", expansion="Test term")
        assert item.category is None


class TestRestrictedArea:
    """限制区域模型测试"""

    def test_full_restricted_area(self):
        """完整限制区域"""
        area = RestrictedArea(
            name="RA-01",
            type="restricted",
            coordinates="40N116E",
            altitude_limits="0-10000FT",
            time_limits="0600-1800",
            description="军事演习区域",
        )
        assert area.name == "RA-01"
        assert area.type == "restricted"

    def test_minimal_restricted_area(self):
        """最小限制区域"""
        area = RestrictedArea()
        assert area.name is None


class TestNotamParseRequest:
    """解析请求模型测试"""

    def test_valid_request(self):
        """有效请求"""
        request = NotamParseRequest(
            notam_text="Q)EGTT/QFALC/IV/NBO/A/000/999\nA)EGLL\nB)2403150600\nE)RUNWAY CLSD",
            include_llm=True,
        )
        assert request.notam_text is not None
        assert request.include_llm is True

    def test_request_without_llm(self):
        """不带 LLM 解析的请求"""
        request = NotamParseRequest(
            notam_text="Q)EGTT/QFALC/IV/NBO/A/000/999\nA)EGLL\nE)TEST",
            include_llm=False,
        )
        assert request.include_llm is False

    def test_request_with_context(self):
        """带上下文的请求"""
        context = {"q_line": {"fir": "EGTT", "notam_code": "QFALC"}}
        request = NotamParseRequest(
            notam_text="Q)EGTT/QFALC/IV/NBO/A/000/999\nA)EGLL\nE)TEST",
            include_llm=True,
            context=context,
        )
        assert request.context == context

    def test_empty_notam_text_validation(self):
        """空 NOTAM 文本验证"""
        # Pydantic v2 不会自动验证空字符串，除非使用约束
        request = NotamParseRequest(notam_text="")
        assert request.notam_text == ""


class TestNotamParseResponse:
    """解析响应模型测试"""

    def test_minimal_response(self):
        """最小响应"""
        response = NotamParseResponse(
            raw_input="Q)EGTT/QFALC/IV/NBO/A/000/999\nA)EGLL\nE)TEST",
        )
        assert response.raw_input is not None
        assert response.warnings == []
        assert response.errors == []
        assert response.parser_version == "0.3.0"

    def test_full_response(self):
        """完整响应"""
        response = NotamParseResponse(
            raw_input="Q)EGTT/QFALC/IV/NBO/A/000/999\nA)EGLL\nB)2403150600\nE)RUNWAY CLSD",
            q_line=QLineResponse(fir="EGTT", fir_name="London FIR"),
            a_location=["EGLL"],
            time_window=TimeWindow(
                start="2024-03-15T06:00:00Z",
                end="2024-03-15T18:00:00Z",
            ),
            e_raw="RUNWAY CLSD",
            e_parsed=EParsedResponse(
                summary="跑道关闭",
                translation="跑道关闭",
                category="跑道相关",
            ),
        )
        assert response.q_line.fir == "EGTT"
        assert len(response.a_location) == 1
        assert response.e_parsed.summary == "跑道关闭"

    def test_response_with_errors(self):
        """带错误的响应"""
        response = NotamParseResponse(
            raw_input="INVALID NOTAM",
            q_line=None,
            a_location=None,
            errors=["缺少 Q 行", "缺少 A 行"],
            warnings=["格式可能不正确"],
        )
        assert len(response.errors) == 2
        assert len(response.warnings) == 1


class TestHealthResponse:
    """健康检查响应模型测试"""

    def test_health_response(self):
        """健康检查响应"""
        health = HealthResponse(
            status="healthy",
            version="0.3.0",
            llm_enabled=True,
            qcode_coverage=176,
            fir_coverage=102,
        )
        assert health.status == "healthy"
        assert health.qcode_coverage == 176


class TestBatchParseRequest:
    """批量解析请求模型测试"""

    def test_valid_batch_request(self):
        """有效批量请求"""
        request = BatchParseRequest(
            notam_texts=[
                "Q)EGTT/QFALC/IV/NBO/A/000/999\nA)EGLL\nE)TEST1",
                "Q)EGTT/QFALC/IV/NBO/A/000/999\nA)EGKK\nE)TEST2",
            ],
            include_llm=True,
        )
        assert len(request.notam_texts) == 2

    def test_empty_batch(self):
        """空批量请求"""
        request = BatchParseRequest(notam_texts=[])
        assert len(request.notam_texts) == 0


class TestBatchParseResult:
    """批量解析结果项模型测试"""

    def test_successful_result(self):
        """成功解析结果"""
        result = BatchParseResult(
            index=0,
            result=NotamParseResponse(raw_input="Q)EGTT/QFALC\nA)EGLL\nE)TEST"),
            error=None,
        )
        assert result.index == 0
        assert result.error is None

    def test_failed_result(self):
        """失败解析结果"""
        result = BatchParseResult(
            index=1,
            result=None,
            error="解析失败：缺少 Q 行",
        )
        assert result.index == 1
        assert "解析失败" in result.error


class TestBatchParseResponse:
    """批量解析响应模型测试"""

    def test_batch_response(self):
        """批量响应"""
        response = BatchParseResponse(
            total=5,
            success=4,
            failed=1,
            results=[
                BatchParseResult(
                    index=0,
                    result=NotamParseResponse(raw_input="NOTAM 1"),
                    error=None,
                ),
                BatchParseResult(
                    index=1,
                    result=None,
                    error="Error",
                ),
            ],
        )
        assert response.total == 5
        assert response.success == 4
        assert response.failed == 1


class TestJsonSchemaGeneration:
    """JSON Schema 生成测试"""

    def test_notam_parse_response_schema(self):
        """NotamParseResponse JSON Schema"""
        schema = NotamParseResponse.model_json_schema()

        assert schema["type"] == "object"
        assert "properties" in schema
        assert "raw_input" in schema["properties"]
        assert "q_line" in schema["properties"]
        assert "e_raw" in schema["properties"]
        assert "e_parsed" in schema["properties"]

    def test_health_response_schema(self):
        """HealthResponse JSON Schema"""
        schema = HealthResponse.model_json_schema()

        assert schema["type"] == "object"
        assert "properties" in schema
        assert "status" in schema["properties"]
        assert "version" in schema["properties"]
        assert "llm_enabled" in schema["properties"]
        assert "qcode_coverage" in schema["properties"]

    def test_e_parsed_response_schema(self):
        """EParsedResponse JSON Schema"""
        schema = EParsedResponse.model_json_schema()

        assert schema["type"] == "object"
        props = schema["properties"]

        assert "summary" in props
        assert "translation" in props
        assert "category" in props
        assert "terminology" in props
        assert "restricted_areas" in props
        assert "validation_report" in props

        # 验证 terminology 是数组
        assert props["terminology"]["type"] == "array"

    def test_q_line_response_schema(self):
        """QLineResponse JSON Schema"""
        schema = QLineResponse.model_json_schema()

        props = schema["properties"]
        assert "fir" in props
        assert "notam_code" in props
        assert "code_description" in props
        assert "traffic" in props
        assert "coordinates_parsed" in props
        assert "radius_parsed" in props

    def test_time_window_schema(self):
        """TimeWindow JSON Schema"""
        schema = TimeWindow.model_json_schema()

        props = schema["properties"]
        assert "start" in props
        assert "end" in props
        assert "is_permanent" in props
        assert "is_estimated" in props
        assert "schedules" in props

        # 验证布尔类型
        assert props["is_permanent"]["type"] == "boolean"

    def test_coordinates_schema(self):
        """Coordinates JSON Schema"""
        schema = Coordinates.model_json_schema()

        props = schema["properties"]
        assert "latitude" in props
        assert "longitude" in props
        assert "raw" in props

        # 验证数字类型
        assert props["latitude"]["type"] == "number"
        assert props["longitude"]["type"] == "number"

    def test_altitude_range_schema(self):
        """AltitudeRange JSON Schema"""
        schema = AltitudeRange.model_json_schema()

        props = schema["properties"]
        assert "lower" in props
        assert "upper" in props
        assert "lower_source" in props
        assert "upper_source" in props

    def test_notam_type_enum_schema(self):
        """NotamType 枚举 Schema"""
        # 使用 AnyOf 或生成包含枚举字段的模型来测试枚举
        from pydantic import BaseModel

        class TestModel(BaseModel):
            notam_type: NotamType

        schema = TestModel.model_json_schema()

        # 枚举应该在 schema 中以 enum 形式出现
        assert "notam_type" in schema["properties"]
        notam_type_schema = schema["properties"]["notam_type"]

        # Pydantic 可能将枚举放在 $defs 中引用
        if "$ref" in notam_type_schema:
            # 从 $defs 中获取枚举定义
            ref = notam_type_schema["$ref"]
            ref_name = ref.split("/")[-1]
            assert ref_name in schema.get("$defs", {})
            enum_def = schema["$defs"][ref_name]
            assert "enum" in enum_def
            assert "NOTAMN" in enum_def["enum"]
            assert "NOTAMR" in enum_def["enum"]
            assert "NOTAMC" in enum_def["enum"]
        else:
            # 直接内联枚举
            assert "enum" in notam_type_schema
            assert "NOTAMN" in notam_type_schema["enum"]
            assert "NOTAMR" in notam_type_schema["enum"]
            assert "NOTAMC" in notam_type_schema["enum"]

    def test_batch_parse_response_schema(self):
        """BatchParseResponse JSON Schema"""
        schema = BatchParseResponse.model_json_schema()

        props = schema["properties"]
        assert "total" in props
        assert "success" in props
        assert "failed" in props
        assert "results" in props

        # 验证整数类型
        assert props["total"]["type"] == "integer"


class TestModelValidation:
    """模型验证测试"""

    def test_model_validate_dict(self):
        """从字典验证模型"""
        data = {
            "raw_input": "Q)EGTT/QFALC\nA)EGLL\nE)TEST",
            "q_line": {"fir": "EGTT"},
            "a_location": ["EGLL"],
        }
        response = NotamParseResponse.model_validate(data)

        assert response.raw_input == "Q)EGTT/QFALC\nA)EGLL\nE)TEST"
        assert response.q_line.fir == "EGTT"

    def test_model_validate_with_nested_objects(self):
        """嵌套对象验证"""
        data = {
            "raw_input": "Q)EGTT/QFALC\nA)EGLL\nE)TEST",
            "q_line": {
                "fir": "EGTT",
                "coordinates_parsed": {
                    "latitude": 51.4775,
                    "longitude": -0.4614,
                    "raw": "5147N00028W",
                },
            },
            "time_window": {
                "start": "2024-03-15T06:00:00Z",
                "is_permanent": False,
                "schedules": [],
            },
        }
        response = NotamParseResponse.model_validate(data)

        assert response.q_line.coordinates_parsed.latitude == 51.4775
        assert response.time_window.start == "2024-03-15T06:00:00Z"

    def test_model_validate_json_string(self):
        """从 JSON 字符串验证"""
        json_str = '{"raw_input": "TEST NOTAM", "q_line": {"fir": "EGTT"}}'
        response = NotamParseResponse.model_validate_json(json_str)

        assert response.raw_input == "TEST NOTAM"
        assert response.q_line.fir == "EGTT"

    def test_model_dump(self):
        """模型转换为字典"""
        response = NotamParseResponse(
            raw_input="TEST",
            q_line=QLineResponse(fir="EGTT"),
        )
        data = response.model_dump()

        assert isinstance(data, dict)
        assert data["raw_input"] == "TEST"
        assert data["q_line"]["fir"] == "EGTT"

    def test_model_dump_json(self):
        """模型转换为 JSON"""
        response = NotamParseResponse(
            raw_input="TEST",
            q_line=QLineResponse(fir="EGTT"),
        )
        json_str = response.model_dump_json()

        assert isinstance(json_str, str)
        assert "TEST" in json_str
        assert "EGTT" in json_str

    def test_model_dump_exclude(self):
        """排除字段导出"""
        response = NotamParseResponse(
            raw_input="TEST",
            q_line=QLineResponse(fir="EGTT"),
            warnings=["warning 1"],
        )
        data = response.model_dump(exclude={"warnings"})

        assert "warnings" not in data
        assert data["raw_input"] == "TEST"

    def test_model_dump_none_exclude(self):
        """排除 None 值"""
        response = NotamParseResponse(raw_input="TEST")
        data = response.model_dump(exclude_none=True)

        assert "q_line" not in data  # q_line 为 None，被排除
        assert "raw_input" in data


class TestSchemaCompatibility:
    """Schema 兼容性测试"""

    def test_roundtrip_dict(self):
        """字典 -> 模型 -> 字典往返"""
        original_data = {
            "raw_input": "Q)EGTT/QFALC\nA)EGLL\nE)TEST",
            "q_line": {"fir": "EGTT", "fir_name": "London"},
            "a_location": ["EGLL"],
            "time_window": {
                "start": "2024-03-15T06:00:00Z",
                "end": "2024-03-15T18:00:00Z",
                "schedules": [],
            },
            "e_raw": "TEST",
        }

        # 模型验证
        response = NotamParseResponse.model_validate(original_data)

        # 转换回字典
        result_data = response.model_dump()

        assert result_data["raw_input"] == original_data["raw_input"]
        assert result_data["q_line"]["fir"] == "EGTT"

    def test_nested_model_compatibility(self):
        """嵌套模型兼容性"""
        # EParsedResponse 嵌套在 NotamParseResponse 中
        e_parsed = EParsedResponse(
            summary="测试摘要",
            translation="测试翻译",
            category="测试分类",
            terminology=[{"term": "RWY", "expansion": "跑道"}],
        )

        response = NotamParseResponse(
            raw_input="TEST",
            e_parsed=e_parsed,
        )

        data = response.model_dump()
        assert data["e_parsed"]["summary"] == "测试摘要"
        assert len(data["e_parsed"]["terminology"]) == 1
