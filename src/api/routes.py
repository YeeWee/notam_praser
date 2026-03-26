"""NOTAM 解析 API 路由

提供同步解析端点，接收 NOTAM 文本，返回结构化 JSON。
基于真实 NOTAM 数据（2005 条，176 种 QCODE）设计。
"""
from fastapi import APIRouter, HTTPException, status
from typing import Optional, Dict, Any, List
import re

from ..parsers.regex_parser import RegexParser, ParseResult
from ..parsers.llm_parser import LLMParser
from ..parsers.qcode_database import get_qcode_description, get_fir_description
from ..config import get_settings
from .models import (
    NotamParseRequest,
    NotamParseResponse,
    NotamIdentifier,
    QLineResponse,
    TimeWindow,
    EParsedResponse,
    HealthResponse,
    BatchParseRequest,
    BatchParseResponse,
    BatchParseResult,
    AltitudeRange,
    Coordinates,
    Radius,
    TimeSchedule,
)

router = APIRouter()
settings = get_settings()

# NOTAM ID 模式：A0766/26 NOTAMN
NOTAM_ID_PATTERN = re.compile(
    r'^([A-Z])(\d{4})/(\d{2})\s*(NOTAMN|NOTAMR|NOTAMC)?',
    re.IGNORECASE
)


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """健康检查端点"""
    llm_enabled = bool(settings.openai_api_key)
    return HealthResponse(
        status="healthy",
        version="0.3.0",
        llm_enabled=llm_enabled,
        qcode_coverage=176,  # 支持 176 种 QCODE
        fir_coverage=102,     # 支持 102 个 FIR (79.1% 覆盖率)
    )


@router.post("/parse", response_model=NotamParseResponse)
async def parse_notam(request: NotamParseRequest):
    """解析单条 NOTAM

    接收原始 NOTAM 文本，返回结构化解析结果。

    解析流程：
    1. NOTAM ID 提取：解析系列、编号、年份、类型
    2. 正则解析层：提取 Q/A/B/C/D/E 行结构化字段
    3. Q 行解码：FIR 名称、QCODE 描述、交通类型等
    4. LLM 解析层（可选）：解析 E 行语义

    Args:
        request: NOTAM 解析请求

    Returns:
        结构化解析结果

    Raises:
        HTTPException: 400 - 无效的 NOTAM 文本
    """
    # 验证输入
    if not request.notam_text or not request.notam_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="NOTAM 文本不能为空"
        )

    # Step 1: 提取 NOTAM ID
    notam_id = _extract_notam_id(request.notam_text)

    # Step 2: 正则解析层
    regex_parser = RegexParser()
    regex_result = regex_parser.parse(request.notam_text)

    # Step 3: 构建响应
    response = NotamParseResponse(
        notam_id=notam_id,
        raw_input=request.notam_text,
        confidence_score=regex_result.confidence_score,
        confidence_level="low" if regex_result.confidence_score < 80.0 else None,
        q_line=_q_line_to_response(regex_result.q_line) if regex_result.q_line else None,
        a_location=regex_result.a_location,
        time_window=_build_time_window(regex_result),
        altitude_range=_build_altitude_range(regex_result),
        e_raw=regex_result.e_raw,
        warnings=regex_result.warnings,
        errors=regex_result.errors,
    )

    # Step 4: LLM 解析层（可选）
    if request.include_llm and regex_result.e_raw:
        _add_llm_parsing(response, regex_result, request.context)

    return response


@router.post("/parse/batch", response_model=BatchParseResponse)
async def parse_notam_batch(request: BatchParseRequest):
    """批量解析 NOTAM

    Args:
        request: 批量解析请求

    Returns:
        批量解析结果
    """
    results: List[BatchParseResult] = []
    success_count = 0
    failed_count = 0

    for i, notam_text in enumerate(request.notam_texts):
        try:
            # 复用单条解析逻辑
            parse_request = NotamParseRequest(
                notam_text=notam_text,
                include_llm=request.include_llm,
            )
            result = await parse_notam(parse_request)
            results.append(BatchParseResult(
                index=i,
                result=result,
                error=None,
            ))
            success_count += 1
        except Exception as e:
            results.append(BatchParseResult(
                index=i,
                result=None,
                error=str(e),
            ))
            failed_count += 1

    return BatchParseResponse(
        total=len(request.notam_texts),
        success=success_count,
        failed=failed_count,
        results=results,
    )


