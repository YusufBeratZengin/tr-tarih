# Contributing

Use Python 3.10 or newer. Create a branch in your own checkout, then install the development dependencies:

```sh
python -m pip install -e ".[dev]"
python -m ruff check .
python -m mypy src
python -m pytest -q
python scripts/make-demo.py
python -m build
python -m twine check dist/*
```

Tests must be offline, meaningful and deterministic. Keep combined statement/branch coverage at or above 85%; include failure cases and CLI exit codes when changing parsing. CLI tests can invoke `tr_tarih.cli.main` directly, so subprocess permissions are unnecessary. CI checks Python 3.10–3.14 on Windows and Linux.

If installing packages is unavailable, set `PYTHONPATH=src` (PowerShell: `$env:PYTHONPATH = 'src'`) and use existing development tools. Pytest also sets the source path automatically. The example and demo generator run straight from the checkout. Building a distribution still needs Hatchling; report an unavailable backend instead of claiming the build passed.

Keep runtime dependencies at zero. Preserve public APIs, update both READMEs with matching sections, regenerate the demo after CLI changes, and add user-visible changes to `CHANGELOG.md`. Do not include private data, credentials or machine-specific paths in examples, tests, issues or logs.

Use small Conventional Commits: `feat:`, `fix:`, `test:`, `docs:`, `ci:` or `chore:`. Explain the resulting behavior and validation in your pull request. Follow [the Code of Conduct](CODE_OF_CONDUCT.md); report vulnerabilities through [SECURITY.md](SECURITY.md).

## Maintainer release procedure

Publishing is a separate maintainer action. Preparing a checkout does not authorize a release.

1. Update the changelog and bump `pyproject.toml` and `tr_tarih.__version__` together. Use SemVer; breaking changes during 0.x increment the minor version.
2. Run all checks above, inspect the wheel and source distribution, and install the wheel in a clean environment. `twine check` validates distributions without uploading them.
3. Commit as `chore(release): vX.Y.Z`. Only when a release is explicitly authorized, tag that commit `vX.Y.Z` and push the tag.
4. `publish.yml` verifies the version, runs quality checks, builds and validates distributions, then publishes through PyPI trusted publishing with OIDC in the `pypi` environment.

Before the first release, configure a PyPI pending/trusted publisher for owner `YusufBeratZengin`, repository `tr-tarih`, workflow `publish.yml` and environment `pypi`. Configure environment reviewers if desired. Do not store an API token. The tag must match both version declarations. No public release or repository setup is assumed by the source installation instructions.
