"""Date and relative time parsing and formatting examples.

Run from a source checkout:
    python examples/dates_and_times.py
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

# Allow the example to run before installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tr_tarih import (  # noqa: E402
    DateParser,
    format_date,
    format_datetime,
    format_relative,
    parse_datetime,
    parse_datetime_detailed,
)


def main() -> None:
    now = datetime(2026, 10, 23, 10, 0)
    print(f"Reference moment: {now.isoformat()}\n")

    # 1. Parsing relative expressions and calendar dates
    phrases = [
        "yarın saat 15:30",
        "3 gün önce",
        "gelecek cuma akşamı",
        "29 Ekim 2026",
        "önümüzdeki ayın ilk günü",
    ]
    print("--- 1. Natural language dates ---")
    for phrase in phrases:
        dt = parse_datetime(phrase, now=now)
        print(f"  {phrase:<28} -> {dt.isoformat()}")

    # 2. Detailed results and assumptions
    print("\n--- 2. Detailed results & assumptions ---")
    detailed = parse_datetime_detailed("cuma akşamı", now=now)
    print(f"  Input: {detailed.text}")
    print(f"  Value: {detailed.value.isoformat() if detailed.value else None}")
    for assumption in detailed.assumptions:
        print(f"  Note : {assumption}")

    # 3. Formatting dates and times
    print("\n--- 3. Formatting styles ---")
    sample_dt = datetime(2026, 10, 29, 14, 0)
    print(f"  Long date & time : {format_datetime(sample_dt)}")
    print(f"  Without weekday  : {format_datetime(sample_dt, weekday=False)}")
    print(f"  Long date only   : {format_date(sample_dt, style='long')}")
    print(f"  Short date       : {format_date(sample_dt, style='short')}")
    print(f"  ISO date         : {format_date(sample_dt, style='iso')}")

    # 4. Relative time ('ago' display)
    print("\n--- 4. Relative time display ---")
    targets = [
        ("Now", now),
        ("In 3 days", datetime(2026, 10, 26, 10, 0)),
        ("2 hours ago", datetime(2026, 10, 23, 8, 0)),
        ("2 weeks later", datetime(2026, 11, 6, 10, 0)),
        ("1 year ago", datetime(2025, 10, 23, 10, 0)),
    ]
    for label, target in targets:
        relative = format_relative(target, now=now)
        print(f"  {label:<15} ({target.date()}) -> {relative}")

    # 5. Timezones and ambiguous expressions
    print("\n--- 5. Timezones & ambiguous expressions ---")
    parser = DateParser(reference=now, tz="Europe/Istanbul")
    dt_tz = parser.parse_datetime("yarın saat 15:30")
    print(f"  Istanbul tz     : {dt_tz.isoformat()}")

    ambiguous = parse_datetime_detailed("hafta sonu", reference=now)
    print(f"  Ambiguous phrase: {ambiguous.text} -> reason: {ambiguous.reason}")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
