"""ICAO QCODE 解码数据库

基于 ICAO Doc 8126 标准和真实 NOTAM 数据 (2005 条，176 种唯一 QCODE) 生成。

QCODE 结构说明:
- 格式：Q + 类别 (1 位) + 子类别 (1 位) + 具体项 (2 位)
- 示例：QRTCA = Q + R(限制区) + T(临时) + CA(可用)

类别分类 (第 2 位):
- A = 航路信息服务 (AIS)
- C = 通信 (Communications)
- F = 机场 (Aerodrome)
- G = GNSS
- I = 仪表着陆系统 (ILS)
- L = 灯光 (Lights)
- M = 气象服务 (Meteorology)
- N = 导航设施 (Navaids)
- O = 机场其他设施
- P = 跑道 (Runway)
- R = 限制空域 (Restricted Area)
- S = 滑行道 (Taxiway)
- W = 警告 (Warning)
- X = 特殊/未分类
"""
from typing import Dict, Optional

# QCODE 完整解码表 - 基于真实 NOTAM 数据覆盖 (176 种)
QCODE_DESCRIPTIONS: Dict[str, str] = {
    # ==================== 航路信息服务 (A) ====================
    "QACCH": "航路信息 - 变更 (AIS Change)",
    "QACXX": "航路信息 - 未指定 (AIS Unspecified)",
    "QAECA": "航路信息 - 可用 (AIS Available)",
    "QAEXX": "航路信息 - 未指定 (AIS Unspecified)",
    "QAFLP": "航路信息 - 飞行计划 (AIS Flight Plan)",
    "QAFTT": "航路信息 - 测试 (AIS Test)",
    "QAFXX": "航路信息 - 未指定 (AIS Unspecified)",
    "QANCA": "航路信息 - 可用 (AIS Available)",
    "QANLC": "航路信息 - 关闭 (AIS Closed)",
    "QANTT": "航路信息 - 测试 (AIS Test)",
    "QAPXX": "航路信息 - 未指定 (AIS Unspecified)",
    "QARCA": "航路信息 - 可用 (AIS Available)",
    "QARCH": "航路信息 - 变更 (AIS Change)",
    "QARCS": "航路信息 - 服务 (AIS Service)",
    "QARLC": "航路信息 - 关闭 (AIS Closed)",
    "QARXX": "航路信息 - 未指定 (AIS Unspecified)",
    "QATCH": "航路信息 - 变更 (AIS Change)",
    "QATLT": "航路信息 - 限制 (AIS Limited)",
    "QATXX": "航路信息 - 未指定 (AIS Unspecified)",

    # ==================== 通信 (C) ====================
    "QCAAS": "通信 - ATC 频率可用 (ATC Frequency Available)",
    "QCALF": "通信 - 频率限制 (Frequency Limited)",
    "QCALT": "通信 - 频率限制 (Frequency Limited)",
    "QCAXX": "通信 - 未指定 (Communications Unspecified)",
    "QCBLS": "通信 - 基站服务 (Base Station Service)",
    "QCDAS": "通信 - 数据链可用 (Data Link Available)",
    "QCDXX": "通信 - 未指定 (Data Link Unspecified)",
    "QCEAS": "通信 - 应急频率可用 (Emergency Frequency Available)",
    "QCELT": "通信 - 应急限制 (Emergency Limited)",
    "QCPAS": "通信 - 可用 (Communications Available)",
    "QCSAS": "通信 - 服务可用 (Communication Service Available)",
    "QCSLT": "通信 - 服务限制 (Communication Service Limited)",
    "QCTAS": "通信 - ATIS 可用 (ATIS Available)",

    # ==================== 机场 (F) ====================
    "QFAAH": "机场 - 动物活动 (Animal Activity)",
    "QFAAP": "机场 - 可用 (Aerodrome Available)",
    "QFAHG": "机场 - 危险物 (Hazardous Goods)",
    "QFAHW": "机场 - 野生动物 (Wildlife Hazard)",
    "QFAHX": "机场 - 危险物 (Hazard)",
    "QFALC": "机场关闭 (Aerodrome Closed)",
    "QFALT": "机场限制 (Aerodrome Limited)",
    "QFATT": "机场 - 测试 (Aerodrome Test)",
    "QFAXX": "机场 - 未指定 (Aerodrome Unspecified)",
    "QFFAH": "机场消防 - 可用 (Fire Fighting Available)",
    "QFGAS": "机场地面服务 - 可用 (Ground Service Available)",
    "QFGXX": "机场地面服务 - 未指定 (Ground Service Unspecified)",
    "QFMAU": "机场维护 - 不可用 (Maintenance Unavailable)",
    "QFMXX": "机场维护 - 未指定 (Maintenance Unspecified)",
    "QFTAS": "机场交通 - 可用 (Traffic Available)",
    "QFWAS": "机场警告 - 可用 (Aerodrome Warning Available)",
    "QFWXX": "机场警告 - 未指定 (Aerodrome Warning Unspecified)",

    # ==================== GNSS (G) ====================
    "QGAXX": "GNSS - 未指定 (GNSS Unspecified)",
    "QGWLS": "GNSS - 警告服务 (GNSS Warning Service)",
    "QGWXX": "GNSS - 警告未指定 (GNSS Warning Unspecified)",

    # ==================== 仪表着陆系统 (I) ====================
    "QICAS": "ILS CAT I 可用 (ILS Cat I Available)",
    "QICCT": "ILS 校验中 (ILS Calibration)",
    "QIDAS": "ILS DME 可用 (ILS DME Available)",
    "QIDLT": "ILS DME 限制 (ILS DME Limited)",
    "QIGAS": "ILS GP 可用 (ILS Glide Path Available)",
    "QIGCT": "ILS GP 校验 (ILS Glide Path Calibration)",
    "QIIAS": "ILS 识别可用 (ILS Identification Available)",
    "QILAS": "ILS 定位器可用 (ILS Localizer Available)",
    "QITAS": "ILS 台站可用 (ILS Station Available)",
    "QITCG": "ILS 台站校验 (ILS Station Calibration)",
    "QIUAS": "ILS 不可用 (ILS Unavailable)",
    "QIUCG": "ILS 校验 (ILS Calibration)",
    "QIUCT": "ILS 测试 (ILS Test)",
    "QIUXX": "ILS 未指定 (ILS Unspecified)",
    "QIXAS": "ILS 可用 (ILS Available)",
    "QIYAS": "ILS 可用 (ILS Available)",

    # ==================== 灯光 (L) ====================
    "QLAAS": "进近灯可用 (Approach Lights Available)",
    "QLAAW": "进近灯警告 (Approach Lights Warning)",
    "QLACG": "进近灯校验 (Approach Lights Calibration)",
    "QLAXX": "进近灯未指定 (Approach Lights Unspecified)",
    "QLCAS": "跑道中线灯可用 (Centerline Lights Available)",
    "QLEAS": "跑道边灯可用 (Edge Lights Available)",
    "QLEXX": "跑道边灯未指定 (Edge Lights Unspecified)",
    "QLHAS": "直升机机场灯可用 (Heliport Lights Available)",
    "QLIAS": "跑道灯可用 (Runway Lights Available)",
    "QLIAW": "跑道灯警告 (Runway Lights Warning)",
    "QLPAS": "跑道中线灯可用 (Runway Centerline Lights Available)",
    "QLRAS": "跑道边灯可用 (Runway Edge Lights Available)",
    "QLTAS": "滑行道灯可用 (Taxiway Lights Available)",
    "QLTXX": "滑行道灯未指定 (Taxiway Lights Unspecified)",
    "QLXAS": "机场灯标可用 (Aerodrome Beacon Available)",
    "QLXXX": "机场灯标未指定 (Aerodrome Beacon Unspecified)",
    "QLYAS": "停止灯可用 (Stop Lights Available)",
    "QLZAS": "机场灯可用 (Aerodrome Lights Available)",

    # ==================== 气象服务 (M) ====================
    "QMAXX": "气象 - 未指定 (Meteorology Unspecified)",
    "QMDCH": "气象数据变更 (Meteorological Data Change)",
    "QMHAS": "高空风可用 (High Altitude Wind Available)",
    "QMKLC": "气象标志关闭 (Meteorological Markers Closed)",
    "QMKXX": "气象标志未指定 (Meteorological Markers Unspecified)",
    "QMMAW": "气象警告 (Meteorological Warning)",
    "QMNHW": "无重要气象 (No Significant Weather)",
    "QMNLC": "气象报告关闭 (Meteorological Reports Closed)",
    "QMNXX": "气象报告未指定 (Meteorological Reports Unspecified)",
    "QMOXX": "气象观测未指定 (Meteorological Observation Unspecified)",
    "QMPHW": "机场气象警告 (Meteorological Aerodrome Warning)",
    "QMPLC": "机场预报关闭 (Aerodrome Forecast Closed)",
    "QMPXX": "机场预报未指定 (Aerodrome Forecast Unspecified)",
    "QMRAH": "雷达可用 (Radar Available)",
    "QMRAW": "雷达警告 (Radar Warning)",
    "QMRLC": "雷达关闭 (Radar Closed)",
    "QMRLL": "雷达限制 (Radar Limited)",
    "QMRLT": "雷达限制 (Radar Limited)",
    "QMRXX": "雷达未指定 (Radar Unspecified)",
    "QMXLC": "重要气象关闭 (Significant Weather Closed)",
    "QMXLT": "重要气象限制 (Significant Weather Limited)",
    "QMXXX": "重要气象未指定 (Significant Weather Unspecified)",
    "QMYLC": "气象未指定 (Meteorology Closed)",

    # ==================== 导航设施 (N) ====================
    "QNBAS": "NDB 可用 (NDB Available)",
    "QNDAS": "DME 可用 (DME Available)",
    "QNDCT": "DME 校验 (DME Calibration)",
    "QNLXX": "导航灯未指定 (Navigation Lights Unspecified)",
    "QNMAS": "VOR/DME 可用 (VOR/DME Available)",
    "QNMCT": "VOR/DME 校验 (VOR/DME Calibration)",
    "QNNAS": "导航台可用 (Navigation Station Available)",
    "QNNXX": "导航台未指定 (Navigation Station Unspecified)",
    "QNVAS": "VOR 可用 (VOR Available)",
    "QNVCT": "VOR 校验 (VOR Calibration)",
    "QNVXX": "VOR 未指定 (VOR Unspecified)",

    # ==================== 机场其他设施 (O) ====================
    "QOATT": "机场其他设施 - 测试 (Other Aerodrome Test)",
    "QOBCE": "障碍物 - 存在 (Obstacle Exist)",
    "QOBXX": "障碍物 - 未指定 (Obstacle Unspecified)",
    "QOLAS": "机场限制区可用 (Aerodrome Limitation Available)",

    # ==================== 跑道 (P) ====================
    "QPAAU": "跑道进近区域不可用 (Approach Area Unavailable)",
    "QPAXX": "跑道进近区域未指定 (Approach Area Unspecified)",
    "QPDAU": "跑道入口不可用 (Threshold Unavailable)",
    "QPDCH": "跑道入口变更 (Threshold Change)",
    "QPFCA": "跑道关闭 (Runway Closed)",
    "QPFCS": "跑道关闭 (Runway Closed)",
    "QPIAU": "跑道灯不可用 (Runway Lights Unavailable)",
    "QPICH": "跑道灯变更 (Runway Lights Change)",
    "QPILT": "跑道灯限制 (Runway Lights Limited)",
    "QPIXX": "跑道灯未指定 (Runway Lights Unspecified)",
    "QPOCH": "跑道其他变更 (Other Runway Change)",
    "QPUCH": "跑道其他变更 (Other Runway Change)",

    # ==================== 限制空域 (R) ====================
    "QRACA": "告警区可用 (Alert Area Available)",
    "QRALW": "告警区警告 (Alert Area Warning)",
    "QRAXX": "告警区未指定 (Alert Area Unspecified)",
    "QRDCA": "危险区可用 (Danger Area Available)",
    "QRDCD": "危险区已指定 (Danger Area Designated)",
    "QRDTT": "危险区测试 (Danger Area Test)",
    "QRDXX": "危险区未指定 (Danger Area Unspecified)",
    "QRMCA": "军事限制区可用 (Military Restricted Area Available)",
    "QROXX": "限制空域未指定 (Restricted Airspace Unspecified)",
    "QRPCA": "临时限制区可用 (Prohibited Area Available)",
    "QRRCA": "限制区可用 (Restricted Area Available)",
    "QRTCA": "临时限制区可用 (Temporary Restricted Area Available)",
    "QRTLP": "临时限制区限制 (Temporary Restricted Area Limited)",
    "QRTTT": "临时限制区测试 (Temporary Restricted Area Test)",

    # ==================== 滑行道 (S) ====================
    "QSAAS": "滑行道可用 (Taxiway Available)",
    "QSAXX": "滑行道未指定 (Taxiway Unspecified)",
    "QSBLC": "滑行道桥关闭 (Taxiway Bridge Closed)",
    "QSBXX": "滑行道桥未指定 (Taxiway Bridge Unspecified)",
    "QSCXX": "滑行道关闭未指定 (Taxiway Closed Unspecified)",
    "QSEAU": "滑行道边缘不可用 (Taxiway Edge Unavailable)",
    "QSPAH": "滑行道停机位可用 (Taxiway Parking Available)",
    "QSPXX": "滑行道停机位未指定 (Taxiway Parking Unspecified)",
    "QSTLC": "滑行道灯关闭 (Taxiway Lights Closed)",
    "QSTXX": "滑行道灯未指定 (Taxiway Lights Unspecified)",

    # ==================== 警告 (W) ====================
    "QWALW": "警告 - 鸟类活动 (Bird Activity Warning)",
    "QWCLW": "警告 - 攀爬警告 (Climbing Warning)",
    "QWDLW": "警告 - 下降警告 (Descending Warning)",
    "QWELW": "警告 - 恶劣天气 (Extreme Weather Warning)",
    "QWFLW": "警告 - 飞行限制 (Flight Limitation Warning)",
    "QWGLW": "警告 - 一般警告 (General Warning)",
    "QWLLW": "警告 - 低空警告 (Low Level Warning)",
    "QWMLW": "警告 - 军事活动 (Military Activity Warning)",
    "QWPLW": "警告 - 演习 (Exercise Warning)",
    "QWTLW": "警告 - 恐怖主义威胁 (Terrorism Warning)",
    "QWULW": "警告 - 鸟击 (Bird Strike Warning)",
    "QWVLW": "警告 - 火山活动 (Volcanic Activity Warning)",
    "QWWLW": "警告 - 广域警告 (Wide Area Warning)",
    "QWYLW": "警告 - 火山灰 (Volcanic Ash Warning)",
    "QWZLW": "警告 - 危险区 (Danger Zone Warning)",

    # ==================== 特殊/未分类 (X) ====================
    "QXXXX": "未分类/其他 (Unspecified)",
}

