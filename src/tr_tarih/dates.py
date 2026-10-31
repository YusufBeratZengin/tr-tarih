"""Turkish dates and times: parse natural language, format dates and relative times."""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone, tzinfo
from decimal import Decimal
from typing import Literal

from ._text import fold, matches_stem, tokenize
from .numbers import scan_number
from .result import ParseResult, failure

__all__ = [
    "DateParser",
    "MONTH_NAMES",
    "WEEKDAY_NAMES",
    "DateStyle",
    "format_date",
    "format_datetime",
    "format_relative",
    "parse_date",
    "parse_date_detailed",
    "parse_datetime",
    "parse_datetime_detailed",
]

DateStyle = Literal["long", "short", "iso"]

MONTH_NAMES = (
    "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
)  # fmt: skip
WEEKDAY_NAMES = ("Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar")

_MONTH_STEMS: tuple[tuple[str, ...], ...] = (
    ("ocak", "ocag"), ("subat",), ("mart",), ("nisan",), ("mayis",), ("haziran",),
    ("temmuz",), ("agustos",), ("eylul",), ("ekim",), ("kasim",), ("aralik", "aralig"),
)  # fmt: skip
_WEEKDAY_STEMS = ("pazartesi", "sali", "carsamba", "persembe", "cuma", "cumartesi", "pazar")

_PERIOD_STEMS = {
    "sabah": "sabah", "sabahleyin": "sabah", "ogle": "ogle", "oglen": "ogle",
    "ogleyin": "ogle", "ikindi": "ikindi", "aksam": "aksam", "aksamleyin": "aksam",
    "gece": "gece", "geceleyin": "gece",
}  # fmt: skip
_PERIOD_DEFAULT_HOUR = {
    "sabah": 8, "ogle": 12, "ogleden_sonra": 15, "ogleden_once": 10,
    "ikindi": 16, "aksam": 19, "gece": 22, "gece_yarisi": 0,
}  # fmt: skip

_OFFSET_RE = re.compile(r"^([+-])(\d{1,2})(?::?(\d{2}))?$")

_STATIC_TIMEZONES: dict[str, tzinfo] = {
    "utc": timezone.utc,
    "z": timezone.utc,
    "gmt": timezone.utc,
    "tsi": timezone(timedelta(hours=3), name="TSİ"),
    "trt": timezone(timedelta(hours=3), name="TRT"),
    "europe/istanbul": timezone(timedelta(hours=3), name="Europe/Istanbul"),
    "istanbul": timezone(timedelta(hours=3), name="Europe/Istanbul"),
}


def _resolve_timezone(tz: tzinfo | str) -> tzinfo:
    """Resolve a timezone specification (tzinfo or name/offset string) into a tzinfo object."""
    if isinstance(tz, tzinfo):
        return tz
    if not isinstance(tz, str):
        raise TypeError(f"saat dilimi tzinfo veya str olmalıdır: {type(tz).__name__}")
    cleaned = tz.strip()
    folded = fold(cleaned)
    if folded in _STATIC_TIMEZONES:
        return _STATIC_TIMEZONES[folded]
    if match := _OFFSET_RE.fullmatch(cleaned):
        sign = 1 if match.group(1) == "+" else -1
        hours = int(match.group(2))
        minutes = int(match.group(3) or 0)
        if not (0 <= hours <= 23 and 0 <= minutes <= 59):
            raise ValueError(f"geçersiz saat dilimi ofseti: {tz!r}")
        return timezone(sign * timedelta(hours=hours, minutes=minutes))
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(cleaned)
    except Exception:
        raise ValueError(f"geçersiz veya bilinmeyen saat dilimi: {tz!r}") from None


_UNITS = {
    "saniye": "s", "sn": "s", "dakika": "m", "dk": "m", "dak": "m", "saat": "h",
    "gun": "d", "hafta": "w", "ay": "M", "yil": "y", "sene": "y",
}  # fmt: skip
_AY = frozenset({"ay", "ayi", "ayin", "ayinda", "ayinin", "ayina", "ayindan", "ayda", "aya"})
_HAFTA = frozenset({"hafta", "haftanin", "haftasi", "haftada", "haftaya"})
_YIL = frozenset(
    {"yil", "yili", "yilin", "yilinda", "yilinin", "sene", "senenin", "senede", "seneye"}
)
_GUN = frozenset({"gun", "gunu", "gunun", "gunde"})
_REL = {"gecen": -1, "bu": 0, "gelecek": 1, "onumuzdeki": 1}
_ORDINALS = {
    "ilk": 1, "birinci": 1, "ikinci": 2, "ucuncu": 3, "dorduncu": 4, "besinci": 5,
    "son": -1, "sonuncu": -1,
}  # fmt: skip
_FILLERS = frozenset(
    {"gunu", "gunun", "gunde", "tarih", "tarihi", "tarihinde", "ve", "tam", "icin"}
)

_COLON_TIME = re.compile(r"(\d{1,2}):(\d{2})(?::(\d{2}))?")
_DOT_TIME = re.compile(r"(\d{1,2})\.(\d{2})")
_ISO = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")
_DMY = re.compile(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4}|\d{2})")
_DM = re.compile(r"(\d{1,2})[./](\d{1,2})")


class _Fail(Exception):
    """Internal: abort parsing with a user-facing reason."""


