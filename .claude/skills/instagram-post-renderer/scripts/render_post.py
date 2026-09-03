#!/usr/bin/env python3
"""Render a finished 1080x1350 Instagram post from the Gallery HTML template.

No paid image generation and no network at render time: fonts ship with the
skill and are inlined as base64, and headless Chromium turns the page into a
JPEG that the Instagram Graph API will accept as-is.

    python3 render_post.py --pillar "design tip" \
        --headline "Your homepage does not need a slider." \
        --deck "It splits attention..." --out build/tue.jpg
"""

import argparse
import base64
import html
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import tempfile

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(SKILL_DIR, "templates", "post.html")
FONT_DIR = os.path.join(SKILL_DIR, "resources", "fonts")
LOGO_DIR = os.path.join(SKILL_DIR, "resources", "logo")

WIDTH, HEIGHT = 1080, 1350

PILLARS = ("project showcase", "design tip", "philosophy")

# The eyebrow is a quiet label, not a hashtag. One per pillar, fixed, so the
# grid reads as a series rather than six unrelated posts.
DEFAULT_EYEBROW = {
    "project showcase": "Recent work",
    "design tip": "Design tip",
    "philosophy": "Notes",
}

# Instagram rejects anything outside 4:5 .. 1.91:1 and anything over 8 MB.
MAX_BYTES = 8 * 1024 * 1024

CHROME_CANDIDATES = [
    os.environ.get("CHROME_BIN", ""),
    "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "chromium",
    "chromium-browser",
    "google-chrome",
    "google-chrome-stable",
]


def find_chrome():
    """Locate a Chromium/Chrome binary, preferring an explicit CHROME_BIN."""
    for cand in CHROME_CANDIDATES:
        if not cand:
            continue
        if os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand
        found = shutil.which(cand)
        if found:
            return found
    # Fall back to any Playwright-managed build so a version bump doesn't break us.
    pw_root = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")
    if os.path.isdir(pw_root):
        for entry in sorted(os.listdir(pw_root), reverse=True):
            for rel in ("chrome-linux/chrome", "chrome-mac/Chromium.app/Contents/MacOS/Chromium"):
                path = os.path.join(pw_root, entry, rel)
                if os.path.isfile(path) and os.access(path, os.X_OK):
                    return path
    sys.exit(
        "Could not find Chrome or Chromium. Install one, or set CHROME_BIN to its path."
    )


def data_uri(path):
    """Read a file into a base64 data: URI so the page has no external requests."""
    mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
    if path.lower().endswith(".ttf"):
        mime = "font/ttf"
    with open(path, "rb") as fh:
        return "data:%s;base64,%s" % (mime, base64.b64encode(fh.read()).decode("ascii"))


def font_uri(name):
    path = os.path.join(FONT_DIR, name)
    if not os.path.isfile(path):
        sys.exit("Missing bundled font: %s" % path)
    return data_uri(path)


def find_logo(explicit):
    """Use --logo if given, else the first file dropped in resources/logo/."""
    if explicit:
        if not os.path.isfile(explicit):
            sys.exit("Logo not found: %s" % explicit)
        return explicit
    if os.path.isdir(LOGO_DIR):
        for entry in sorted(os.listdir(LOGO_DIR)):
            if entry.lower().endswith((".png", ".svg", ".jpg", ".jpeg", ".webp")):
                return os.path.join(LOGO_DIR, entry)
    return None


def build_html(opts):
    with open(TEMPLATE, encoding="utf-8") as fh:
        tpl = fh.read()

    deck_block = ""
    if opts.deck:
        deck_block = '<p class="deck">%s</p>' % html.escape(opts.deck)

    shot_block = ""
    if opts.screenshot:
        if not os.path.isfile(opts.screenshot):
            sys.exit("Screenshot not found: %s" % opts.screenshot)
        # A fixed slot keeps the composition predictable across a whole batch.
        shot_block = (
            '<div class="shot" style="height:%dpx"><img src="%s" alt=""></div>'
            % (opts.shot_height, data_uri(opts.screenshot))
        )

    logo_path = find_logo(opts.logo)
    if logo_path:
        logo_block = '<img src="%s" alt="javierdiaz.design">' % data_uri(logo_path)
    else:
        logo_block = html.escape(opts.wordmark)

    footer_right = opts.footer_right
    if footer_right is None:
        # Project showcases name the project; the other pillars stay silent.
        footer_right = opts.project if (opts.project and opts.pillar == "project showcase") else ""

    eyebrow = opts.eyebrow or DEFAULT_EYEBROW.get(opts.pillar, "")

    replacements = {
        "{{FONT_FRAUNCES_REGULAR}}": font_uri("Fraunces-Regular.ttf"),
        "{{FONT_FRAUNCES_SEMIBOLD}}": font_uri("Fraunces-SemiBold.ttf"),
        "{{FONT_FRAUNCES_BOLD}}": font_uri("Fraunces-Bold.ttf"),
        "{{FONT_INSTRUMENT_REGULAR}}": font_uri("InstrumentSans-Regular.ttf"),
        "{{FONT_INSTRUMENT_BOLD}}": font_uri("InstrumentSans-Bold.ttf"),
        "{{PILLAR}}": html.escape(opts.pillar),
        "{{EYEBROW}}": html.escape(eyebrow),
        "{{HEADLINE}}": html.escape(opts.headline),
        "{{DECK_BLOCK}}": deck_block,
        "{{SHOT_BLOCK}}": shot_block,
        "{{LOGO_BLOCK}}": logo_block,
        "{{FOOTER_RIGHT}}": html.escape(footer_right),
    }
    for token, value in replacements.items():
        tpl = tpl.replace(token, value)
    return tpl


