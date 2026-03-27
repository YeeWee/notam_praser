"""QCODE 覆盖测试

使用真实 NOTAM 数据验证解析器对各种 QCODE 的覆盖能力。

测试目标:
1. Top 50 QCODE 的 NOTAM 都能被正确解析
2. 统计解析成功率
3. 识别解析失败的 QCODE
"""
import pytest
from typing import List, Dict

from src.parsers.regex_parser import RegexParser
from tests.utils.notam_data_loader import (
    load_all_notams,
    group_by_qcode,
    get_top_qcodes,
    extract_fields,
)


class TestQCodeCoverage:
    """QCODE 覆盖测试"""

    @pytest.fixture(scope="class")
    def all_notams(self):
        """加载所有 NOTAM"""
        return load_all_notams()

    @pytest.fixture(scope="class")
    def qcode_groups(self, all_notams):
        """按 QCODE 分组"""
        return group_by_qcode(all_notams)

    @pytest.fixture(scope="class")
    def top_qcodes(self, all_notams):
        """获取 Top 50 QCODE"""
        return get_top_qcodes(all_notams, top_n=50)

    @pytest.fixture
    def parser(self):
        """创建解析器"""
        return RegexParser()

    def test_top_qcodes_have_samples(self, qcode_groups, top_qcodes):
        """验证 Top QCODE 都有样本"""
        for qcode in top_qcodes:
            assert qcode in qcode_groups, f"QCODE {qcode} 缺少样本"
            assert len(qcode_groups[qcode]) > 0, f"QCODE {qcode} 样本为空"

    @pytest.mark.parametrize("qcode_index", range(20))
    def test_parse_top_20_qcodes(
        self,
        parser,
        qcode_groups,
        top_qcodes,
        qcode_index
    ):
        """测试 Top 20 QCODE 的解析

        每个 QCODE 测试第一个样本
        """
        if qcode_index >= len(top_qcodes):
            pytest.skip("超出 Top QCODE 范围")

        qcode = top_qcodes[qcode_index]
        samples = qcode_groups.get(qcode, [])

        if not samples:
            pytest.skip(f"QCODE {qcode} 没有样本")

        notam = samples[0]
        result = parser.parse(notam)

        # 验证 Q 行解析成功
        assert result.q_line is not None, f"QCODE {qcode} 的 Q 行解析失败"
        assert result.q_line.notam_code == qcode, \
            f"QCODE 解析不匹配：期望 {qcode}, 得到 {result.q_line.notam_code}"

    @pytest.mark.parametrize("qcode_index", range(10))
    def test_parse_multiple_samples_per_qcode(
        self,
        parser,
        qcode_groups,
        top_qcodes,
        qcode_index
    ):
        """每个 QCODE 测试多个样本

        测试每个 QCODE 的前 3 个样本
        """
        if qcode_index >= len(top_qcodes):
            pytest.skip("超出 Top QCODE 范围")

        qcode = top_qcodes[qcode_index]
        samples = qcode_groups.get(qcode, [])

        if len(samples) < 3:
            pytest.skip(f"QCODE {qcode} 样本不足 3 个")

        success_count = 0
        for sample in samples[:3]:
            result = parser.parse(sample)
            if result.q_line is not None:
                success_count += 1

        # 至少应该成功解析 2 个
        assert success_count >= 2, \
            f"QCODE {qcode} 解析成功率过低：{success_count}/3"

    def test_qcode_coverage_statistics(self, qcode_groups, top_qcodes):
        """QCODE 覆盖统计"""
        parser = RegexParser()

        results = {
            'success': [],
            'failed': [],
            'skipped': [],
        }

        for qcode in top_qcodes[:20]:
            samples = qcode_groups.get(qcode, [])
            if not samples:
                results['skipped'].append(qcode)
                continue

            # 测试第一个样本
            result = parser.parse(samples[0])
            if result.q_line is not None:
                results['success'].append(qcode)
            else:
                results['failed'].append(qcode)

        # 打印统计（在 verbose 模式下可见）
        print(f"\n\nQCODE 覆盖统计:")
        print(f"  总计：{len(top_qcodes[:20])}")
        print(f"  成功：{len(results['success'])}")
        print(f"  失败：{len(results['failed'])}")
        print(f"  跳过：{len(results['skipped'])}")

        if results['failed']:
            print(f"  失败的 QCODE: {results['failed']}")

        # 成功率应该 >= 90%
        total_tested = len(results['success']) + len(results['failed'])
        if total_tested > 0:
            success_rate = len(results['success']) / total_tested
            assert success_rate >= 0.9, f"QCODE 覆盖率过低：{success_rate:.2%}"


