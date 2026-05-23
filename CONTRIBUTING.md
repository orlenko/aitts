# Contributing

Thanks for your interest! Bug reports, feature ideas, and PRs are all welcome.

## Development setup

```sh
git clone https://github.com/orlenko/aitts
cd aitts
uv sync
```

You'll need an `OPENAI_API_KEY` in your environment or a `.env` file for end-to-end testing.

## Common tasks

```sh
uv run pytest                       # run tests
uv run ruff check .                 # lint
uv run ruff check . --fix           # autofix
uv run aisay "hello"                # try the local CLI
uv tool install . --reinstall --no-cache  # install local checkout as global tool
```

The test suite does not call the OpenAI API — it covers the CLI surface, splitter, and playback lock.

## Pull requests

- Open against `main`.
- Keep changes focused; one logical change per PR.
- If you change CLI behavior, update the README and add a `CHANGELOG.md` entry under `[Unreleased]`.
- All checks (lint + pytest on macOS, Python 3.11–3.13) must pass.

## Releasing

Maintainers only.

1. Move `[Unreleased]` entries in `CHANGELOG.md` under a new `[X.Y.Z] — YYYY-MM-DD` heading.
2. Bump `__version__` in `src/aitts/__init__.py`.
3. Commit and tag: `git tag vX.Y.Z && git push --tags`.
4. The `publish` workflow builds and uploads to PyPI via trusted publishing.

### One-time PyPI setup

Before the first release:

1. Create the `aitts` project on PyPI (or claim the name).
2. In the project's "Publishing" settings, add a **pending trusted publisher**:
   - Owner: `orlenko`
   - Repository: `aitts`
   - Workflow: `publish.yml`
   - Environment: leave blank (or set to `pypi` and match in workflow).
3. Push your first version tag — PyPI promotes the pending publisher on first successful run.
