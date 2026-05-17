# Contributing to sigma-jsonrpc

Thanks for your interest in contributing! Please follow these guidelines to keep the project maintainable and reliable.

## Required Checks Before Submitting a Pull Request

Every PR **must** pass these checks before merging:

### 1. Linting (ruff)

```bash
ruff check app tests
ruff format --check app tests
```

Zero errors required. Ruff enforces PEP 8 and project conventions.

### 2. Python Syntax Validation

```bash
python -m compileall app tests
```

### 3. Unit Tests

```bash
python -m unittest discover -s tests -p 'test_*.py'
```

All tests must pass. If you change behavior, add or update tests.

### 4. Secret Scanning

The CI runs [gitleaks](https://github.com/gitleaks/gitleaks) on every PR. Avoid committing secrets, tokens, or credentials.

## GitHub Actions CI

Two workflows run automatically:

| Workflow | Trigger | What it does |
|---|---|---|
| **CI** | Every PR and push to `main` | Secret scan, linting, syntax check, unit tests |
| **Publish GHCR Image** | Push to `main`, semver tag `v*.*.*`, or manual dispatch | Quality gates → build & push Docker image to `ghcr.io` |

## Branch Protection

The `main` branch is protected. PRs **cannot be merged** unless:
- All CI checks pass (secret scan, linting, tests)
- At least one review is approved
- All checklist items in the PR template are completed

## Dependency Updates

Dependencies are updated automatically via [Dependabot](.github/dependabot.yml) on a weekly schedule for:
- Python packages (`requirements.txt`, `requirements-dev.txt`)
- Docker base image
- GitHub Actions

## Local Development Setup

```bash
# Clone and enter the repository
git clone https://github.com/your-org/sigma-jsonrpc.git
cd sigma-jsonrpc

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install sigma-cli and backends
bash scripts/install_plugins.sh

# Run tests
python -m unittest discover -s tests -p 'test_*.py'

# Run ruff
ruff check app tests
ruff check app tests --fix   # auto-fix where possible
ruff format app tests
```
