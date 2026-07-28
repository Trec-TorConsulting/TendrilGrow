# Contributing to TendrilGrow

Thanks for helping improve TendrilGrow.

## Before you start

- Read `README.md` for product context and architecture.
- Review open issues before starting new work.
- For substantial changes, open an issue first to align scope.

## Development setup

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/pip install -r requirements-test.txt
```

## Workflow

1. Create a topic branch from `main`.
2. Make focused commits with clear messages.
3. Run checks locally:

```bash
./.venv/bin/ruff check .
./.venv/bin/pytest -q
```

4. Open a Pull Request with:
   - Problem statement
   - Scope and implementation summary
   - Validation evidence (tests/screenshots/log snippets)

## Pull request standards

- Keep PRs small and focused.
- Add or update tests for behavior changes.
- Update docs for user-visible changes.
- Do not include secrets, real API keys, or private URLs.

## Coding standards

- Follow existing integration patterns and naming.
- Prefer explicit typing and small functions.
- Preserve backward compatibility where possible.
- Use redaction-safe logging for sensitive fields.

## OpenSpec workflow

This repository uses OpenSpec for planning and implementation tracking.

- Propose changes first when introducing non-trivial behavior.
- Keep tasks/specs synchronized with implemented changes.

## Reporting bugs

Please include:

- Home Assistant version
- TendrilGrow version
- Integration configuration context (without secrets)
- Reproduction steps
- Expected vs actual behavior
- Relevant logs

## Code of Conduct

By participating, you agree to `CODE_OF_CONDUCT.md`.
