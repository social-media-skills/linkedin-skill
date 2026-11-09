#!/usr/bin/env python3
"""Render LinkedIn images (4:5 or 1:1) from the user's own photos and an images.json spec: a photo
with a short headline, a quote card, one big number, a short list, or the photo alone. For single
image posts and 2 to 20 image sets.

    python3 scripts/render_images.py images.json --out images/
    python3 scripts/render_images.py slides.json --out slides/ --pdf slides/carousel.pdf

Spec (paths relative to images.json):

{
  "brand": {"name": "Jane Doe", "site": "janedoe.com", "logo": "media/logo.png",
            "font": "serif" | "sans", "font_file": "fonts/MyFont.ttf",
            "colors": {"bg": "#F4EFE6", "fg": "#14182B", "accent": "#9A4E12"}},
  "images": [
    {"id": "earthset", "layout": "plain", "image": "media/earthset.jpg", "size": "4:5", "focus": [0.5, 0.6]},
    {"id": "lesson", "layout": "photo", "image": "media/team.jpg", "headline": "We shipped in 9 days"},
    {"id": "quote", "layout": "quote", "quote": "Specific beats clever.", "by": "Jane Doe", "role": "Founder, Acme",
     "image": "media/jane.jpg"},
    {"id": "number", "layout": "fact", "big": "9 days", "headline": "from launch to splashdown", "image": "media/x.jpg"},
    {"id": "steps", "layout": "list", "headline": "What we changed", "items": ["...", "..."]}
  ]
}

Sizes: "4:5" (1080x1350, the most room in the feed), "1:1" (1080x1080). Layouts:
- plain: the photo alone, cropped around `focus` (most posts: a real photo needs no words on it).
- photo: the photo with a short headline in a band at the top.
- quote: a short quote, the name and role under it, an optional round headshot.
- fact:  one big number or word over a darkened photo, a line under it.
- list:  a headline and 3 to 6 short numbered lines.
Text on LinkedIn images stays short: the post text carries the message, the image stops the scroll.
Writes images/<id>.jpg (sRGB JPEG, no metadata), contact-sheet.jpg and manifest.json (each image's
source photos and headline size on a phone), which li_check.py reads.
"""
import argparse, json, os, re, shutil, subprocess, sys, urllib.request

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lilib as P  # noqa: E402

LANCZOS = P.LANCZOS

W, H = 1000, 1250            # layout units; the file is saved 1080 wide
SIZES = {"4:5": 1250, "1:1": 1000}
OUT_W = 1080
S = 2                      # render at 2x and downscale: crisp text
FEED_W = 360               # an image's width in the LinkedIn feed on a phone
MARGIN = 64
HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "..", "fonts")
FONT_FILES = {
    "sans": ("Inter.ttf", "ofl/inter/Inter%5Bopsz,wght%5D.ttf"),
    "serif": ("InstrumentSerif-Regular.ttf", "ofl/instrumentserif/InstrumentSerif-Regular.ttf"),
}
DEFAULT_COLORS = {"bg": "#F6F1E7", "fg": "#1B1A17", "accent": "#B4441E"}
WARNINGS = []


def warn(msg):
    WARNINGS.append(msg)
    print("warning: " + msg, file=sys.stderr)


# ---------- fonts ----------

CUSTOM_FONT = {}        # kind -> a font file the user chose (brand.font_file), e.g. for CJK or Arabic


def font_path(kind):
    if kind in CUSTOM_FONT:
        return CUSTOM_FONT[kind]
    name, remote = FONT_FILES[kind]
    path = os.path.join(FONTS, name)
    if os.path.exists(path) and os.path.getsize(path) > 10000:
        return path
    os.makedirs(FONTS, exist_ok=True)   # some registries strip binary files: fetch the open font once
    url = "https://raw.githubusercontent.com/google/fonts/main/" + remote
    part = path + ".part"
    try:
        urllib.request.urlretrieve(url, part)
    except Exception:
        if shutil.which("curl"):
            subprocess.run(["curl", "-sfL", url, "-o", part], check=False)
    if not os.path.exists(part) or os.path.getsize(part) < 10000:
        if os.path.exists(part):
            os.remove(part)
        sys.exit(f"Font {name} missing and could not be downloaded from {url}")
    os.replace(part, path)
    return path


