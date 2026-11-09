#!/usr/bin/env python3
"""Show each post the way the LinkedIn feed will: the name and headline, the text cut at
"...see more", the image or image grid, the video poster or the link card. One page to approve.

    python3 scripts/preview.py plan.json --out preview/

Writes preview/index.html (open it in a browser: phone and desktop widths, the full text under each
post) and preview/preview.png (every post at phone width: look at it yourself first; if the hook
isn't above "...see more" there, it isn't for most readers).
Image grids follow LinkedIn's layouts: 2 side by side; 3 and 4 as one large and the rest beside or
under it; 5 or more show 4 with "+N" on the last.
"""
import argparse, html, json, os, shutil, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lilib as P  # noqa: E402

PHONE_W = 390
HERE = os.path.dirname(os.path.abspath(__file__))


def esc(s):
    return html.escape(str(s or ""))


def font(size, weight="Regular"):
    from PIL import ImageFont
    try:
        f = ImageFont.truetype(os.path.join(HERE, "..", "fonts", "Inter.ttf"), size)
        f.set_variation_by_name(weight)
        return f
    except Exception:
        return ImageFont.load_default()


def poster(path):
    if path.lower().endswith(P.VIDEO_EXT):
        return P.frame_at(path, 0.0)
    return P.open_image(path)


def cut(text, has_media):
    """(shown, hidden?) at the fold: about 140 characters or 3 lines with media, at a word boundary."""
    t = text.strip()
    lines = t.split("\n")
    limit = P.FOLD_MOBILE
    if has_media and len(lines) > P.FOLD_LINES:
        limit = min(limit, len("\n".join(lines[:P.FOLD_LINES])))
    if len(t) <= limit:
        return t, False
    s = t[:limit]
    if " " in s[-25:]:
        s = s[: s.rfind(" ")]
    return s.rstrip(), True


def grid(imgs, w):
    """LinkedIn-style layout of 1 to 20 images in a box w wide. Returns a Pillow image."""
    from PIL import Image, ImageDraw
    from PIL import ImageOps
    n = len(imgs)
    if n == 1:
        im = imgs[0]
        r = max(0.8, min(1.91, im.width / im.height))
        return ImageOps.fit(im, (w, round(w / r)), P.LANCZOS)
    g = 3
    if n == 2:
        h = round(w * 0.62)
        out = Image.new("RGB", (w, h), "#FFFFFF")
        half = (w - g) // 2
        for i in range(2):
            out.paste(ImageOps.fit(imgs[i], (half, h), P.LANCZOS), (i * (half + g), 0))
        return out
    first_tall = imgs[0].height >= imgs[0].width
    shown = imgs[:4]
    rest = len(shown) - 1
    if first_tall:     # one large on the left, the rest stacked on the right
        h = round(w * 1.0)
        lw = round(w * 0.66)
        out = Image.new("RGB", (w, h), "#FFFFFF")
        out.paste(ImageOps.fit(shown[0], (lw, h), P.LANCZOS), (0, 0))
        ch = (h - g * (rest - 1)) // rest
        for i, im in enumerate(shown[1:]):
            out.paste(ImageOps.fit(im, (w - lw - g, ch), P.LANCZOS), (lw + g, i * (ch + g)))
    else:              # one large on top, the rest in a row under it
        th = round(w * 0.56)
        bh = round(w * 0.33)
        out = Image.new("RGB", (w, th + g + bh), "#FFFFFF")
        out.paste(ImageOps.fit(shown[0], (w, th), P.LANCZOS), (0, 0))
        cw = (w - g * (rest - 1)) // rest
        for i, im in enumerate(shown[1:]):
            out.paste(ImageOps.fit(im, (cw, bh), P.LANCZOS), (i * (cw + g), th + g))
    if n > 4:
        d = ImageDraw.Draw(out, "RGBA")
        if first_tall:
            box = (lw + g, (rest - 1) * (ch + g), w, h)
        else:
            box = ((rest - 1) * (cw + g), th + g, w, th + g + bh)
        d.rectangle(box, fill=(0, 0, 0, 140))
        label = f"+{n - 4}"
        f = font(30, "SemiBold")
        d.text(((box[0] + box[2] - d.textlength(label, font=f)) / 2, (box[1] + box[3]) / 2 - 18), label, font=f, fill="#FFFFFF")
    return out


