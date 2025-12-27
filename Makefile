.PHONY: help install install-dev install-all venv clean test test-unit test-integration coverage lint format typecheck docs docs-serve demo run build publish pre-commit docker-up docker-down docker-logs

# Variables
PYTHON := python3
VENV := .venv
UV := uv
PIP := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/pytest
PYTHON_VENV := $(VENV)/bin/python
SPHINX := $(VENV)/bin/sphinx-build
RUFF := $(VENV)/bin/ruff
MYPY := $(VENV)/bin/mypy

# Colors
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

# Default target
.DEFAULT_GOAL := help

#==============================================================================
# HELP
#==============================================================================

help: ## Show this help message
	@echo ""
	@echo "$(BLUE)╔══════════════════════════════════════════════════════════════╗$(NC)"
	@echo "$(BLUE)║            🔍 RCA Agent - Available Commands                 ║$(NC)"
	@echo "$(BLUE)╚══════════════════════════════════════════════════════════════╝$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""

#==============================================================================
# INSTALLATION
#==============================================================================

venv: ## Create virtual environment
	@echo "$(BLUE)📦 Creating virtual environment...$(NC)"
	@$(PYTHON) -m venv $(VENV)
	@echo "$(GREEN)✅ Virtual environment created in $(VENV)$(NC)"

install: venv ## Install base dependencies
	@echo "$(BLUE)📥 Installing dependencies...$(NC)"
	@$(PIP) install --upgrade pip
	@$(PIP) install -e .
	@echo "$(GREEN)✅ Installation complete$(NC)"

install-dev: venv ## Install development dependencies (tests, linting)
	@echo "$(BLUE)📥 Installing development dependencies...$(NC)"
	@$(PIP) install --upgrade pip
	@$(PIP) install -e ".[dev]"
	@$(VENV)/bin/pre-commit install
	@echo "$(GREEN)✅ Dev installation complete$(NC)"

install-all: venv ## Install all dependencies (dev, docs, huggingface, ollama)
	@echo "$(BLUE)📥 Installing all dependencies...$(NC)"
	@$(PIP) install --upgrade pip
	@$(PIP) install -e ".[all]"
	@$(VENV)/bin/pre-commit install
	@echo "$(GREEN)✅ Full installation complete$(NC)"

install-uv: ## Install with uv (faster)
	@echo "$(BLUE)📥 Installing with uv...$(NC)"
	@$(UV) venv $(VENV)
	@$(UV) pip install -e ".[all]"
	@echo "$(GREEN)✅ UV installation complete$(NC)"

#==============================================================================
# TESTS
#==============================================================================

test: ## Run all tests
	@echo "$(BLUE)🧪 Running tests...$(NC)"
	@$(PYTEST) tests/ -v
	@echo "$(GREEN)✅ Tests complete$(NC)"

test-unit: ## Run unit tests only
	@echo "$(BLUE)🧪 Running unit tests...$(NC)"
	@$(PYTEST) tests/unit/ -v -m unit
	@echo "$(GREEN)✅ Unit tests complete$(NC)"

test-integration: ## Run integration tests only
	@echo "$(BLUE)🧪 Running integration tests...$(NC)"
	@$(PYTEST) tests/integration/ -v -m integration
	@echo "$(GREEN)✅ Integration tests complete$(NC)"

test-fast: ## Run fast tests (skip slow tests)
	@echo "$(BLUE)🧪 Running fast tests...$(NC)"
	@$(PYTEST) tests/ -v -m "not slow"
	@echo "$(GREEN)✅ Fast tests complete$(NC)"

#==============================================================================
# COVERAGE
#==============================================================================

coverage: ## Calculate code coverage
	@echo "$(BLUE)📊 Calculating coverage...$(NC)"
	@$(PYTEST) tests/ --cov=src/rca_agent --cov-report=term-missing --cov-report=html:htmlcov
	@echo "$(GREEN)✅ Coverage report generated in htmlcov/$(NC)"

