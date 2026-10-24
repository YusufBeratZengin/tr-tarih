"""Turkish numbers: parse digits and words, spell integers and decimals out."""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation, localcontext

from ._text import SUFFIXES, fold, tokenize
from .result import ParseResult, failure

__all__ = ["format_number", "number_to_words", "parse_number", "parse_number_detailed"]

_UNIT_WORDS = ("sıfır", "bir", "iki", "üç", "dört", "beş", "altı", "yedi", "sekiz", "dokuz")
_TENS_WORDS = ("", "on", "yirmi", "otuz", "kırk", "elli", "altmış", "yetmiş", "seksen", "doksan")
_SCALE_WORDS = ("", "bin", "milyon", "milyar", "trilyon", "katrilyon")

_UNITS = {fold(w): i for i, w in enumerate(_UNIT_WORDS)} | {"dord": 4}
_TENS = {fold(w): i * 10 for i, w in enumerate(_TENS_WORDS) if w}
_SCALES = {fold(w): 10 ** (3 * i) for i, w in enumerate(_SCALE_WORDS) if w}
_SUFFIXABLE = _UNITS | _TENS

_DIGITS = re.compile(r"\d+(?:[.,]\d+)*")
_TR_MIXED = re.compile(r"\d{1,3}(?:\.\d{3})+,\d+")
_EN_MIXED = re.compile(r"\d{1,3}(?:,\d{3})+\.\d+")
_EN_GROUPS = re.compile(r"\d{1,3}(?:,\d{3}){2,}")
_TR_GROUPS = re.compile(r"[1-9]\d{0,2}(?:\.\d{3})+")

# Allowed predecessor states for every kind of token in the number grammar.
_ALLOWED: dict[str, frozenset[str]] = {
    "digits": frozenset({"start", "scale"}),
    "unit": frozenset({"start", "scale", "tens", "hundred"}),
    "tens": frozenset({"start", "scale", "hundred"}),
    "hundred": frozenset({"start", "unit", "scale"}),
    "half": frozenset({"digits", "unit", "tens"}),
    "yarim": frozenset({"start", "scale"}),
    "comma": frozenset({"digits", "unit", "tens", "hundred", "scale"}),
}
_FIXED_WORDS = {"yuz": ("hundred", 100), "bucuk": ("half", 0), "yarim": ("yarim", 0)}


def parse_digits(token: str) -> Decimal | None:
    """Read a digit string with Turkish separators (``1.250,50``); English style too.

    A lone dot followed by exactly three digits is a thousands separator
    (``1.250`` is 1250); any other single dot or comma is a decimal point.
    """
    if not _DIGITS.fullmatch(token):
        return None
    if token.isdigit():
        return Decimal(token)
    dots, commas = token.count("."), token.count(",")
    if dots and commas:
        if _TR_MIXED.fullmatch(token):
            return Decimal(token.replace(".", "").replace(",", "."))
        if _EN_MIXED.fullmatch(token):
            return Decimal(token.replace(",", ""))
        return None
    if commas:
        if commas == 1:
            return Decimal(token.replace(",", "."))
        return Decimal(token.replace(",", "")) if _EN_GROUPS.fullmatch(token) else None
    if _TR_GROUPS.fullmatch(token):
        return Decimal(token.replace(".", ""))
    return Decimal(token) if dots == 1 else None


def _word_kind(token: str) -> tuple[str, int, bool] | None:
    """Classify a number word as (kind, value, suffixed). Units and tens may carry endings."""
    if token in _UNITS:
        return "unit", _UNITS[token], False
    if token in _TENS:
        return "tens", _TENS[token], False
    if token in _SCALES:
        return "scale", _SCALES[token], False
    if token in _FIXED_WORDS:
        return _FIXED_WORDS[token][0], _FIXED_WORDS[token][1], False
    if token == "virgul":
        return "comma", 0, False
    for cut in (1, 2, 3):
        stem, ending = token[:-cut], token[-cut:]
        if ending in SUFFIXES and stem in _SUFFIXABLE:
            return ("unit" if stem in _UNITS else "tens"), _SUFFIXABLE[stem], True
    return None


def _scan_fraction(tokens: list[str], j: int) -> tuple[str, int]:
    """Read the digits after "virgül": words (sıfır..dokuz) or a digit token."""
    digits = ""
    while j < len(tokens):
        tok = tokens[j]
        if tok in _UNITS:
            digits += str(_UNITS[tok])
        elif tok.isdigit():
            digits += tok
        else:
            break
        j += 1
    return digits, j


def scan_number(tokens: list[str], start: int) -> tuple[Decimal, int] | None:
    """Read the longest number at ``tokens[start:]``; return (value, next index).

    Understands digits (``250``, ``1,5``, ``1.250``), words (``iki yüz elli``) and
    mixes (``250 bin``, ``2 milyon 500 bin``, ``bir buçuk milyon``, ``bir virgül beş``).
    """
    # Decimal arithmetic must not silently round long input to the caller's precision.
    with localcontext() as context:
        context.prec = max(context.prec, sum(map(len, tokens[start:])) + 32)
        return _scan_number(tokens, start)


