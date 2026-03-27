"""测试工具包 - LLM 测试辅助

提供 LLM 真实调用测试的辅助功能：
- API 可用性检测
- 跳过装饰器
- 响应缓存
- Mock vs Real 对比
"""
import os
import json
import hashlib
from pathlib import Path
from typing import Optional, Any, Dict
from functools import wraps

import pytest
from dotenv import load_dotenv

# 加载 .env 配置
load_dotenv()

# 缓存目录
CACHE_DIR = Path(__file__).parent.parent / ".llm_cache"
CACHE_DIR.mkdir(exist_ok=True)


def is_llm_api_available() -> bool:
    """检测 LLM API 是否可用

    检查 OPENAI_API_KEY 是否已在 .env 中配置

    Returns:
        bool: API 是否可用
    """
    api_key = os.getenv("OPENAI_API_KEY")
    return bool(api_key and api_key != "your_api_key_here")


def get_api_config() -> Dict[str, str]:
    """获取 API 配置

    Returns:
        配置字典
    """
    return {
        "api_key": os.getenv("OPENAI_API_KEY", ""),
        "api_base": os.getenv("OPENAI_API_BASE", ""),
        "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    }


def skip_if_no_llm_api(reason: Optional[str] = None):
    """如果 LLM API 不可用则跳过测试

    使用:
        @skip_if_no_llm_api()
        def test_something():
            ...

    Args:
        reason: 自定义跳过原因
    """
    default_reason = "OPENAI_API_KEY not configured in .env"

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not is_llm_api_available():
                pytest.skip(reason or default_reason)
            return func(*args, **kwargs)
        return wrapper
    return decorator


def _get_cache_key(prompt: str, model: str) -> str:
    """生成缓存键"""
    content = f"{prompt}|||{model}"
    return hashlib.md5(content.encode()).hexdigest()[:16]


def _get_cache_file(cache_key: str) -> Path:
    """获取缓存文件路径"""
    return CACHE_DIR / f"{cache_key}.json"


def load_cached_response(cache_key: str) -> Optional[Dict[str, Any]]:
    """从缓存加载 LLM 响应

    Args:
        cache_key: 缓存键

    Returns:
        缓存的响应或 None
    """
    cache_file = _get_cache_file(cache_key)
    if cache_file.exists():
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return None


def save_cached_response(cache_key: str, response: Dict[str, Any]):
    """保存 LLM 响应到缓存

    Args:
        cache_key: 缓存键
        response: LLM 响应
    """
    cache_file = _get_cache_file(cache_key)
    try:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(response, f, ensure_ascii=False, indent=2)
    except IOError as e:
        print(f"Warning: Failed to cache response: {e}")


def cached_llm_call(llm_func):
    """LLM 调用缓存装饰器

    装饰的函数会将调用结果缓存到 .llm_cache 目录

    使用:
        @cached_llm_call
        def call_llm(prompt):
            return client.chat.completions.create(...)

    Args:
        llm_func: LLM 调用函数

    Returns:
        带缓存的包装函数
    """
    @wraps(llm_func)
    def wrapper(prompt: str, model: str = "gpt-4o-mini", **kwargs):
        cache_key = _get_cache_key(prompt, model)

        # 尝试从缓存加载
        cached = load_cached_response(cache_key)
        if cached is not None:
            print(f"[LLM Cache Hit] {cache_key}")
            return cached

        # 调用实际函数
        print(f"[LLM Cache Miss] {cache_key}, calling API...")
        result = llm_func(prompt, model=model, **kwargs)

        # 保存到缓存
        save_cached_response(cache_key, result)

        return result
    return wrapper


class LLMMockVsRealComparator:
    """Mock 与真实 LLM 结果对比器

    使用:
        comparator = LLMMockVsRealComparator()
        result = comparator.compare(mock_response, real_response, notam_text)
    """

    def __init__(self):
        self.comparison_results = []

    def compare(
        self,
        mock_result: Any,
        real_result: Any,
        notam_text: str
    ) -> Dict[str, Any]:
        """对比 Mock 和真实结果

        Args:
            mock_result: Mock 结果
            real_result: 真实结果
            notam_text: NOTAM 文本

        Returns:
            对比报告
        """
        result = {
            'notam': notam_text[:100] + '...' if len(notam_text) > 100 else notam_text,
            'mock_summary': getattr(mock_result, 'summary', None),
            'real_summary': getattr(real_result, 'summary', None),
            'mock_translation': getattr(mock_result, 'translation', None),
            'real_translation': getattr(real_result, 'translation', None),
            'mock_category': getattr(mock_result, 'category', None),
            'real_category': getattr(real_result, 'category', None),
            'summary_match': False,
            'translation_match': False,
            'category_match': False,
        }

        # 比较字段
        result['summary_match'] = result['mock_summary'] == result['real_summary']
        result['translation_match'] = result['mock_translation'] == result['real_translation']
        result['category_match'] = result['mock_category'] == result['real_category']

        self.comparison_results.append(result)
        return result

    def get_statistics(self) -> Dict[str, Any]:
        """获取对比统计"""
        if not self.comparison_results:
            return {'total': 0}

        total = len(self.comparison_results)
        summary_matches = sum(1 for r in self.comparison_results if r['summary_match'])
        translation_matches = sum(1 for r in self.comparison_results if r['translation_match'])
        category_matches = sum(1 for r in self.comparison_results if r['category_match'])

        return {
            'total': total,
            'summary_match_rate': summary_matches / total if total else 0,
            'translation_match_rate': translation_matches / total if total else 0,
            'category_match_rate': category_matches / total if total else 0,
        }


def create_mock_llm_response(
    summary: str = "测试摘要",
    translation: str = "测试翻译",
    category: str = "OTHER",
    terminology: Optional[list] = None,
    restricted_areas: Optional[list] = None
) -> str:
    """创建 Mock LLM 响应（用于测试）

    Args:
        summary: 摘要
        translation: 翻译
        category: 分类
        terminology: 术语列表
        restricted_areas: 限制区域列表

    Returns:
        JSON 字符串
    """
    response = {
        "summary": summary,
        "translation": translation,
        "category": category,
        "terminology": terminology or [],
        "restricted_areas": restricted_areas or [],
    }
    return json.dumps(response, ensure_ascii=False)
