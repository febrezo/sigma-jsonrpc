# CI and GHCR publishing

This repository includes two GitHub Actions workflows.

## 1) Pull request quality gates

File: .github/workflows/ci.yml

When it runs:

- on every pull request
- on push to main

What it checks:

- dependency installation
- Python syntax compilation for app and tests
- full unit test suite using unittest discovery
- repository secret scanning with gitleaks

## 2) Tagged image publishing to GHCR

File: .github/workflows/release-ghcr.yml

When it runs:

- on git tag push matching v*.*.*
- manual trigger from workflow_dispatch

What it does:

- logs in to ghcr.io using GITHUB_TOKEN
- builds Docker image from Dockerfile
- publishes tags derived from semantic version:
  - full version (example: 2.1.0)
  - major.minor (example: 2.1)
  - major (example: 2)

Published image reference:

- ghcr.io/<owner>/<repository>

Important note about GITHUB_TOKEN:

- `${{ secrets.GITHUB_TOKEN }}` is an ephemeral token injected by GitHub Actions at workflow runtime.
- It is not a hardcoded token stored in this repository.
- The repository does not contain a literal GitHub package-publishing token.

Example pull:

- docker pull ghcr.io/<owner>/<repository>:2.1.0

## Requiring tests before merge

GitHub Actions alone does not enforce merge blocking unless branch protection is configured.

In repository settings:

1. Open Settings -> Branches.
2. Create or edit branch protection rule for main.
3. Enable Require status checks to pass before merging.
4. Select the checks named Secret Scan and Quality Gates.

After that, pull requests cannot merge until secret scanning and unit tests pass.