def render(opts):
    chrome = find_chrome()
    out = os.path.abspath(opts.out)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)

    workdir = tempfile.mkdtemp(prefix="ig-post-")
    try:
        page = os.path.join(workdir, "post.html")
        with open(page, "w", encoding="utf-8") as fh:
            fh.write(build_html(opts))

        shot = os.path.join(workdir, "post.png")
        cmd = [
            chrome,
            "--headless",
            "--no-sandbox",
            "--disable-gpu",
            "--hide-scrollbars",
            "--force-device-scale-factor=1",
            "--default-background-color=FAF9F5",
            # Lets the autofit script finish before the frame is captured.
            "--virtual-time-budget=6000",
            "--window-size=%d,%d" % (WIDTH, HEIGHT),
            "--screenshot=%s" % shot,
            # Same run returns the DOM, so we can read back what the autofit chose.
            "--dump-dom",
            "file://%s" % page,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if not os.path.isfile(shot):
            sys.exit(
                "Chromium produced no screenshot.\n%s\n%s"
                % (proc.stdout[-2000:], proc.stderr[-2000:])
            )

        fitted = re.search(r'data-headline-size="(\d+)"', proc.stdout or "")
        overflowed = re.search(r'data-overflow="1"', proc.stdout or "")
        lines_m = re.search(r'data-headline-lines="(\d+)"', proc.stdout or "")
        headline_px = int(fitted.group(1)) if fitted else 0
        headline_lines = int(lines_m.group(1)) if lines_m else 0

        if opts.keep_html:
            kept = os.path.splitext(out)[0] + ".html"
            shutil.copy(page, kept)

        try:
            from PIL import Image
        except ImportError:
            sys.exit("Pillow is required for JPEG output. Install it with: pip install Pillow")

        with Image.open(shot) as im:
            if im.size != (WIDTH, HEIGHT):
                sys.exit("Expected %dx%d, got %dx%d" % (WIDTH, HEIGHT, im.size[0], im.size[1]))
            if out.lower().endswith(".png"):
                shutil.copy(shot, out)
            else:
                # Flatten onto paper so any alpha becomes the brand background,
                # never the black that JPEG would otherwise give it.
                rgb = Image.new("RGB", im.size, (250, 249, 245))
                rgb.paste(im, mask=im.split()[3] if im.mode == "RGBA" else None)
                quality = opts.quality
                rgb.save(out, "JPEG", quality=quality, subsampling=0, optimize=True)
                # Instagram caps images at 8 MB; step quality down if we exceed it.
                while os.path.getsize(out) > MAX_BYTES and quality > 60:
                    quality -= 5
                    rgb.save(out, "JPEG", quality=quality, subsampling=0, optimize=True)
    finally:
        if not opts.keep_temp:
            shutil.rmtree(workdir, ignore_errors=True)

    size = os.path.getsize(out)
    if size > MAX_BYTES:
        sys.exit("Rendered file is %d bytes, over Instagram's 8 MB limit." % size)
    return out, size, headline_px, headline_lines, bool(overflowed)


def parse_args(argv):
    p = argparse.ArgumentParser(description="Render a 1080x1350 Instagram post.")
    p.add_argument("--pillar", choices=PILLARS, required=True)
    p.add_argument("--headline", required=True, help="On-image display text.")
    p.add_argument("--deck", default="", help="Optional supporting line under the headline.")
    p.add_argument("--eyebrow", default="", help="Override the default pillar label.")
    p.add_argument("--project", default="", help="Project name (project showcases only).")
    p.add_argument("--footer-right", default=None, help="Override the footer's right-hand text.")
    p.add_argument("--screenshot", default="", help="Real project screenshot to embed.")
    p.add_argument("--shot-height", type=int, default=460, help="Height of the screenshot slot.")
    p.add_argument("--logo", default="", help="Logo file; defaults to resources/logo/.")
    p.add_argument("--wordmark", default="javierdiaz.design", help="Fallback when no logo exists.")
    p.add_argument("--out", required=True, help="Output path (.jpg for Instagram, .png to inspect).")
    p.add_argument("--quality", type=int, default=92)
    p.add_argument("--keep-html", action="store_true", help="Write the HTML next to the image.")
    p.add_argument("--keep-temp", action="store_true")
    p.add_argument("--json", action="store_true", help="Print a JSON result line.")
    return p.parse_args(argv)


def main(argv=None):
    opts = parse_args(argv if argv is not None else sys.argv[1:])
    out, size, headline_px, headline_lines, overflowed = render(opts)

    # A headline that had to shrink below ~52px has stopped being display type.
    # Say so plainly instead of quietly shipping a wall of text.
    warning = ""
    if overflowed:
        warning = ("Headline does not fit even at the minimum size. "
                   "Cut it down before using this image.")
    elif headline_lines > 5:
        warning = ("Headline wraps to %d lines. Over 5 it stops reading as display type - "
                   "move the detail into the caption and keep the image to one idea."
                   % headline_lines)
    elif headline_px and headline_px < 52:
        warning = ("Headline shrank to %dpx to fit. Under ~52px it reads as a paragraph, "
                   "not a headline - consider moving detail into the caption." % headline_px)

    if opts.json:
        print(json.dumps({"path": out, "bytes": size, "width": WIDTH, "height": HEIGHT,
                          "headline_px": headline_px, "headline_lines": headline_lines,
                          "warning": warning}))
    else:
        print("Rendered %s (%d x %d, %.0f KB, headline %dpx / %d lines)"
              % (out, WIDTH, HEIGHT, size / 1024.0, headline_px, headline_lines))
        if warning:
            print("WARNING: " + warning)
    return 0


if __name__ == "__main__":
    sys.exit(main())
