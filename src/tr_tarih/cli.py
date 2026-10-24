"""Command line interface: ``tr-tarih date "yarın saat 15:30"``."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from . import __version__
from .dates import (
    format_date,
    format_datetime,
    format_relative,
    parse_datetime_detailed,
)
from .money import format_money, parse_money_detailed
from .numbers import number_to_words, parse_number_detailed
from .result import ParseResult

EXIT_OK = 0
EXIT_UNCLEAR = 1
EXIT_USAGE = 2


def _iso(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"invalid ISO date-time: {value!r} (example: 2026-10-23T10:00)"
        ) from None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tr-tarih",
        description="Parse and format Turkish dates, numbers and money.",
    )
    parser.add_argument("--version", action="version", version=f"tr-tarih {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    def with_parse_flags(name: str, help_text: str) -> argparse.ArgumentParser:
        child = sub.add_parser(name, help=help_text, description=help_text)
        child.add_argument("text", help="the Turkish expression to parse")
        child.add_argument("--json", action="store_true", help="print a JSON object")
        child.add_argument("--explain", action="store_true", help="show assumptions or the reason")
        return child

    date_cmd = with_parse_flags("date", "parse a date/time expression")
    date_cmd.add_argument("--now", type=_iso, help="reference moment, ISO format (default: now)")
    with_parse_flags("number", "parse a number (digits or words)")
    with_parse_flags("money", "parse a lira amount")

    words = sub.add_parser("words", help="spell a number out in Turkish")
    words.add_argument("number")

    fmt_date = sub.add_parser("fmt-date", help="format an ISO date or date-time")
    fmt_date.add_argument("value", type=_iso)
    fmt_date.add_argument("--style", choices=["long", "short", "iso"], default="long")
    fmt_date.add_argument("--no-weekday", action="store_true")

    fmt_money = sub.add_parser("fmt-money", help="format an amount as Turkish lira")
    fmt_money.add_argument("amount")
    fmt_money.add_argument("--style", choices=["symbol", "suffix", "words"], default="symbol")

    ago = sub.add_parser("ago", help="describe an ISO date-time relative to now")
    ago.add_argument("value", type=_iso)
    ago.add_argument("--now", type=_iso)
    return parser


def _show(result: ParseResult[Any], rendered: str | None, args: argparse.Namespace) -> int:
    if args.json:
        payload = {
            "input": result.text,
            "ok": result.ok,
            "value": rendered,
            "reason": result.reason,
            "assumptions": list(result.assumptions),
        }
        print(json.dumps(payload, ensure_ascii=False))
        return EXIT_OK if result.ok else EXIT_UNCLEAR
    if not result.ok:
        print(f"anlaşılamadı: {result.reason}", file=sys.stderr)
        return EXIT_UNCLEAR
    print(rendered)
    if args.explain:
        for note in result.assumptions:
            print(f"# {note}")
    return EXIT_OK


def _dispatch(args: argparse.Namespace) -> int:
    command: str = args.command
    if command == "date":
        parsed = parse_datetime_detailed(args.text, args.now)
        return _show(parsed, parsed.value.isoformat() if parsed.value else None, args)
    if command == "number":
        number = parse_number_detailed(args.text)
        return _show(number, str(number.value) if number.value is not None else None, args)
    if command == "money":
        money = parse_money_detailed(args.text)
        return _show(money, str(money.value) if money.value is not None else None, args)
    if command == "words":
        try:
            print(number_to_words(args.number.replace(",", ".")))
        except ValueError as error:
            print(f"error: {error}", file=sys.stderr)
            return EXIT_USAGE
        return EXIT_OK
    if command == "fmt-date":
        value: datetime = args.value
        if args.style == "long" and (value.hour or value.minute or value.second):
            print(format_datetime(value, weekday=not args.no_weekday))
        else:
            print(format_date(value, weekday=not args.no_weekday, style=args.style))
        return EXIT_OK
    if command == "fmt-money":
        try:
            print(format_money(Decimal(args.amount.replace(",", ".")), style=args.style))
        except (InvalidOperation, ValueError) as error:
            print(f"error: invalid amount: {error}", file=sys.stderr)
            return EXIT_USAGE
        return EXIT_OK
    try:
        print(format_relative(args.value, args.now or datetime.now(args.value.tzinfo)))
    except (TypeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_USAGE
    return EXIT_OK


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return the exit status: 0 ok, 1 unclear text, 2 bad usage."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")
    try:
        args = _build_parser().parse_args(argv)
    except SystemExit as exit_request:
        return int(exit_request.code) if isinstance(exit_request.code, int) else EXIT_USAGE
    return _dispatch(args)


def run() -> int:
    """Console-script entry point."""
    return main()


__all__ = ["main", "run"]
