"""Number grammar, exact decimal values and formatting round trips."""

from decimal import Decimal

import pytest

from tr_tarih import (
    ParseError,
    format_number,
    number_to_words,
    parse_number,
    parse_number_detailed,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("sıfır", 0),
        ("İKİ YÜZ ELLİ BİN", 250000),
        ("bin", 1000),
        ("yüz", 100),
        ("on dokuz", 19),
        ("2 milyon 500 bin", 2500000),
        ("bir buçuk milyon", 1500000),
        ("yarım", Decimal("0.5")),
        ("eksi üç", -3),
        ("−1.250,50", Decimal("-1250.50")),
        ("1,234.50", Decimal("1234.50")),
        ("1,234,567", 1234567),
        ("1.250", 1250),
        ("0.125", Decimal("0.125")),
        ("12.5", Decimal("12.5")),
        ("1,5", Decimal("1.5")),
        ("bir virgül sıfır beş", Decimal("1.05")),
        ("bir virgül 25", Decimal("1.25")),
        ("bir virgül beş milyon", 1500000),
        ("üçe", 3),
        ("kırka", 40),
        ("1.234.567,89", Decimal("1234567.89")),
    ],
)
def test_parse(text: str, expected: int | Decimal) -> None:
    assert parse_number(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "",
        "eksi",
        "merhaba",
        "bir iki",
        "yirmi on",
        "sıfır yüz",
        "bir virgül",
        "milyon milyon",
        "bin milyon",
        "1.23.456",
        "1,23,4",
        "1.2,3",
        "bir sıfır",
        "bir virgül beş altı yedi kelime",
        "bir milyon iki yüz üç TL",
    ],
)
def test_invalid(text: str) -> None:
    result = parse_number_detailed(text)
    assert not result.ok and result.reason and result.value is None
    with pytest.raises(ParseError):
        parse_number(text)


@pytest.mark.parametrize("text", ["-.5", ".5", ",5", "5.", "1;5", "5!", "¥5", "5−"])
def test_reject_unrecognized_characters(text: str) -> None:
    assert not parse_number_detailed(text).ok
    with pytest.raises(ParseError):
        parse_number(text)


@pytest.mark.parametrize(
    "value",
    [
        0,
        1,
        11,
        20,
        99,
        100,
        101,
        900,
        1000,
        1100,
        12009,
        1000000,
        123456789,
        10**15,
        -(10**18 - 1),
        Decimal("-12.005"),
        Decimal("0.5"),
    ],
)
def test_word_roundtrip(value: int | Decimal) -> None:
    assert parse_number(number_to_words(value)) == value


def test_word_spelling() -> None:
    assert number_to_words(1250) == "bin iki yüz elli"
    assert number_to_words(Decimal("-1.50")) == "eksi bir virgül beş"


@pytest.mark.parametrize("value", ["no", "NaN", "Infinity", "-Infinity", 10**18])
def test_words_reject_invalid(value: str | int) -> None:
    with pytest.raises(ValueError):
        number_to_words(value)


def test_words_reject_bool() -> None:
    with pytest.raises(TypeError):
        number_to_words(True)


def test_formatting() -> None:
    assert format_number(Decimal("-1250000.50")) == "-1.250.000,50"
    assert format_number("1.005", 2) == "1,01"
    assert format_number(12, 2) == "12,00"
    assert format_number(0) == "0"
    with pytest.raises(TypeError):
        format_number(1.5)  # type: ignore[arg-type]


def test_number_parsing_edge_cases() -> None:
    consecutive_scales = parse_number_detailed("milyar milyon")
    assert not consecutive_scales.ok
    assert consecutive_scales.reason and "milyon" in consecutive_scales.reason

    zero_after_unit = parse_number_detailed("on sıfır")
    assert not zero_after_unit.ok
    assert zero_after_unit.reason and "sifir" in zero_after_unit.reason

    with pytest.raises(ValueError, match="decimals must be a non-negative integer"):
        format_number(10, decimals=-1)
