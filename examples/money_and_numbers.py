"""Turkish number and lira amount parsing and formatting examples.

Run from a source checkout:
    python examples/money_and_numbers.py
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

# Allow the example to run before installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tr_tarih import (  # noqa: E402
    ParseError,
    format_money,
    format_number,
    number_to_words,
    parse_money,
    parse_money_detailed,
    parse_number,
)


def main() -> None:
    # 1. Parsing numbers from words and digits
    print("--- 1. Number parsing ---")
    number_inputs = [
        "yirmi beş",
        "iki yüz elli bin",
        "bir virgül beş milyon",
        "1.250.000",
        "eksi kırk iki",
    ]
    for text in number_inputs:
        val = parse_number(text)
        print(f"  {text:<25} -> {val} ({type(val).__name__})")

    # 2. Number to words and formatting
    print("\n--- 2. Numbers to words & formatting ---")
    print(f"  1250 in words             -> {number_to_words(1250)}")
    print(f"  -15.5 in words            -> {number_to_words(Decimal('-15.5'))}")
    print(f"  format_number(1250000.5)  -> {format_number(Decimal('1250000.5'), decimals=2)}")
    print(f"  format_number(42)         -> {format_number(42)}")

    # 3. Lira parsing
    print("\n--- 3. Lira parsing ---")
    money_inputs = [
        "beş lira elli kuruş",
        "1.250,50 TL",
        "₺ 350",
        "on iki bin beş yüz lira",
        "TL -45,50",
    ]
    for text in money_inputs:
        val = parse_money(text)
        print(f"  {text:<25} -> {val} TL")

    # 4. Lira formatting styles
    print("\n--- 4. Lira formatting styles ---")
    amount = Decimal("1250.50")
    print(f"  Symbol style : {format_money(amount, style='symbol')}")
    print(f"  Suffix style : {format_money(amount, style='suffix')}")
    print(f"  Words style  : {format_money(amount, style='words')}")
    print(f"  Without cents: {format_money(Decimal('1250'), cents=False)}")

    # 5. Error handling and detailed results
    print("\n--- 5. Error handling & detailed feedback ---")
    unclear = "elli bin dolar"
    try:
        parse_money(unclear)
    except ParseError as error:
        print(f"  Caught ParseError: {error}")

    detailed = parse_money_detailed("1200")
    print(f"  Implicit currency input: {detailed.text}")
    print(f"  Parsed value           : {detailed.value}")
    for note in detailed.assumptions:
        print(f"  Assumption             : {note}")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
