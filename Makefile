# NOTAM Parser Makefile

.PHONY: help test test-real test-slow test-qcode test-edge test-cov clean

help: ## 显示帮助信息
	@echo "NOTAM Parser 测试命令"
	@echo ""
	@echo "  make test         - 运行快速测试（Mock 模式，排除慢速测试）"
	@echo "  make test-real    - 运行真实 LLM 测试（需要.env 中配置 OPENAI_API_KEY）"
	@echo "  make test-slow    - 运行所有测试（含慢速和真实 LLM）"
	@echo "  make test-qcode   - 运行 QCODE 覆盖测试"
	@echo "  make test-edge    - 运行边界情况测试"
	@echo "  make test-cov     - 生成测试覆盖率报告"
	@echo "  make clean        - 清理缓存和临时文件"

test: ## 运行快速测试（Mock 模式，排除慢速测试）
	pytest tests/ -v -m "not slow and not real_llm"

test-real: ## 运行真实 LLM 测试（需要.env 中配置 OPENAI_API_KEY）
	pytest tests/ -m real_llm -v

test-slow: ## 运行所有测试（含慢速和真实 LLM）
	pytest tests/ -v

test-qcode: ## 运行 QCODE 覆盖测试
	pytest tests/test_qcode_coverage.py -v

test-edge: ## 运行边界情况测试
	pytest tests/test_edge_cases.py -v

test-cov: ## 生成测试覆盖率报告
	pytest tests/ --cov=src --cov-report=html --cov-report=term-missing
	@echo ""
	@echo "覆盖率报告已生成：htmlcov/index.html"

clean: ## 清理缓存和临时文件
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf __pycache__/
	rm -rf tests/__pycache__/
	rm -rf src/__pycache__/
	rm -rf tests/.llm_cache/
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@echo "清理完成"
