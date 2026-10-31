"""Calendar semantics, ambiguity, leap years and timezone preservation."""

from datetime import date, datetime, timedelta, timezone

import pytest

from tr_tarih import (
    DateParser,
    ParseError,
    format_date,
    format_datetime,
    format_relative,
    parse_date,
    parse_date_detailed,
    parse_datetime,
    parse_datetime_detailed,
)

NOW = datetime(2026, 10, 23, 10, 20, 30)  # Friday


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("bugün", "2026-10-23T00:00:00"),
        ("yarın saat 15:30", "2026-10-24T15:30:00"),
        ("dün", "2026-10-22T00:00:00"),
        ("öbür gün", "2026-10-25T00:00:00"),
        ("evvelsi gün", "2026-10-21T00:00:00"),
        ("şimdi", "2026-10-23T10:20:30"),
        ("23 Ekim 2026", "2026-10-23T00:00:00"),
        ("23.10.26", "2026-10-23T00:00:00"),
        ("2026-10-23", "2026-10-23T00:00:00"),
        ("23/10", "2026-10-23T00:00:00"),
        ("akşam yedi buçuk", "2026-10-23T19:30:00"),
        ("saat 15.30", "2026-10-23T15:30:00"),
        ("12:30:45", "2026-10-23T12:30:45"),
        ("sabah", "2026-10-23T08:00:00"),
        ("bu akşam", "2026-10-23T19:00:00"),
        ("öğleden sonra", "2026-10-23T15:00:00"),
        ("öğleden önce 9", "2026-10-23T09:00:00"),
        ("gece yarısı", "2026-10-23T00:00:00"),
        ("gece 12", "2026-10-23T00:00:00"),
        ("gece 8", "2026-10-23T20:00:00"),
        ("gece 2", "2026-10-23T02:00:00"),
        ("öğle 2", "2026-10-23T14:00:00"),
        ("öğle 11", "2026-10-23T11:00:00"),
        ("sabah 9", "2026-10-23T09:00:00"),
        ("akşam 19", "2026-10-23T19:00:00"),
        ("akşam 23 Ekim", "2026-10-23T19:00:00"),
        ("3 gün sonra", "2026-10-26T10:20:30"),
        ("iki hafta önce", "2026-10-09T10:20:30"),
        ("2 saat 30 dakika sonra", "2026-10-23T12:50:30"),
        ("yarım saat sonra", "2026-10-23T10:50:30"),
        ("3 gün sonra saat 14:00", "2026-10-26T14:00:00"),
        ("gelecek ay", "2026-11-23T00:00:00"),
        ("geçen yıl", "2025-10-23T00:00:00"),
        ("haftaya", "2026-10-30T00:00:00"),
        ("seneye", "2027-10-23T00:00:00"),
        ("gelecek hafta salı", "2026-10-27T00:00:00"),
        ("bu pazartesi", "2026-10-19T00:00:00"),
        ("gelecek cuma", "2026-10-30T00:00:00"),
        ("geçen cuma", "2026-10-16T00:00:00"),
        ("cuma", "2026-10-23T00:00:00"),
        ("salı günü", "2026-10-27T00:00:00"),
        ("23 Ekim 2026 Cuma", "2026-10-23T00:00:00"),
        ("ayın 15'i", "2026-10-15T00:00:00"),
        ("gelecek ayın son günü", "2026-11-30T00:00:00"),
        ("Şubat 2028 ilk günü", "2028-02-01T00:00:00"),
        ("Ekim 2026 ikinci pazartesi", "2026-10-12T00:00:00"),
        ("Ekim 2026 son cuma", "2026-10-30T00:00:00"),
        ("gelecek yıl 5 Ocak", "2027-01-05T00:00:00"),
        ("gelecek ay 5", "2026-11-05T00:00:00"),
        ("Ekim ayı 5 2026", "2026-10-05T00:00:00"),
    ],
)
def test_parse(text: str, expected: str) -> None:
    assert parse_datetime(text, NOW) == datetime.fromisoformat(expected)


