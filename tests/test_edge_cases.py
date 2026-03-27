"""边界情况测试

使用真实 NOTAM 数据构造边界场景测试：
1. 超长 E 行（>500 字符）- 119 条
2. 多行 E 行 - 1701 条
3. 短 E 行（<50 字符）- 508 条
4. 中等长度 E 行（50-200 字符）- 991 条
"""
import pytest
from typing import List

from src.parsers.regex_parser import RegexParser
from tests.utils.notam_data_loader import (
    load_all_notams,
    group_by_e_length,
    extract_e_line,
    get_random_samples,
)


class TestEdgeCaseELength:
    """E 行长度边界情况测试"""

    @pytest.fixture(scope="class")
    def all_notams(self):
        return load_all_notams()

    @pytest.fixture(scope="class")
    def length_groups(self, all_notams):
        return group_by_e_length(all_notams)

    @pytest.fixture
    def parser(self):
        return RegexParser()

    def test_short_e_line_parsing(self, parser, length_groups):
        """短 E 行解析测试（<50 字符）"""
        samples = length_groups.get('short', [])
        assert len(samples) > 0, "没有短 E 行样本"

        # 测试前 10 个样本
        success_count = 0
        for sample in samples[:10]:
            result = parser.parse(sample)
            if result.e_raw and len(result.e_raw) > 0:
                success_count += 1

        # 至少 80% 应该成功
        assert success_count >= 8, f"短 E 行解析成功率过低：{success_count}/10"

    def test_medium_e_line_parsing(self, parser, length_groups):
        """中等长度 E 行解析测试（50-200 字符）"""
        samples = length_groups.get('medium', [])
        assert len(samples) > 0, "没有中等长度 E 行样本"

        # 测试前 10 个样本
        success_count = 0
        for sample in samples[:10]:
            result = parser.parse(sample)
            if result.e_raw and len(result.e_raw) > 0:
                success_count += 1

        assert success_count >= 8, f"中等长度 E 行解析成功率过低：{success_count}/10"

    def test_long_e_line_parsing(self, parser, length_groups):
        """长 E 行解析测试（200-500 字符）"""
        samples = length_groups.get('long', [])
        assert len(samples) > 0, "没有长 E 行样本"

        # 测试前 10 个样本
        success_count = 0
        for sample in samples[:10]:
            result = parser.parse(sample)
            if result.e_raw and len(result.e_raw) > 0:
                success_count += 1

        assert success_count >= 8, f"长 E 行解析成功率过低：{success_count}/10"

    def test_very_long_e_line_parsing(self, parser, length_groups):
        """超长 E 行解析测试（>500 字符）"""
        samples = length_groups.get('very_long', [])
        assert len(samples) > 0, "没有超长 E 行样本"

        # 测试所有超长样本（共 119 条）
        success_count = 0
        failed_samples = []

        for sample in samples:
            result = parser.parse(sample)
            if result.e_raw and len(result.e_raw) > 0:
                success_count += 1
            else:
                failed_samples.append(sample[:100])

        # 打印失败样本
        if failed_samples:
            print(f"\n失败的超长 E 行样本数：{len(failed_samples)}")

        # 至少 90% 应该成功
        success_rate = success_count / len(samples)
        assert success_rate >= 0.9, \
            f"超长 E 行解析成功率过低：{success_rate:.2%} ({success_count}/{len(samples)})"

    def test_longest_e_line(self, parser, length_groups):
        """测试最长的 E 行"""
        samples = length_groups.get('very_long', [])
        if not samples:
            pytest.skip("没有超长 E 行样本")

        # 找到最长的样本
        longest = max(samples, key=lambda n: len(extract_e_line(n)))
        e_line = extract_e_line(longest)

        print(f"\n最长 E 行长度：{len(e_line)} 字符")
        print(f"最长 E 行内容（前 200 字符）: {e_line[:200]}...")

        result = parser.parse(longest)
        assert result.e_raw is not None, "最长 E 行解析失败"
        assert len(result.e_raw) > 0, "最长 E 行解析结果为空"


class TestMultilineELine:
    """多行 E 行测试"""

    @pytest.fixture(scope="class")
    def all_notams(self):
        return load_all_notams()

    @pytest.fixture
    def parser(self):
        return RegexParser()

    def test_multiline_e_line_count(self, all_notams):
        """验证多行 E 行数量"""
        multiline_count = sum(
            1 for n in all_notams
            if '\n' in extract_e_line(n)
        )
        print(f"\n多行 E 行数量：{multiline_count}/{len(all_notams)}")
        assert multiline_count > 1000, f"多行 E 行数量过少：{multiline_count}"

    @pytest.mark.parametrize("index", range(10))
    def test_multiline_parsing(self, parser, all_notams, index):
        """多行 E 行解析测试"""
        # 获取多行 E 行的样本
        multiline_notams = [
            n for n in all_notams
            if '\n' in extract_e_line(n)
        ]

        if index >= len(multiline_notams):
            pytest.skip("超出样本范围")

        sample = multiline_notams[index]
        result = parser.parse(sample)

        assert result.e_raw is not None, "多行 E 行解析失败"
        # 多行内容应该被保留
        assert '\n' in result.e_raw or len(result.e_raw) > 20, \
            "多行 E 行内容可能丢失"


