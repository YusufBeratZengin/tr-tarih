"""Text normalisation shared by every parser (Turkish-aware, ASCII-folded tokens)."""

from __future__ import annotations

import re

_FOLD = str.maketrans("çğıöşüâîû", "cgiosuaiu")
_APOSTROPHE_SUFFIX = re.compile(r"['\u2019\u02bc`\u00b4]([a-zA-ZçğıöşüÇĞİÖŞÜâîû]*)")
_TOKEN = re.compile(r"\d+(?:[./:,-]\d+)*|[a-z]+|[₺$€£]")

#: Case/ending forms that may follow a month or weekday stem ("Ekim" -> "ekimde").
SUFFIXES = frozenset(
    {
        "", "a", "e", "ya", "ye", "da", "de", "ta", "te", "dan", "den", "tan", "ten",
        "in", "un", "nin", "nun", "i", "u", "yi", "yu", "si", "su", "ki", "daki", "deki",
        "taki", "teki", "la", "le", "yla", "yle", "sina", "sine", "sinda", "sinde",
        "sindan", "sinden", "sinin", "sinun", "siyla", "siyle", "ini", "ina", "ine",
        "inde", "inden", "inda", "indan", "inin", "iyle", "ndan", "nden", "nda", "nde", "na", "ne",
    }
)  # fmt: skip


def turkish_lower(text: str) -> str:
    """Lower-case with the Turkish dotted/dotless I rules."""
    return text.replace("İ", "i").replace("I", "ı").lower().replace("\u0307", "")


def fold(text: str) -> str:
    """Lower-case and fold Turkish letters to ASCII (``Çarşamba`` -> ``carsamba``)."""
    return turkish_lower(text).translate(_FOLD)


def tokenize(text: str) -> list[str]:
    """Split text into folded tokens; apostrophe suffixes (``3'te``) are dropped.

    Numbers keep their separators (``23.10.2026``, ``15:30``, ``1.250,50``) so the
    callers can interpret them; currency symbols are kept as single tokens.
    """
    cleaned = _APOSTROPHE_SUFFIX.sub("", text.replace("\u00a0", " "))
    return _TOKEN.findall(fold(cleaned))


def matches_stem(token: str, stems: tuple[str, ...]) -> bool:
    """True if ``token`` is one of ``stems`` followed by a known Turkish ending."""
    return any(token.startswith(s) and token[len(s) :] in SUFFIXES for s in stems)
