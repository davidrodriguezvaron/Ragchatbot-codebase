#!/bin/bash
# Script to format all Python code in the project

echo "🎨 Running code formatters..."

echo "📦 Running isort..."
uv run isort backend/ main.py

echo "⬛ Running black..."
uv run black backend/ main.py

echo "✨ Code formatting complete!"
