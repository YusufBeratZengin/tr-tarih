"""Run from a source checkout: python examples/basic.py."""

import sys
from datetime import datetime
from pathlib import Path

# Allow the example to run before installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tr_tarih import format_money, number_to_words, parse_datetime, parse_money, parse_number  # noqa: E402


def main() -> None:
    reference = datetime(2026, 10, 23, 10)
    print(parse_datetime("yarın saat 15:30", now=reference).isoformat())
    print(parse_number("iki yüz elli bin"))
    print(format_money(parse_money("beş lira elli kuruş")))
    print(number_to_words(1250))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
