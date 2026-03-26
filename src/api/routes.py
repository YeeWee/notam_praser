"""NOTAM 解析 API 路由

提供同步解析端点，接收 NOTAM 文本，返回结构化 JSON
"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

from ..parsers.regex_parser import RegexParser, ParseResult
from ..parsers.llm_parser import LLMParser, parse_notam_e_line
from ..config import get_settings

router = APIRouter()
settings = get_settings()


class NotamParseRequest(BaseModel):
    """NOTAM 解析请求"""
    notam_text: str = Field(..., description="原始 NOTAM 文本")
    include_llm: bool = Field(
        default=True,
        description="是否启用 LLM 解析（摘要、翻译、分类等）"
    )
    context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="上下文信息（如 Q 行解析结果）"
    )


class TerminologyItem(BaseModel):
    """术语解释项"""
    term: str
    expansion: str
    category: Optional[str] = None


class RestrictedArea(BaseModel):
    """限制区域"""
    name: Optional[str] = None
    type: Optional[str] = None
    coordinates: Optional[str] = None
    altitude_limits: Optional[str] = None
    time_limits: Optional[str] = None
    description: Optional[str] = None


class QLineResponse(BaseModel):
    """Q 行解析结果"""
    fir: Optional[str] = None
    fir_name: Optional[str] = None
    notam_code: Optional[str] = None
    code_description: Optional[str] = None
    traffic: Optional[str] = None
    purpose: Optional[str] = None
    scope: Optional[str] = None
    lower_altitude: Optional[str] = None
    upper_altitude: Optional[str] = None
    coordinates: Optional[str] = None
    radius: Optional[str] = None


class NotamParseResponse(BaseModel):
    """NOTAM 解析响应"""
    # Q 行解析
    q_line: Optional[QLineResponse] = None
    # A 行：适用机场/空域
    a_location: Optional[List[str]] = None
    # B 行：生效时间 (ISO 8601)
    b_time: Optional[str] = None
    # C 行：结束时间 (ISO 8601)
    c_time: Optional[str] = None
    # D 行：时间段/重复性
    d_schedule: Optional[str] = None
    # E 行：原始文本
    e_raw: Optional[str] = None
    # E 行：LLM 解析结果
    e_parsed: Optional[Dict[str, Any]] = None
    # 警告和错误
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    version: str
    llm_enabled: bool


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """健康检查端点"""
    llm_enabled = bool(settings.openai_api_key)
    return HealthResponse(
        status="healthy",
        version="0.1.0-mvp",
        llm_enabled=llm_enabled
    )


@router.post("/parse", response_model=NotamParseResponse)
async def parse_notam(request: NotamParseRequest):
    """解析单条 NOTAM

    接收原始 NOTAM 文本，返回结构化解析结果。

    解析流程：
    1. 正则解析层：提取 Q/A/B/C/D/E 行结构化字段
    2. LLM 解析层（可选）：解析 E 行语义（摘要、翻译、分类、术语、限制区域）
    3. 术语库校验：验证 LLM 输出的术语解释

    Args:
        request: NOTAM 解析请求

    Returns:
        结构化解析结果

    Raises:
        HTTPException: 400 - 无效的 NOTAM 文本
        HTTPException: 500 - LLM 解析失败
    """
    # 验证输入
    if not request.notam_text or not request.notam_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="NOTAM 文本不能为空"
        )

    # 初始化解析器
    regex_parser = RegexParser()

    # Step 1: 正则解析层
    regex_result = regex_parser.parse(request.notam_text)

    # 构建响应
    response = NotamParseResponse(
        q_line=_q_line_to_response(regex_result.q_line) if regex_result.q_line else None,
        a_location=regex_result.a_location,
        b_time=regex_result.b_time.isoformat() if regex_result.b_time else None,
        c_time=regex_result.c_time.isoformat() if regex_result.c_time else None,
        d_schedule=regex_result.d_schedule,
        e_raw=regex_result.e_raw,
        warnings=regex_result.warnings,
        errors=regex_result.errors
    )

    # Step 2: LLM 解析层（可选）
    if request.include_llm and regex_result.e_raw:
        try:
            # 构建上下文（Q 行解码结果）
            context = None
            if regex_result.q_line:
                q_decoder = regex_parser.decode_q_line(regex_result.q_line)
                context = {"q_line": q_decoder}

            # 调用 LLM 解析器
            llm_parser = LLMParser(
                api_key=settings.openai_api_key,
                api_base=settings.openai_api_base,
                model=settings.openai_model
            )
            llm_result = llm_parser.parse_with_retry(
                e_text=regex_result.e_raw,
                context=context,
                max_retries=settings.llm_max_retries
            )

            # 构建 E 行解析结果
            response.e_parsed = {
                "summary": llm_result.summary,
                "translation": llm_result.translation,
                "category": llm_result.category,
                "terminology": llm_result.terminology,
                "restricted_areas": llm_result.restricted_areas,
                "validation_report": llm_result.validation_report,
                "raw_llm_response": llm_result.raw_llm_response
            }

        except Exception as e:
            # LLM 解析失败，不中断整体解析
            response.warnings.append(f"LLM 解析失败：{str(e)}")
            response.e_parsed = {
                "summary": None,
                "translation": None,
                "category": None,
                "terminology": [],
                "restricted_areas": [],
                "error": f"LLM 解析失败：{str(e)}"
            }

    return response


def _q_line_to_response(q_line) -> QLineResponse:
    """将 QLineResult 转换为 QLineResponse"""
    from ..parsers.regex_parser import RegexParser

    decoder = RegexParser()
    decoded = decoder.decode_q_line(q_line)

    return QLineResponse(
        fir=q_line.fir,
        fir_name=decoded.get("fir_name"),
        notam_code=q_line.notam_code,
        code_description=decoded.get("code_description"),
        traffic=q_line.traffic,
        purpose=q_line.purpose,
        scope=q_line.scope,
        lower_altitude=q_line.lower_altitude,
        upper_altitude=q_line.upper_altitude,
        coordinates=q_line.coordinates,
        radius=q_line.radius
    )