coverage-report: coverage ## Open coverage report in browser
	@echo "$(BLUE)🌐 Opening coverage report...$(NC)"
	@open htmlcov/index.html 2>/dev/null || xdg-open htmlcov/index.html 2>/dev/null || echo "Open htmlcov/index.html manually"

#==============================================================================
# CODE QUALITY
#==============================================================================

lint: ## Check code style with ruff
	@echo "$(BLUE)🔍 Checking code style...$(NC)"
	@$(RUFF) check src/ tests/
	@echo "$(GREEN)✅ Lint check complete$(NC)"

lint-fix: ## Auto-fix code style issues
	@echo "$(BLUE)🔧 Auto-fixing code style...$(NC)"
	@$(RUFF) check src/ tests/ --fix
	@echo "$(GREEN)✅ Fixes applied$(NC)"

format: ## Format code with ruff
	@echo "$(BLUE)✨ Formatting code...$(NC)"
	@$(RUFF) format src/ tests/
	@echo "$(GREEN)✅ Formatting complete$(NC)"

typecheck: ## Check types with mypy
	@echo "$(BLUE)🔎 Checking types...$(NC)"
	@$(MYPY) src/rca_agent/
	@echo "$(GREEN)✅ Type check complete$(NC)"

check: lint typecheck test ## Run all checks (lint, typecheck, test)
	@echo "$(GREEN)✅ All checks passed$(NC)"

pre-commit: ## Run pre-commit on all files
	@echo "$(BLUE)🔄 Running pre-commit...$(NC)"
	@$(VENV)/bin/pre-commit run --all-files
	@echo "$(GREEN)✅ Pre-commit complete$(NC)"

#==============================================================================
# DOCUMENTATION
#==============================================================================

docs: ## Generate Sphinx documentation
	@echo "$(BLUE)📚 Generating documentation...$(NC)"
	@cd docs && make html SPHINXBUILD=../$(SPHINX)
	@echo "$(GREEN)✅ Documentation generated in docs/_build/html/$(NC)"

docs-serve: docs ## Generate and serve documentation locally
	@echo "$(BLUE)🌐 Serving documentation at http://localhost:8080$(NC)"
	@cd docs/_build/html && $(PYTHON_VENV) -m http.server 8080

docs-clean: ## Clean generated documentation
	@echo "$(BLUE)🧹 Cleaning documentation...$(NC)"
	@cd docs && make clean
	@echo "$(GREEN)✅ Documentation cleaned$(NC)"

#==============================================================================
# DEMO & RUN
#==============================================================================

demo: ## Run a demo (scenarios: oom, schema-break, source-timeout, code-regression)
	@echo "$(BLUE)🎮 Running demo...$(NC)"
	@$(VENV)/bin/rca-agent demo --scenario oom

demo-all: ## Run all demo scenarios
	@echo "$(BLUE)🎮 Running all demo scenarios...$(NC)"
	@$(VENV)/bin/rca-agent demo --scenario oom
	@echo ""
	@$(VENV)/bin/rca-agent demo --scenario schema-break
	@echo ""
	@$(VENV)/bin/rca-agent demo --scenario source-timeout
	@echo ""
	@$(VENV)/bin/rca-agent demo --scenario code-regression

run: ## Start the webhook server
	@echo "$(BLUE)🚀 Starting server...$(NC)"
	@$(VENV)/bin/rca-agent serve --port 8000

run-dev: ## Start the server in development mode (with reload)
	@echo "$(BLUE)🚀 Starting server in dev mode...$(NC)"
	@$(VENV)/bin/rca-agent serve --port 8000 --reload

stats: ## Show incident statistics
	@$(VENV)/bin/rca-agent stats

#==============================================================================
# DOCKER
#==============================================================================

