"""Generate docs/demo.svg from actual CLI output, without subprocesses or dependencies."""

from __future__ import annotations

import io
import shlex
import sys
from contextlib import redirect_stdout
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tr_tarih.cli import main  # noqa: E402

COMMANDS = (
    ("date", "yarın saat 15:30", "--now", "2026-10-23T10:00"),
    ("number", "iki yüz elli bin"),
    ("money", "beş lira elli kuruş"),
    ("fmt-money", "1250.5"),
)


def render() -> str:
    lines: list[tuple[str, str]] = []
    for args in COMMANDS:
        lines.append(("#93c5fd", "$ tr-tarih " + shlex.join(args)))
        capture = io.StringIO()
        with redirect_stdout(capture):
            status = main(args)
        if status:
            raise RuntimeError(f"demo command failed with status {status}: {args}")
        lines.extend(("#e2e8f0", line) for line in capture.getvalue().splitlines())
        lines.append(("#e2e8f0", ""))
    width = max(720, max(len(text) for _, text in lines) * 9 + 48)
    height = 76 + 25 * len(lines)
    rows = "\n".join(
        f'<text x="24" y="{78 + i * 25}" fill="{color}">{escape(text)}</text>'
        for i, (color, text) in enumerate(lines)
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title description">\n'
        '<title id="title">tr-tarih terminal demo</title>\n'
        '<desc id="description">Actual output of Turkish date, number and lira parsing.</desc>\n'
        f'<rect width="{width}" height="{height}" rx="12" fill="#0f172a"/>\n'
        '<circle cx="24" cy="24" r="6" fill="#f87171"/>\n'
        '<circle cx="44" cy="24" r="6" fill="#fbbf24"/>\n'
        '<circle cx="64" cy="24" r="6" fill="#4ade80"/>\n'
        '<g font-family="DejaVu Sans Mono,Consolas,monospace" font-size="14">\n'
        + rows
        + "\n</g>\n</svg>\n"
    )


if __name__ == "__main__":
    (ROOT / "docs" / "demo.svg").write_text(render(), encoding="utf-8", newline="\n")