def _check_ambiguous(tokens: list[str]) -> None:
    if not tokens:
        return
    if len(tokens) == 1 and tokens[0].isdigit():
        raise _Fail(
            "yalnızca sayı verilmiş; gün için 'ayın 15'i', "
            "saat için 'saat 15:00' gibi bağlam ekleyin"
        )

    for i, t in enumerate(tokens):
        if t == "hafta":
            nxt = tokens[i + 1] if i + 1 < len(tokens) else ""
            if nxt == "sonu":
                raise _Fail(
                    "ifade belirsiz: 'hafta sonu' cumartesi ve pazar günlerini kapsar; "
                    "belirli bir gün belirtin (ör. 'cumartesi')"
                )
            if nxt in ("ici", "icinde"):
                raise _Fail(
                    "ifade belirsiz: 'hafta içi' pazartesi-cuma günlerini kapsar; "
                    "belirli bir gün belirtin"
                )
            if nxt in ("basi", "basinda"):
                raise _Fail(
                    "ifade belirsiz: 'hafta başı' yerine belirli bir gün adı belirtin "
                    "(ör. 'pazartesi')"
                )

    for i, t in enumerate(tokens):
        if t in ("ay", "ayin"):
            nxt = tokens[i + 1] if i + 1 < len(tokens) else ""
            if nxt in ("basi", "basinda"):
                raise _Fail(
                    "ifade belirsiz: 'ay başı' kesin bir gün numarası belirtmez; "
                    "gün numarası ekleyin (ör. 'ayın 1'i')"
                )
            if nxt in ("ortasi", "ortasinda"):
                raise _Fail(
                    "ifade belirsiz: 'ay ortası' kesin bir gün numarası belirtmez; "
                    "gün numarası ekleyin (ör. 'ayın 15'i')"
                )
            if nxt in ("sonu", "sonunda"):
                after_nxt = tokens[i + 2] if i + 2 < len(tokens) else ""
                if after_nxt not in _GUN:
                    raise _Fail(
                        "ifade belirsiz: 'ay sonu' için gün belirtilmemiş; "
                        "'ayın son günü' ya da gün numarası kullanın"
                    )

    if "aksamustu" in tokens:
        raise _Fail(
            "ifade belirsiz: 'akşamüstü' kesin bir saat belirtmez; "
            "lütfen kesin bir saat belirtin (ör. 'akşam 18:00')"
        )
    for i, t in enumerate(tokens[:-1]):
        nxt = tokens[i + 1]
        if t == "aksama" and nxt == "dogru":
            raise _Fail(
                "ifade belirsiz: 'akşama doğru' kesin bir saat belirtmez; "
                "lütfen kesin bir saat belirtin (ör. 'akşam 18:00')"
            )
        if t == "sabaha" and nxt == "karsi":
            raise _Fail(
                "ifade belirsiz: 'sabaha karşı' kesin bir saat belirtmez; "
                "lütfen kesin bir saat belirtin (ör. 'sabah 05:00')"
            )
        if t == "ogleye" and nxt == "dogru":
            raise _Fail(
                "ifade belirsiz: 'öğleye doğru' kesin bir saat belirtmez; "
                "lütfen kesin bir saat belirtin (ör. 'saat 11:30')"
            )
        if t == "geceye" and nxt == "dogru":
            raise _Fail(
                "ifade belirsiz: 'geceye doğru' kesin bir saat belirtmez; "
                "lütfen kesin bir saat belirtin (ör. 'akşam 21:00')"
            )

    if "birazdan" in tokens:
        raise _Fail(
            "ifade belirsiz: 'birazdan' kesin bir süre belirtmez; "
            "lütfen dakika veya saat belirtin (ör. '15 dakika sonra')"
        )
    if "yakinda" in tokens:
        raise _Fail(
            "ifade belirsiz: 'yakında' kesin bir tarih veya süre belirtmez; "
            "lütfen kesin bir tarih belirtin"
        )
    for i, t in enumerate(tokens[:-1]):
        nxt = tokens[i + 1]
        if t == "az" and nxt in ("sonra", "once"):
            raise _Fail(
                "ifade belirsiz: 'az sonra' kesin bir süre belirtmez; "
                "lütfen dakika veya saat belirtin (ör. '15 dakika sonra')"
            )
        if t == "yakin" and nxt in ("zamanda", "zaman"):
            raise _Fail(
                "ifade belirsiz: 'yakın zamanda' kesin bir tarih veya süre belirtmez; "
                "lütfen kesin bir tarih belirtin"
            )
        if t == "birkac":
            raise _Fail(
                "ifade belirsiz: 'birkaç' kesin bir miktar değildir; "
                "kesin sayı belirtin (ör. '3 gün sonra')"
            )

    for i, t in enumerate(tokens[:-1]):
        nxt = tokens[i + 1]
        if t in ("gelecek", "onumuzdeki", "bu", "gecen") and nxt in _HAFTA:
            has_weekday = any(_match_weekday(tok) is not None for tok in tokens)
            has_day = any(tok.isdigit() and int(tok) <= 31 for tok in tokens)
            if not has_weekday and not has_day:
                raise _Fail(
                    f"ifade belirsiz: '{t} hafta' için gün belirtilmemiş; "
                    f"gün adı ekleyin (ör. '{t} hafta salı')"
                )


def add_months(day: date, months: int) -> date:
    """Shift by calendar months, clamping the day (31 Jan + 1 month = 28/29 Feb)."""
    index = day.year * 12 + day.month - 1 + months
    year, month = divmod(index, 12)
    month += 1
    return day.replace(
        year=year, month=month, day=min(day.day, calendar.monthrange(year, month)[1])
    )


