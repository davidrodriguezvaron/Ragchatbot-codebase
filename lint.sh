#!/bin/bash
# Script to run linting checks

echo "🔍 Running linting checks..."

echo "📋 Running ruff..."
uv run ruff check backend/ main.py

echo "✅ Linting complete!"