def _extract_notam_id(notam_text: str) -> Optional[NotamIdentifier]:
    """提取 NOTAM ID

    支持格式：
    - A0766/26 NOTAMN
    - A0766/26 NOTAMR
    - A0766/26 NOTAMC
    """
    first_line = notam_text.strip().split('\n')[0]
    match = NOTAM_ID_PATTERN.match(first_line)

    if not match:
        return None

    series = match.group(1)
    number = match.group(2)
    year = match.group(3)
    type_ = match.group(4) or "NOTAMN"

    # 提取 NOTAMR 替换关系
    replaces = None
    if type_.upper() == "NOTAMR":
        notamr_pattern = re.compile(r'NOTAMR\s+([A-Z]\d{4}/\d{2})')
        notamr_match = notamr_pattern.search(notam_text)
        if notamr_match:
            replaces = notamr_match.group(1)

    return NotamIdentifier(
        series=series,
        number=number,
        year=year,
        type=type_.upper(),
        full_id=f"{series}{number}/{year} {type_}",
        replaces=replaces,
    )


def _build_time_window(regex_result: ParseResult) -> Optional[TimeWindow]:
    """构建时间窗口"""
    if not regex_result.b_time and not regex_result.c_time:
        return None

    # 解析 D 行结构化时间表
    schedules = []
    for d_sched in regex_result.d_schedules:
        schedules.append(TimeSchedule(
            start=d_sched.start.isoformat() if d_sched.start else None,
            end=d_sched.end.isoformat() if d_sched.end else None,
            recurrence=d_sched.recurrence,
            raw=d_sched.raw,
        ))

    return TimeWindow(
        start=regex_result.b_time.isoformat() if regex_result.b_time else None,
        end=regex_result.c_time.isoformat() if regex_result.c_time else None,
        is_permanent=regex_result.c_is_perm,
        is_estimated=regex_result.c_is_est,
        schedule=regex_result.d_schedule,
        schedules=schedules,
    )


def _build_altitude_range(regex_result: ParseResult) -> Optional[AltitudeRange]:
    """构建高度范围"""
    if not regex_result.altitude_range:
        return None

    return AltitudeRange(
        lower=regex_result.altitude_range.lower,
        upper=regex_result.altitude_range.upper,
        lower_source=regex_result.altitude_range.lower_source,
        upper_source=regex_result.altitude_range.upper_source,
    )


def _q_line_to_response(q_line) -> QLineResponse:
    """将 QLineResult 转换为 QLineResponse"""
    decoder = RegexParser()
    decoded = decoder.decode_q_line(q_line)

    # 解析坐标和半径
    coords_parsed = None
    radius_parsed = None

    if q_line.coordinates:
        coords_parsed = decoder.parse_coordinate(q_line.coordinates)
    if q_line.radius:
        radius_parsed = decoder.parse_radius(q_line.radius)

    return QLineResponse(
        fir=q_line.fir,
        fir_name=decoded.get("fir_name"),
        notam_code=q_line.notam_code,
        code_description=decoded.get("code_description"),
        traffic=q_line.traffic,
        traffic_decoded=decoded.get("traffic"),
        purpose=q_line.purpose,
        purpose_decoded=decoded.get("purpose"),
        scope=q_line.scope,
        scope_decoded=decoded.get("scope"),
        lower_altitude=q_line.lower_altitude,
        upper_altitude=q_line.upper_altitude,
        coordinates=q_line.coordinates,
        radius=q_line.radius,
        coordinates_parsed=Coordinates(
            latitude=coords_parsed.latitude,
            longitude=coords_parsed.longitude,
            raw=coords_parsed.raw,
        ) if coords_parsed else None,
        radius_parsed=Radius(
            value=radius_parsed.value,
            unit=radius_parsed.unit,
            raw=radius_parsed.raw,
        ) if radius_parsed else None,
        raw=q_line.raw,
    )


def _add_llm_parsing(
    response: NotamParseResponse,
    regex_result: ParseResult,
    context: Optional[Dict[str, Any]] = None,
):
    """添加 LLM 解析结果到响应"""
    try:
        # 构建上下文（Q 行解码结果）
        llm_context = None
        if regex_result.q_line:
            q_decoder = RegexParser().decode_q_line(regex_result.q_line)
            llm_context = {"q_line": q_decoder}

        # 调用 LLM 解析器
        llm_parser = LLMParser(
            api_key=settings.openai_api_key,
            api_base=settings.openai_api_base,
            model=settings.openai_model,
        )
        llm_result = llm_parser.parse_with_retry(
            e_text=regex_result.e_raw,
            context=llm_context,
            max_retries=settings.llm_max_retries,
        )

        # 构建 E 行解析结果
        response.e_parsed = EParsedResponse(
            summary=llm_result.summary,
            translation=llm_result.translation,
            category=llm_result.category,
            terminology=llm_result.terminology,
            restricted_areas=llm_result.restricted_areas,
            validation_report=llm_result.validation_report,
            raw_llm_response=llm_result.raw_llm_response,
        )

    except Exception as e:
        # LLM 解析失败，不中断整体解析
        response.warnings.append(f"LLM 解析失败：{str(e)}")
        response.e_parsed = EParsedResponse(
            summary=None,
            translation=None,
            category=None,
            terminology=[],
            restricted_areas=[],
            validation_report={"error": f"LLM 解析失败：{str(e)}"},
            raw_llm_response=None,
        )
