"""Render the HTML reports to PDF via headless Chrome.

Three things have to be fixed before printing or the output is unusable:

  THEME    The pages follow prefers-color-scheme, and a machine set to dark mode
           prints white text on a dark background. Forcing data-theme="light"
           pins them, because the dark rule is written as
           :root:where(:not([data-theme=light])).

  PAGE     Content is up to 1180 px wide. On Letter or A4 portrait that scales
           down far enough to make the axis labels unreadable, so the print
           stylesheet asks for A3 portrait.

  BREAKS   Without break-inside:avoid a chart lands half on one page and half on
           the next. Cards, figures and tables are kept whole.

Backgrounds are forced on as well; without print-color-adjust the shaded bands
that mark where a rule changes the position simply vanish.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORTS = [
    ROOT / "testing" / "porocilo_pogoji_BTC.html",
    ROOT / "testing" / "porocilo_parametri_BTC.html",
]
CHROME = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
]

PRINT_CSS = """
<style id="print-fix">
@page { size: A3 portrait; margin: 12mm 10mm; }
@media print {
  html, body { background: #fff !important; }
  * { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
  main { max-width: none !important; padding: 0 !important; }
  .card, .fig, table, svg { break-inside: avoid; page-break-inside: avoid; }
  h1, h2, h3 { break-after: avoid; page-break-after: avoid; }
  h2 { break-before: auto; }
  a { text-decoration: none; color: inherit; }
}
</style>
"""


def browser() -> Path:
    for p in CHROME:
        if p.exists():
            return p
    raise SystemExit("ne najdem ne Chroma ne Edgea")


def prepare(src: Path, tmp: Path) -> Path:
    html = src.read_text(encoding="utf-8")
    if 'data-theme' not in html.split("<head>")[0]:
        html = html.replace('<html lang="sl">', '<html lang="sl" data-theme="light">', 1)
    html = html.replace("</head>", PRINT_CSS + "</head>", 1)
    out = tmp / src.name
    out.write_text(html, encoding="utf-8")
    return out


def main() -> int:
    exe = browser()
    print(f"tiskalnik: {exe.name}")
    tmp = Path(tempfile.mkdtemp(prefix="pdf_"))
    rc = 0
    for src in REPORTS:
        if not src.exists():
            print(f"  MANJKA {src.name}")
            rc = 1
            continue
        staged = prepare(src, tmp)
        pdf = src.with_suffix(".pdf")
        # Render to a scratch path and swap it in. Printing straight onto the
        # target fails when a viewer has it open, and -- worse -- leaves the old
        # file in place, which any check based on size alone reads as success.
        scratch = tmp / (src.stem + ".pdf")
        scratch.unlink(missing_ok=True)
        cmd = [str(exe), "--headless=new", "--disable-gpu", "--no-sandbox",
               f"--user-data-dir={tmp / 'profile'}",   # never touch the live profile
               "--no-pdf-header-footer", "--virtual-time-budget=8000",
               f"--print-to-pdf={scratch}", staged.as_uri()]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if not scratch.exists():
            cmd[cmd.index("--no-pdf-header-footer")] = "--print-to-pdf-no-header"
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if not scratch.exists() or scratch.stat().st_size < 20_000:
            print(f"  NAPAKA pri {src.name}: {(r.stderr or '')[-300:]}")
            rc = 1
            continue
        try:
            os.replace(scratch, pdf)
        except PermissionError:
            print(f"  ZAKLENJEN {pdf.name} — zapri ga v pregledovalniku in poženi znova")
            rc = 1
            continue
        pages = pdf.read_bytes().count(b"/Type /Page") or pdf.read_bytes().count(b"/Type/Page")
        print(f"  {pdf.name:32} {pdf.stat().st_size/1024:>6.0f} kB · ~{pages} strani")

    shutil.rmtree(tmp, ignore_errors=True)
    return rc


if __name__ == "__main__":
    sys.exit(main())