# FIR (飞行情报区) 解码表 - 全球主要 FIR
FIR_DESCRIPTIONS: Dict[str, str] = {
    # 中国
    "ZBPE": "Beijing FIR (北京飞行情报区)",
    "ZSHA": "Shanghai FIR (上海飞行情报区)",
    "ZGZU": "Guangzhou FIR (广州飞行情报区)",
    "ZPKM": "Kunming FIR (昆明飞行情报区)",
    "ZJHK": "Haikou FIR (海口飞行情报区)",
    "ZYTX": "Shenyang FIR (沈阳飞行情报区)",
    "ZLXN": "Xining FIR (西宁飞行情报区)",
    "ZWUQ": "Urumqi FIR (乌鲁木齐飞行情报区)",
    "ZYYY": "Sanya FIR (三亚飞行情报区)",
    # 欧洲
    "EGTT": "London FIR (UK)",
    "EGPX": "Scottish FIR (UK)",
    "EGXX": "UK (Multiple FIR)",
    "EDGG": "Bremen FIR (Germany)",
    "EDMM": "Munich FIR (Germany)",
    "EDWW": "Hannover FIR (Germany)",
    "LFFF": "Paris FIR (France)",
    "LFBB": "Bordeaux FIR (France)",
    "LFEE": "Reims FIR (France)",
    "LFMM": "Marseille FIR (France)",
    "LFRR": "France (Oceanic)",
    "LFXX": "France (Multiple FIR)",
    "LECM": "Madrid FIR (Spain)",
    "LECB": "Barcelona FIR (Spain)",
    "LSAS": "Switzerland FIR",
    "LIMM": "Roma FIR (Italy)",
    "LIRR": "Milano FIR (Italy)",
    "LIBB": "Brindisi FIR (Italy)",
    "LIXX": "Italy (Multiple FIR)",
    "EHAA": "Amsterdam FIR (Netherlands)",
    "EBBU": "Brussels FIR (Belgium)",
    "LRBB": "Bucharest FIR (Romania)",
    "LBSR": "Sofia FIR (Bulgaria)",
    "LYBA": "Belgrade FIR (Serbia)",
    "LAAA": "Albania FIR",
    "LGGG": "Athens FIR (Greece)",
    "LHCC": "Budapest FIR (Hungary)",
    "LJLA": "Ljubljana FIR (Slovenia)",
    "LOVV": "Vienna FIR (Austria)",
    "EPWW": "Warszawa FIR (Poland)",
    "LKAA": "Praha FIR (Czech Republic)",
    "EYVL": "Vilnius FIR (Lithuania)",
    "EFIN": "Finland FIR",
    "EETT": "Tallinn FIR (Estonia)",
    "EVRR": "Riga FIR (Latvia)",
    "ESAA": "Stockholm FIR (Sweden)",
    "EKDK": "Copenhagen FIR (Denmark)",
    "ENOB": "Bodo FIR (Norway)",
    "UEEE": "Tallinn FIR (Estonia)",
    # 俄罗斯及独联体
    "UUWV": "Moscow FIR (Russia)",
    "ULLL": "St. Petersburg FIR (Russia)",
    "USTV": "Yekaterinburg FIR (Russia)",
    "UNNT": "Novosibirsk FIR (Russia)",
    "USSV": "Sverdlovsk FIR (Russia)",
    "UWWW": "Samara FIR (Russia)",
    "UNKL": "Krasnoyarsk FIR (Russia)",
    "UATT": "Tomsk FIR (Russia)",
    "UMMV": "Murmansk FIR (Russia)",
    "UHHH": "Khabarovsk FIR (Russia)",
    "UHMM": "Magadan FIR (Russia)",
    "UEEE": "Yakutsk FIR (Russia)",
    "UAAA": "Almaty FIR (Kazakhstan)",
    "UAII": "Astana FIR (Kazakhstan)",
    "UMKK": "Kishinev FIR (Moldova)",
    # 亚洲
    "RJJJ": "Tokyo FIR (Japan)",
    "RJAA": "Tokyo Narita FIR (Japan)",
    "RJBB": "Osaka FIR (Japan)",
    "RKRR": "Incheon FIR (Korea)",
    "RKJJ": "Gimpo FIR (Korea)",
    "VTBB": "Bangkok FIR (Thailand)",
    "VIDF": "Delhi FIR (India)",
    "VOMF": "Mumbai FIR (India)",
    "VABF": "Ahmedabad FIR (India)",
    "VCCF": "Colombo FIR (Sri Lanka)",
    "VVHM": "Ho Chi Minh FIR (Vietnam)",
    "WSJC": "Jakarta FIR (Indonesia)",
    "WMFC": "Kuala Lumpur FIR (Malaysia)",
    "RPHI": "Manila FIR (Philippines)",
    "RCAA": "Taipei FIR (Taiwan)",
    "PGZU": "Guam FIR",
    "OJAC": "Amman FIR (Jordan)",
    "OEJD": "Jeddah FIR (Saudi Arabia)",
    "OERF": "Riyadh FIR (Saudi Arabia)",
    "OMAE": "Abu Dhabi FIR (UAE)",
    "OOMM": "Muscat FIR (Oman)",
    "HECC": "Cairo FIR (Egypt)",
    "GMMM": "Morocco FIR",
    "UGGG": "Entebbe FIR (Uganda)",
    # 北美
    "KZNY": "New York ARTCC (USA)",
    "KZDC": "Washington ARTCC (USA)",
    "KZLA": "Los Angeles ARTCC (USA)",
    "KZOA": "Oakland ARTCC (USA)",
    "KZID": "Indianapolis ARTCC (USA)",
    "KZAK": "Anchorage ARTCC Oceanic (USA)",
    "KZOB": "Cleveland ARTCC (USA)",
    "KZMP": "Minneapolis ARTCC (USA)",
    "KZBW": "Boston ARTCC (USA)",
    "KZAU": "Chicago ARTCC (USA)",
    "KZTL": "Atlanta ARTCC (USA)",
    "KZSE": "Seattle ARTCC (USA)",
    "CZEG": "Edmonton FIR (Canada)",
    "CZVR": "Vancouver FIR (Canada)",
    "CZUL": "Montreal FIR (Canada)",
    "CZQX": "Gander FIR (Canada)",
    "CZYZ": "Toronto FIR (Canada)",
    "CZWG": "Winnipeg FIR (Canada)",
    # 大洋洲
    "YMMM": "Melbourne FIR (Australia)",
    "YBBB": "Brisbane FIR (Australia)",
    "NZZO": "Auckland FIR (New Zealand)",
    "NZZC": "Christchurch FIR (New Zealand)",
    "AYPM": "Port Moresby FIR (Papua New Guinea)",
    "NTTT": "Tahiti FIR (French Polynesia)",
    "NFFF": "Fiji FIR",
    # 极地
    "PAZA": "Anchorage ARTCC (USA - Alaska)",
    "PHZH": "Honolulu ARTCC (USA - Hawaii)",
    # 南美
    "SCCZ": "Punta Arenas FIR (Chile)",
    "SCEZ": "Santiago FIR (Chile)",
    "SCTZ": "Ezeiza FIR (Argentina)",
    "SAEF": "Ezeiza FIR (Argentina)",
    "VECF": "Caracas FIR (Venezuela)",
    # 北大西洋
    "CZQX": "Gander FIR (Canada - Atlantic)",
    "EGGX": "Shanwick Oceanic (UK)",
    "LPPC": "Santa Maria FIR (Portugal)",
    "GVSC": "Sal FIR (Cape Verde)",
}


