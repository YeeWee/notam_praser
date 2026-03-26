"""NOTAM LLM 解析器

解析 NOTAM E 行（非结构化语义内容）：
- 摘要生成
- 全文翻译
- 语义分类
- 术语解释
- 限制区域解析
"""
import json
import re
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from .terminology_db import TerminologyDatabase, get_terminology_db


@dataclass
class LLMParserResult:
    """LLM 解析结果"""
    summary: Optional[str] = None  # 摘要
    translation: Optional[str] = None  # 翻译
    category: Optional[str] = None  # 语义分类
    terminology: List[Dict[str, Any]] = field(default_factory=list)  # 术语解释
    restricted_areas: List[Dict[str, Any]] = field(default_factory=list)  # 限制区域
    raw_llm_response: Optional[str] = None  # 原始 LLM 响应
    validation_report: Optional[Dict[str, Any]] = None  # 校验报告
    confidence_score: float = 0.0  # 置信度评分


class LLMParser:
    """NOTAM LLM 解析器"""

    # 预定义分类
    CATEGORIES = {
        "RUNWAY": "跑道相关",
        "TAXIWAY": "滑行道相关",
        "AERODROME": "机场相关",
        "NAVIGATION": "导航设施",
        "AIRSPACE": "空域限制",
        "WEATHER": "天气相关",
        "OBSTACLE": "障碍物",
        "MILITARY": "军事活动",
        "EVENT": "特殊事件",
        "OTHER": "其他",
    }

    def __init__(self, api_key: Optional[str] = None, api_base: Optional[str] = None, model: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.api_base = api_base
        self.model = model
        self.terminology_db = get_terminology_db()
        self._client = None

    @property
    def client(self):
        """懒加载 OpenAI 客户端"""
        if self._client is None:
            try:
                from openai import OpenAI
                kwargs = {"api_key": self.api_key} if self.api_key else {}
                if self.api_base:
                    kwargs["base_url"] = self.api_base
                self._client = OpenAI(**kwargs)
            except ImportError:
                raise ImportError("请安装 openai 包：pip install openai")
        return self._client

    def parse(self, e_text: str, context: Optional[Dict[str, Any]] = None) -> LLMParserResult:
        """解析 E 行文本

        Args:
            e_text: E 行原始文本
            context: 上下文信息（Q 行解析结果等）

        Returns:
            LLM 解析结果
        """
        if not e_text or not e_text.strip():
            return LLMParserResult()

        # 构建 prompt
        prompt = self._build_prompt(e_text, context)

        # 调用 LLM
        response = self._call_llm(prompt)

        # 解析响应
        result = self._parse_response(response, e_text)

        # 术语校验
        result.validation_report = self._validate_terminology(result.terminology)

        # 计算 LLM 解析置信度
        result.confidence_score = self._calculate_confidence(result)

        return result

    def _calculate_confidence(self, result: LLMParserResult) -> float:
        """计算 LLM 解析置信度 (0-25 分，按比例转换为 0-100)

        评分标准:
        - LLM 返回有效 JSON: 10 分
        - 摘要和翻译存在：8 分
        - 术语校验通过：7 分

        Returns:
            置信度分数 (0-100)
        """
        score = 0.0

        # LLM 返回有效 JSON (10 分)
        if result.raw_llm_response:
            score += 10.0

        # 摘要和翻译存在 (8 分)
        if result.summary:
            score += 4.0
        if result.translation:
            score += 4.0

        # 术语校验通过 (7 分)
        if result.validation_report:
            if result.validation_report.get("is_valid", False):
                score += 7.0
            else:
                # 术语校验失败，部分得分
                score += 2.0

        # 转换为 0-100 分制
        return (score / 25.0) * 100.0

    def _build_prompt(self, e_text: str, context: Optional[Dict[str, Any]] = None) -> str:
        """构建 LLM Prompt"""
        context_info = ""
        if context:
            q_line = context.get("q_line", {})
            if q_line:
                fir = q_line.get("fir", "")
                code = q_line.get("notam_code", "")
                context_info = f"- FIR: {fir}\n- NOTAM Code: {code}\n"

        prompt = f"""你是一个航空领域的专业 NOTAM 解析助手。请解析以下 NOTAM E 行内容。

{context_info}
E 行内容：
```
{e_text}
```

请以严格的 JSON 格式返回以下字段：

{{
    "summary": "用 1-2 句话概括 NOTAM 的核心内容（中文）",
    "translation": "将 E 行完整翻译为中文",
    "category": "从以下分类中选择最匹配的一个：RUNWAY, TAXIWAY, AERODROME, NAVIGATION, AIRSPACE, WEATHER, OBSTACLE, MILITARY, EVENT, OTHER",
    "terminology": [
        {{
            "term": "原文术语或缩写",
            "expansion": "完整解释（包含中文）",
            "category": "术语分类"
        }}
    ],
    "restricted_areas": [
        {{
            "name": "区域名称或标识",
            "type": "区域类型（如 restricted, danger, prohibited 等）",
            "coordinates": "坐标（如有）",
            "altitude_limits": "高度限制（如有）",
            "time_limits": "时间限制（如有）",
            "description": "区域描述"
        }}
    ]
}}

注意：
1. 如果某个字段不适用，返回 null 或空数组
2. terminology 只包含 E 行中的专业术语和缩写
3. restricted_areas 只包含明确提到的限制区域
4. 确保输出是有效的 JSON，可以被 json.loads() 解析"""

        return prompt

    def _call_llm(self, prompt: str, max_retries: int = 3) -> str:
        """调用 LLM API"""
        import time

        last_error = None
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "你是一个专业的航空 NOTAM 解析助手，只返回有效的 JSON 格式响应。"},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,  # 低温度确保输出稳定
                    max_tokens=2000,
                )
                return response.choices[0].message.content
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    # 指数退避
                    delay = 2 ** attempt
                    time.sleep(delay)
                continue

        raise last_error or Exception("LLM 调用失败")

    def _parse_response(self, response: str, original_text: str) -> LLMParserResult:
        """解析 LLM 响应"""
        result = LLMParserResult(raw_llm_response=response)

        # 清理响应（处理可能的 markdown 代码块标记）
        cleaned = response.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)

            result.summary = data.get("summary")
            result.translation = data.get("translation")
            result.category = self._decode_category(data.get("category"))
            result.terminology = data.get("terminology", [])
            result.restricted_areas = data.get("restricted_areas", [])

        except json.JSONDecodeError as e:
            # JSON 解析失败，尝试降级处理
            result.summary = f"[解析失败] LLM 返回了无效的 JSON: {str(e)}"
            result.translation = original_text  # 返回原文作为降级
            result.category = "OTHER"
            result.terminology = []
            result.restricted_areas = []

        return result

    def _decode_category(self, category: Optional[str]) -> str:
        """解码分类"""
        if not category:
            return "未分类"
        return self.CATEGORIES.get(category.upper(), category)

    def _validate_terminology(self, terminology: List[Dict[str, Any]]) -> Dict[str, Any]:
        """校验术语解释"""
        if not terminology:
            return {"is_valid": True, "warnings": [], "errors": []}

        report = self.terminology_db.validate_llm_output(terminology)

        return {
            "is_valid": report.is_valid,
            "corrected_terms": [
                {"term": m.term, "corrected_to": m.expansion}
                for m in report.terminology_corrected
            ],
            "warnings": report.warnings,
            "errors": report.errors,
        }

    def parse_with_retry(self, e_text: str, context: Optional[Dict[str, Any]] = None, max_retries: int = 3) -> LLMParserResult:
        """带重试的解析（用于 Schema 验证失败时重试）"""
        last_result = None

        for attempt in range(max_retries):
            try:
                result = self.parse(e_text, context)

                # 验证结果有效性
                if result.validation_report and result.validation_report.get("is_valid", True):
                    return result

                last_result = result

            except Exception as e:
                last_result = LLMParserResult(
                    summary=f"[解析失败] 第{attempt + 1}次重试失败：{str(e)}"
                )

        return last_result or LLMParserResult()


# 便捷函数
def parse_notam_e_line(
    e_text: str,
    context: Optional[Dict[str, Any]] = None,
    api_key: Optional[str] = None,
    api_base: Optional[str] = None,
    model: str = "gpt-4o-mini"
) -> LLMParserResult:
    """便捷函数：解析 NOTAM E 行"""
    parser = LLMParser(api_key=api_key, api_base=api_base, model=model)
    return parser.parse_with_retry(e_text, context)