def _scan_number(tokens: list[str], start: int) -> tuple[Decimal, int] | None:
    total = Decimal(0)
    current = Decimal(0)
    last_scale = 0
    prev = "start"
    j = consumed = start
    while j < len(tokens):
        tok = tokens[j]
        value = parse_digits(tok)
        suffixed = False
        if value is not None:
            kind, number = "digits", value
        else:
            classified = _word_kind(tok)
            if classified is None:
                break
            kind, raw, suffixed = classified
            number = Decimal(raw)
        if kind == "scale":
            if last_scale and int(number) >= last_scale:
                break
            if prev == "scale" and int(number) != 1000:
                break
            group = current if prev not in ("start", "scale") else Decimal(1)
            total += group * number
            current, last_scale, prev = Decimal(0), int(number), "scale"
            j = consumed = j + 1
            continue
        if prev not in _ALLOWED[kind]:
            break
        if kind == "hundred":
            if prev == "unit" and not 0 < current < 10:
                break
            current = (current or Decimal(1)) * 100
        elif kind in ("digits", "unit", "tens"):
            if kind == "unit" and number == 0 and prev != "start":
                break
            current += number
        elif kind in ("half", "yarim"):
            current += Decimal("0.5")
            kind = "half"
        else:  # comma
            digits, nxt = _scan_fraction(tokens, j + 1)
            if not digits:
                break
            current += Decimal("0." + digits)
            j = consumed = nxt
            # A fraction may only be followed by a scale word ("bir virgül beş milyon").
            if j < len(tokens) and tokens[j] in _SCALES:
                prev = "frac"
                continue
            break
        prev = kind
        j = consumed = j + 1
        if suffixed:
            break
    if consumed == start:
        return None
    return total + current, consumed


def simplify(value: Decimal) -> int | Decimal:
    """Return an ``int`` for whole values, a normalised ``Decimal`` otherwise."""
    if value == value.to_integral_value():
        return int(value)
    with localcontext() as context:
        context.prec = max(context.prec, len(value.as_tuple().digits))
        return value.normalize()


def parse_number_detailed(text: str) -> ParseResult[int | Decimal]:
    """Parse a Turkish number; never raises. See :func:`parse_number`."""
    tokens = tokenize(text, strict=True)
    negative = False
    if tokens and tokens[0] in ("-", "−", "–", "eksi"):
        negative, tokens = True, tokens[1:]
    if not tokens:
        return failure(text, "metinde sayı yok")
    scanned = scan_number(tokens, 0)
    if scanned is None:
        return failure(text, f"sayı olarak anlaşılamadı: {tokens[0]!r}")
    value, end = scanned
    if end != len(tokens):
        return failure(text, f"sayının ardından anlaşılamayan kısım: {' '.join(tokens[end:])!r}")
    return ParseResult(text=text, value=simplify(value.copy_negate() if negative else value))


def parse_number(text: str) -> int | Decimal:
    """Parse ``"iki yüz elli bin"``, ``"250 bin"``, ``"1,5 milyon"`` or ``"1.250,5"``.

    Returns an ``int`` for whole numbers and a ``Decimal`` otherwise.
    Raises :class:`~tr_tarih.ParseError` if the text is not a number.
    """
    return parse_number_detailed(text).unwrap()


def _group_words(group: int, scale_index: int) -> str:
    hundreds, rest = divmod(group, 100)
    tens, units = divmod(rest, 10)
    if scale_index == 1 and group == 1:
        return "bin"
    parts: list[str] = []
    if hundreds:
        parts.append("yüz" if hundreds == 1 else f"{_UNIT_WORDS[hundreds]} yüz")
    if tens:
        parts.append(_TENS_WORDS[tens])
    if units:
        parts.append(_UNIT_WORDS[units])
    if scale_index:
        parts.append(_SCALE_WORDS[scale_index])
    return " ".join(parts)


def _integer_words(value: int) -> str:
    if value == 0:
        return _UNIT_WORDS[0]
    if value >= 10**18:
        raise ValueError("number_to_words supports values below 10**18")
    groups: list[str] = []
    scale_index = 0
    while value:
        value, group = divmod(value, 1000)
        if group:
            groups.append(_group_words(group, scale_index))
        scale_index += 1
    return " ".join(reversed(groups))


def number_to_words(value: int | Decimal | float | str) -> str:
    """Spell a number out in Turkish: ``1250`` -> ``"bin iki yüz elli"``.

    Decimals use "virgül": ``Decimal("1.5")`` -> ``"bir virgül beş"``.
    """
    if isinstance(value, bool):
        raise TypeError("bool is not a number")
    try:
        number = value if isinstance(value, Decimal) else Decimal(str(value))
    except InvalidOperation:
        raise ValueError(f"not a number: {value!r}") from None
    if not number.is_finite():
        raise ValueError("number must be finite")
    sign = "eksi " if number < 0 else ""
    number = number.copy_abs()
    integer = int(number)
    fraction = format(number, "f").partition(".")[2].rstrip("0")
    words = _integer_words(integer)
    if fraction:
        words += " virgül " + " ".join(_UNIT_WORDS[int(d)] for d in fraction)
    return sign + words


def format_number(value: int | Decimal | str, decimals: int | None = None) -> str:
    """Format with Turkish separators: ``Decimal("1250000.5")`` -> ``"1.250.000,5"``.

    ``decimals`` fixes the number of fraction digits (rounded half up).
    """
    if isinstance(value, float | bool):
        raise TypeError("pass int, Decimal or str instead of float or bool")
    number = Decimal(value)
    if not number.is_finite():
        raise ValueError("number must be finite")
    if decimals is not None:
        if isinstance(decimals, bool) or not isinstance(decimals, int) or decimals < 0:
            raise ValueError("decimals must be a non-negative integer")
        with localcontext() as context:
            context.prec = max(context.prec, len(format(number, "f")) + decimals + 2)
            number = number.quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)
    text = format(number, "f")
    sign = "-" if text.startswith("-") else ""
    whole, _, frac = text.lstrip("-").partition(".")
    grouped = f"{int(whole):,}".replace(",", ".")
    return sign + grouped + ("," + frac if frac else "")
