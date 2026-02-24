#!/bin/bash
# Script to run all quality checks (format check + lint + tests)

set -e  # Exit on any error

echo "🚀 Running full quality checks..."
echo ""

echo "1️⃣  Checking code formatting..."
echo "   Running isort check..."
uv run isort --check-only backend/ main.py || {
    echo "❌ isort check failed. Run './format.sh' to fix."
    exit 1
}

echo "   Running black check..."
uv run black --check backend/ main.py || {
    echo "❌ black check failed. Run './format.sh' to fix."
    exit 1
}

echo "✅ Code formatting is correct"
echo ""

echo "2️⃣  Running linting..."
uv run ruff check backend/ main.py || {
    echo "❌ Linting failed. Fix the issues above."
    exit 1
}

echo "✅ Linting passed"
echo ""

echo "3️⃣  Running tests..."
cd backend && uv run pytest || {
    echo "❌ Tests failed."
    exit 1
}

echo ""
echo "🎉 All quality checks passed!"
