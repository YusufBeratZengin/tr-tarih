"""Regression cases for crashes, decimal precision and contradictory input."""

from datetime import datetime
from decimal import Decimal, localcontext

import pytest

from tr_tarih import (
    format_money,
    format_number,
    number_to_words,
    parse_datetime_detailed,
    parse_money,
    parse_number,
)
from tr_tarih.cli import main


@pytest.mark.parametrize(
    ("text", "now"),
    [
        ("yarın", datetime(9999, 12, 31)),
        ("dün", datetime(1, 1, 1)),
        ("100000000000000000000000 yıl sonra", datetime(2026, 1, 1)),
        ("100000000000000000000000 gün sonra", datetime(2026, 1, 1)),
        ("31 Şubat 0000", datetime(2026, 1, 1)),
    ],
)
def test_out_of_range_is_a_failed_result(text: str, now: datetime) -> None:
    result = parse_datetime_detailed(text, now)
    assert not result.ok and result.reason


def test_exact_decimal_independent_of_context() -> None:
    digits = "123456789012345678901234567890.0123456789"
    with localcontext() as context:
        context.prec = 6
        assert parse_number(digits) == Decimal(digits)
        assert parse_number("-" + digits) == Decimal("-" + digits)
        assert parse_money(digits + " TL") == Decimal(digits)
        assert format_number(digits, 2) == "123.456.789.012.345.678.901.234.567.890,01"
        assert format_money(digits) == "₺123.456.789.012.345.678.901.234.567.890,01"
        assert number_to_words("123456.00001") == (
            "yüz yirmi üç bin dört yüz elli altı virgül sıfır sıfır sıfır sıfır bir"
        )


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_nonfinite_number_format(value: str) -> None:
    with pytest.raises(ValueError):
        format_number(value)


@pytest.mark.parametrize("decimals", [-1, True])
def test_invalid_precision(decimals: int) -> None:
    with pytest.raises(ValueError):
        format_number(1, decimals)


def test_bool_number_format() -> None:
    with pytest.raises(TypeError):
        format_number(True)


def test_cli_mixed_timezone(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["ago", "2026-10-23T10:00+03:00", "--now", "2026-10-23T10:00"]) == 2
    assert "error:" in capsys.readouterr().err