docker-up: ## Start Docker environment (Airflow + RCA Agent)
	@echo "$(BLUE)🐳 Starting Docker Compose...$(NC)"
	@cd demo && docker-compose up -d
	@echo "$(GREEN)✅ Services started$(NC)"
	@echo "   - Airflow: http://localhost:8080 (admin/admin)"
	@echo "   - RCA Agent API: http://localhost:8000"

docker-down: ## Stop Docker environment
	@echo "$(BLUE)🐳 Stopping Docker Compose...$(NC)"
	@cd demo && docker-compose down
	@echo "$(GREEN)✅ Services stopped$(NC)"

docker-logs: ## Show Docker logs
	@cd demo && docker-compose logs -f

docker-build: ## Rebuild Docker images
	@echo "$(BLUE)🐳 Rebuilding images...$(NC)"
	@cd demo && docker-compose build --no-cache
	@echo "$(GREEN)✅ Images rebuilt$(NC)"

docker-clean: ## Clean Docker volumes
	@echo "$(BLUE)🧹 Cleaning Docker volumes...$(NC)"
	@cd demo && docker-compose down -v
	@echo "$(GREEN)✅ Volumes cleaned$(NC)"

#==============================================================================
# BUILD & PUBLISH
#==============================================================================

build: clean ## Build the package
	@echo "$(BLUE)📦 Building package...$(NC)"
	@$(PYTHON_VENV) -m build
	@echo "$(GREEN)✅ Package built in dist/$(NC)"

publish-test: build ## Publish to TestPyPI
	@echo "$(BLUE)📤 Publishing to TestPyPI...$(NC)"
	@$(PYTHON_VENV) -m twine upload --repository testpypi dist/*
	@echo "$(GREEN)✅ Published to TestPyPI$(NC)"

publish: build ## Publish to PyPI
	@echo "$(YELLOW)⚠️  Publishing to PyPI...$(NC)"
	@$(PYTHON_VENV) -m twine upload dist/*
	@echo "$(GREEN)✅ Published to PyPI$(NC)"

#==============================================================================
# CLEANUP
#==============================================================================

clean: ## Clean generated files
	@echo "$(BLUE)🧹 Cleaning...$(NC)"
	@rm -rf build/
	@rm -rf dist/
	@rm -rf *.egg-info
	@rm -rf src/*.egg-info
	@rm -rf .pytest_cache/
	@rm -rf .mypy_cache/
	@rm -rf .ruff_cache/
	@rm -rf htmlcov/
	@rm -rf .coverage
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete
	@echo "$(GREEN)✅ Cleanup complete$(NC)"

clean-all: clean ## Clean everything (including venv)
	@echo "$(BLUE)🧹 Full cleanup...$(NC)"
	@rm -rf $(VENV)
	@rm -rf data/
	@echo "$(GREEN)✅ Full cleanup complete$(NC)"

#==============================================================================
# UTILITIES
#==============================================================================

version: ## Show version
	@$(VENV)/bin/rca-agent version

env-example: ## Create .env file from .env.example
	@cp .env.example .env
	@echo "$(GREEN)✅ .env file created. Edit it with your API keys.$(NC)"

tree: ## Show project tree structure
	@tree -I '__pycache__|*.egg-info|.venv|.git|htmlcov|.pytest_cache|.mypy_cache|.ruff_cache' -L 3

info: ## Show project information
	@echo ""
	@echo "$(BLUE)╔══════════════════════════════════════════════════════════════╗$(NC)"
	@echo "$(BLUE)║               🔍 RCA Agent - Project Info                    ║$(NC)"
	@echo "$(BLUE)╚══════════════════════════════════════════════════════════════╝$(NC)"
	@echo ""
	@echo "  $(GREEN)Python:$(NC)     $$($(PYTHON) --version)"
	@echo "  $(GREEN)Venv:$(NC)       $(VENV)"
	@echo "  $(GREEN)Version:$(NC)    $$($(VENV)/bin/rca-agent version 2>/dev/null || echo 'Not installed')"
	@echo ""
