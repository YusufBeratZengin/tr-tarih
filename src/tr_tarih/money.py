"""Turkish lira amounts: parse and format. Amounts are always :class:`~decimal.Decimal`."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation, localcontext
from typing import Literal

from ._text import matches_stem, tokenize
from .numbers import format_number, number_to_words, scan_number
from .result import ParseResult, failure

__all__ = ["MoneyStyle", "format_money", "parse_money", "parse_money_detailed"]

MoneyStyle = Literal["symbol", "suffix", "words"]

_LIRA_MARKERS = frozenset({"₺", "tl", "try"})
_FOREIGN = frozenset({"$", "€", "£", "usd", "eur", "gbp", "dolar", "euro", "sterlin"})
_CENT = Decimal("0.01")


def _is_lira(token: str) -> bool:
    return token in _LIRA_MARKERS or matches_stem(token, ("lira",))


def _is_kurus(token: str) -> bool:
    return matches_stem(token, ("kurus",))


def parse_money_detailed(text: str) -> ParseResult[Decimal]:
    """Parse a lira amount; never raises. See :func:`parse_money`."""
    with localcontext() as context:
        context.prec = max(context.prec, len(text) + 32)
        return _parse_money(text)


def _parse_money(text: str) -> ParseResult[Decimal]:
    stripped = text.strip()
    negative = stripped[:1] in ("-", "−", "–") or stripped[1:2] in ("-", "−")
    tokens = tokenize(stripped)
    if tokens and tokens[0] == "eksi":
        negative, tokens = True, tokens[1:]
    for token in tokens:
        if token in _FOREIGN:
            return failure(text, f"yalnızca Türk lirası desteklenir, bulunan: {token!r}")
    if not tokens:
        return failure(text, "metinde tutar yok")

    assumptions: list[str] = []
    i = 0
    marker = False
    if _is_lira(tokens[0]) and len(tokens) > 1:
        marker, i = True, 1
    scanned = scan_number(tokens, i)
    if scanned is None:
        return failure(text, f"tutar olarak anlaşılamadı: {tokens[i]!r}")
    amount, i = scanned
    lira = amount
    kurus = Decimal(0)
    if i < len(tokens) and _is_kurus(tokens[i]) and not marker:
        lira, kurus, marker, i = Decimal(0), amount, True, i + 1
    elif i < len(tokens) and _is_lira(tokens[i]) and not marker:
        marker, i = True, i + 1
        rest = scan_number(tokens, i)
        if rest is not None and rest[1] < len(tokens) and _is_kurus(tokens[rest[1]]):
            kurus, i = rest[0], rest[1] + 1
    if i != len(tokens):
        return failure(text, f"tutarın ardından anlaşılamayan kısım: {' '.join(tokens[i:])!r}")
    if not marker:
        assumptions.append("para birimi belirtilmedi; Türk lirası varsayıldı")
    value = lira + kurus / 100
    return ParseResult(
        text=text, value=-value if negative else value, assumptions=tuple(assumptions)
    )


def parse_money(text: str) -> Decimal:
    """Parse ``"₺1.250,50"``, ``"1.250,50 TL"``, ``"bin iki yüz lira"`` or ``"5 lira 50 kuruş"``.

    Always returns a :class:`~decimal.Decimal`. Only Turkish lira is supported.
    Raises :class:`~tr_tarih.ParseError` if the text is not an amount.
    """
    return parse_money_detailed(text).unwrap()


def _to_decimal(amount: int | Decimal | str) -> Decimal:
    if isinstance(amount, float | bool):
        raise TypeError("money must be int, Decimal or str, never float or bool")
    try:
        value = Decimal(amount)
        if not value.is_finite():
            raise ValueError("amount must be finite")
        with localcontext() as context:
            context.prec = max(context.prec, len(format(value, "f")) + 4)
            return value.quantize(_CENT, rounding=ROUND_HALF_UP)
    except InvalidOperation:
        raise ValueError(f"not an amount: {amount!r}") from None


def format_money(
    amount: int | Decimal | str,
    *,
    style: MoneyStyle = "symbol",
    cents: bool = True,
) -> str:
    """Format an amount: ``"₺1.250,50"``, ``"1.250,50 TL"`` or spelled out.

    ``cents=False`` drops ",00" from whole amounts. Floats are rejected on purpose.
    """
    value = _to_decimal(amount)
    if style == "words":
        whole = value.copy_abs()
        lira, kurus = int(whole), int((whole - int(whole)) * 100)
        parts = [f"{number_to_words(lira)} lira"]
        if kurus:
            parts.append(f"{number_to_words(kurus)} kuruş")
        return ("eksi " if value < 0 else "") + " ".join(parts)
    if style not in ("symbol", "suffix"):
        raise ValueError(f"unknown style: {style!r}")
    decimals = 0 if not cents and value == value.to_integral_value() else 2
    body = format_number(value.copy_abs(), decimals)
    text = f"₺{body}" if style == "symbol" else f"{body} TL"
    return "-" + text if value < 0 else text
