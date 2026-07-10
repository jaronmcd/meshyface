# Contributing to Meshyface

Thanks for your interest in contributing!

## Development setup

Python 3.11 or later is required.

```bash
git clone https://github.com/jaronmcd/meshyface.git
cd meshyface
pip install -r requirements-dev.txt
```

## Running tests

```bash
python -m pytest
```

## Checking coverage

```bash
python -m pytest \
  --cov=meshdash \
  --cov=mesh_dashboard \
  --cov=mesh_connection \
  --cov-report=term \
  --cov-fail-under=80
```

## Docker build

```bash
docker build -t meshyface:ci .
docker run --rm meshyface:ci --help
```

## Submitting changes

1. For anything non-trivial, open an issue first to discuss the approach.
2. Fork the repository and create a branch from `main`.
3. Make your changes and ensure all tests pass locally.
4. Do not bump `meshdash.__version__` for routine pull requests. Runtime
   builds identify themselves by git commit, and PR previews may set
   `MESH_DASH_PR_NUMBER` so `/api/revision` reports
   `<12-char-hash> · PR #<number>`. Reserve package version bumps for explicit
   release/versioning work.
5. Open a pull request — CI (tests on Python 3.11–3.13, Docker smoke test, coverage) must be green before merge.

## Reporting security vulnerabilities

Please do not open a public issue for security vulnerabilities. Report them
privately via GitHub's security advisory feature or by contacting the
maintainer directly.
