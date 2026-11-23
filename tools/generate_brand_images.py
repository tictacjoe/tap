#!/usr/bin/env python3
"""Generate TAP's brand images: favicon, touch icon, and social preview card.

Outputs (all written to the tap-site repo root, next to index.html):

    favicon.svg            browser-tab icon (scales cleanly at any size)
    favicon-32.png         PNG fallback for browsers that ignore SVG icons
    apple-touch-icon.png   180x180 icon for iOS/Android home-screen bookmarks
    og-image.png           1200x630 link-preview card for Bluesky, Facebook,
                           iMessage, Slack, Substack, etc. (Open Graph image)

Colors are copied from the :root tokens at the top of index.html so the
images match the live site. If the palette there changes, update PALETTE
below and re-run:

    python3 tools/generate_brand_images.py

Re-running is safe: it overwrites the four files. Commit them afterwards.
Requires Pillow (pip install --break-system-packages pillow).
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Repo root = parent of this tools/ folder.
ROOT = Path(__file__).resolve().parent.parent

# --- Palette: mirrors index.html :root custom properties -------------------
PALETTE = {
    "paper": "#EDEFE7",       # --paper (page background)
    "paper_card": "#F7F8F2",  # --paper-card
    "ink": "#1D2220",         # --ink (body text)
    "ink_soft": "#52564F",    # --ink-soft
    "brass": "#96762C",       # --brass ("The Accountability Project" line)
    "rule": "#A9AC9A",        # --rule-strong (masthead double rule)
}

# The six curated-tracker identity colors (--trk-*), in tab order. Used as
# a striped band on the social card so it reads as "several trackers".
TRACKER_COLORS = [
    "#b0561a",  # Corporate Deregulation
    "#7a3f8f",  # Cabinet-Level Accountability
    "#00846a",  # Government Service Redirection
    "#a3303f",  # Trump Family
    "#3462b0",  # DHS and ICE
    "#4f5b66",  # User Topics
]

# Serif fonts available in WSL Ubuntu that resemble the site's Georgia
# stack. First one found wins.
SERIF_REGULAR = [
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSerif-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
]
SERIF_BOLD = [
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSerif-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
]


def load_font(candidates, size):
    """Return the first TrueType font in `candidates` that exists."""
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    raise SystemExit(f"No serif font found; tried {candidates}")


def centered_text(draw, y, text, font, fill, width, spacing=0):
    """Draw `text` horizontally centered at vertical position `y`.

    `spacing` adds extra pixels between letters, mimicking the site's
    letter-spacing on the TAP wordmark.
    """
    if spacing == 0:
        w = draw.textlength(text, font=font)
        draw.text(((width - w) / 2, y), text, font=font, fill=fill)
        return
    # Letter-by-letter so we can add tracking.
    widths = [draw.textlength(ch, font=font) for ch in text]
    total = sum(widths) + spacing * (len(text) - 1)
    x = (width - total) / 2
    for ch, w in zip(text, widths):
        draw.text((x, y), ch, font=font, fill=fill)
        x += w + spacing


# --- favicon.svg ------------------------------------------------------------
# A bold serif "T" on the paper color, with a brass bar underneath echoing
# the masthead rule. A single letter stays legible at 16px where "TAP"
# would blur into a smudge.
FAVICON_SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="10" fill="{PALETTE['ink']}"/>
  <text x="32" y="46" text-anchor="middle"
        font-family="Georgia, 'Times New Roman', serif"
        font-size="46" font-weight="700" fill="{PALETTE['paper']}">T</text>
  <rect x="14" y="52" width="36" height="4" fill="{PALETTE['brass']}"/>
</svg>
"""


def draw_icon(size):
    """Raster version of the favicon design at `size` x `size` pixels."""
    # Draw at 4x and downsample for smooth anti-aliased edges.
    s = size * 4
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    radius = int(s * 10 / 64)
    d.rounded_rectangle([0, 0, s - 1, s - 1], radius=radius, fill=PALETTE["ink"])
    font = load_font(SERIF_BOLD, int(s * 50 / 64))
    # Center the T using its actual ink bounding box.
    bbox = d.textbbox((0, 0), "T", font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (s - tw) / 2 - bbox[0]
    y = s * 0.44 - th / 2 - bbox[1]
    d.text((x, y), "T", font=font, fill=PALETTE["paper"])
    bar_top = int(s * 52 / 64)
    d.rectangle([int(s * 14 / 64), bar_top, int(s * 50 / 64), bar_top + int(s * 4 / 64)],
                fill=PALETTE["brass"])
    return img.resize((size, size), Image.LANCZOS)


def draw_og_card():
    """1200x630 link-preview card styled like the site masthead."""
    W, H = 1200, 630
    img = Image.new("RGB", (W, H), PALETTE["paper"])
    d = ImageDraw.Draw(img)

    # Tracker-color band along the bottom (one stripe per tracker).
    band_h = 22
    stripe_w = W / len(TRACKER_COLORS)
    for i, color in enumerate(TRACKER_COLORS):
        d.rectangle([int(i * stripe_w), H - band_h, int((i + 1) * stripe_w), H], fill=color)

    # Wordmark: "TAP", uppercase, wide tracking, like header.masthead h1.
    centered_text(d, 95, "TAP", load_font(SERIF_REGULAR, 170), PALETTE["ink"], W, spacing=14)

    # Brass project-name line.
    centered_text(d, 300, "THE ACCOUNTABILITY PROJECT", load_font(SERIF_BOLD, 40),
                  PALETTE["brass"], W, spacing=4)

    # Double rule, like the masthead's border-bottom: 3px double.
    for y in (370, 377):
        d.line([(300, y), (900, y)], fill=PALETTE["rule"], width=2)

    # Tagline: two lines, soft ink.
    body = load_font(SERIF_REGULAR, 34)
    centered_text(d, 410, "Executive branch actions since January 2025,", body, PALETTE["ink_soft"], W)
    centered_text(d, 455, "sourced to primary records. Search every entry.", body, PALETTE["ink_soft"], W)

    # Site address, small, above the band.
    centered_text(d, 540, "tictacjoe.github.io/tap", load_font(SERIF_REGULAR, 26),
                  PALETTE["ink_soft"], W)
    return img


def main():
    (ROOT / "favicon.svg").write_text(FAVICON_SVG)
    draw_icon(32).save(ROOT / "favicon-32.png", optimize=True)
    # Apple touch icons should be opaque; flatten onto the ink color.
    touch = draw_icon(180)
    flat = Image.new("RGB", touch.size, PALETTE["ink"])
    flat.paste(touch, mask=touch.split()[3])
    flat.save(ROOT / "apple-touch-icon.png", optimize=True)
    draw_og_card().save(ROOT / "og-image.png", optimize=True)
    for name in ("favicon.svg", "favicon-32.png", "apple-touch-icon.png", "og-image.png"):
        print(f"wrote {name} ({(ROOT / name).stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
