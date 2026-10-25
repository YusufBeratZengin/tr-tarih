"""Keep copy-paste examples and the generated demo aligned with real behavior."""

import re
import runpy
import shlex
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from tr_tarih.cli import main

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("readme", ["README.md", "README.tr.md"])
def test_cli_examples(readme: str, capsys: pytest.CaptureFixture[str]) -> None:
    content = (ROOT / readme).read_text(encoding="utf-8")
    blocks = re.findall(r"```(?:sh|console)\n(.*?)```", content, re.DOTALL)
    count = 0
    for block in blocks:
        for line in block.splitlines():
            if line.startswith(("tr-tarih ", "$ tr-tarih ")):
                command = shlex.split(line.removeprefix("$ "))
                assert main(command[1:]) == 0
                count += 1
    assert count >= 10
    assert not capsys.readouterr().err


@pytest.mark.parametrize("readme", ["README.md", "README.tr.md"])
def test_python_examples(readme: str) -> None:
    content = (ROOT / readme).read_text(encoding="utf-8")
    blocks = re.findall(r"```python\n(.*?)```", content, re.DOTALL)
    assert blocks
    for block in blocks:
        exec(compile(block, readme, "exec"), {})


def test_example_output(capsys: pytest.CaptureFixture[str]) -> None:
    runpy.run_path(str(ROOT / "examples" / "basic.py"), run_name="__main__")
    output = capsys.readouterr().out
    for readme in ("README.md", "README.tr.md"):
        assert "```text\n" + output + "```" in (ROOT / readme).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "example_name",
    ["basic.py", "dates_and_times.py", "money_and_numbers.py"],
)
def test_all_examples_run(example_name: str, capsys: pytest.CaptureFixture[str]) -> None:
    runpy.run_path(str(ROOT / "examples" / example_name), run_name="__main__")
    captured = capsys.readouterr()
    assert captured.out
    assert not captured.err


def test_demo_is_reproducible_and_accessible() -> None:
    generator = runpy.run_path(str(ROOT / "scripts" / "make-demo.py"))
    generated = generator["render"]()
    assert generated == (ROOT / "docs" / "demo.svg").read_text(encoding="utf-8")
    document = ET.fromstring(generated)
    assert document.attrib["role"] == "img"
    assert document.find("{http://www.w3.org/2000/svg}title") is not None
    assert "2026-10-24T15:30:00" in generated
    assert "₺1.250,50" in generated
