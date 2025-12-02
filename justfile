# AKAI Fire Library - Development Commands
# Requires: just (https://github.com/casey/just) and uv (https://github.com/astral-sh/uv)

# Default recipe to display available commands
default:
    @just --list

# Setup development environment
setup:
    @echo "Setting up development environment..."
    uv venv
    @echo "Virtual environment created."
    @echo "Installing dependencies..."
    uv pip install -r requirements.txt
    @echo "✓ Development environment ready!"

# Install dependencies
install:
    uv pip install -r requirements.txt

# Install package in development mode
install-dev:
    uv pip install -e .

# Format code with black
format:
    uv run black .

# Check code formatting without making changes
format-check:
    uv run black --check .

# Run all tests
test:
    uv run python -m unittest discover tests -v

# Run specific test file
test-file file:
    uv run python -m unittest {{file}} -v

# Run tests with hardware (comprehensive report)
test-hardware:
    uv run python run_hardware_tests.py

# Run a specific example
example name:
    uv run python examples/{{name}}.py

# List all available examples
examples:
    @echo "Available examples:"
    @find examples -name "*.py" -not -path "*/dupes/*" | sed 's|examples/||' | sed 's|\.py$||' | sort

# Clean up generated files
clean:
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete
    find . -type f -name "*.pyo" -delete
    find . -type f -name ".coverage" -delete
    find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true


# Check code quality and run tests
check: format-check test

# Full development cycle: format, test, clean
dev: format test clean

# Update requirements.txt with current installed packages
freeze:
    uv pip freeze > requirements.txt

# Show project status
status:
    @echo "🔥 AKAI Fire Library Status"
    @echo "=========================="
    @echo "Python version: $(python --version)"
    @echo "Virtual environment: $({{ if os() == "windows" { ".venv/Scripts/python" } else { ".venv/bin/python" } }} --version 2>/dev/null || echo 'Not activated')"
    @echo "Installed packages:"
    @uv pip list --quiet || echo "Run 'just setup' to install dependencies"

# Run the mock GUI (if available)
mock:
    uv run python examples/screen_simple.py