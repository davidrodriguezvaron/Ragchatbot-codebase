.PHONY: help install format lint check test run clean

help:
	@echo "Available commands:"
	@echo "  make install       - Install all dependencies"
	@echo "  make format        - Format code with black and isort"
	@echo "  make lint          - Run linting checks with ruff"
	@echo "  make check         - Run all quality checks (format + lint + test)"
	@echo "  make test          - Run test suite"
	@echo "  make run           - Start the development server"
	@echo "  make clean         - Remove cache and build artifacts"

install:
	uv sync

format:
	@echo "🎨 Formatting code..."
	uv run isort backend/ main.py
	uv run black backend/ main.py
	@echo "✨ Done!"

lint:
	@echo "🔍 Running linter..."
	uv run ruff check backend/ main.py

check:
	@echo "🚀 Running full quality checks..."
	@echo "\n1️⃣  Checking imports..."
	uv run isort --check-only backend/ main.py
	@echo "\n2️⃣  Checking formatting..."
	uv run black --check backend/ main.py
	@echo "\n3️⃣  Running linter..."
	uv run ruff check backend/ main.py
	@echo "\n4️⃣  Running tests..."
	cd backend && uv run pytest
	@echo "\n🎉 All checks passed!"

test:
	cd backend && uv run pytest

run:
	./run.sh

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	@echo "🧹 Cleaned cache and build artifacts"
