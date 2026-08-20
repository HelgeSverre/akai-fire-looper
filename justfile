# akai-fire-looper — Python library for the AKAI Fire MIDI controller
#
# Dev Python is pinned to 3.12 via .python-version: pygame 2.6.1's font
# module is broken on 3.14 and would take the pygame-mock tests with it.

uv := "uv"

# Show available recipes
default:
    @just --list

# === Setup ===

# Create .venv and sync every dependency from pyproject.toml/uv.lock
[group('setup')]
setup:
    {{ uv }} sync --all-extras

# Smoke-test packaging: install the repo as an editable package
[group('setup')]
install-editable:
    {{ uv }} pip install -e .

# === QA ===

# Run the full test suite
[group('qa')]
test:
    {{ uv }} run python -m unittest discover tests

# Run specific tests (e.g. just test-file tests.test_canvas)
[group('qa')]
test-file *ARGS:
    {{ uv }} run python -m unittest {{ ARGS }}

# Check formatting without changing files
[group('qa')]
lint:
    {{ uv }} run black --check .

# Pre-commit gate: formatting + tests
[group('qa')]
check: lint test

# === Format ===

# Format all Python files
[group('format')]
format:
    {{ uv }} run black .

# === Run ===

# Run an example by name (just example display_hello_world)
[group('run')]
example name:
    {{ uv }} run python "examples/{{ name }}.py"

# List available examples
[group('run')]
examples:
    @find examples -maxdepth 1 -name "*.py" | sed 's|examples/||;s|\.py$||' | sort

# Interactive pygame mock of the controller (clickable window)
[group('run')]
mock:
    {{ uv }} run python mock_gui_pygame.py

# Terminal-UI mock of the controller (rich)
[group('run')]
tui:
    {{ uv }} run python examples/run_tui_mock.py

# === Clean ===

# Remove caches and generated output
[group('clean')]
clean:
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.py[cod]" -delete
    find . -type f -name ".coverage" -delete
    find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
    rm -rf _screens dist build
