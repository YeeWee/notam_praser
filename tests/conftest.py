"""测试配置和共享 fixture

提供全局可用的测试资源：
- 真实 NOTAM 数据加载
- QCODE 分组数据
- LLM API 可用性检测
"""
import pytest
import os
import sys
from pathlib import Path

# 加载 .env 配置
from dotenv import load_dotenv
load_dotenv()

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
DATA_FILE = PROJECT_ROOT / "datas" / "input_notams.csv"

# 确保项目源码在路径中
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(scope="session")
def project_root():
    """项目根目录"""
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def data_file():
    """NOTAM 数据文件路径"""
    return DATA_FILE


@pytest.fixture(scope="session")
def all_notams():
    """加载所有真实 NOTAM 数据

    返回:
        list: NOTAM 文本列表
    """
    from tests.utils.notam_data_loader import load_all_notams
    return load_all_notams()


@pytest.fixture(scope="session")
def qcode_groups(all_notams):
    """按 QCODE 分组的 NOTAM 数据

    返回:
        dict: {qcode: [notam_text, ...]}
    """
    from tests.utils.notam_data_loader import group_by_qcode
    return group_by_qcode(all_notams)


@pytest.fixture(scope="session")
def e_length_groups(all_notams):
    """按 E 行长度分组的 NOTAM 数据

    返回:
        dict: {'short': [...], 'medium': [...], 'long': [...], 'very_long': [...]}
    """
    from tests.utils.notam_data_loader import group_by_e_length
    return group_by_e_length(all_notams)


@pytest.fixture
def get_notam_by_qcode(qcode_groups):
    """获取指定 QCODE 的 NOTAM 样本

    使用:
        def test_something(get_notam_by_qcode):
            notams = get_notam_by_qcode('QRTCA')
    """
    def _get(qcode, count=1):
        notams = qcode_groups.get(qcode, [])
        return notams[:count] if count else notams
    return _get


@pytest.fixture
def get_random_notams(all_notams):
    """获取随机 NOTAM 样本

    使用:
        def test_something(get_random_notams):
            samples = get_random_notams(10)
    """
    import random
    def _get(count=10):
        return random.sample(all_notams, min(count, len(all_notams)))
    return _get


@pytest.fixture
def real_llm_enabled():
    """检测 LLM API 是否可用

    如果 OPENAI_API_KEY 未配置，跳过测试
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "your_api_key_here":
        pytest.skip("OPENAI_API_KEY not configured in .env")
    return True


@pytest.fixture
def openai_api_key():
    """获取 OpenAI API Key"""
    return os.getenv("OPENAI_API_KEY", "")


@pytest.fixture
def openai_api_base():
    """获取 OpenAI API Base URL"""
    return os.getenv("OPENAI_API_BASE", "")


@pytest.fixture
def openai_model():
    """获取 OpenAI 模型名称"""
    return os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def pytest_configure(config):
    """配置 pytest marker"""
    config.addinivalue_line(
        "markers", "real_llm: 使用真实 LLM API 调用（需要配置 OPENAI_API_KEY）"
    )
    config.addinivalue_line(
        "markers", "slow: 慢速测试（批量测试、性能测试）"
    )
    config.addinivalue_line(
        "markers", "integration: 集成测试"
    )
    config.addinivalue_line(
        "markers", "qcode: QCODE 覆盖测试"
    )
    config.addinivalue_line(
        "markers", "edge_case: 边界情况测试"
    )