class TestQCodeSpecificParsing:
    """特定 QCODE 解析测试

    针对常见 QCODE 的特定解析逻辑进行测试
    """

    @pytest.fixture
    def parser(self):
        return RegexParser()

    @pytest.fixture
    def samples_by_qcode(self):
        """获取特定 QCODE 的样本"""
        notams = load_all_notams()
        return group_by_qcode(notams)

    def test_qafxx_parsing(self, parser, samples_by_qcode):
        """QAFXX - 航空信息解析"""
        samples = samples_by_qcode.get('QAFXX', [])
        if not samples:
            pytest.skip("无 QAFXX 样本")

        result = parser.parse(samples[0])
        assert result.q_line is not None
        assert result.q_line.notam_code == 'QAFXX'

    def test_qrtca_parsing(self, parser, samples_by_qcode):
        """QRTCA - 限制区激活解析"""
        samples = samples_by_qcode.get('QRTCA', [])
        if not samples:
            pytest.skip("无 QRTCA 样本")

        result = parser.parse(samples[0])
        assert result.q_line is not None
        assert result.q_line.notam_code == 'QRTCA'

    def test_qrdca_parsing(self, parser, samples_by_qcode):
        """QRDCA - 危险区激活解析"""
        samples = samples_by_qcode.get('QRDCA', [])
        if not samples:
            pytest.skip("无 QRDCA 样本")

        result = parser.parse(samples[0])
        assert result.q_line is not None
        assert result.q_line.notam_code == 'QRDCA'

    def test_qrrca_parsing(self, parser, samples_by_qcode):
        """QRRCA - 军事活动区解析"""
        samples = samples_by_qcode.get('QRRCA', [])
        if not samples:
            pytest.skip("无 QRRCA 样本")

        result = parser.parse(samples[0])
        assert result.q_line is not None
        assert result.q_line.notam_code == 'QRRCA'

    def test_qmxlc_parsing(self, parser, samples_by_qcode):
        """QMXLC - 军事演习解析"""
        samples = samples_by_qcode.get('QMXLC', [])
        if not samples:
            pytest.skip("无 QMXLC 样本")

        result = parser.parse(samples[0])
        assert result.q_line is not None
        assert result.q_line.notam_code == 'QMXLC'


class TestFullQCodeExhaustive:
    """完整 QCODE 穷举测试（慢速）

    测试所有 QCODE 的所有样本（标记为 slow）
    """

    @pytest.fixture
    def parser(self):
        return RegexParser()

    @pytest.fixture
    def all_data(self):
        notams = load_all_notams()
        return {
            'notams': notams,
            'groups': group_by_qcode(notams),
        }

    @pytest.mark.slow
    @pytest.mark.qcode
    def test_all_qcodes_all_samples(self, parser, all_data):
        """测试所有 QCODE 的所有样本

        这是一个慢速测试，用于完整验证
        """
        groups = all_data['groups']

        results = {
            'total': 0,
            'success': 0,
            'failed': [],
        }

        for qcode, samples in groups.items():
            for sample in samples:
                results['total'] += 1
                result = parser.parse(sample)

                if result.q_line is not None:
                    results['success'] += 1
                else:
                    results['failed'].append({
                        'qcode': qcode,
                        'notam': sample[:100],
                    })

        # 打印详细统计
        success_rate = results['success'] / results['total'] if results['total'] else 0
        print(f"\n\n完整 QCODE 测试统计:")
        print(f"  总样本数：{results['total']}")
        print(f"  成功：{results['success']}")
        print(f"  成功率：{success_rate:.2%}")
        print(f"  失败：{len(results['failed'])}")

        # 成功率应该 >= 85%（考虑到数据可能存在格式问题）
        assert success_rate >= 0.85, \
            f"整体解析成功率过低：{success_rate:.2%}"
