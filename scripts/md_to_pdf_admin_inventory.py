"""Convert docs/Admin_API_Inventory.md to PDF via HTML + Chrome headless."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[1]
MD = ROOT / "docs" / "Admin_API_Inventory.md"
HTML = ROOT / "docs" / "Admin_API_Inventory.html"
PDF = ROOT / "docs" / "Admin_API_Inventory.pdf"

CHROME_CANDIDATES = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
]

CSS = """
@page { size: A4; margin: 14mm 12mm; }
html { font-size: 11px; }
body {
  font-family: "Microsoft YaHei", "Segoe UI", "PingFang SC", sans-serif;
  color: #1a1a1a;
  line-height: 1.45;
  max-width: 100%;
}
h1 { font-size: 20px; margin: 0 0 10px; border-bottom: 2px solid #222; padding-bottom: 6px; }
h2 { font-size: 14px; margin: 18px 0 8px; page-break-after: avoid; }
blockquote {
  margin: 8px 0 12px;
  padding: 8px 12px;
  background: #f5f7fa;
  border-left: 3px solid #4a6fa5;
  color: #333;
}
table {
  width: 100%;
  border-collapse: collapse;
  margin: 0 0 10px;
  table-layout: fixed;
  page-break-inside: auto;
}
th, td {
  border: 1px solid #c9d0d8;
  padding: 4px 6px;
  vertical-align: top;
  word-wrap: break-word;
  overflow-wrap: anywhere;
}
th { background: #eef2f7; font-weight: 600; text-align: left; }
tr { page-break-inside: avoid; }
td:nth-child(1), th:nth-child(1) { width: 18%; }
td:nth-child(2), th:nth-child(2) { width: 52%; font-family: Consolas, "Courier New", monospace; font-size: 10px; }
td:nth-child(3), th:nth-child(3) { width: 30%; }
code { font-family: Consolas, "Courier New", monospace; font-size: 10px; }
ol, ul { margin: 6px 0 10px 22px; }
p { margin: 6px 0; }
hr { border: none; border-top: 1px solid #ddd; margin: 16px 0; }
"""


def find_browser() -> Path:
    for p in CHROME_CANDIDATES:
        if p.exists():
            return p
    raise SystemExit("Chrome/Edge not found for PDF rendering")


def main() -> None:
    text = MD.read_text(encoding="utf-8")
    body = markdown.markdown(
        text,
        extensions=["tables", "fenced_code", "sane_lists"],
    )
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<title>CapitalPay Admin API Inventory</title>
<style>{CSS}</style>
</head>
<body>
{body}
</body>
</html>
"""
    HTML.write_text(html, encoding="utf-8")

    browser = find_browser()
    # file:/// URL with forward slashes
    url = HTML.resolve().as_uri()
    cmd = [
        str(browser),
        "--headless=new",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={PDF.resolve()}",
        url,
    ]
    print("Running:", " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
        raise SystemExit(proc.returncode)
    if not PDF.exists() or PDF.stat().st_size < 1000:
        raise SystemExit(f"PDF not created or too small: {PDF}")
    print(f"Wrote {PDF} ({PDF.stat().st_size} bytes)")
    # keep HTML as intermediate is fine; optional cleanup
    HTML.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
