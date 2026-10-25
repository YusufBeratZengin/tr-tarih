# Changelog

All notable changes are recorded here, following [Keep a Changelog 1.1](https://keepachangelog.com/en/1.1.0/) and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Runnable standalone examples for date/time parsing (`examples/dates_and_times.py`) and number/lira processing (`examples/money_and_numbers.py`).
- Dedicated examples documentation (`examples/README.md`) and automated clean execution tests for all example scripts.
- Additional test coverage for period stem suffixes, conflicting date offsets, empty currency markers, consecutive scale words, and invalid formatting arguments.

### Documentation

- Documented additional examples and added `format_date` to options tables across English and Turkish READMEs.

### Fixed

- Number and money parsers reject unsupported punctuation and currency symbols instead of
  silently dropping them; decimals without a leading zero are rejected.
- Negative lira amounts retain their sign after currency prefixes such as `TL -5`;
  misplaced or repeated signs are rejected.

## [0.1.0] - 2026-10-24

### Added

- Typed, dependency-free Turkish date/time, number and lira parsers and formatters.
- CLI with JSON results, explanatory assumptions and distinct exit codes.
- Detailed parse results and strict APIs with `ParseError`.
- Offline tests with an enforced 85% statement/branch coverage threshold.
- English and Turkish guides, runnable example and reproducible terminal SVG.
- Cross-platform CI, CodeQL, Dependabot, community templates and tag-based release workflow.

### Fixed

- Out-of-range calendar expressions return a failed result instead of crashing.
- Long decimal inputs retain their precision even with a reduced Decimal context.
- Invalid formatter inputs and mixed CLI timezone references produce clear errors.
- Calendar dates allow a year after the month marker and day.

[Unreleased]: https://github.com/YusufBeratZengin/tr-tarih/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/YusufBeratZengin/tr-tarih/releases/tag/v0.1.0
