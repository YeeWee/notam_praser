# NOTAM Parser

NOTAM（航行通告）完整解析器 - 将 ICAO 标准格式的 NOTAM 转换为结构化 JSON。

## 功能

- **正则解析层**：提取 Q/A/B/C/D/E 行结构化字段
  - Q 行完整解码（FIR、NOTAM 代码、交通类型、目的、范围、高度、坐标）
  - A/B/C/D/E 行解析
- **LLM 解析层**：E 行语义解析
  - 摘要生成
  - 全文翻译（英→中）
  - 语义分类
  - 术语解释（ICAO Doc 8400 标准术语库校验）
  - 限制区域解析
- **SQLite 缓存**：可选的解析结果缓存

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置

创建 `.env` 文件：

```env
# 应用配置
APP_NAME="NOTAM Parser"
DEBUG=true

# LLM 配置（可选）
OPENAI_API_KEY=your_api_key
OPENAI_MODEL=gpt-4o-mini

# 缓存配置
CACHE_ENABLED=true
CACHE_TTL=3600
```

### 启动服务

```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

API 文档：http://localhost:8000/docs

## 使用示例

### API 调用

```bash
curl -X POST "http://localhost:8000/api/v1/parse" \
  -H "Content-Type: application/json" \
  -d '{
    "notam_text": "Q)EGTT/QFALC/IV/NBO/A/000/999\nA)EGLL\nB)2403150600\nC)2403151800\nE)RUNWAY 09L CLSD",
    "include_llm": true
  }'
```

### Python SDK

```python
from src.parsers.regex_parser import RegexParser
from src.parsers.llm_parser import LLMParser

# 正则解析
regex_parser = RegexParser()
result = regex_parser.parse(notam_text)

# LLM 解析
llm_parser = LLMParser(api_key="your_key")
llm_result = llm_parser.parse(e_text)
```

## API 端点

- `GET /` - 根端点
- `GET /api/v1/health` - 健康检查
- `POST /api/v1/parse` - 解析 NOTAM

## 测试

```bash
pytest tests/ -v
```

## 项目结构

```
notam_praser/
├── src/
│   ├── __init__.py
│   ├── main.py              # FastAPI 应用入口
│   ├── config.py            # 配置管理
│   ├── database.py          # SQLite 缓存
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py        # API 路由
│   └── parsers/
│       ├── __init__.py
│       ├── regex_parser.py  # 正则解析器
│       ├── llm_parser.py    # LLM 解析器
│       └── terminology_db.py # ICAO 术语库
├── tests/
│   ├── __init__.py
│   ├── test_regex_parser.py
│   ├── test_llm_parser.py
│   ├── test_terminology_db.py
│   ├── test_api.py
│   └── test_integration.py
├── requirements.txt
├── pytest.ini
└── README.md
```

## 解析示例

### 输入（NOTAM 原始文本）

```
Q)EGTT/QFALC/IV/NBO/A/000/999/5147N00028W005
A)EGLL
B)2403150600
C)2403151800
E)RUNWAY 09L CLSD DUE TO WIP
```

### 输出（结构化 JSON）

```json
{
  "q_line": {
    "fir": "EGTT",
    "fir_name": "London FIR (UK)",
    "notam_code": "QFALC",
    "code_description": "Aerodrome closed",
    "traffic": "I",
    "purpose": "NBO",
    "scope": "A",
    "lower_altitude": "000",
    "upper_altitude": "999"
  },
  "a_location": ["EGLL"],
  "b_time": "2024-03-15T06:00:00",
  "c_time": "2024-03-15T18:00:00",
  "e_raw": "RUNWAY 09L CLSD DUE TO WIP",
  "e_parsed": {
    "summary": "跑道 09L 因施工关闭",
    "translation": "跑道 09L 因施工关闭",
    "category": "跑道相关",
    "terminology": [
      {"term": "RWY", "expansion": "Runway (跑道)", "category": "airport"},
      {"term": "CLSD", "expansion": "Closed (关闭)", "category": "status"}
    ]
  }
}
```

## 状态

- [x] MVP: 同步 API + 正则解析 + LLM 解析 + 术语库
- [ ] Phase 2: 异步任务队列 + PostgreSQL + 批量解析

## 许可证

MIT