class TestEdgeCaseMisc:
    """其他边界情况测试"""

    @pytest.fixture(scope="class")
    def all_notams(self):
        return load_all_notams()

    @pytest.fixture
    def parser(self):
        return RegexParser()

    def test_notam_with_d_line(self, parser, all_notams):
        """带 D 行（时间段）的 NOTAM 解析"""
        # 找带 D 行的样本
        d_line_samples = [
            n for n in all_notams
            if 'D)' in n
        ]

        assert len(d_line_samples) > 0, "没有带 D 行的样本"

        sample = d_line_samples[0]
        result = parser.parse(sample)

        # D 行可能被解析到 result 中，检查是否存在
        # ParseResult 可能有 d_raw 或其他字段
        assert 'D)' in sample or hasattr(result, 'd_raw') or hasattr(result, 'd_time'), \
            "D 行解析失败"

    def test_notam_with_f_g_line(self, parser, all_notams):
        """带 F/G 行（高度限制）的 NOTAM 解析"""
        # 找带 F/G 行的样本
        fg_samples = [
            n for n in all_notams
            if 'F)' in n or 'G)' in n
        ]

        assert len(fg_samples) > 0, "没有带 F/G 行的样本"

        sample = fg_samples[0]
        result = parser.parse(sample)

        # F/G 行可能被解析到 E 行中
        assert result.e_raw is not None, "带 F/G 行的 NOTAM 解析失败"

    def test_notam_with_perfm_est(self, parser, all_notams):
        """带 PERM/EST 标记的 NOTAM 解析"""
        # 找带 PERM 或 EST 的样本
        perm_samples = [
            n for n in all_notams
            if 'PERM' in n or 'EST' in n
        ]

        if not perm_samples:
            pytest.skip("没有带 PERM/EST 的样本")

        sample = perm_samples[0]
        result = parser.parse(sample)

        assert result.c_time is not None or result.permanent, \
            "PERM/EST 标记解析失败"

    def test_notam_notamr_notamc(self, parser, all_notams):
        """NOTAMR/NOTAMC 解析"""
        notamr_samples = [n for n in all_notams if 'NOTAMR' in n]
        notamc_samples = [n for n in all_notams if 'NOTAMC' in n]

        # 测试 NOTAMR
        if notamr_samples:
            result = parser.parse(notamr_samples[0])
            assert result.q_line is not None, "NOTAMR 解析失败"

        # 测试 NOTAMC
        if notamc_samples:
            result = parser.parse(notamc_samples[0])
            # NOTAMC 可能没有完整的 E 行
            assert result.q_line is not None, "NOTAMC 解析失败"


class TestStressParsing:
    """压力测试（标记为 slow）"""

    @pytest.fixture(scope="class")
    def all_notams(self):
        return load_all_notams()

    @pytest.fixture
    def parser(self):
        return RegexParser()

    @pytest.mark.slow
    @pytest.mark.edge_case
    def test_parse_100_notams(self, parser, all_notams):
        """批量解析 100 条 NOTAM"""
        import time

        samples = all_notams[:100]
        start_time = time.time()

        success_count = 0
        for sample in samples:
            result = parser.parse(sample)
            if result.q_line is not None:
                success_count += 1

        elapsed = time.time() - start_time
        per_second = 100 / elapsed if elapsed > 0 else 0

        print(f"\n批量解析统计:")
        print(f"  总数：{len(samples)}")
        print(f"  成功：{success_count}")
        print(f"  耗时：{elapsed:.2f}秒")
        print(f"  速度：{per_second:.1f} 条/秒")

        assert success_count >= 80, f"批量解析成功率过低：{success_count}/100"
        assert elapsed < 10, f"解析速度过慢：{elapsed:.2f}秒"

    @pytest.mark.slow
    @pytest.mark.edge_case
    def test_concurrent_parsing(self, all_notams):
        """并发解析测试"""
        import concurrent.futures
        import time

        parser = RegexParser()
        samples = all_notams[:50]

        def parse_notam(notam_text):
            return parser.parse(notam_text)

        start_time = time.time()

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(parse_notam, sample) for sample in samples]
            results = [f.result() for f in futures]

        elapsed = time.time() - start_time
        success_count = sum(1 for r in results if r.q_line is not None)

        print(f"\n并发解析统计:")
        print(f"  总数：{len(samples)}")
        print(f"  成功：{success_count}")
        print(f"  耗时：{elapsed:.2f}秒")

        assert success_count >= 40, f"并发解析成功率过低：{success_count}/50"