@pytest.mark.parametrize(
    "text",
    [
        "",
        "merhaba",
        "saat",
        "saat beş",
        "25:00",
        "12:60",
        "12:00:60",
        "sabah akşam",
        "bugün yarın",
        "31 Şubat 2026",
        "23.13.2026",
        "2026-00-01",
        "Ekim",
        "ilk cuma",
        "ayın ilk",
        "Şubat 2026 beşinci pazartesi",
        "23 Ekim 2026 Salı",
        "bu ay gelecek ay",
        "1,5 ay sonra",
        "bugün 2 gün sonra",
        "2 saat sonra saat 14:00",
        "saat 1,2",
        "ve",
    ],
)
def test_unclear(text: str) -> None:
    result = parse_datetime_detailed(text, NOW)
    assert not result.ok and result.reason
    with pytest.raises(ParseError):
        parse_datetime(text, NOW)
    assert parse_date_detailed(text, NOW).reason == result.reason


def test_calendar_clamping() -> None:
    reference = datetime(2028, 1, 31, 10)
    assert parse_datetime("1 ay sonra", reference) == datetime(2028, 2, 29, 10)
    assert parse_date("gelecek ay", reference) == date(2028, 2, 29)
    assert parse_date("1 yıl sonra", datetime(2028, 2, 29)) == date(2029, 2, 28)


def test_timezone_and_default_reference() -> None:
    tz = timezone(timedelta(hours=3))
    result = parse_datetime("yarın saat 15:30", NOW.replace(tzinfo=tz))
    assert result == datetime(2026, 10, 24, 15, 30, tzinfo=tz)
    assert parse_datetime("2026-10-23").date() == date(2026, 10, 23)
    assert parse_date_detailed("23 Ekim", NOW).assumptions
    assert parse_datetime_detailed("sabah", NOW).assumptions


def test_format() -> None:
    assert format_date(NOW) == "23 Ekim 2026 Cuma"
    assert format_date(NOW, weekday=False) == "23 Ekim 2026"
    assert format_date(NOW, style="short") == "23.10.2026"
    assert format_date(NOW, style="iso") == "2026-10-23"
    assert format_datetime(NOW) == "23 Ekim 2026 Cuma 10:20"
    assert format_datetime(NOW, weekday=False, seconds=True) == "23 Ekim 2026 10:20:30"
    with pytest.raises(ValueError):
        format_date(NOW, style="wrong")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (0, "şimdi"),
        (9, "şimdi"),
        (-10, "10 saniye önce"),
        (60, "1 dakika sonra"),
        (-7200, "2 saat önce"),
        (86400 * 3, "3 gün sonra"),
        (86400 * 14, "2 hafta sonra"),
        (86400 * 60, "2 ay sonra"),
        (-86400 * 365, "1 yıl önce"),
    ],
)
def test_relative(seconds: int, expected: str) -> None:
    assert format_relative(NOW + timedelta(seconds=seconds), NOW) == expected


def test_relative_default() -> None:
    assert format_relative(datetime.now(timezone.utc)) == "şimdi"


def test_dates_edge_cases() -> None:
    assert parse_datetime("sabahta saat 8", now=NOW) == datetime(2026, 10, 23, 8, 0)
    assert parse_datetime("gece yarısı saat 0", now=NOW) == datetime(2026, 10, 23, 0, 0)

    unclear_clock = parse_datetime_detailed("saat yarın", now=NOW)
    assert not unclear_clock.ok
    assert unclear_clock.reason and "geçerli bir saat yok" in unclear_clock.reason

    conflicting = parse_datetime_detailed("23 Ekim 2026 2 gün önce", now=NOW)
    assert not conflicting.ok
    assert conflicting.reason and "birden fazla tarih ifadesi" in conflicting.reason