def wrap(d, text, f, width):
    out = []
    for para in text.split("\n"):
        line = ""
        for word in para.split(" "):
            trial = (line + " " + word).strip() if line else word
            if d.textlength(trial, font=f) <= width or not line:
                line = trial
            else:
                out.append(line)
                line = word
        out.append(line)
    return out


def card_png(post, acc, base, page):
    """One post at phone width, as an image."""
    from PIL import Image, ImageDraw
    w = PHONE_W
    pad = 14
    tmp = Image.new("RGB", (w, 10))
    d = ImageDraw.Draw(tmp)
    body = font(15)
    name_f, sub_f = font(15, "SemiBold"), font(12)
    media = [P.resolve(base, m) for m in P.media_of(post) if os.path.exists(P.resolve(base, m))]
    shown, more = cut(post.get("text", ""), bool(media or post.get("link")))
    lines = wrap(d, shown + (" ...see more" if more else ""), body, w - 2 * pad)
    lh = 21
    head_h = 62
    text_h = lh * len(lines) + 10
    vis = None
    if media:
        imgs = [poster(m) for m in media]
        imgs = [i for i in imgs if i is not None]
        if imgs:
            vis = grid(imgs, w)
    elif post.get("link"):
        from PIL import ImageOps
        title = (page or {}).get("title") or P.domain(post["link"])
        card = None
        if page and page.get("card_file") and post.get("page"):
            cp = os.path.join(os.path.dirname(P.resolve(base, post["page"])), page["card_file"])
            if os.path.exists(cp):
                card = ImageOps.fit(P.open_image(cp), (w, round(w / 1.91)), P.LANCZOS)
        ch = card.height if card else 0
        vis = Image.new("RGB", (w, ch + 84), "#EEF3F8")
        if card:
            vis.paste(card, (0, 0))
        dd = ImageDraw.Draw(vis)
        for k, ln in enumerate(wrap(dd, title, font(14, "SemiBold"), w - 2 * pad)[:2]):
            dd.text((pad, ch + 12 + k * 20), ln, font=font(14, "SemiBold"), fill="#191919")
        dd.text((pad, ch + 58), P.domain(post["link"]), font=font(12), fill="#666666")
    vh = vis.height if vis else 0
    H = head_h + text_h + vh + 46
    out = Image.new("RGB", (w, H), "#FFFFFF")
    d = ImageDraw.Draw(out)
    d.ellipse([pad, 12, pad + 40, 52], fill="#C9D3DD" if acc.get("kind") == "profile" else "#2F3B4A")
    d.text((pad + 52, 13), str(acc.get("name") or post.get("account") or "(no account)"), font=name_f, fill="#191919")
    d.text((pad + 52, 33), (acc.get("headline") or ("Company Page" if acc.get("kind") == "page" else ""))[:46], font=sub_f, fill="#666666")
    y = head_h
    for i, ln in enumerate(lines):
        if more and i == len(lines) - 1 and ln.endswith("...see more"):
            pre = ln[: -len("...see more")]
            d.text((pad, y), pre, font=body, fill="#191919")
            d.text((pad + d.textlength(pre, font=body), y), "...see more", font=body, fill="#666666")
        else:
            d.text((pad, y), ln, font=body, fill="#191919")
        y += lh
    y = head_h + text_h
    if vis:
        out.paste(vis, (0, y))
        if P.fmt_of(post) == "video":
            cx, cy = w // 2, y + vh // 2
            d.ellipse([cx - 26, cy - 26, cx + 26, cy + 26], fill="#000000")
            d.polygon([(cx - 8, cy - 14), (cx - 8, cy + 14), (cx + 16, cy)], fill="#FFFFFF")
        y += vh
    d.line([(pad, y + 10), (w - pad, y + 10)], fill="#E8E8E8")
    for k, lab in enumerate(["Like", "Comment", "Repost", "Send"]):
        d.text((pad + 8 + k * 92, y + 18), lab, font=font(13, "SemiBold"), fill="#666666")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("plan")
    ap.add_argument("--out", default="preview")
    a = ap.parse_args()
    from PIL import Image
    base = os.path.dirname(os.path.abspath(a.plan))
    plan = P.load_plan(a.plan)
    accounts = plan["accounts"]
    out = a.out if os.path.isabs(a.out) else os.path.join(base, a.out)
    mdir = os.path.join(out, "media")
    os.makedirs(mdir, exist_ok=True)
    P.check_ids(plan["posts"])
    posts = sorted(plan["posts"], key=lambda p: p.get("at") or "")
    cards, sections = [], []
    for p in posts:
        acc = accounts.get(p.get("account")) or {}
        page = None
        if p.get("page") and os.path.exists(P.resolve(base, p["page"])):
            try:
                page = json.load(open(P.resolve(base, p["page"]), encoding="utf-8"))
            except Exception:
                page = None
        missing = [m for m in P.media_of(p) if not os.path.exists(P.resolve(base, m))]
        if missing:
            print(f"{p['id']}: media missing ({', '.join(missing)}); shown without it")
        card = card_png(p, acc, base, page)
        cards.append(card)
        name = f"{p['id']}.png"
        card.save(os.path.join(mdir, name))
        files = []
        for i, m in enumerate(P.media_of(p)):
            src = P.resolve(base, m)
            if os.path.exists(src):
                fn = f"{p['id']}-{i + 1}{os.path.splitext(src)[1].lower()}"
                shutil.copyfile(src, os.path.join(mdir, fn))
                files.append(fn)
        d = P.parse_local(p.get("at"), acc.get("timezone") or plan.get("timezone"))
        when = d.strftime("%a %d %b %Y, %H:%M") if d else ("now" if p.get("now") else "not scheduled yet")
        url, _ = P.link_of(p)
        media_html = "".join(
            (f'<video src="media/{esc(f)}" controls muted playsinline></video>' if f.lower().endswith(P.VIDEO_EXT)
             else f'<img src="media/{esc(f)}" alt="">') for f in files)
        sections.append(f'''<section>
<h2>{esc(p["id"])} <span>{esc(acc.get("name") or p.get("account"))} ({esc(acc.get("kind"))}), {esc(when)}</span></h2>
<div class="row"><img class="card" src="media/{esc(name)}" alt="How the post shows in the feed on a phone">
<div class="full"><p class="text">{esc(p.get("text")).replace(chr(10), "<br>")}</p>
{f'<p class="link">Link card: <a href="{esc(url)}">{esc(url)}</a></p>' if url and P.is_url(url) else ""}
<div class="media">{media_html}</div></div></div></section>''')
    if cards:
        gap = 24
        W = len(cards) * (PHONE_W + gap) + gap
        Hh = max(c.height for c in cards) + 2 * gap
        sheet = Image.new("RGB", (W, Hh), "#F4F2EE")
        for i, c in enumerate(cards):
            sheet.paste(c, (gap + i * (PHONE_W + gap), gap))
        sheet.save(os.path.join(out, "preview.png"))
    doc = f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>LinkedIn preview</title>