def get_qcode_description(code: str) -> Optional[str]:
    """获取 QCODE 的中文描述

    Args:
        code: 5 位 QCODE (如 QFALC) 或 4 位代码 (如 FALC)

    Returns:
        QCODE 描述，如无匹配则返回 None
    """
    # 标准化：确保为 5 位格式
    if len(code) == 4:
        code = "Q" + code
    elif len(code) == 5 and not code.startswith("Q"):
        code = "Q" + code

    # 精确匹配
    if code in QCODE_DESCRIPTIONS:
        return QCODE_DESCRIPTIONS[code]

    # 尝试前缀匹配 (类别级)
    if len(code) >= 3:
        prefix = code[:3]
        for qcode, desc in QCODE_DESCRIPTIONS.items():
            if qcode.startswith(prefix):
                return f"{desc} (近似匹配：{qcode})"

    return None


def get_fir_description(fir: str) -> Optional[str]:
    """获取 FIR 的中文描述

    Args:
        fir: FIR 代码 (如 ZBPE, EGTT)

    Returns:
        FIR 描述，如无匹配则返回 None
    """
    return FIR_DESCRIPTIONS.get(fir.upper())


def get_all_qcodes() -> list:
    """获取所有已知 QCODE 列表"""
    return list(QCODE_DESCRIPTIONS.keys())


def get_qcode_by_category(category: str) -> list:
    """按类别获取 QCODE 列表

    Args:
        category: 类别代码 (A=航路，C=通信，F=机场，L=灯光，
                  M=气象，N=导航，P=跑道，R=限制区，S=滑行道，
                  W=警告，X=特殊)

    Returns:
        该类别下的 QCODE 列表
    """
    return [code for code in QCODE_DESCRIPTIONS.keys()
            if code[1] == category.upper()]
