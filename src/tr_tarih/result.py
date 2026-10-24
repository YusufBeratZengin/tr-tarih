"""Result and error types shared by the ``parse_*_detailed`` functions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


class ParseError(ValueError):
    """Raised by the strict ``parse_*`` functions when the text cannot be understood."""


@dataclass(frozen=True)
class ParseResult(Generic[T]):
    """Outcome of a ``parse_*_detailed`` call.

    ``value`` is ``None`` when the text is unclear; ``reason`` then says why (in
    Turkish, the language of the input). ``assumptions`` lists defaults that were
    applied to a successful parse, such as "year not given; reference year used".
    """

    text: str
    value: T | None = None
    reason: str | None = None
    assumptions: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        """True if ``value`` is set."""
        return self.value is not None

    def unwrap(self) -> T:
        """Return ``value`` or raise :class:`ParseError` carrying ``reason``."""
        if self.value is None:
            raise ParseError(f"{self.text!r}: {self.reason or 'anlaşılamadı'}")
        return self.value


def failure(text: str, reason: str) -> ParseResult[T]:
    """Build a failed result."""
    return ParseResult(text=text, reason=reason)