def _match_month(token: str) -> int | None:
    for index, stems in enumerate(_MONTH_STEMS):
        if matches_stem(token, stems):
            return index + 1
    return None


def _match_weekday(token: str) -> int | None:
    for index, stem in enumerate(_WEEKDAY_STEMS):
        if matches_stem(token, (stem,)):
            return index
    return None


def _match_period(token: str) -> str | None:
    if token in _PERIOD_STEMS:
        return _PERIOD_STEMS[token]
    for stem, name in _PERIOD_STEMS.items():
        if matches_stem(token, (stem,)):
            return name
    return None


@dataclass
class _Parser:
    text: str
    now: datetime
    strict: bool = False
    tokens: list[str] = field(init=False)
    used: list[bool] = field(init=False)
    assumptions: list[str] = field(default_factory=list)
    clock: tuple[int, int, int] | None = None
    base: date | None = None
    source: str = ""
    moment: datetime | None = None
    keep_now_time: bool = False
    clock_offset: bool = False
    parsed_tz: tzinfo | None = None

    def __post_init__(self) -> None:
        self.tokens = tokenize(self.text)
        self.used = [False] * len(self.tokens)

    # -- helpers -----------------------------------------------------------------
    def find_timezone(self) -> None:
        """Detect timezone tokens or offset annotations (TSİ, UTC, GMT, Z, +03:00)."""
        # 1. Check for UTC/GMT with optional offset (e.g. "UTC+3", "GMT-5", "UTC +03:00")
        utc_match = re.search(
            r"\b(?:UTC|GMT)\s*([+-]\s*\d{1,2}(?::?\d{2})?)?\b",
            self.text,
            re.IGNORECASE,
        )
        if utc_match:
            offset_part = utc_match.group(1)
            if offset_part:
                self.parsed_tz = _resolve_timezone(offset_part.replace(" ", ""))
            else:
                self.parsed_tz = timezone.utc
            for i, token in enumerate(self.tokens):
                if not self.used[i] and token in ("utc", "gmt"):
                    self.mark(i)
                    nxt = self.free(i + 1)
                    if nxt and (nxt.isdigit() or _OFFSET_RE.fullmatch(nxt)):
                        self.mark(i + 1)
                    return
            return

        # 2. Check for TSİ / TRT / Europe/Istanbul
        for i, token in enumerate(self.tokens):
            if not self.used[i] and token in ("tsi", "trt"):
                self.parsed_tz = _resolve_timezone(token)
                self.mark(i)
                return

        # 3. Check for offset following time (e.g. "15:30 +03:00")
        offset_match = re.search(
            r"(?:(?:\b\d{1,2}:\d{2}(?::\d{2})?)\s*)([+-]\d{2}(?::?\d{2})?)\b",
            self.text,
        )
        if offset_match:
            offset_str = offset_match.group(1)
            try:
                self.parsed_tz = _resolve_timezone(offset_str)
                num_part = offset_str.lstrip("+-")
                for i, token in enumerate(self.tokens):
                    if not self.used[i] and token == num_part:
                        self.mark(i)
                        break
                return
            except ValueError:
                pass

        # 4. Check for 'Z' timezone marker
        for i, token in enumerate(self.tokens):
            if not self.used[i] and token == "z":
                self.parsed_tz = timezone.utc
                self.mark(i)
                return
    def masked(self) -> list[str]:
        return ["" if u else t for t, u in zip(self.tokens, self.used, strict=True)]

    def mark(self, *indexes: int) -> None:
        for index in indexes:
            self.used[index] = True

    def free(self, index: int) -> str:
        """Token at ``index`` if it exists and is unused, else an empty string."""
        if 0 <= index < len(self.tokens) and not self.used[index]:
            return self.tokens[index]
        return ""

    def set_base(self, value: date, source: str) -> None:
        if self.moment is not None or (self.base is not None and self.base != value):
            raise _Fail("birden fazla tarih ifadesi var; hangisinin kastedildiği belirsiz")
        self.base, self.source = value, source

    def build(self, year: int, month: int, day: int) -> date:
        try:
            return date(year, month, day)
        except ValueError:
            raise _Fail(f"geçersiz tarih: {day} {MONTH_NAMES[month - 1]} {year}") from None

    # -- time of day -------------------------------------------------------------
    def find_periods(self) -> tuple[str, int] | None:
        """Mark a period word ("akşam", "öğleden sonra") and return (name, last index)."""
        found: tuple[str, int] | None = None
        for i, token in enumerate(self.tokens):
            if self.used[i]:
                continue
            name: str | None = None
            last = i
            if token == "ogleden" and self.free(i + 1) in ("sonra", "once"):
                name, last = f"ogleden_{self.tokens[i + 1]}", i + 1
            elif token == "gece" and self.free(i + 1) == "yarisi":
                name, last = "gece_yarisi", i + 1
            else:
                name = _match_period(token)
            if name is None:
                continue
            if found is not None:
                raise _Fail("birden fazla gün bölümü var (sabah, akşam, ...)")
            self.mark(*range(i, last + 1))
            if self.free(i - 1) == "bu":
                self.mark(i - 1)
                self.set_base(self.now.date(), "bu")
            found = (name, last)
        return found

    def read_clock_token(self, index: int, after_saat: bool) -> tuple[int, int, int, int] | None:
        """Read "15:30", "15.30" (after "saat") or a number at ``index``.

        Returns (hour, minute, second, tokens used) or None.
        """
        token = self.free(index)
        if not token:
            return None
        match = _COLON_TIME.fullmatch(token)
        if match is None and after_saat:
            match = _DOT_TIME.fullmatch(token)
        if match is not None:
            seconds = int(match.group(3)) if match.lastindex and match.lastindex >= 3 else 0
            return int(match.group(1)), int(match.group(2)), seconds, 1
        if token.isdigit() and _match_month(self.free(index + 1)) is not None:
            return None  # "akşam 23 Ekim": the number is a day, not an hour
        scanned = scan_number(self.masked(), index)
        if scanned is None:
            return None
        value, end = scanned
        if value != int(value) and value - int(value) != Decimal("0.5"):
            return None
        return int(value), 30 if value != int(value) else 0, 0, end - index

    def resolve_clock(self, period: tuple[str, int] | None) -> None:
        saat = next(
            (i for i, t in enumerate(self.tokens) if t == "saat" and not self.used[i]), None
        )
        hour = minute = second = 0
        explicit_colon = False
        read: tuple[int, int, int, int] | None = None
        start = -1
        if saat is not None:
            start = saat + 1
            read = self.read_clock_token(start, after_saat=True)
            if read is None:
                raise _Fail("'saat' sözcüğünden sonra geçerli bir saat yok")
            self.mark(saat)
        elif period is not None:
            start = period[1] + 1
            read = self.read_clock_token(start, after_saat=False)
        else:
            for i, token in enumerate(self.tokens):
                if not self.used[i] and _COLON_TIME.fullmatch(token):
                    start, read = i, self.read_clock_token(i, after_saat=False)
                    break
        if read is None and period is None:
            return
        name = period[0] if period else None
        if read is None:
            if name is None:  # pragma: no cover - guarded above
                return
            hour = _PERIOD_DEFAULT_HOUR[name]
            if name != "gece_yarisi":
                self.assumptions.append(
                    f"saat verilmedi; '{_pretty_period(name)}' için {hour:02d}:00 varsayıldı"
                )
        else:
            hour, minute, second, count = read
            explicit_colon = ":" in self.tokens[start] or (
                saat is not None and "." in self.tokens[start]
            )
            self.mark(*range(start, start + count))
            hour = _apply_period(hour, name, explicit_colon, self.text)
        if not (0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
            raise _Fail(f"geçersiz saat: {hour:02d}:{minute:02d}")
        self.clock = (hour, minute, second)

    # -- dates -------------------------------------------------------------------
    def numeric_dates(self) -> None:
        for i, token in enumerate(self.tokens):
            if self.used[i]:
                continue
            if m := _ISO.fullmatch(token):
                year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
            elif m := _DMY.fullmatch(token):
                day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
                if len(m.group(3)) == 2:
                    year += 2000
            elif (m := _DM.fullmatch(token)) and int(m.group(2)) <= 12:
                day, month = int(m.group(1)), int(m.group(2))
                year = self.now.year
                self.assumptions.append(f"yıl belirtilmedi; {year} kullanıldı")
            else:
                continue
            if not 1 <= month <= 12:
                raise _Fail(f"geçersiz ay: {month}")
            self.set_base(self.build(year, month, day), "numeric")
            self.mark(i)

    def day_words(self) -> None:
        for i, token in enumerate(self.tokens):
            if self.used[i]:
                continue
            shift: int | None = None
            last = i
            if token == "bugun":
                shift = 0
            elif token == "yarin":
                shift = 1
            elif token == "dun":
                shift = -1
            elif token == "obur" and self.free(i + 1) == "gun":
                shift, last = 2, i + 1
            elif token in ("evvelsi", "evvelki", "onceki") and self.free(i + 1) == "gun":
                shift, last = -2, i + 1
            elif token == "simdi":
                shift = 0
                self.keep_now_time = True
            if shift is None:
                continue
            self.set_base(self.now.date() + timedelta(days=shift), "word")
            self.mark(*range(i, last + 1))

    def offsets(self) -> None:
        """ "3 gün sonra", "iki hafta önce", "2 saat 30 dakika sonra"."""
        n = len(self.tokens)
        for k in range(n):
            if self.used[k]:
                continue
            masked = self.masked()
            j = k
            parts: list[tuple[Decimal, str]] = []
            while True:
                scanned = scan_number(masked, j)
                if scanned is None or scanned[1] >= n or masked[scanned[1]] not in _UNITS:
                    break
                parts.append((scanned[0], _UNITS[masked[scanned[1]]]))
                j = scanned[1] + 1
            if not parts or j >= n or masked[j] not in ("sonra", "once", "evvel"):
                continue
            sign = 1 if masked[j] == "sonra" else -1
            self.mark(*range(k, j + 1))
            self.apply_offset(parts, sign)
            return

    def apply_offset(self, parts: list[tuple[Decimal, str]], sign: int) -> None:
        if self.source:
            raise _Fail("birden fazla tarih ifadesi var; hangisinin kastedildiği belirsiz")
        months = 0
        delta = timedelta()
        clock_unit = False
        for value, unit in parts:
            if unit in "My":
                if value != int(value):
                    raise _Fail("ay ve yıl tam sayı olmalı")
                months += int(value) * (12 if unit == "y" else 1)
                continue
            seconds = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}[unit]
            delta += timedelta(seconds=float(value * seconds))
            clock_unit = clock_unit or unit in "smh"
        self.clock_offset = clock_unit
        shifted = add_months(self.now.date(), sign * months)
        moment = datetime.combine(shifted, self.now.timetz()) + sign * delta
        self.moment, self.source = moment, "offset"

    def calendar_phrases(self) -> None:
        """Month/year names, relative scopes ("geçen ay"), ordinals and weekdays."""
        scopes = self.read_scopes()
        month_at = next(
            (
                (i, m)
                for i, t in enumerate(self.tokens)
                if not self.used[i] and (m := _match_month(t))
            ),
            None,
        )
        month_idx: int | None = None
        month_value: int | None = None
        if month_at is not None:
            month_idx, month_value = month_at
            self.mark(month_idx)
            if self.free(month_idx + 1) in _AY:
                self.mark(month_idx + 1)
        year = self.read_year(month_idx)
        scope_month = scopes.get("ay")

        ordinal = next(
            (
                (i, _ORDINALS[t])
                for i, t in enumerate(self.tokens)
                if not self.used[i] and t in _ORDINALS
            ),
            None,
        )
        weekday_at = next(
            (
                (i, w)
                for i, t in enumerate(self.tokens)
                if not self.used[i] and (w := _match_weekday(t)) is not None
            ),
            None,
        )

        if ordinal is not None:
            self.ordinal_phrase(ordinal, weekday_at, month_value, year, scope_month, scopes)
            return
        consumed: set[str] = set()
        if month_value is not None or scope_month is not None:
            day_index = self.find_day_number(month_idx)
            if day_index is not None:
                self.day_in_month(day_index, month_value, year, scope_month, scopes)
                consumed |= {"ay", "yil"}
            elif month_value is not None:
                raise _Fail("ay verilmiş ama gün belirtilmemiş")
        if weekday_at is not None:
            consumed.add("hafta")
        self.scope_only({k: v for k, v in scopes.items() if k not in consumed})
        if weekday_at is not None:
            self.weekday_phrase(weekday_at, scopes)

    def read_scopes(self) -> dict[str, int]:
        scopes: dict[str, int] = {}
        for i, token in enumerate(self.tokens):
            if self.used[i]:
                continue
            nxt = self.free(i + 1)
            kind = (
                "ay" if nxt in _AY else "hafta" if nxt in _HAFTA else "yil" if nxt in _YIL else ""
            )
            if token in _REL and kind:
                if kind in scopes:
                    raise _Fail("birden fazla göreli dönem ifadesi var")
                scopes[kind] = _REL[token]
                self.mark(i, i + 1)
            elif token == "haftaya" and "hafta" not in scopes:
                scopes["hafta"] = 1
                self.mark(i)
            elif token == "seneye" and "yil" not in scopes:
                scopes["yil"] = 1
                self.mark(i)
            elif token == "ayin" and "ay" not in scopes and self.bare_month_context(i):
                scopes["ay"] = 0
                self.mark(i)
        return scopes

    def bare_month_context(self, index: int) -> bool:
        """ "ayın 15'i", "ayın son günü": a bare "ayın" refers to the current month."""
        nxt = self.free(index + 1)
        return nxt in _ORDINALS or nxt.isdigit()

    def read_year(self, month_idx: int | None) -> int | None:
        if month_idx is None:
            return None
        for i in (month_idx + 1, month_idx + 2, month_idx + 3, month_idx - 1):
            token = self.free(i)
            if len(token) == 4 and token.isdigit():
                self.mark(i)
                return int(token)
        return None

    def month_context(
        self,
        month_value: int | None,
        year: int | None,
        scope_month: int | None,
        scopes: dict[str, int],
    ) -> tuple[int, int]:
        today = self.now.date()
        year_shift = scopes.get("yil", 0)
        if month_value is not None:
            if year is None:
                year = today.year + year_shift
                self.assumptions.append(f"yıl belirtilmedi; {year} kullanıldı")
            return year, month_value
        shifted = add_months(today.replace(day=1), scope_month or 0)
        return (year if year is not None else shifted.year + year_shift), shifted.month

    def ordinal_phrase(
        self,
        ordinal: tuple[int, int],
        weekday_at: tuple[int, int] | None,
        month_value: int | None,
        year: int | None,
        scope_month: int | None,
        scopes: dict[str, int],
    ) -> None:
        index, number = ordinal
        if month_value is None and scope_month is None:
            raise _Fail("sıra sayısı (ilk, son, ...) için ay belirtilmemiş")
        y, m = self.month_context(month_value, year, scope_month, scopes)
        last_day = calendar.monthrange(y, m)[1]
        nxt = self.free(index + 1)
        if weekday_at is not None and weekday_at[0] == index + 1:
            weekday = weekday_at[1]
            if number == -1:
                end = date(y, m, last_day)
                value = end - timedelta(days=(end.weekday() - weekday) % 7)
            else:
                first = date(y, m, 1)
                value = first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (number - 1))
                if value.month != m:
                    raise _Fail(
                        f"{MONTH_NAMES[m - 1]} {y} ayında {number}. {WEEKDAY_NAMES[weekday]} yok"
                    )
            self.mark(index, index + 1)
        elif nxt in _GUN:
            value = date(y, m, last_day if number == -1 else min(number, last_day))
            self.mark(index, index + 1)
        else:
            raise _Fail("sıra sayısından sonra gün adı ya da 'gün' bekleniyordu")
        self.set_base(value, "calendar")

    def day_in_month(
        self,
        day_index: int,
        month_value: int | None,
        year: int | None,
        scope_month: int | None,
        scopes: dict[str, int],
    ) -> None:
        y, m = self.month_context(month_value, year, scope_month, scopes)
        self.mark(day_index)
        self.set_base(self.build(y, m, int(self.tokens[day_index])), "calendar")

    def find_day_number(self, month_idx: int | None) -> int | None:
        candidates: list[int] = []
        if month_idx is not None:
            candidates = [month_idx - 1, month_idx + 1, month_idx + 2]
            candidates = [c for c in candidates if c >= 0]
        else:
            candidates = list(range(len(self.tokens)))
        for i in candidates:
            token = self.free(i)
            if token.isdigit() and len(token) <= 2 and 1 <= int(token) <= 31:
                return i
        return None

    def weekday_phrase(self, weekday_at: tuple[int, int], scopes: dict[str, int]) -> None:
        index, weekday = weekday_at
        today = self.now.date()
        prev = self.free(index - 1)
        week_scope = scopes.get("hafta")
        if prev == "bu" and week_scope is None:
            week_scope = 0
            self.mark(index - 1)
        self.mark(index)
        if self.free(index + 1) in _GUN:
            self.mark(index + 1)
        monday = today - timedelta(days=today.weekday())
        if week_scope is not None:
            value = monday + timedelta(days=7 * week_scope + weekday)
            self.set_base(value, "weekday")
            return
        if prev in ("gelecek", "onumuzdeki"):
            self.mark(index - 1)
            self.set_base(
                today + timedelta(days=(weekday - today.weekday() - 1) % 7 + 1), "weekday"
            )
            return
        if prev == "gecen":
            self.mark(index - 1)
            self.set_base(
                today - timedelta(days=(today.weekday() - weekday - 1) % 7 + 1), "weekday"
            )
            return
        if self.base is not None or self.moment is not None:
            reference = self.moment.date() if self.moment is not None else self.base
            if reference is not None and reference.weekday() != weekday:
                raise _Fail(
                    f"{WEEKDAY_NAMES[weekday]} günü, {format_date(reference, weekday=False)} "
                    f"tarihiyle uyuşmuyor ({WEEKDAY_NAMES[reference.weekday()]})"
                )
            return
        self.assumptions.append("yalnızca gün adı verildi; bugünden itibaren ilk uygun gün alındı")
        self.set_base(today + timedelta(days=(weekday - today.weekday()) % 7), "weekday")

    def scope_only(self, scopes: dict[str, int]) -> None:
        if not scopes:
            return
        value = self.now.date()
        value = value + timedelta(days=7 * scopes.get("hafta", 0))
        value = add_months(value, scopes.get("ay", 0) + 12 * scopes.get("yil", 0))
        self.set_base(value, "scope")

    # -- driver ------------------------------------------------------------------
    def run(self) -> datetime:
        if not self.tokens:
            raise _Fail("metin boş")
        _check_ambiguous(self.tokens)
        self.find_timezone()
        period = self.find_periods()
        self.offsets()
        self.resolve_clock(period)
        if self.clock_offset and self.clock is not None:
            raise _Fail("hem süre hem saat verilmiş")
        self.numeric_dates()
        self.day_words()
        self.calendar_phrases()
        for i, token in enumerate(self.tokens):
            if not self.used[i] and token not in _FILLERS and token != "saat":
                raise _Fail(f"anlaşılmayan sözcük: {token!r}")
        if self.moment is not None:
            if self.clock is not None:
                dt = datetime.combine(self.moment.date(), time(*self.clock), self.now.tzinfo)
            else:
                dt = self.moment
        else:
            if self.base is None:
                if self.clock is None:
                    raise _Fail("tarih ya da saat bulunamadı")
                self.base = self.now.date()
            if self.clock is not None:
                clock = time(*self.clock)
            elif self.keep_now_time:
                clock = self.now.timetz().replace(tzinfo=None)
            else:
                clock = time(0, 0)
            dt = datetime.combine(self.base, clock, self.now.tzinfo)

        if self.parsed_tz is not None:
            dt = dt.replace(tzinfo=self.parsed_tz)
        if self.strict and self.assumptions:
            raise _Fail(f"belirsiz ifade; varsayım gerekiyor: {'; '.join(self.assumptions)}")
        return dt