@pytest.mark.parametrize(
    ("expr", "expected_snippet"),
    [
        ("hafta sonu", "hafta sonu"),
        ("hafta içi", "hafta içi"),
        ("hafta başı", "hafta başı"),
        ("hafta başında", "hafta başı"),
        ("ay başı", "ay başı"),
        ("ayın başı", "ay başı"),
        ("ay ortası", "ay ortası"),
        ("ayın ortası", "ay ortası"),
        ("ay sonu", "ay sonu"),
        ("ayın sonu", "ay sonu"),
        ("akşamüstü", "akşamüstü"),
        ("akşama doğru", "akşama doğru"),
        ("sabaha karşı", "sabaha karşı"),
        ("öğleye doğru", "öğleye doğru"),
        ("geceye doğru", "geceye doğru"),
        ("birazdan", "birazdan"),
        ("az sonra", "az sonra"),
        ("yakında", "yakında"),
        ("yakın zamanda", "yakın zamanda"),
        ("birkaç gün sonra", "birkaç"),
        ("birkaç saat önce", "birkaç"),
        ("gelecek hafta", "gün belirtilmemiş"),
        ("bu hafta", "gün belirtilmemiş"),
        ("geçen hafta", "gün belirtilmemiş"),
        ("önümüzdeki hafta", "gün belirtilmemiş"),
        ("15", "yalnızca sayı verilmiş"),
    ],
)
def test_ambiguous_expressions_explained(expr: str, expected_snippet: str) -> None:
    result = parse_datetime_detailed(expr, now=NOW)
    assert not result.ok
    assert result.reason is not None and expected_snippet in result.reason
    with pytest.raises(ParseError) as exc_info:
        parse_datetime(expr, now=NOW)
    assert expected_snippet in str(exc_info.value)


@pytest.mark.parametrize(
    "expr",
    [
        "sabah 15:00",
        "sabah 19",
        "öğleden önce 14:00",
        "öğle 20:00",
        "öğle 8",
        "öğleden sonra 9",
        "öğleden sonra 21:00",
        "ikindi 9",
        "ikindi 20:00",
        "akşam 2",
        "akşam 15:00",
        "gece 14:00",
        "gece yarısı 3",
    ],
)
def test_contradictory_periods_and_hours(expr: str) -> None:
    result = parse_datetime_detailed(expr, now=NOW)
    assert not result.ok
    assert result.reason is not None and "çelişiyor" in result.reason
    with pytest.raises(ParseError, match="çelişiyor"):
        parse_datetime(expr, now=NOW)


def test_timezone_and_reference_api() -> None:
    # 1. string timezone names and offsets
    res_ist = parse_datetime("yarın saat 15:30", reference=NOW, tz="Europe/Istanbul")
    assert res_ist.tzinfo is not None
    assert res_ist.hour == 15 and res_ist.minute == 30 and res_ist.day == 24

    res_utc = parse_datetime("yarın saat 15:30", reference=NOW, tz="UTC")
    assert res_utc == datetime(2026, 10, 24, 15, 30, tzinfo=timezone.utc)

    res_offset = parse_datetime("yarın saat 15:30", reference=NOW, tz="+03:00")
    assert res_offset.tzinfo == timezone(timedelta(hours=3))

    res_neg_offset = parse_datetime("yarın saat 15:30", reference=NOW, tz="-05:00")
    assert res_neg_offset.tzinfo == timezone(timedelta(hours=-5))

    res_tsi = parse_datetime("yarın saat 15:30", reference=NOW, tz="TSİ")
    assert res_tsi.tzinfo == timezone(timedelta(hours=3), name="TSİ")

    res_trt = parse_datetime("yarın saat 15:30", reference=NOW, timezone="TRT")
    assert res_trt.tzinfo == timezone(timedelta(hours=3), name="TRT")

    # 2. date as reference
    res_date_ref = parse_datetime("yarın saat 12:00", reference=date(2026, 10, 23))
    assert res_date_ref == datetime(2026, 10, 24, 12, 0)

    # 3. parse_date with reference and timezone
    d = parse_date("yarın", reference=NOW, tz="+03:00")
    assert d == date(2026, 10, 24)

    res_d_detailed = parse_date_detailed("yarın", reference=NOW, tz="+03:00")
    assert res_d_detailed.ok and res_d_detailed.value == date(2026, 10, 24)

    # 4. Error on conflicting arguments
    with pytest.raises(ValueError, match="hem 'now' hem 'reference'"):
        parse_datetime("yarın", now=NOW, reference=datetime(2025, 1, 1))

    with pytest.raises(ValueError, match="hem 'tz' hem 'timezone'"):
        parse_datetime("yarın", tz="UTC", timezone="+03:00")

    # 5. Invalid timezone handling
    unclear_tz = parse_datetime_detailed("yarın", reference=NOW, tz="Gecersiz/Bolge")
    assert not unclear_tz.ok
    assert unclear_tz.reason and "geçersiz veya bilinmeyen saat dilimi" in unclear_tz.reason

    with pytest.raises(ParseError, match="geçersiz veya bilinmeyen saat dilimi"):
        parse_datetime("yarın", reference=NOW, tz="Gecersiz/Bolge")

    with pytest.raises(TypeError, match="referans zaman datetime veya date"):
        parse_datetime_detailed("yarın", reference=12345)  # type: ignore[arg-type]


