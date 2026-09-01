# Contributing to TendrilGrow

Thanks for helping improve TendrilGrow.

## Before you start

- Read `README.md` for product context and architecture.
- Review open issues before starting new work.
- For substantial changes, open an issue first to align scope.

## Development setup

TendrilGrow targets Python 3.13+ and the current Home Assistant release.

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/pip install -r requirements-test.txt
```

Run the same checks CI runs before pushing:

```bash
./.venv/bin/ruff format --check .
./.venv/bin/ruff check .
./.venv/bin/pytest -q
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

## Commit and PR conventions

- This project follows [Conventional Commits](https://www.conventionalcommits.org/)
  (for example, `feat(sensor): ...`, `fix(config): ...`, `docs: ...`).
- Keep the **README** HACS-friendly (install first, internals last). User docs
  live under `docs/` and must stay accurate when entities or flows change.
- Keep PRs small and focused, and fill in the pull request template.
- Add or update tests for behavior changes, and update docs for user-visible
  changes.

## Documentation

User-facing docs live under `docs/` and are built with MkDocs Material. Preview
locally with:

```bash
./.venv/bin/pip install -r requirements-docs.txt
./.venv/bin/mkdocs serve
```

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
