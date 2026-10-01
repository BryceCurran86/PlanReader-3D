#!/usr/bin/env python3
"""Screenshot every ``*_<preset>.html`` in a directory with headless Chromium.

The Three.js CDN URL in the page is served from a local copy (--three PATH to
three.min.js) so the render works without network access.
usage: render_audit_screenshots.py DIR --three /path/to/three.min.js
"""
from __future__ import annotations

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("directory")
    ap.add_argument("--three", required=True)
    ap.add_argument("--width", type=int, default=1600)
    ap.add_argument("--height", type=int, default=1000)
    args = ap.parse_args()
    three = Path(args.three).read_bytes()
    d = Path(args.directory)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--no-sandbox"])
        for html in sorted(d.glob("*_*.html")):
            page = browser.new_page(viewport={"width": args.width, "height": args.height})
            page.route("**/three.min.js", lambda route: route.fulfill(body=three, content_type="application/javascript"))
            page.goto(html.resolve().as_uri())
            page.wait_for_function("window.__READY === true", timeout=60000)
            page.screenshot(path=str(html.with_suffix(".png")))
            page.close()
            print("wrote", html.with_suffix(".png"))
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