def test_date_parser_class() -> None:
    tz = timezone(timedelta(hours=3), name="TSİ")
    parser = DateParser(reference=NOW, tz=tz)

    dt = parser.parse_datetime("yarın saat 15:30")
    assert dt == datetime(2026, 10, 24, 15, 30, tzinfo=tz)

    dt_res = parser.parse_datetime_detailed("yarın saat 15:30")
    assert dt_res.ok and dt_res.value == dt

    d = parser.parse_date("yarın")
    assert d == date(2026, 10, 24)

    d_res = parser.parse_date_detailed("yarın")
    assert d_res.ok and d_res.value == d


def test_text_embedded_timezones() -> None:
    # TSİ in text
    res1 = parse_datetime("23 Ekim 2026 saat 15:30 TSİ", now=NOW)
    assert res1.tzinfo == timezone(timedelta(hours=3), name="TSİ")
    assert res1.hour == 15 and res1.minute == 30

    # UTC in text
    res2 = parse_datetime("23 Ekim 2026 15:30 UTC", now=NOW)
    assert res2.tzinfo == timezone.utc
    assert res2.hour == 15

    # UTC+3 in text
    res3 = parse_datetime("23 Ekim 2026 15:30 UTC+3", now=NOW)
    assert res3.tzinfo == timezone(timedelta(hours=3))
    assert res3.hour == 15

    # Target timezone conversion
    res4 = parse_datetime("23 Ekim 2026 15:30 UTC", now=NOW, tz="+03:00")
    assert res4.tzinfo == timezone(timedelta(hours=3))
    assert res4.hour == 18 and res4.minute == 30

    # Offset in text
    res5 = parse_datetime("23 Ekim 2026 15:30 +03:00", now=NOW)
    assert res5.tzinfo == timezone(timedelta(hours=3))
    assert res5.hour == 15

    # ISO strings with timezone offsets
    iso1 = parse_datetime("2026-10-23T15:30:00+03:00")
    assert iso1 == datetime(2026, 10, 23, 15, 30, tzinfo=timezone(timedelta(hours=3)))

    iso2 = parse_datetime("2026-10-23T15:30:00Z")
    assert iso2 == datetime(2026, 10, 23, 15, 30, tzinfo=timezone.utc)

    iso3 = parse_datetime("2026-10-23 15:30:00+03:00")
    assert iso3 == datetime(2026, 10, 23, 15, 30, tzinfo=timezone(timedelta(hours=3)))


def test_strict_mode() -> None:
    # Missing year requires assumption
    res_assumed = parse_datetime_detailed("23 Ekim saat 10:00", now=NOW, strict=False)
    assert res_assumed.ok and len(res_assumed.assumptions) > 0

    res_strict = parse_datetime_detailed("23 Ekim saat 10:00", now=NOW, strict=True)
    assert not res_strict.ok
    assert res_strict.reason and "varsayım gerekiyor" in res_strict.reason

    # Fully specified datetime succeeds in strict mode
    res_full = parse_datetime_detailed("23 Ekim 2026 saat 10:00", now=NOW, strict=True)
    assert res_full.ok
    assert res_full.value == datetime(2026, 10, 23, 10, 0)
