"""NOTAM 解析置信度计算器

基于科学评分标准计算解析结果的置信度分数 (0-100)。

评分模型:
- 第一层：必填字段完整性 (40 分)
- 第二层：字段有效性验证 (35 分)
- 第三层：LLM 解析质量 (25 分)
- 错误惩罚：每个错误扣 5 分，每个警告扣 2 分
"""
from typing import Optional, Dict, Any
from dataclasses import dataclass

from .qcode_database import get_qcode_description, get_fir_description


@dataclass
class ConfidenceBreakdown:
    """置信度细分（用于内部计算和调试）"""
    base_completeness: float = 0.0  # 必填字段完整性 (0-40)
    validity_bonus: float = 0.0     # 字段有效性 (0-35)
    llm_quality: float = 0.0        # LLM 解析质量 (0-25)
    error_penalty: float = 0.0      # 错误惩罚
    final_score: float = 0.0        # 最终分数 (0-100)


class ConfidenceCalculator:
    """置信度计算器"""

    # 评分权重
    WEIGHT_Q_LINE = 15.0          # Q 行存在且可解析
    WEIGHT_A_LINE = 10.0          # A 行存在
    WEIGHT_B_LINE = 10.0          # B 行存在且时间有效
    WEIGHT_E_LINE = 5.0           # E 行存在

    WEIGHT_QCODE_VALID = 15.0     # QCODE 在数据库中
    WEIGHT_FIR_VALID = 10.0       # FIR 在数据库中
    WEIGHT_TIME_LOGIC = 5.0       # C 时间 >= B 时间
    WEIGHT_COORD_VALID = 3.0      # 坐标格式有效
    WEIGHT_RADIUS_VALID = 2.0     # 半径格式有效

    WEIGHT_LLM_JSON = 10.0        # LLM 返回有效 JSON
    WEIGHT_LLM_CONTENT = 8.0      # 摘要和翻译存在
    WEIGHT_LLM_TERMINOLOGY = 7.0  # 术语校验通过

    CONFIDENCE_LEVEL_THRESHOLD = 80.0  # 低置信度阈值

    def calculate(
        self,
        regex_result: Any,  # ParseResult
        llm_result: Optional[Any] = None,  # LLMParserResult
    ) -> float:
        """计算置信度分数

        Args:
            regex_result: 正则解析结果
            llm_result: LLM 解析结果（可选）

        Returns:
            置信度分数 (0-100)
        """
        breakdown = ConfidenceBreakdown()

        # 第一层：必填字段完整性 (40 分)
        breakdown.base_completeness = self._calculate_completeness(regex_result)

        # 第二层：字段有效性验证 (35 分)
        breakdown.validity_bonus = self._calculate_validity(regex_result)

        # 第三层：LLM 解析质量 (25 分)
        if llm_result:
            breakdown.llm_quality = self._calculate_llm_quality(llm_result)

        # 错误惩罚
        breakdown.error_penalty = self._calculate_penalty(regex_result)

        # 计算最终分数
        breakdown.final_score = (
            breakdown.base_completeness +
            breakdown.validity_bonus +
            breakdown.llm_quality -
            breakdown.error_penalty
        )

        # 归一化到 0-100
        breakdown.final_score = max(0.0, min(100.0, breakdown.final_score))

        return breakdown.final_score

    def _calculate_completeness(self, regex_result: Any) -> float:
        """计算必填字段完整性得分 (0-40)"""
        score = 0.0

        # Q 行存在且可解析 (15 分)
        if regex_result.q_line:
            score += self.WEIGHT_Q_LINE
        else:
            # Q 行缺失是严重问题，扣完
            pass

        # A 行存在 (10 分)
        if regex_result.a_location:
            score += self.WEIGHT_A_LINE
        else:
            score -= self.WEIGHT_A_LINE * 0.5  # 扣 5 分

        # B 行存在且时间有效 (10 分)
        if regex_result.b_time:
            score += self.WEIGHT_B_LINE
        else:
            score -= self.WEIGHT_B_LINE * 0.5  # 扣 5 分

        # E 行存在 (5 分)
        if regex_result.e_raw:
            score += self.WEIGHT_E_LINE
        else:
            # E 行缺失不扣分（某些 NOTAM 可能没有 E 行）
            pass

        return max(0.0, score)

    def _calculate_validity(self, regex_result: Any) -> float:
        """计算字段有效性得分 (0-35)"""
        score = 0.0
        q_line = regex_result.q_line

        # QCODE 在数据库中 (15 分)
        if q_line and q_line.notam_code:
            qcode_desc = get_qcode_description(q_line.notam_code)
            if qcode_desc:
                score += self.WEIGHT_QCODE_VALID
            # 否则不得分

        # FIR 在数据库中 (10 分)
        if q_line and q_line.fir:
            fir_desc = get_fir_description(q_line.fir)
            if fir_desc:
                score += self.WEIGHT_FIR_VALID
            # 否则不得分

        # C 时间 >= B 时间 (5 分)
        if regex_result.b_time and regex_result.c_time:
            if regex_result.c_time >= regex_result.b_time:
                score += self.WEIGHT_TIME_LOGIC
            else:
                # 时间逻辑错误，扣分
                score -= self.WEIGHT_TIME_LOGIC * 0.5
        elif regex_result.b_time or regex_result.c_is_perm:
            # 有 B 时间或标记为 PERM，认为是有效的
            score += self.WEIGHT_TIME_LOGIC

        # 坐标格式有效 (3 分)
        if q_line and q_line.coordinates:
            # 坐标已在正则解析时验证过格式
            score += self.WEIGHT_COORD_VALID

        # 半径格式有效 (2 分)
        if q_line and q_line.radius:
            # 半径已在正则解析时验证过格式
            score += self.WEIGHT_RADIUS_VALID

        return max(0.0, score)

    def _calculate_llm_quality(self, llm_result: Any) -> float:
        """计算 LLM 解析质量得分 (0-25)"""
        score = 0.0

        # LLM 返回有效 JSON (10 分)
        # 如果能到达这里，说明 LLM 调用成功且 JSON 解析成功
        if llm_result.raw_llm_response:
            score += self.WEIGHT_LLM_JSON

        # 摘要和翻译存在 (8 分)
        if llm_result.summary:
            score += self.WEIGHT_LLM_CONTENT * 0.5
        if llm_result.translation:
            score += self.WEIGHT_LLM_CONTENT * 0.5

        # 术语校验通过 (7 分)
        if llm_result.validation_report:
            if llm_result.validation_report.get("is_valid", False):
                score += self.WEIGHT_LLM_TERMINOLOGY
            else:
                # 术语校验失败，部分扣分
                score += self.WEIGHT_LLM_TERMINOLOGY * 0.3

        return max(0.0, min(25.0, score))

    def _calculate_penalty(self, regex_result: Any) -> float:
        """计算错误惩罚"""
        penalty = 0.0

        # 每个错误扣 5 分
        penalty += len(regex_result.errors or []) * 5.0

        # 每个警告扣 2 分
        penalty += len(regex_result.warnings or []) * 2.0

        return penalty

    @staticmethod
    def get_confidence_level(score: float) -> Optional[str]:
        """获取置信度等级标记

        Args:
            score: 置信度分数 (0-100)

        Returns:
            "low" 表示低置信度，None 表示正常
        """
        if score < ConfidenceCalculator.CONFIDENCE_LEVEL_THRESHOLD:
            return "low"
        return None


def calculate_confidence(
    regex_result: Any,
    llm_result: Optional[Any] = None,
) -> tuple[float, Optional[str]]:
    """便捷函数：计算置信度分数和等级

    Args:
        regex_result: 正则解析结果
        llm_result: LLM 解析结果（可选）

    Returns:
        (confidence_score, confidence_level) 元组
    """
    calculator = ConfidenceCalculator()
    score = calculator.calculate(regex_result, llm_result)
    level = calculator.get_confidence_level(score)
    return score, level
