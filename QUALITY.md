# Code Quality Tools

This project uses several tools to maintain code quality and consistency.

## Tools Included

- **Black**: Automatic code formatter for Python
- **Ruff**: Fast Python linter (replaces flake8, pylint, etc.)
- **isort**: Automatic import sorter
- **pytest**: Testing framework

## Installation

Install all development dependencies:

```bash
uv sync
```

## Usage

### Format Code

To automatically format all Python code:

```bash
./format.sh
```

This runs:
- `isort` - Sorts and organizes imports
- `black` - Formats code to consistent style

### Check Linting

To check for code issues without fixing:

```bash
./lint.sh
```

### Run Full Quality Checks

To run all checks (formatting, linting, and tests):

```bash
./quality-check.sh
```

This will:
1. Check if code is properly formatted (without modifying)
2. Run linting checks
3. Run the test suite

**Note**: This script will exit on the first failure.

## Configuration

All tool configurations are in `pyproject.toml`:

- **Line length**: 100 characters (Black, Ruff, isort)
- **Python version**: 3.13+
- **Excluded directories**: `.venv`, `chroma_db`, build artifacts

## Pre-commit Integration (Optional)

You can set up these checks to run automatically before commits. Add to `.git/hooks/pre-commit`:

```bash
#!/bin/bash
./quality-check.sh
```

Make it executable:
```bash
chmod +x .git/hooks/pre-commit
```

## CI/CD Integration

Add to your CI pipeline:

```yaml
- name: Run quality checks
  run: ./quality-check.sh
```