<style>
:root{{--bg:#F4F2EE;--fg:#191919;--muted:#666;--card:#fff;--line:#e8e8e8}}
@media (prefers-color-scheme:dark){{:root{{--bg:#1b1f23;--fg:#eee;--muted:#aaa;--card:#2a2f35;--line:#3a3f45}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,sans-serif}}
main{{max-width:1100px;margin:0 auto;padding:24px 16px 64px}} h1{{font-size:22px;margin:0 0 4px}} .lede{{color:var(--muted);margin:0 0 24px}}
section{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin:0 0 20px}}
h2{{font-size:17px;margin:0 0 12px}} h2 span{{color:var(--muted);font-weight:400;font-size:14px}}
.row{{display:grid;grid-template-columns:{PHONE_W}px minmax(0,1fr);gap:24px;align-items:start}}
.card{{width:{PHONE_W}px;max-width:100%;border:1px solid var(--line);border-radius:8px}}
.text{{white-space:normal;margin:0 0 12px}} .link{{color:var(--muted);overflow-wrap:anywhere}}
.media img,.media video{{max-width:220px;margin:0 8px 8px 0;border-radius:6px;vertical-align:top}}
@media (max-width:760px){{.row{{grid-template-columns:1fr}}}}
</style></head><body><main>
<h1>{len(posts)} LinkedIn posts, ready for a yes</h1>
<p class="lede">Left: each post as the feed shows it on a phone, cut at "...see more". Right: the full text and media.</p>
{"".join(sections)}
</main></body></html>'''
    with open(os.path.join(out, "index.html"), "w", encoding="utf-8") as f:
        f.write(doc)
    print(f"wrote {P.rel(os.path.join(out, 'index.html'), os.getcwd())} and preview.png (look at preview.png first)")


if __name__ == "__main__":
    main()
