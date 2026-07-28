# IFPI Learning Platform — Development Commands
# ============================================
# Common commands for testing, linting, and type-checking.

.PHONY: help typecheck test fmt lint check pre-commit install-hooks

# Default target
help:
	@echo "IFPI Development Commands"
	@echo "========================"
	@echo ""
	@echo "Testing:"
	@echo "  make test            - Run backend pytest suite"
	@echo "  make typecheck       - Run frontend tsc --noEmit"
	@echo ""
	@echo "Code Quality:"
	@echo "  make fmt             - Auto-format Python (autoflake + black)"
	@echo "  make lint            - Run basic lint checks (Python compile + typecheck)"
	@echo "  make check           - Run lint + test (full pre-commit check)"
	@echo ""
	@echo "Git Hooks:"
	@echo "  make install-hooks   - Install pre-commit hooks"
	@echo "  make pre-commit      - Run all pre-commit checks manually"

# ─── Frontend ────────────────────────────────────────────────────

typecheck:
	@echo "Running tsc --noEmit..."
	cd frontend && yarn typecheck

# ─── Backend ─────────────────────────────────────────────────────

test:
	@echo "Running backend tests..."
	cd backend && python -m pytest tests/ -q

# ─── Formatting ──────────────────────────────────────────────────

fmt:
	@echo "Formatting Python code..."
	cd backend && python -m autoflake --in-place --remove-all-unused-imports -r routers services
	cd backend && python -m black routers services --quiet 2>/dev/null || echo "black not installed — skipping"

# ─── Linting ─────────────────────────────────────────────────────

lint:
	@echo "Running Python syntax checks..."
	cd backend && python -m py_compile $$(find routers services -name '*.py' -not -path '*/__pycache__/*')
	@echo "Python syntax: OK"
	@echo "Running TypeScript typecheck..."
	cd frontend && yarn typecheck

# ─── Full check (mirrors CI) ─────────────────────────────────────

check: lint test
	@echo ""
	@echo "All checks passed."

# ─── Pre-commit hooks ────────────────────────────────────────────

install-hooks:
	@echo "Installing pre-commit hooks..."
	pip install pre-commit -q
	pre-commit install
	@echo "Hooks installed. Run 'make pre-commit' to test."

pre-commit:
	@echo "Running pre-commit checks..."
	pre-commit run --all-files
