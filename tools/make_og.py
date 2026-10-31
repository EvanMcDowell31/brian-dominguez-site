#!/usr/bin/env python3
"""Render src/og.png, the 1200x630 card that link previews show, with headless Chrome.

    python3 tools/make_og.py [path to chrome or headless_shell]
"""
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from build import waveform  # noqa: E402

DEFAULT_CHROME = Path.home() / "Library/Caches/ms-playwright/chromium_headless_shell-1194/chrome-mac/headless_shell"

CARD = """<!doctype html>
<html><head><meta charset="utf-8"><style>
html, body { margin: 0; width: 1200px; height: 630px; overflow: hidden; background: #f6f2ea; }
.card { position: relative; box-sizing: border-box; width: 1200px; height: 630px; padding: 88px 92px; color: #1d1a16;
        font-family: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif; }
.eyebrow { margin: 0; font: 600 24px/1 -apple-system, "Helvetica Neue", Arial, sans-serif; letter-spacing: 0.18em;
           text-transform: uppercase; color: #a84a20; }
h1 { margin: 26px 0 0; font-size: 124px; font-weight: 600; line-height: 1; letter-spacing: -0.025em; }
.line { margin: 30px 0 0; font: 32px/1.35 -apple-system, "Helvetica Neue", Arial, sans-serif; color: #4a443c; }
.wave { position: absolute; left: 92px; bottom: 70px; width: 1016px; height: 96px; fill: #a84a20; opacity: 0.9; }
</style></head><body><div class="card">
<p class="eyebrow">Audiobook narrator</p>
<h1>Brian Dominguez</h1>
<p class="line">The Disavowed &middot; Sam on the Way &middot; science fiction and nonfiction</p>
{wave}
</div></body></html>
"""


def main() -> None:
    chrome = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CHROME
    if not chrome.exists():
        sys.exit(f"No Chrome at {chrome}; pass the path to chrome or headless_shell.")
    out = ROOT / "src" / "og.png"
    with tempfile.TemporaryDirectory() as tmp:
        card = Path(tmp) / "card.html"
        card.write_text(CARD.replace("{wave}", waveform(145, 96, "wave")))  # 145 bars x 7 px fills the 1016 px text width
        subprocess.run([str(chrome), f"--screenshot={out}", "--window-size=1200,630", "--hide-scrollbars",
                        "--force-device-scale-factor=1", card.as_uri()], check=True, capture_output=True)
    print(f"wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