def _pretty_period(name: str) -> str:
    return (
        name.replace("_", " ")
        .replace("ogleden", "öğleden")
        .replace("aksam", "akşam")
        .replace("ogle", "öğle")
        .replace("once", "önce")
        .replace("yarisi", "yarısı")
    )


def _apply_period(hour: int, period: str | None, explicit: bool, text: str) -> int:
    """Convert a 12-hour reading to 24 hours using the day period ("akşam 7" -> 19)."""
    if period is None:
        if explicit or hour == 0 or hour >= 12:
            return hour
        raise _Fail(
            f"saat belirsiz ({hour}): 'sabah {hour}' ya da 'akşam {hour}' gibi gün bölümü ekleyin, "
            f"ya da {hour:02d}:00 biçiminde yazın"
        )
    if period in ("sabah", "ogleden_once"):
        if explicit and hour >= 12:
            raise _Fail(
                f"'{_pretty_period(period)}' gün bölümü ile saat {hour:02d}:00 birbiriyle çelişiyor"
            )
        if not (5 <= hour <= 11):
            raise _Fail(
                f"'{_pretty_period(period)}' gün bölümü ile saat {hour:02d}:00 birbiriyle çelişiyor"
            )
        return hour
    if period == "ogle":
        if hour > 12:
            if not (11 <= hour <= 14):
                raise _Fail(
                    f"'{_pretty_period(period)}' gün bölümü ile saat {hour:02d}:00 "
                    "birbiriyle çelişiyor"
                )
            return hour
        if hour in (11, 12):
            return hour
        if 1 <= hour <= 2:
            return hour + 12
        raise _Fail(
            f"'{_pretty_period(period)}' gün bölümü ile saat {hour:02d}:00 birbiriyle çelişiyor"
        )
    if period == "ogleden_sonra":
        if hour > 12:
            if not (12 <= hour <= 18):
                raise _Fail(
                    f"'{_pretty_period(period)}' gün bölümü ile saat {hour:02d}:00 "
                    "birbiriyle çelişiyor"
                )
            return hour
        if hour == 12:
            return 12
        if 1 <= hour <= 6:
            return hour + 12
        raise _Fail(
            f"'{_pretty_period(period)}' gün bölümü ile saat {hour:02d}:00 birbiriyle çelişiyor"
        )
    if period == "ikindi":
        if hour > 12:
            if not (15 <= hour <= 18):
                raise _Fail(
                    f"'{_pretty_period(period)}' gün bölümü ile saat {hour:02d}:00 "
                    "birbiriyle çelişiyor"
                )
            return hour
        if 3 <= hour <= 6:
            return hour + 12
        raise _Fail(
            f"'{_pretty_period(period)}' gün bölümü ile saat {hour:02d}:00 birbiriyle çelişiyor"
        )
    if period == "aksam":
        if hour > 12:
            if not (17 <= hour <= 22):
                raise _Fail(
                    f"'{_pretty_period(period)}' gün bölümü ile saat {hour:02d}:00 "
                    "birbiriyle çelişiyor"
                )
            return hour
        if 5 <= hour <= 10:
            return hour + 12
        raise _Fail(
            f"'{_pretty_period(period)}' gün bölümü ile saat {hour:02d}:00 birbiriyle çelişiyor"
        )
    if period == "gece":
        if hour > 12:
            if not (20 <= hour <= 23):
                raise _Fail(
                    f"'{_pretty_period(period)}' gün bölümü ile saat {hour:02d}:00 "
                    "birbiriyle çelişiyor"
                )
            return hour
        if hour == 12:
            return 0
        if hour >= 8:
            return hour + 12
        if hour <= 5:
            return hour
        raise _Fail(
            f"'{_pretty_period(period)}' gün bölümü ile saat {hour:02d}:00 birbiriyle çelişiyor"
        )
    if period == "gece_yarisi":
        if hour in (0, 12, 24):
            return 0
        raise _Fail(f"'gece yarısı' gün bölümü ile saat {hour:02d}:00 birbiriyle çelişiyor")
    return hour + 12 if hour < 12 else hour