def missing_glyphs(text, f):
    """Characters the font can't draw (they'd show as empty boxes): emoji, CJK in a Latin font...
    A character renders exactly like the font's 'missing' box when the font has no glyph for it."""
    def ink(ch):
        size = max(8, int(getattr(f, "size", 40) * 2))
        im = Image.new("L", (size * 2, size * 2))
        ImageDraw.Draw(im).text((size // 2, size // 2), ch, font=f, fill=255)
        return im.tobytes()
    try:
        notdef = ink("\uffff")
    except Exception:
        return []
    out = []
    for ch in sorted(set(str(text))):
        if ch.isspace() or unicodedata_category(ch).startswith(("C", "Z")):
            continue
        try:
            if ink(ch) == notdef:
                out.append(ch)
        except Exception:
            out.append(ch)
    return out


def unicodedata_category(ch):
    import unicodedata
    return unicodedata.category(ch)


_cache = {}


def font(kind, size, weight="Regular"):
    key = (kind, size, weight)
    if key not in _cache:
        f = ImageFont.truetype(font_path(kind), size)
        if kind == "sans":
            try:
                f.set_variation_by_name(weight)
            except Exception:
                pass
        _cache[key] = f
    return _cache[key]


def hexcolor(v, fallback):
    v = (v or "").strip().lstrip("#")
    if re.fullmatch(r"[0-9a-fA-F]{6}", v):
        return "#" + v.upper()
    if re.fullmatch(r"[0-9a-fA-F]{3}", v):
        return "#" + "".join(c * 2 for c in v).upper()
    return fallback


def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def luminance(h):
    def ch(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(c) for c in rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


# ---------- images ----------

def load(base, rel, label="image"):
    if not isinstance(rel, str) or not rel:
        sys.exit(f"{label}: an image path is missing")
    path = P.resolve(base, rel)
    if not os.path.exists(path):
        sys.exit(f"{label}: image not found: {rel}")
    return P.open_image(path)


def load_logo(base, rel):
    path = P.resolve(base, rel)
    if not os.path.exists(path):
        sys.exit(f"logo not found: {rel}")
    im = ImageOps.exif_transpose(Image.open(path))
    return im.convert("RGBA")     # keeps transparency: pasted with its own alpha


def cover(im, w, h, focus=(0.5, 0.5), label=""):
    """Crop-to-fill around the subject. Warns when the photo is upscaled a lot (it will look soft)."""
    scale = max(w / im.width, h / im.height)
    if scale > 1.6 * S:
        warn(f"{label}: the photo is small for this space ({im.width}x{im.height}); it will look soft. Use a larger original.")
    nw, nh = max(w, round(im.width * scale)), max(h, round(im.height * scale))
    im = im.resize((nw, nh), LANCZOS)
    fx, fy = focus
    left = min(max(0, round(fx * nw - w / 2)), nw - w)
    top = min(max(0, round(fy * nh - h / 2)), nh - h)
    return im.crop((left, top, left + w, top + h))


# ---------- text ----------

def wrap(draw, text, f, width):
    lines = []
    for para in str(text).split("\n"):
        line = ""
        for word in para.split():
            trial = (line + " " + word).strip()
            if draw.textlength(trial, font=f) <= width or not line:
                line = trial
            else:
                lines.append(line)
                line = word
        lines.append(line)
    return lines


def balanced(draw, text, f, width):
    """Wrap, then even out the line lengths (no lone word on the last line) by narrowing the box
    while the number of lines stays the same."""
    lines = wrap(draw, text, f, width)
    if len(lines) < 2:
        return lines
    spread = lambda ls: max(draw.textlength(x, font=f) for x in ls) - draw.textlength(ls[-1], font=f)
    best, w = lines, width
    while w > width * 0.6:
        w -= width * 0.03
        trial = wrap(draw, text, f, w)
        if len(trial) != len(lines):
            break
        if spread(trial) < spread(best):
            best = trial
    return best


def fit(draw, text, kind, weight, width, max_h, start, minimum, max_lines, label):
    """Largest size (down to `minimum`) at which the text fits the box in at most max_lines."""
    size = start
    while True:
        f = font(kind, size * S, weight)
        lines = balanced(draw, text, f, width * S)
        lh = round(size * S * (1.08 if kind == "serif" else 1.14))
        if (len(lines) <= max_lines and lh * len(lines) <= max_h * S) or size <= minimum:
            if size <= minimum and (len(lines) > max_lines or lh * len(lines) > max_h * S):
                warn(f"{label}: '{text[:40]}...' is too long to stay readable; cut it to a few words")
            too_wide = [ln for ln in lines if draw.textlength(ln, font=f) > width * S]
            if too_wide and size > minimum // 2:
                size -= 2          # one long word: keep shrinking rather than cut it off
                continue
            if too_wide:
                warn(f"{label}: the word '{too_wide[0].split()[0]}' is wider than the image; shorten it")
            gone = missing_glyphs(text, f)
            if gone:
                warn(f"{label}: the font can't draw {' '.join(gone[:6])} (they'd show as empty boxes); "
                     "remove them or set brand.font_file to a font that has them")
            return f, lines, lh, size
        size -= 2


def draw_lines(draw, lines, f, lh, x, y, fill, align="left", width=None):
    for i, ln in enumerate(lines):
        lx = x
        if align == "center" and width:
            lx = x + (width * S - draw.textlength(ln, font=f)) / 2
        draw.text((lx, y + i * lh), ln, font=f, fill=fill)
    return y + lh * len(lines)


# ---------- layouts ----------

class Card:
    def __init__(self, spec, brand, base):
        self.spec, self.brand, self.base = spec, brand, base
        c = brand.get("colors") or {}
        self.bg = hexcolor(spec.get("bg") or c.get("bg"), DEFAULT_COLORS["bg"])
        self.fg = hexcolor(spec.get("fg") or c.get("fg"), DEFAULT_COLORS["fg"])
        self.accent = hexcolor(spec.get("accent") or c.get("accent"), DEFAULT_COLORS["accent"])
        self.kind = str(spec.get("font") or brand.get("font") or "serif").lower()
        if self.kind not in FONT_FILES:
            warn(f"{spec.get('id')}: font '{self.kind}' isn't serif or sans; using serif")
            self.kind = "serif"
        self.weight = "Bold" if self.kind == "sans" else "Regular"
        self.img = Image.new("RGB", (W * S, H * S), self.bg)
        self.d = ImageDraw.Draw(self.img)
        self.label = spec.get("id", "image")
        self.headline_px = None
        if contrast(self.bg, self.fg) < 4.5:
            warn(f"{self.label}: text and background colours are too close (contrast {contrast(self.bg, self.fg):.1f}:1, needs 4.5)")

    def photo(self, rel, w, h, focus=None):
        f = focus or self.spec.get("focus") or (0.5, 0.5)
        try:
            fx, fy = (min(1.0, max(0.0, float(v))) for v in f)
        except (TypeError, ValueError):
            warn(f"{self.label}: focus {f!r} must be two numbers from 0 to 1, like [0.5, 0.4]; using the centre")
            fx, fy = 0.5, 0.5
        return cover(load(self.base, rel, self.label), w * S, h * S, (fx, fy), self.label)

    def headline(self, x, y, width, max_h, start=96, minimum=56, max_lines=4, fill=None, align="left"):
        text = self.spec.get("headline", "")
        if not text:
            return y
        f, lines, lh, size = fit(self.d, text, self.kind, self.weight, width, max_h, start, minimum, max_lines, self.label)
        self.headline_px = size
        return draw_lines(self.d, lines, f, lh, x * S, y * S, fill or self.fg, align, width) / S

    def sub(self, x, y, width, fill=None, size=38, align="left"):
        text = self.spec.get("sub")
        if not text:
            return y
        f, lines, lh, _ = fit(self.d, text, "sans", "Medium", width, 160, size, 30, 3, self.label)
        return draw_lines(self.d, lines, f, lh, x * S, y * S, fill or self.fg, align, width) / S

    def footer(self, fill=None, on_photo=False):
        """The site (or logo) small, bottom centre: findable, never an ad."""
        b = self.brand
        y = H - 58
        logo = b.get("logo")
        if logo:
            lg = load_logo(self.base, logo)
            lg.thumbnail((260 * S, 44 * S))
            self.img.paste(lg, ((W * S - lg.width) // 2, (y - 6) * S), lg)
            return
        text = b.get("site") or b.get("name")
        if not text:
            return
        f = font("sans", 26 * S, "Medium")
        gone = missing_glyphs(text, f)
        if gone:
            warn(f"{self.label}: the font can't draw {' '.join(gone[:6])} in the footer (they'd show as empty boxes)")
        tw = self.d.textlength(text, font=f)
        if on_photo:
            pad = 16 * S
            box = [(W * S - tw) / 2 - pad, (y - 8) * S, (W * S + tw) / 2 + pad, (y + 34) * S]
            self.d.rounded_rectangle(box, radius=21 * S, fill=(0, 0, 0))
            fill = "#FFFFFF"
        self.d.text(((W * S - tw) / 2, y * S), text, font=f, fill=fill or self.fg)

    # --- layouts (geometry in fractions of H, so 4:5 and 1:1 both work) ---

    def layout_plain(self):
        self.img.paste(self.photo(self.spec["image"], W, H), (0, 0))
        if self.spec.get("headline"):
            warn(f"{self.label}: plain images carry no text; put the line in the post instead")

    def layout_photo(self):
        band = round(H * 0.26)
        self.img.paste(self.photo(self.spec["image"], W, H - band), (0, band * S))
        y = self.headline(MARGIN, round(band * 0.2), W - 2 * MARGIN, band - round(band * 0.3), start=80, minimum=50, max_lines=2)
        self.sub(MARGIN, y + 10, W - 2 * MARGIN, fill=self.accent, size=34)
        self.footer(on_photo=True)

    def layout_quote(self):
        q = self.spec.get("quote") or ""
        if not q:
            sys.exit(f"{self.label}: a quote card needs \"quote\"")
        top = round(H * 0.16)
        f, lines, lh, size = fit(self.d, "\u201c" + q + "\u201d", self.kind, self.weight, W - 2 * MARGIN, round(H * 0.5),
                                 92, 52, 6, self.label)
        self.headline_px = size
        y = draw_lines(self.d, lines, f, lh, MARGIN * S, top * S, self.fg) / S + 40
        self.d.rectangle([MARGIN * S, y * S, (MARGIN + 80) * S, (y + 6) * S], fill=self.accent)
        y += 34
        x = MARGIN
        if self.spec.get("image"):
            r = 64
            ph = self.photo(self.spec["image"], 2 * r, 2 * r)
            mask = Image.new("L", ph.size, 0)
            ImageDraw.Draw(mask).ellipse([0, 0, ph.width - 1, ph.height - 1], fill=255)
            self.img.paste(ph, (MARGIN * S, round(y * S)), mask)
            x = MARGIN + 2 * r + 28
        nf = font("sans", 40 * S, "SemiBold")
        self.d.text((x * S, (y + 18) * S), self.spec.get("by", ""), font=nf, fill=self.fg)
        if self.spec.get("role"):
            self.d.text((x * S, (y + 72) * S), self.spec["role"], font=font("sans", 32 * S, "Regular"), fill=self.accent)
        for t in (self.spec.get("by", ""), self.spec.get("role", "")):
            gone = missing_glyphs(t, nf) if t else []
            if gone:
                warn(f"{self.label}: the font can't draw {' '.join(gone[:6])} in the name or role")

    def layout_fact(self):
        if self.spec.get("image"):
            ph = self.photo(self.spec["image"], W, H)
            self.img.paste(Image.blend(ph, Image.new("RGB", ph.size, (0, 0, 0)), float(self.spec.get("darken", 0.45))), (0, 0))
            fg = "#FFFFFF"
        else:
            fg = self.fg
        big = str(self.spec.get("big", ""))
        bf, lines, lh, _ = fit(self.d, big, self.kind, self.weight, W - 2 * MARGIN, round(H * 0.3), 260, 110, 2, self.label)
        y = round(H * 0.3)
        draw_lines(self.d, lines, bf, lh, MARGIN * S, y * S, self.accent, "center", W - 2 * MARGIN)
        y = y + lh * len(lines) / S + 24
        y = self.headline(MARGIN, y, W - 2 * MARGIN, round(H * 0.22), start=70, minimum=46, align="center", fill=fg)
        self.sub(MARGIN, y + 16, W - 2 * MARGIN, fill=fg, align="center", size=34)
        self.footer(fill=fg)

    def layout_list(self):
        items = self.spec.get("items") or []
        if not 3 <= len(items) <= 6:
            warn(f"{self.label}: a list image reads best with 3 to 6 short lines, got {len(items)}")
        y = self.headline(MARGIN, round(H * 0.07), W - 2 * MARGIN, round(H * 0.2), start=80, minimum=50, max_lines=2)
        y += 36
        space = H - 110 - y
        each = min(space / max(1, len(items)), 170)
        nf = font("sans", 34 * S, "Bold")
        for i, it in enumerate(items, 1):
            iy = y + (i - 1) * each
            r = 26
            self.d.ellipse([MARGIN * S, (iy + 2) * S, (MARGIN + 2 * r) * S, (iy + 2 + 2 * r) * S], fill=self.accent)
            n = str(i)
            self.d.text(((MARGIN + r) * S - self.d.textlength(n, font=nf) / 2, (iy + 9) * S), n, font=nf, fill=self.bg)
            f, lines, lh, _ = fit(self.d, it, "sans", "Medium", W - 2 * MARGIN - 80, each - 8, min(46, int(each * 0.42)), 28, 2, self.label)
            draw_lines(self.d, lines, f, lh, (MARGIN + 80) * S, (iy + 6) * S, self.fg)
        self.footer()

    def render(self):
        layout = self.spec.get("layout", "plain")
        fn = getattr(self, "layout_" + layout, None)
        if not fn:
            sys.exit(f"{self.label}: unknown layout '{layout}' (plain, photo, quote, fact, list)")
        if layout in ("plain", "photo") and not self.spec.get("image"):
            sys.exit(f"{self.label}: the '{layout}' layout needs an image")
        fn()
        return self.img.resize((OUT_W, round(OUT_W * H / W)), LANCZOS)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("spec")
    ap.add_argument("--out", default="images")
    ap.add_argument("--only", help="render just these image ids, comma-separated (the manifest keeps the others)")
    ap.add_argument("--pdf", help="also save the rendered images, in order, as one PDF (a document carousel to upload in the app)")
    a = ap.parse_args()
    base = os.path.dirname(os.path.abspath(a.spec))
    try:
        with open(a.spec, encoding="utf-8") as f:
            spec = json.load(f)
    except (OSError, ValueError) as e:
        sys.exit(f"can't read {a.spec}: {e}")
    if not isinstance(spec, dict) or not isinstance(spec.get("images"), list):
        sys.exit(f"{a.spec} needs an \"images\" list (see the top of this script)")
    out = a.out if os.path.isabs(a.out) else os.path.join(base, a.out)
    os.makedirs(out, exist_ok=True)
    brand = spec.get("brand") or {}
    if brand.get("font_file"):
        ff = P.resolve(base, brand["font_file"])
        if not os.path.exists(ff):
            sys.exit(f"brand.font_file not found: {brand['font_file']}")
        CUSTOM_FONT["serif"] = CUSTOM_FONT["sans"] = ff
    P.check_ids(spec["images"], "image")
    only = set(a.only.split(",")) if a.only else None
    mpath = os.path.join(out, "manifest.json")
    old = {}
    if only and os.path.exists(mpath):
        try:
            old = {m["id"]: m for m in json.load(open(mpath, encoding="utf-8")).get("images", [])}
        except Exception:
            old = {}
    manifest, thumbs = [], []
    global H
    for p in spec["images"]:
        if only and p["id"] not in only:
            if p["id"] in old:
                manifest.append(old[p["id"]])
            continue
        before = len(WARNINGS)
        size = str(p.get("size") or spec.get("size") or "4:5")
        if size not in SIZES:
            sys.exit(f"{p['id']}: size must be 4:5 or 1:1, not {size}")
        H = SIZES[size]
        card = Card(p, brand, base)
        img = card.render()
        path = os.path.join(out, p["id"] + ".jpg")
        img.save(path, "JPEG", quality=90, optimize=True, progressive=True)
        hp = card.headline_px
        srcs = [p["image"]] if p.get("image") else [t["image"] for t in p.get("tiles", []) if isinstance(t, dict)]
        manifest.append({"id": p["id"], "file": P.rel(path, base), "layout": p.get("layout", "photo"),
                         "headline": p.get("headline", ""), "headline_px": hp,
                         "headline_px_in_feed": round(hp * FEED_W / W, 1) if hp else None,
                         "spec_dir": P.rel(base, out), "images": srcs,
                         "size": size, "warnings": WARNINGS[before:]})
        thumbs.append((p["id"], img))
        print(f"wrote {P.rel(path, base)}" + (f"  (headline {hp}px, {round(hp * FEED_W / W, 1)}px in the feed)" if hp else ""))
    with open(mpath, "w", encoding="utf-8") as f:
        json.dump({"images": manifest}, f, indent=1, ensure_ascii=False)
    if only:     # the contact sheet always shows every image in the manifest
        have = {i for i, _ in thumbs}
        for m in manifest:
            if m["id"] not in have:
                fp = P.resolve(base, m["file"])
                if os.path.exists(fp):
                    thumbs.append((m["id"], Image.open(fp).convert("RGB")))
        order = [p["id"] for p in spec["images"]]
        thumbs.sort(key=lambda t: order.index(t[0]) if t[0] in order else 999)
    thumbs = [t for _, t in thumbs]
    if thumbs:
        tw, gap = 300, 16
        th = max(int(tw * t.height / t.width) for t in thumbs)
        sheet = Image.new("RGB", (len(thumbs) * (tw + gap) + gap, th + 2 * gap), "#E9E9E9")
        for i, t in enumerate(thumbs):
            sheet.paste(t.resize((tw, int(tw * t.height / t.width)), LANCZOS), (gap + i * (tw + gap), gap))
        sheet.save(os.path.join(out, "contact-sheet.jpg"), quality=88)
        print(f"wrote {P.rel(os.path.join(out, 'contact-sheet.jpg'), base)}: look at it before going on")
    if a.pdf and thumbs:
        pdf = a.pdf if os.path.isabs(a.pdf) else os.path.join(base, a.pdf)
        sizes = {t.size for t in thumbs}
        if len(sizes) > 1:
            warn("the pages have different sizes; LinkedIn wants every page of a document the same size")
        thumbs[0].save(pdf, "PDF", save_all=True, append_images=thumbs[1:], resolution=150)
        print(f"wrote {P.rel(pdf, base)} ({len(thumbs)} pages): upload it in LinkedIn as a document; the posting API here doesn't send documents")
    if WARNINGS:
        print(f"{len(WARNINGS)} warning(s) above: fix them before checking", file=sys.stderr)


if __name__ == "__main__":
    main()
