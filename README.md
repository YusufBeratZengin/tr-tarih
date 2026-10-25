# tr-tarih
[![CI](https://github.com/YusufBeratZengin/tr-tarih/actions/workflows/ci.yml/badge.svg)](https://github.com/YusufBeratZengin/tr-tarih/actions/workflows/ci.yml) [![PyPI](https://img.shields.io/pypi/v/tr-tarih)](https://pypi.org/project/tr-tarih/) [![MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE) ![Python](https://img.shields.io/badge/python-3.10%2B-blue) ![Dependencies](https://img.shields.io/badge/dependencies-zero-green)
[English](README.md) | [Türkçe](README.tr.md)

Parse and format Turkish dates, times, numbers and lira amounts from your terminal or Python.
Typed, offline and dependency-free at runtime, with explicit reasons for unclear input.
Install from this checkout: `python -m pip install .`
Try: `tr-tarih date "yarın saat 15:30" --now 2026-10-23T10:00`

```console
$ tr-tarih number "iki yüz elli bin"
250000
$ tr-tarih fmt-money 1250.5
₺1.250,50
```

## Demo

![Actual terminal output](docs/demo.svg)

Regenerate from actual CLI output with `python scripts/make-demo.py`. No terminal capture service or subprocess is needed.

## Install

Requires Python 3.10 or newer. The install command above uses this source checkout; a public PyPI release has not been verified. Installing requires Hatchling as a build dependency, but using the library does not require any third-party package.

Without installing, set the source path and use the module:

```sh
# Linux / macOS
export PYTHONPATH=src
python -m tr_tarih --help
```

```powershell
# PowerShell
$env:PYTHONPATH = 'src'
python -m tr_tarih --help
```

After installation, `tr-tarih` and `python -m tr_tarih` accept the same arguments.

## Usage

### CLI

```sh
tr-tarih date "yarın saat 15:30" --now 2026-10-23T10:00
tr-tarih date "gelecek ayın son günü" --now 2026-10-23T10:00 --explain
tr-tarih number "bir virgül beş milyon" --json
tr-tarih money "beş lira elli kuruş" --json
tr-tarih words 1250
tr-tarih fmt-date 2026-10-23T15:30
tr-tarih fmt-money 1250.5 --style words
tr-tarih ago 2026-10-26 --now 2026-10-23
```

`date`, `number` and `money` support `--json` and `--explain`. JSON contains `input`, `ok`, `value`, `reason` and `assumptions`; `value` is a string or `null` to preserve exact decimals. Exit codes: **0** success/help, **1** unclear input, **2** invalid CLI usage. Errors go to stderr unless JSON was requested. For negative positional numbers, use `tr-tarih words -- -5`.

### Python API

```python
from datetime import datetime
from tr_tarih import format_money, parse_datetime, parse_money, parse_number

reference = datetime(2026, 10, 23, 10)
assert parse_datetime("yarın saat 15:30", reference).isoformat() == "2026-10-24T15:30:00"
assert parse_number("iki yüz elli bin") == 250000
assert format_money(parse_money("beş lira elli kuruş")) == "₺5,50"
```

The strict `parse_date`, `parse_datetime`, `parse_number` and `parse_money` functions raise `ParseError` (a `ValueError`) for unclear input. Their `*_detailed` counterparts return a frozen `ParseResult` with `.ok`, `.value`, `.reason`, `.assumptions` and `.unwrap()`.

Dates return `date` / `datetime`; numbers return `int` when whole and `Decimal` otherwise; money always returns `Decimal`. `format_date`, `format_datetime`, `format_relative`, `format_number`, `number_to_words` and `format_money` produce Turkish text. Date and money style types are available from `tr_tarih.dates` and `tr_tarih.money`.

## Examples

Run `python examples/basic.py` from the checkout; installation is optional. Its actual output is:

```text
2026-10-24T15:30:00
250000
₺5,50
bin iki yüz elli
```

Additional standalone examples:
- `python examples/dates_and_times.py`: Natural language dates, day periods, relative offsets and formatting.
- `python examples/money_and_numbers.py`: Spelled numbers, currency parsing, formatting styles and error handling.

## Configuration / options

No configuration file, locale setup or network access is required.

| Command / API | Options | Default |
| --- | --- | --- |
| `date` | `--now` ISO reference, `--json`, `--explain` | Local current time |
| `number`, `money` | `--json`, `--explain` | Plain output |
| `words` | Number with decimal dot or comma | Turkish words |
| `fmt-date` | `--style long/short/iso`, `--no-weekday` | Long, includes weekday |
| `fmt-money` | `--style symbol/suffix/words` | `₺1.250,50` |
| `ago` | `--now` ISO reference | Current time in the value's timezone |
| `format_date` | `weekday`, `style` (`long`/`short`/`iso`) | `True`, `long` |
| `format_datetime` | `weekday`, `seconds` | `True`, `False` |
| `format_number` | `decimals` (non-negative integer) | Preserve fractional digits |
| `format_money` | `style`, `cents` | `symbol`, `True` |

## How it works

Turkish-aware case folding handles dotted/dotless I, ASCII spellings and common suffixes. A deterministic grammar reads numbers, calendar phrases, weekdays and offsets. Unconsumed words or conflicting dates return a reason instead of a guess.

Calendar month/year offsets clamp the day: January 31 plus one month becomes February 28 or 29. A date without a clock defaults to midnight; a duration offset keeps the reference time. A bare weekday means today or the next occurrence; `gelecek cuma` is strictly future, while `bu cuma` belongs to the Monday-based current week. Missing years use the reference year. Two-digit years mean 2000–2099.

Bare hours below 12 require a day period (`akşam yedi`) or an explicit clock (`07:00`). Day periods without clocks use documented defaults: morning 08:00, noon 12:00, before noon 10:00, afternoon 15:00, late afternoon 16:00, evening 19:00, night 22:00, midnight 00:00. Detailed results expose assumptions for missing years, bare weekdays, day-period defaults and omitted currency.

## Limitations / privacy note

- This is a phrase parser, not a general Turkish language model or an extractor for arbitrary sentences. Spelled-out calendar days, holidays, recurrence rules and timezone names are not supported.
- Supply `now` / `--now` for reproducible results. A library reference's timezone is preserved; use ISO offsets with the CLI. `ago` requires both moments to be timezone-aware or both naive.
- Number separators follow Turkish conventions: `1.250` means 1250 and `1,250` means 1.25. English mixed grouping such as `1,250.50` is also accepted. Number words support magnitudes below `10**18`.
- Only Turkish lira is supported. Missing currency assumes TL. Formatting rounds half up to kuruş; parsing preserves input precision. Money formatting rejects floats and booleans; pass `Decimal`, integer or decimal-dot string.
- Relative display uses whole units, with 30-day months and 365-day years; differences under ten seconds read `şimdi`. Calendar parsing supports years 1–9999.
- All input stays in your process. There is no telemetry, network call, persistent history or external service. CLI output itself contains the supplied expression when using JSON; handle it accordingly.

## Development

From the source checkout:

```sh
python -m pip install -e ".[dev]"
python -m ruff check .
python -m mypy src
python -m pytest -q
python scripts/make-demo.py
python -m build
python -m twine check dist/*
```

Tests run offline, use fixed references and exercise CLI entry points in process. Pytest enforces **85% combined statement and branch coverage**. CI runs on Ubuntu and Windows with Python 3.10–3.14, and checks distribution metadata and installation separately. No runtime dependency is needed for the example or demo generator.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md), [the Code of Conduct](CODE_OF_CONDUCT.md), [SECURITY.md](SECURITY.md) and [CHANGELOG.md](CHANGELOG.md). Release automation is prepared for tags; publishing requires a maintainer-configured PyPI trusted publisher.

## License

[MIT](LICENSE), copyright 2026 Yusuf Berat Zengin.