def parse_datetime_detailed(
    text: str,
    now: datetime | date | None = None,
    *,
    reference: datetime | date | None = None,
    tz: tzinfo | str | None = None,
    timezone: tzinfo | str | None = None,
    strict: bool = False,
) -> ParseResult[datetime]:
    """Parse a Turkish date/time expression; return ``value=None`` and a reason if unclear.

    ``reference`` / ``now`` sets the reference moment (default: ``datetime.now()``).
    ``tz`` / ``timezone`` specifies a target timezone (tzinfo object, offset string, or IANA name).
    ``strict`` disallows implicit assumptions (omitted year, default hours for day periods).
    """
    if reference is not None and now is not None and reference != now:
        raise ValueError("hem 'now' hem 'reference' argümanı verilemez")
    if tz is not None and timezone is not None and tz != timezone:
        raise ValueError("hem 'tz' hem 'timezone' argümanı verilemez")

    ref_input = reference if reference is not None else now
    tz_input = tz if tz is not None else timezone

    try:
        target_tz = _resolve_timezone(tz_input) if tz_input is not None else None
    except ValueError as exc:
        return failure(text, str(exc))

    if ref_input is None:
        ref_moment = datetime.now(target_tz)
    elif isinstance(ref_input, datetime):
        if target_tz is not None:
            ref_moment = (
                ref_input.replace(tzinfo=target_tz)
                if ref_input.tzinfo is None
                else ref_input.astimezone(target_tz)
            )
        else:
            ref_moment = ref_input
    elif isinstance(ref_input, date):
        ref_moment = datetime.combine(ref_input, time(0, 0), target_tz)
    else:
        raise TypeError(f"referans zaman datetime veya date olmalıdır: {type(ref_input).__name__}")

    stripped = text.strip()
    if (
        ("T" in stripped or (" " in stripped and (":" in stripped or "+" in stripped)))
        and len(stripped) >= 10
    ):
        iso_candidate = stripped
        if iso_candidate.endswith(("Z", "z")):
            iso_candidate = iso_candidate[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(iso_candidate)
            if target_tz is not None:
                dt = (
                    dt.astimezone(target_tz)
                    if dt.tzinfo is not None
                    else dt.replace(tzinfo=target_tz)
                )
            return ParseResult(text=text, value=dt)
        except ValueError:
            pass

    parser = _Parser(text=text, now=ref_moment, strict=strict)
    try:
        value = parser.run()
    except _Fail as exc:
        return failure(text, str(exc))
    except (ValueError, OverflowError):
        return failure(text, "tarih veya süre desteklenen aralığın dışında (yıl: 1–9999)")

    if target_tz is not None and value.tzinfo is not None and value.tzinfo != target_tz:
        value = value.astimezone(target_tz)
    elif target_tz is not None and value.tzinfo is None:
        value = value.replace(tzinfo=target_tz)

    return ParseResult(text=text, value=value, assumptions=tuple(parser.assumptions))


def parse_datetime(
    text: str,
    now: datetime | date | None = None,
    *,
    reference: datetime | date | None = None,
    tz: tzinfo | str | None = None,
    timezone: tzinfo | str | None = None,
    strict: bool = False,
) -> datetime:
    """Parse ``"yarın saat 15:30"``, ``"23 Ekim 2026"``, ``"3 gün sonra"``, ...

    Raises :class:`~tr_tarih.ParseError` when the expression is unclear; use
    :func:`parse_datetime_detailed` to get a reason instead of an exception.
    """
    return parse_datetime_detailed(
        text, now=now, reference=reference, tz=tz, timezone=timezone, strict=strict
    ).unwrap()


def parse_date_detailed(
    text: str,
    now: datetime | date | None = None,
    *,
    reference: datetime | date | None = None,
    tz: tzinfo | str | None = None,
    timezone: tzinfo | str | None = None,
    strict: bool = False,
) -> ParseResult[date]:
    """Like :func:`parse_datetime_detailed` but returns only the calendar date."""
    result = parse_datetime_detailed(
        text, now=now, reference=reference, tz=tz, timezone=timezone, strict=strict
    )
    value = result.value.date() if result.value is not None else None
    return ParseResult(text=text, value=value, reason=result.reason, assumptions=result.assumptions)


def parse_date(
    text: str,
    now: datetime | date | None = None,
    *,
    reference: datetime | date | None = None,
    tz: tzinfo | str | None = None,
    timezone: tzinfo | str | None = None,
    strict: bool = False,
) -> date:
    """Like :func:`parse_datetime` but returns only the calendar date."""
    return parse_date_detailed(
        text, now=now, reference=reference, tz=tz, timezone=timezone, strict=strict
    ).unwrap()


@dataclass(frozen=True)
class DateParser:
    """Configured Turkish date/time parser with fixed reference moment and timezone."""

    reference: datetime | date | None = None
    tz: tzinfo | str | None = None
    strict: bool = False

    def parse_datetime_detailed(self, text: str) -> ParseResult[datetime]:
        """Parse text into a :class:`~tr_tarih.ParseResult` containing a datetime."""
        return parse_datetime_detailed(
            text, reference=self.reference, tz=self.tz, strict=self.strict
        )

    def parse_datetime(self, text: str) -> datetime:
        """Parse text into a datetime or raise :class:`~tr_tarih.ParseError`."""
        return self.parse_datetime_detailed(text).unwrap()

    def parse_date_detailed(self, text: str) -> ParseResult[date]:
        """Parse text into a :class:`~tr_tarih.ParseResult` containing a date."""
        return parse_date_detailed(
            text, reference=self.reference, tz=self.tz, strict=self.strict
        )

    def parse_date(self, text: str) -> date:
        """Parse text into a date or raise :class:`~tr_tarih.ParseError`."""
        return self.parse_date_detailed(text).unwrap()


def format_date(value: date | datetime, *, weekday: bool = True, style: DateStyle = "long") -> str:
    """Format a date: ``"23 Ekim 2026 Cuma"`` (default), ``"23.10.2026"`` or ISO."""
    if style == "short":
        return f"{value.day:02d}.{value.month:02d}.{value.year}"
    if style == "iso":
        return value.strftime("%Y-%m-%d")
    if style != "long":
        raise ValueError(f"unknown style: {style!r}")
    text = f"{value.day} {MONTH_NAMES[value.month - 1]} {value.year}"
    return f"{text} {WEEKDAY_NAMES[value.weekday()]}" if weekday else text


def format_datetime(value: datetime, *, weekday: bool = True, seconds: bool = False) -> str:
    """Format date and time: ``"23 Ekim 2026 Cuma 15:30"``."""
    clock = f"{value.hour:02d}:{value.minute:02d}" + (f":{value.second:02d}" if seconds else "")
    return f"{format_date(value, weekday=weekday)} {clock}"


_RELATIVE_UNITS = (
    (365 * 86400, "yıl"),
    (30 * 86400, "ay"),
    (7 * 86400, "hafta"),
    (86400, "gün"),
    (3600, "saat"),
    (60, "dakika"),
    (1, "saniye"),
)


def format_relative(value: datetime, now: datetime | None = None) -> str:
    """Describe ``value`` relative to ``now``: ``"3 gün önce"``, ``"2 saat sonra"``.

    The largest whole unit is used (rounded down); months and years are 30 and
    365 days. Differences under ten seconds read ``"şimdi"``.
    """
    reference = now if now is not None else datetime.now(value.tzinfo)
    seconds = (value - reference).total_seconds()
    size = abs(seconds)
    if size < 10:
        return "şimdi"
    for length, name in _RELATIVE_UNITS:
        if size >= length:
            return f"{int(size // length)} {name} {'sonra' if seconds > 0 else 'önce'}"
    return "şimdi"  # pragma: no cover - unreachable, size >= 10 matches "saniye"
