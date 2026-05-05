"""Generate vertical (9:16) slide PNG images from HTML using Playwright.

Usage:
    python make_slides.py <slides.json> <out_dir>

slides.json format:
    [
      {"kind": "title", "title": "...", "subtitle": "...", "tag": "..."},
      {"kind": "point", "n": 1, "of": 3, "headline": "...", "body": "..."},
      ...
    ]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright


W, H = 1920, 1080


HTML_TPL = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<style>
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; width: {W}px; height: {H}px; }}
  body {{
    font-family: 'Hiragino Kaku Gothic ProN', 'Yu Gothic UI', sans-serif;
    background: #0E0E10;
    color: #FFFFFF;
    display: flex;
    flex-direction: column;
    justify-content: center;
    padding: 140px 180px;
    position: relative;
    overflow: hidden;
  }}
  .glow {{
    position: absolute;
    width: 900px;
    height: 900px;
    border-radius: 50%;
    background: radial-gradient(closest-side, rgba(255,109,42,0.55), transparent 70%);
    filter: blur(40px);
    top: -200px;
    right: -200px;
  }}
  .glow2 {{
    position: absolute;
    width: 700px;
    height: 700px;
    border-radius: 50%;
    background: radial-gradient(closest-side, rgba(75,156,255,0.35), transparent 70%);
    filter: blur(50px);
    bottom: -100px;
    left: -200px;
  }}
  .tag {{
    font-size: 38px;
    font-weight: 600;
    letter-spacing: 4px;
    color: #FF6D2A;
    text-transform: uppercase;
    margin-bottom: 60px;
    z-index: 2;
  }}
  .title {{
    font-size: 130px;
    font-weight: 900;
    line-height: 1.15;
    letter-spacing: -1px;
    z-index: 2;
    max-width: 1450px;
  }}
  .subtitle {{
    font-size: 48px;
    font-weight: 400;
    line-height: 1.5;
    color: #C7C7CC;
    margin-top: 50px;
    max-width: 1300px;
    z-index: 2;
  }}
  .pageno {{
    position: absolute;
    bottom: 110px;
    left: 110px;
    font-size: 36px;
    color: #6B6B70;
    letter-spacing: 6px;
    z-index: 2;
  }}
  .footer {{
    position: absolute;
    bottom: 110px;
    right: 110px;
    font-size: 30px;
    color: #6B6B70;
    z-index: 2;
  }}
  .headline {{
    font-size: 90px;
    font-weight: 900;
    line-height: 1.2;
    z-index: 2;
  }}
  .body {{
    font-size: 50px;
    font-weight: 400;
    line-height: 1.7;
    color: #E0E0E5;
    margin-top: 80px;
    z-index: 2;
  }}
</style>
</head>
<body>
  <div class="glow"></div>
  <div class="glow2"></div>
  {INNER}
  <div class="footer">@taiyokimura</div>
</body>
</html>
"""


def render_title(slide):
    inner = (
        f'<div class="tag">{slide.get("tag", "AIの最新")}</div>'
        f'<div class="title">{slide["title"]}</div>'
    )
    if slide.get("subtitle"):
        inner += f'<div class="subtitle">{slide["subtitle"]}</div>'
    return HTML_TPL.format(W=W, H=H, INNER=inner)


def render_point(slide):
    n = slide.get("n", 1)
    of = slide.get("of", 3)
    inner = (
        f'<div class="tag">POINT {n} / {of}</div>'
        f'<div class="headline">{slide["headline"]}</div>'
    )
    if slide.get("body"):
        inner += f'<div class="body">{slide["body"]}</div>'
    inner += f'<div class="pageno">{n:02d}</div>'
    return HTML_TPL.format(W=W, H=H, INNER=inner)


RENDERERS = {"title": render_title, "point": render_point}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("slides_json")
    p.add_argument("out_dir")
    args = p.parse_args()

    slides = json.loads(Path(args.slides_json).read_text(encoding="utf-8"))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    paths = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={"width": W, "height": H},
                                      device_scale_factor=1)
        page = context.new_page()
        for i, slide in enumerate(slides, start=1):
            kind = slide.get("kind", "point")
            html = RENDERERS[kind](slide)
            page.set_content(html)
            page.wait_for_load_state("networkidle")
            out = out_dir / f"slide_{i:02d}.png"
            page.screenshot(path=str(out), full_page=False, omit_background=False)
            paths.append(str(out))
            print(f"[{i}/{len(slides)}] {out}", file=sys.stderr)
        browser.close()
    print(json.dumps(paths, ensure_ascii=False))


if __name__ == "__main__":
    main()
