"""Lira parsing and deterministic half-up rounding."""

from decimal import Decimal

import pytest

from tr_tarih import ParseError, format_money, parse_money, parse_money_detailed


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("₺1.250,50", "1250.50"),
        ("1.250,50 TL", "1250.50"),
        ("TRY 250", "250"),
        ("bin iki yüz lira", "1200"),
        ("beş lira elli kuruş", "5.50"),
        ("elli kuruş", "0.50"),
        ("-₺12,5", "-12.5"),
        ("₺-12,5", "-12.5"),
        ("eksi iki lira", "-2"),
        ("0", "0"),
        ("5 liraya", "5"),
    ],
)
def test_parse(text: str, expected: str) -> None:
    value = parse_money(text)
    assert isinstance(value, Decimal)
    assert value == Decimal(expected)


@pytest.mark.parametrize(
    "text",
    [
        "",
        "eksi",
        "TL",
        "lira",
        "bir dolar",
        "$2",
        "€3",
        "£4",
        "USD 2",
        "1 lira iki",
        "₺2 TL",
        "hello",
    ],
)
def test_invalid(text: str) -> None:
    result = parse_money_detailed(text)
    assert not result.ok and result.reason
    with pytest.raises(ParseError):
        parse_money(text)


@pytest.mark.parametrize("text", ["¥5", "₽5", "-.5 TL", "TL .5", "5! TL", "1;5 TL"])
def test_reject_unrecognized_characters(text: str) -> None:
    assert not parse_money_detailed(text).ok
    with pytest.raises(ParseError):
        parse_money(text)


@pytest.mark.parametrize("marker", ["TL", "TRY", "₺", "lira"])
@pytest.mark.parametrize("sign", ["-", "−", "–", "eksi"])
def test_negative_after_currency_prefix(marker: str, sign: str) -> None:
    assert parse_money(f"{marker} {sign}5") == Decimal("-5")


@pytest.mark.parametrize("text", ["--5 TL", "-TL -5", "TL 5-", "5 - TL", "TL eksi -5"])
def test_reject_misplaced_or_repeated_signs(text: str) -> None:
    assert not parse_money_detailed(text).ok
    with pytest.raises(ParseError):
        parse_money(text)


def test_assumptions() -> None:
    assert parse_money_detailed("12").assumptions
    assert not parse_money_detailed("12 TL").assumptions


def test_format() -> None:
    assert format_money("1250.505") == "₺1.250,51"
    assert format_money(-5, style="suffix") == "-5,00 TL"
    assert format_money(5, cents=False) == "₺5"
    assert format_money("5.5", cents=False) == "₺5,50"
    assert format_money("-5.50", style="words") == "eksi beş lira elli kuruş"
    assert format_money(0, style="words") == "sıfır lira"
    for value in (Decimal("-5.50"), Decimal("0"), Decimal("1250.01")):
        for style in ("symbol", "suffix", "words"):
            assert parse_money(format_money(value, style=style)) == value  # type: ignore[arg-type]


@pytest.mark.parametrize("value", ["invalid", "Infinity", "NaN"])
def test_bad_amount(value: str) -> None:
    with pytest.raises(ValueError):
        format_money(value)


def test_bad_format_arguments() -> None:
    with pytest.raises(TypeError):
        format_money(True)
    with pytest.raises(TypeError):
        format_money(1.5)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        format_money(1, style="other")  # type: ignore[arg-type]
