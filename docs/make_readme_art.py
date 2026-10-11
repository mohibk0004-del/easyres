"""Builds EasyRes README art from page captures in docs/img/raw/*.png.

Capture: build an AppWindow in-process, switch pages with the sidebar and save
`window.grab()` for each (QT_SCALE_FACTOR=2, 1180x760). Then run:
    python docs/make_readme_art.py
Outputs docs/banner.png and compressed docs/img/*.jpg.
"""

from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

DOCS = Path(__file__).parent
RAW = DOCS / "img" / "raw"
ROOT = DOCS.parent

BOLD = "C:/Windows/Fonts/segoeuib.ttf"
REG = "C:/Windows/Fonts/segoeui.ttf"
BLURPLE = (88, 101, 242)
BLACK = (0, 0, 0)
TEXT_2 = (161, 161, 166)


def rounded(img, radius):
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, img.width - 1, img.height - 1], radius, fill=255)
    out = Image.new("RGBA", img.size)
    out.paste(img, (0, 0), mask)
    return out


def shadowed(card, radius, blur=50, offset=30, alpha=210):
    pad = blur * 2
    canvas = Image.new("RGBA", (card.width + pad * 2, card.height + pad * 2), (0, 0, 0, 0))
    sh = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([pad, pad + offset, pad + card.width, pad + card.height + offset], radius, fill=(0, 0, 0, alpha))
    canvas.alpha_composite(sh.filter(ImageFilter.GaussianBlur(blur)))
    framed = rounded(card.convert("RGBA"), radius)
    edge = Image.new("RGBA", framed.size, (0, 0, 0, 0))
    ImageDraw.Draw(edge).rounded_rectangle([0, 0, framed.width - 1, framed.height - 1], radius, outline=(255, 255, 255, 40), width=2)
    framed.alpha_composite(edge)
    canvas.alpha_composite(framed, (pad, pad))
    return canvas, pad


# ---------------------------------------------------------------- compressed screenshots
for png in sorted(RAW.glob("*.png")):
    im = Image.open(png).convert("RGB")
    im.thumbnail((1760, 1760), Image.LANCZOS)
    im.save(DOCS / "img" / f"{png.stem}.jpg", "JPEG", quality=88, optimize=True, progressive=True)
    print("img", png.stem)

# ---------------------------------------------------------------- banner (2400 x 1200)
W, H = 2400, 1200
bg = Image.new("RGB", (W, H), BLACK)
glow = Image.new("RGB", (W, H), (0, 0, 0))
gd = ImageDraw.Draw(glow)
for cx, cy, r, s in [(2000, 80, 640, 0.55), (250, 1180, 480, 0.22)]:
    gd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=tuple(int(c * s) for c in BLURPLE))
banner = ImageChops.screen(bg, glow.filter(ImageFilter.GaussianBlur(260))).convert("RGBA")

# Resolution-grid motif: nested aspect-ratio frames (16:9, 4:3, 5:4) fading in on the left.
frames = Image.new("RGBA", (W, H), (0, 0, 0, 0))
fd = ImageDraw.Draw(frames)
cx, cy = 560, 600
for (w, h), a in [((1100, 619), 26), ((825, 619), 34), ((774, 619), 22)]:
    fd.rounded_rectangle([cx - w // 2, cy - h // 2, cx + w // 2, cy + h // 2], 18, outline=(255, 255, 255, a), width=2)
banner.alpha_composite(frames)

shot = Image.open(RAW / "switch.png").convert("RGB").resize((1180, 760), Image.LANCZOS)
card, pad = shadowed(shot, 24)
card = card.rotate(-4, resample=Image.BICUBIC, expand=True)
banner.alpha_composite(card, (1120 - pad, 190 - pad))

shade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
sd = ImageDraw.Draw(shade)
for x in range(1350):
    sd.line([(x, 0), (x, H)], fill=(0, 0, 0, int(240 * max(0.0, 1 - x / 1350) ** 1.3)))
banner.alpha_composite(shade)

icon = Image.open(ROOT / "icon.png").convert("RGBA").resize((170, 170), Image.LANCZOS)
banner.alpha_composite(rounded(icon, 38), (130, 205))

d = ImageDraw.Draw(banner)
d.text((126, 410), "EasyRes", font=ImageFont.truetype(BOLD, 150), fill=(245, 245, 247))
f = ImageFont.truetype(REG, 50)
d.text((134, 615), "Stretched and custom resolutions,", font=f, fill=TEXT_2)
d.text((134, 681), "one click or one key away.", font=f, fill=TEXT_2)

pills = Image.new("RGBA", (W, H), (0, 0, 0, 0))
pdr = ImageDraw.Draw(pills)
fp = ImageFont.truetype(BOLD, 34)
labels = ["1440 × 1080", "Hotkey toggle", "Safe revert"]
x = 134
for label in labels:
    tw = d.textlength(label, font=fp)
    filled = label == labels[0]
    pdr.rounded_rectangle([x, 800, x + tw + 56, 868], 34, fill=BLURPLE + (255,) if filled else (255, 255, 255, 16), outline=None if filled else (255, 255, 255, 56), width=2)
    x += tw + 56 + 18
banner.alpha_composite(pills)
d = ImageDraw.Draw(banner)
x = 134
for label in labels:
    tw = d.textlength(label, font=fp)
    d.text((x + 28, 812), label, font=fp, fill="white")
    x += tw + 56 + 18

banner.convert("RGB").resize((1600, 800), Image.LANCZOS).save(DOCS / "banner.png", optimize=True)
print("banner")
