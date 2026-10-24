"""Exercise CLI streams and exit codes without needing subprocess privileges."""

import json
import runpy
import sys

import pytest

from tr_tarih import ParseError, ParseResult, __version__
from tr_tarih.cli import main, run


@pytest.mark.parametrize(
    ("args", "output"),
    [
        (["date", "yarın saat 15:30", "--now", "2026-10-23T10:00"], "2026-10-24T15:30:00"),
        (["number", "iki yüz elli bin"], "250000"),
        (["number", "sıfır"], "0"),
        (["money", "5 lira 50 kuruş"], "5.5"),
        (["words", "1250"], "bin iki yüz elli"),
        (["fmt-date", "2026-10-23T15:30"], "23 Ekim 2026 Cuma 15:30"),
        (["fmt-date", "2026-10-23", "--style", "short"], "23.10.2026"),
        (["fmt-date", "2026-10-23", "--no-weekday"], "23 Ekim 2026"),
        (["fmt-money", "1250,50"], "₺1.250,50"),
        (["ago", "2026-10-26", "--now", "2026-10-23"], "3 gün sonra"),
        (["--version"], f"tr-tarih {__version__}"),
    ],
)
def test_success(args: list[str], output: str, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(args) == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == output
    assert not captured.err


@pytest.mark.parametrize("command", ["date", "number", "money"])
def test_json(command: str, capsys: pytest.CaptureFixture[str]) -> None:
    assert main([command, "nope", "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["input"] == "nope" and payload["ok"] is False
    assert payload["value"] is None and payload["reason"]
    assert payload["assumptions"] == []


def test_json_success(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["money", "0", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] and payload["value"] == "0" and payload["assumptions"]


def test_explain_and_error(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["money", "5", "--explain"]) == 0
    assert "# " in capsys.readouterr().out
    assert main(["date", "nope"]) == 1
    captured = capsys.readouterr()
    assert not captured.out and "anlaşılamadı" in captured.err


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["nope"],
        ["date", "yarın", "--now", "nope"],
        ["words", "nope"],
        ["fmt-money", "nope"],
        ["fmt-money", "Infinity"],
    ],
)
def test_usage(args: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    assert main(args) == 2
    assert capsys.readouterr().err


def test_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--help"]) == 0
    assert "COMMAND" in capsys.readouterr().out


def test_entrypoints(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(sys, "argv", ["tr-tarih", "--version"])
    assert run() == 0
    with pytest.raises(SystemExit) as error:
        runpy.run_module("tr_tarih", run_name="__main__")
    assert error.value.code == 0
    assert capsys.readouterr().out.count(__version__) == 2


def test_result_contract() -> None:
    result = ParseResult(text="zero", value=0)
    assert result.ok and result.unwrap() == 0
    with pytest.raises(ParseError, match="anlaşılamadı"):
        ParseResult[int](text="unknown").unwrap()
