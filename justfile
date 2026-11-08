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
    {{ uv }} sync --all-extras

# === QA ===

# Run the full test suite
[group('qa')]
test:
    {{ uv }} run python -m unittest discover

# Run specific tests (e.g. just test-file tests.test_canvas)
[group('qa')]
test-file *ARGS:
    {{ uv }} run python -m unittest {{ ARGS }}

# Check lint and formatting without changing files
[group('qa')]
lint:
    {{ uv }} run ruff check .
    {{ uv }} run ruff format --check .

# Pre-commit gate: formatting + tests
[group('qa')]
check: lint test

# === Format ===

# Format all Python files
[group('format')]
format:
    {{ uv }} run ruff format .

# === Run ===

# Run an example by name (just example pads_color_fades)
[group('run')]
example name:
    {{ uv }} run python -m "examples.{{ name }}"

# Run a complete app (just app circuit / synth_editor / midi_scope)
[group('run')]
app name:
    {{ uv }} run python -m "examples.apps.{{ name }}"

# List available examples
[group('run')]
examples:
    @find examples -maxdepth 1 -name "*.py" ! -name "_*.py" | sed 's|examples/||;s|\.py$||' | sort

# Interactive pygame mock of the controller (clickable window)
[group('run')]
mock:
    {{ uv }} run python mock_gui_pygame.py

# Terminal-UI mock of the controller (rich)
[group('run')]
tui:
    {{ uv }} run python -m examples.mock_terminal

# === Clean ===

# Remove caches and generated output
[group('clean')]
clean:
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.py[cod]" -delete
    find . -type f -name ".coverage" -delete
    find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
    rm -rf _screens dist build
