"""NOTAM 解析 API 响应模型

基于真实 NOTAM 数据（2005 条）分析结果设计，覆盖：
- 176 种唯一 QCODE
- NOTAMN/NOTAMR/NOTAMC 类型
- 多系列（A/B/E/F/H 等）
- 完整的 Q 行解码
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime


class NotamType(str, Enum):
    """NOTAM 类型"""
    NEW = "NOTAMN"           # 新 NOTAM
    REPLACE = "NOTAMR"       # 替换现有 NOTAM
    CANCEL = "NOTAMC"        # 取消现有 NOTAM


class QLineResponse(BaseModel):
    """Q 行解析结果"""
    # 原始字段
    fir: Optional[str] = Field(None, description="飞行情报区代码 (如 ZBPE, EGTT)")
    fir_name: Optional[str] = Field(None, description="FIR 中文名称")
    notam_code: Optional[str] = Field(None, description="QCODE (5 位字母)")
    code_description: Optional[str] = Field(None, description="QCODE 中文描述")

    # 解码字段
    traffic: Optional[str] = Field(None, description="交通类型 (IFR/VFR/Checklist)")
    traffic_decoded: Optional[str] = Field(None, description="交通类型中文描述")
    purpose: Optional[str] = Field(None, description="发布目的 (N/B/O/M 组合)")
    purpose_decoded: Optional[str] = Field(None, description="发布目的中文描述")
    scope: Optional[str] = Field(None, description="适用范围 (A/E/W/K 组合)")
    scope_decoded: Optional[str] = Field(None, description="适用范围中文描述")

    # 高度和位置
    lower_altitude: Optional[str] = Field(None, description="下限高度 (FL)")
    upper_altitude: Optional[str] = Field(None, description="上限高度 (FL)")
    coordinates: Optional[str] = Field(None, description="坐标 (如 5147N00028W)")
    radius: Optional[str] = Field(None, description="半径 (如 005=5NM)")

    # 原始 Q 行文本
    raw: Optional[str] = Field(None, description="原始 Q 行文本")


class NotamIdentifier(BaseModel):
    """NOTAM 标识符"""
    series: Optional[str] = Field(None, description="系列字母 (如 A, B, C)")
    number: Optional[str] = Field(None, description="NOTAM 编号 (4 位)")
    year: Optional[str] = Field(None, description="年份后两位 (如 24)")
    type: Optional[NotamType] = Field(None, description="NOTAM 类型")

    # 完整标识符 (如 A0766/26 NOTAMN)
    full_id: Optional[str] = Field(None, description="完整 NOTAM ID")


class TimeWindow(BaseModel):
    """时间窗口"""
    start: Optional[str] = Field(None, description="生效时间 (ISO 8601)")
    end: Optional[str] = Field(None, description="结束时间 (ISO 8601)")
    is_permanent: bool = Field(False, description="是否永久生效 (PERM)")
    is_estimated: bool = Field(False, description="是否预计时间 (EST)")
    schedule: Optional[str] = Field(None, description="时间段/重复性 (D 行)")


class EParsedResponse(BaseModel):
    """E 行 LLM 解析结果"""
    summary: Optional[str] = Field(None, description="摘要 (中文)")
    translation: Optional[str] = Field(None, description="完整中文翻译")
    category: Optional[str] = Field(None, description="语义分类")

    # 术语解释
    terminology: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="术语解释列表"
    )

    # 限制区域
    restricted_areas: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="限制区域列表"
    )

    # 校验报告
    validation_report: Optional[Dict[str, Any]] = Field(
        None,
        description="术语校验报告"
    )

    # 原始 LLM 响应（用于调试）
    raw_llm_response: Optional[str] = Field(None, description="原始 LLM 响应")


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


class NotamParseResponse(BaseModel):
    """NOTAM 解析响应"""

    # ==================== 元数据 ====================
    notam_id: Optional[NotamIdentifier] = Field(
        None,
        description="NOTAM 标识符"
    )
    raw_input: str = Field(..., description="完整原始 NOTAM 文本")

    # ==================== Q 行解析 ====================
    q_line: Optional[QLineResponse] = Field(
        None,
        description="Q 行解析结果"
    )

    # ==================== A 行：适用机场/空域 ====================
    a_location: Optional[List[str]] = Field(
        None,
        description="适用机场/空域 ICAO 代码列表"
    )

    # ==================== B/C/D 行：时间 ====================
    time_window: Optional[TimeWindow] = Field(
        None,
        description="时间窗口"
    )

    # ==================== E 行：内容 ====================
    e_raw: Optional[str] = Field(None, description="E 行原始文本")
    e_parsed: Optional[EParsedResponse] = Field(
        None,
        description="E 行 LLM 解析结果"
    )

    # ==================== 校验信息 ====================
    warnings: List[str] = Field(
        default_factory=list,
        description="解析警告"
    )
    errors: List[str] = Field(
        default_factory=list,
        description="解析错误"
    )

    # ==================== 解析元数据 ====================
    parser_version: str = Field("0.2.0", description="解析器版本")


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    version: str
    llm_enabled: bool
    qcode_coverage: int = Field(176, description="支持的 QCODE 数量")
    fir_coverage: int = Field(60, description="支持的 FIR 数量")


class TerminologyItem(BaseModel):
    """术语解释项"""
    term: str = Field(..., description="原文术语")
    expansion: str = Field(..., description="完整解释")
    category: Optional[str] = Field(None, description="术语分类")


class RestrictedArea(BaseModel):
    """限制区域"""
    name: Optional[str] = Field(None, description="区域名称")
    type: Optional[str] = Field(None, description="区域类型")
    coordinates: Optional[str] = Field(None, description="坐标")
    altitude_limits: Optional[str] = Field(None, description="高度限制")
    time_limits: Optional[str] = Field(None, description="时间限制")
    description: Optional[str] = Field(None, description="区域描述")


class BatchParseRequest(BaseModel):
    """批量解析请求"""
    notam_texts: List[str] = Field(..., description="NOTAM 文本列表")
    include_llm: bool = Field(True, description="是否启用 LLM 解析")


class BatchParseResult(BaseModel):
    """批量解析结果项"""
    index: int
    result: Optional[NotamParseResponse]
    error: Optional[str] = None


class BatchParseResponse(BaseModel):
    """批量解析响应"""
    total: int
    success: int
    failed: int
    results: List[BatchParseResult]
