.PHONY: help docs docs-serve docs-clean install install-dev install-hooks test lint format type-check check clean version-patch version-minor version-major

# Default target
help:
	@echo "MW75 EEG Streamer - Available commands:"
	@echo ""
	@echo "Documentation:"
	@echo "  docs          Build Sphinx documentation"
	@echo "  docs-serve    Build and serve documentation locally"
	@echo "  docs-clean    Clean documentation build files"
	@echo ""
	@echo "Development:"
	@echo "  install       Install package with all dependencies"
	@echo "  install-dev   Install package with dev dependencies"
	@echo "  install-docs  Install documentation dependencies"
	@echo "  install-hooks Install git pre-commit hooks"
	@echo ""
	@echo "Code Quality:"
	@echo "  test          Run tests"
	@echo "  lint          Run flake8 linting"
	@echo "  format        Format code with black"
	@echo "  type-check    Run mypy type checking"
	@echo "  check         Run format, lint, and type-check"
	@echo ""
	@echo "Cleanup:"
	@echo "  clean         Remove build artifacts"
	@echo ""
	@echo "Version Management:"
	@echo "  version-patch Increment patch version (1.0.3 -> 1.0.4)"
	@echo "  version-minor Increment minor version (1.0.3 -> 1.1.0)"
	@echo "  version-major Increment major version (1.0.3 -> 2.0.0)"

# Documentation targets
docs:
	@echo "Building Sphinx documentation..."
	cd docs-src && uv run sphinx-build -b html . ../docs/api
	@echo "Documentation built in docs/api/"

docs-serve: docs
	@echo "Starting documentation server..."
	@echo "Open http://localhost:8000/api/ in your browser"
	cd docs && uv run -m http.server 8000

docs-clean:
	@echo "Cleaning documentation build files..."
	rm -rf docs-src/_build
	rm -rf docs/api

# Installation targets
install:
	uv pip install -e ".[all]"

install-dev:
	uv pip install -e ".[dev]"

install-docs:
	uv pip install -e ".[docs]"

install-hooks:
	@echo "Installing git pre-commit hooks..."
	@if [ ! -d ".git" ]; then \
		echo "❌ Error: Not in a git repository"; \
		exit 1; \
	fi
	cp hooks/pre-commit .git/hooks/pre-commit
	chmod +x .git/hooks/pre-commit
	@echo "Pre-commit hook installed successfully! Code quality checks will now run automatically before each commit."

# Code quality targets
test:
	@echo "Running tests..."
	uv run -m mw75_streamer.testing

lint:
	@echo "Running flake8..."
	uv run flake8 mw75_streamer/ --exclude=__pycache__

format:
	@echo "Formatting code with black..."
	uv run black mw75_streamer/

type-check:
	@echo "Running mypy type checking..."
	uv run mypy mw75_streamer/ --ignore-missing-imports --disable-error-code=unreachable

check: format lint type-check
	@echo "All code quality checks completed successfully!"

# Cleanup targets
clean:
	@echo "Cleaning build artifacts..."
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf docs-src/_build/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Version management targets
version-patch:
	@echo "Incrementing patch version..."
	@current_version=$$(grep '^version = ' pyproject.toml | head -1 | sed 's/version = "\(.*\)"/\1/'); \
	major=$$(echo $$current_version | cut -d. -f1); \
	minor=$$(echo $$current_version | cut -d. -f2); \
	patch=$$(echo $$current_version | cut -d. -f3); \
	new_patch=$$((patch + 1)); \
	new_version="$$major.$$minor.$$new_patch"; \
	echo "Updating version from $$current_version to $$new_version"; \
	sed -i '' "s/^version = \".*\"/version = \"$$new_version\"/" pyproject.toml; \
	sed -i '' "s/__version__ = \".*\"/__version__ = \"$$new_version\"/" mw75_streamer/__init__.py; \
	echo "Updated pyproject.toml and __init__.py to version $$new_version"

version-minor:
	@echo "Incrementing minor version..."
	@current_version=$$(grep '^version = ' pyproject.toml | head -1 | sed 's/version = "\(.*\)"/\1/'); \
	major=$$(echo $$current_version | cut -d. -f1); \
	minor=$$(echo $$current_version | cut -d. -f2); \
	new_minor=$$((minor + 1)); \
	new_version="$$major.$$new_minor.0"; \
	echo "Updating version from $$current_version to $$new_version"; \
	sed -i '' "s/^version = \".*\"/version = \"$$new_version\"/" pyproject.toml; \
	sed -i '' "s/__version__ = \".*\"/__version__ = \"$$new_version\"/" mw75_streamer/__init__.py; \
	echo "Updated pyproject.toml and __init__.py to version $$new_version"

version-major:
	@echo "Incrementing major version..."
	@current_version=$$(grep '^version = ' pyproject.toml | head -1 | sed 's/version = "\(.*\)"/\1/'); \
	major=$$(echo $$current_version | cut -d. -f1); \
	new_major=$$((major + 1)); \
	new_version="$$new_major.0.0"; \
	echo "Updating version from $$current_version to $$new_version"; \
	sed -i '' "s/^version = \".*\"/version = \"$$new_version\"/" pyproject.toml; \
	sed -i '' "s/__version__ = \".*\"/__version__ = \"$$new_version\"/" mw75_streamer/__init__.py; \
	echo "Updated pyproject.toml and __init__.py to version $$new_version"
