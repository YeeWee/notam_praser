"""ICAO 术语库

提供航空术语解释和 LLM 输出校验
"""
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


# ICAO Doc 8400 常用缩写和术语
ICAO_TERMS: Dict[str, str] = {
    # 机场相关
    "AD": "Aerodrome (机场)",
    "APRT": "Aerodrome (机场)",
    "RWY": "Runway (跑道)",
    "TWY": "Taxiway (滑行道)",
    "APN": "Apron (机坪)",
    "VNR": "Vanway (滑行道)",

    # 导航设施
    "VOR": "VHF Omnidirectional Range (甚高频全向信标)",
    "DME": "Distance Measuring Equipment (测距仪)",
    "NDB": "Non-Directional Beacon (无方向性信标)",
    "ILS": "Instrument Landing System (仪表着陆系统)",
    "GPS": "Global Positioning System (全球定位系统)",
    "GNSS": "Global Navigation Satellite System (全球导航卫星系统)",

    # 空域相关
    "FIR": "Flight Information Region (飞行情报区)",
    "CTR": "Control Zone (管制地带)",
    "TMA": "Terminal Control Area (终端管制区)",
    "AWY": "Airway (航路)",
    "UIR": "Upper Information Region (高空情报区)",

    # 飞行规则
    "IFR": "Instrument Flight Rules (仪表飞行规则)",
    "VFR": "Visual Flight Rules (目视飞行规则)",

    # 状态描述
    "CLSD": "Closed (关闭)",
    "OPS": "Operations (运行)",
    "U/S": "Unserviceable (不可用)",
    "UNRELIABLE": "不可靠",
    "LIMITED": "受限",
    "RESTRICTED": "限制",
    "PROHIBITED": "禁止",
    "DANGER": "危险",

    # 时间相关
    "HR": "Hour (小时)",
    "MIN": "Minute (分钟)",
    "FCST": "Forecast (预报)",
    "EST": "Estimated (预计)",
    "AMD": "Amended (修订)",
    "CNL": "Cancelled (取消)",

    # 天气相关
    "WX": "Weather (天气)",
    "CB": "Cumulonimbus (积雨云)",
    "TC": "Tropical Cyclone (热带气旋)",
    "TS": "Thunderstorm (雷暴)",
    "GR": "Hail (冰雹)",
    "GS": "Small Hail (小冰雹)",
    "SN": "Snow (雪)",
    "RA": "Rain (雨)",
    "FG": "Fog (雾)",
    "BR": "Mist (轻雾)",

    # 其他常用
    "BTN": "Between (在...之间)",
    "WI": "Within (在...之内)",
    "FM": "From (从)",
    "TO": "To (到)",
    "TL": "Until (直到)",
    "PSN": "Position (位置)",
    "COORD": "Coordinates (坐标)",
    "REF": "Reference (参考)",
    "NOTAM": "Notice to Airmen (航行通告)",
    "NOTAMR": "NOTAM Replace (取代航行通告)",
    "NOTAMC": "NOTAM Cancel (取消航行通告)",
}


@dataclass
class TerminologyMatch:
    """术语匹配结果"""
    term: str  # 原文术语
    expansion: str  # 完整解释
    category: str  # 分类
    source: str  # 来源（术语库/LLM）


@dataclass
class ValidationReport:
    """LLM 输出校验报告"""
    is_valid: bool  # 是否通过校验
    terminology_corrected: List[TerminologyMatch] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class TerminologyDatabase:
    """术语数据库"""

    def __init__(self):
        self.terms = ICAO_TERMS
        self._load_additional_terms()

    def _load_additional_terms(self):
        """加载额外术语（可扩展）"""
        # 预留扩展接口
        pass

    def lookup(self, term: str) -> Optional[Dict[str, str]]:
        """查找术语"""
        term_upper = term.upper().strip()

        # 直接匹配
        if term_upper in self.terms:
            return {
                "term": term,
                "expansion": self.terms[term_upper],
                "category": self._categorize_term(term_upper),
                "source": "terminology_db"
            }

        # 部分匹配（处理带标点的情况）
        clean_term = term_upper.rstrip('.,;:!?')
        if clean_term in self.terms:
            return {
                "term": term,
                "expansion": self.terms[clean_term],
                "category": self._categorize_term(clean_term),
                "source": "terminology_db"
            }

        return None

    def _categorize_term(self, term: str) -> str:
        """对术语进行分类"""
        category_keywords = {
            "airport": ["AD", "APRT", "RWY", "TWY", "APN"],
            "navigation": ["VOR", "DME", "NDB", "ILS", "GPS", "GNSS"],
            "airspace": ["FIR", "CTR", "TMA", "AWY", "UIR"],
            "rules": ["IFR", "VFR"],
            "status": ["CLSD", "OPS", "U/S", "UNRELIABLE"],
            "weather": ["WX", "CB", "TC", "TS", "SN", "RA", "FG"],
            "time": ["HR", "MIN", "FCST", "EST"],
        }

        for category, keywords in category_keywords.items():
            if term in keywords:
                return category

        return "general"

    def validate_llm_output(self, llm_terminology: List[Dict[str, Any]]) -> ValidationReport:
        """校验 LLM 输出的术语解释"""
        report = ValidationReport(is_valid=True)

        for item in llm_terminology:
            original_term = item.get("term", "")
            llm_expansion = item.get("expansion", "")

            # 查找术语库中的定义
            db_result = self.lookup(original_term)

            if db_result:
                # 术语库中有定义，对比是否一致
                db_expansion = db_result["expansion"]

                # 简单的文本相似度检查（可扩展）
                if not self._expansions_match(llm_expansion, db_expansion):
                    report.terminology_corrected.append(TerminologyMatch(
                        term=original_term,
                        expansion=db_expansion,
                        category=db_result["category"],
                        source="terminology_db"
                    ))
                    report.warnings.append(
                        f"术语 '{original_term}' 的解释已根据术语库校正"
                    )
            else:
                # 术语库中没有，标记为 LLM 生成
                report.warnings.append(
                    f"术语 '{original_term}' 未在术语库中找到，使用 LLM 解释"
                )

        if report.errors:
            report.is_valid = False

        return report

    def _expansions_match(self, llm_expansion: str, db_expansion: str) -> bool:
        """判断 LLM 解释与术语库解释是否匹配"""
        # 简化处理：检查关键部分是否包含
        llm_lower = llm_expansion.lower()
        db_lower = db_expansion.lower()

        # 如果 LLM 解释包含了术语库的核心内容，认为匹配
        # 例如：术语库说"Runway (跑道)"，LLM 说"跑道"也算匹配
        key_parts = [p.strip() for p in db_lower.split() if len(p) > 2]

        matches = 0
        for part in key_parts:
            if part in llm_lower:
                matches += 1

        # 50% 以上匹配认为有效
        return matches >= len(key_parts) * 0.5 if key_parts else False

    def extract_terms_from_text(self, text: str) -> List[Dict[str, str]]:
        """从文本中提取已知术语"""
        found_terms = []
        text_upper = text.upper()

        for term in self.terms.keys():
            if term in text_upper:
                found_terms.append({
                    "term": term,
                    "expansion": self.terms[term],
                    "category": self._categorize_term(term),
                    "source": "terminology_db"
                })

        return found_terms

    def get_all_terms(self) -> Dict[str, str]:
        """获取所有术语"""
        return self.terms.copy()


# 全局实例
terminology_db = TerminologyDatabase()


def get_terminology_db() -> TerminologyDatabase:
    """获取术语数据库实例"""
    return terminology_db
