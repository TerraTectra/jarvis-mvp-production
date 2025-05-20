.PHONY: install format lint test test-cov test-html mypy check build clean

# Variables
PYTHON = python
PIP = pip
PYTEST = pytest
BLACK = black
ISORT = isort
MYPY = mypy
RUFF = ruff
DOCKER = docker
DOCKER_COMPOSE = docker-compose

# Project variables
PACKAGE = src
TESTS = tests
DOCKER_IMAGE = jarvis-mvp
DOCKER_TAG = latest

# Help
help:
	@echo "Available targets:"
	@echo "  install     - Install development dependencies"
	@echo "  format      - Format code with black and isort"
	@echo "  lint        - Run all linters"
	@echo "  test        - Run tests"
	@echo "  test-cov    - Run tests with coverage"
	@echo "  test-html   - Generate HTML coverage report"
	@echo "  mypy        - Run type checking"
	@echo "  check       - Run all checks (format, lint, mypy, test)"
	@echo "  build       - Build Docker image"
	@echo "  run         - Run the application"
	@echo "  clean       - Clean up temporary files"

# Install development dependencies
install:
	$(PIP) install --upgrade pip
	$(PIP) install -e .[dev]
	pre-commit install

# Format code
format:
	$(BLACK) $(PACKAGE) $(TESTS)
	$(ISORT) $(PACKAGE) $(TESTS)

# Lint code
lint:
	$(RUFF) check --fix $(PACKAGE) $(TESTS)
	$(BLACK) --check $(PACKAGE) $(TESTS)
	$(ISORT) --check-only $(PACKAGE) $(TESTS)

# Run tests
test:
	$(PYTEST) -v $(TESTS)

# Run tests with coverage
test-cov:
	$(PYTEST) --cov=$(PACKAGE) --cov-report=term-missing $(TESTS)

# Generate HTML coverage report
test-html:
	$(PYTEST) --cov=$(PACKAGE) --cov-report=html $(TESTS)

# Run type checking
mypy:
	$(MYPY) $(PACKAGE) $(TESTS) --strict

# Run all checks
check: format lint mypy test

# Build Docker image
build:
	$(DOCKER) build -t $(DOCKER_IMAGE):$(DOCKER_TAG) .

# Run the application
run:
	$(PYTHON) -m $(PACKAGE).main

# Clean up temporary files
clean:
	find . -type d -name "__pycache__" -exec rm -r {} +
	find . -type d -name ".mypy_cache" -exec rm -r {} +
	find . -type d -name ".pytest_cache" -exec rm -r {} +
	rm -rf .coverage htmlcov build dist *.egg-info

# Default target
.DEFAULT_GOAL := help
