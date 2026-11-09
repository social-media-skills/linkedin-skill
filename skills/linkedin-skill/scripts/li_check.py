#!/usr/bin/env python3
"""Check every post in plan.json against LinkedIn's limits and the patterns that cost reach or
trust, before anything is uploaded. Fix media that can be fixed safely, as new files.

    python3 scripts/li_check.py plan.json
    python3 scripts/li_check.py plan.json --fix         # converted copies in fixed/, plan updated

Checks, per post:
- text: up to 3,000 characters; the hook inside the "...see more" cut (about 140 characters on a
  phone, 210 on desktop, about 3 lines with media); engagement bait ("comment YES", "like if you
  agree"); stock AI phrasing; Unicode pseudo-bold (screen readers and search can't read it);
  one-line-per-sentence "broetry"; more than 3 hashtags; @names (they won't tag anyone through the
  API); a URL pasted in the text; against the account's own voice (voice.py), when there is one;
- media: no media, one image, 2 to 20 images, or one video, never mixed and never with a link card;
  images JPEG/PNG/GIF up to 5 MB, at least 552x276, from 3:1 wide to 4:5 tall (taller is cropped),
  under 36 megapixels; video MP4/MOV, H.264, 3 s to 15 min, up to 5 GB, from 1:2.4 to 2.4:1;
- link card: a full https:// address, no shorteners, no redirects (page.py), and the reach
  trade-off stated (reported, never confirmed by LinkedIn);
- accounts: the account exists; profile and Page don't get the same text or media the same day;
  at most one post a day per account, and the weekly count; the same picture or opening line
  already posted on that account (from the log).
Exit code 0 means nothing blocks; warnings are worth reading. Run it until it passes.
"""
import argparse, json, os, re, shutil, subprocess, sys
from collections import defaultdict
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lilib as P  # noqa: E402

BAIT = re.compile(
    r"(\bcomment\s+['\"\u2018\u201c]\w+['\"\u2019\u201d]"
    r"|\bcomment\s+(yes|no|me|guide|link|send|dm)\b"
    r"|\blike\s+(this\s+(post\s+)?)?if\s+you\s+(agree|want|think|like)"
    r"|\b(re)?post\s+(this\s+)?if\s+you|\u267b\ufe0f?\s*repost|\brepost\s+to\s+help"
    r"|\btag\s+(someone|a\s+friend|\d+\s+people|people\s+who|a\s+colleague)"
    r"|\bshare\s+if\s+you\s+agree"
    r"|\bdrop\s+(a|an)\s+\S+\s+(in\s+the\s+comments|below)"
    r"|\btype\s+['\"\u2018\u201c]?\w+['\"\u2019\u201d]?\s+(below|in\s+the\s+comments)"
    r"|\bfollow\s+me\s+for\s+more|^\s*agree\s*\?\s*$)", re.I | re.M)
AI_PHRASES = ["in today's fast-paced", "in today's world", "delve", "game-changer", "game changer", "unlock the",
              "unleash", "elevate your", "navigate the", "ever-evolving", "landscape of", "it's not just about",
              "here's the thing", "let that sink in", "read that again", "buckle up", "the secret sauce",
              "harness the power", "a testament to", "at the end of the day", "in conclusion", "furthermore",
              "moreover", "embark on", "tapestry", "paradigm shift", "synergy", "i'm thrilled to announce",
              "i'm humbled"]
BOLD = re.compile("[\U0001D400-\U0001D7FF]")
URL = re.compile(r"https?://\S+|www\.\S+", re.I)


class Report:
    def __init__(self):
        self.items = []

    def error(self, pid, msg):
        self.items.append(("error", pid, msg))

    def warn(self, pid, msg):
        self.items.append(("warning", pid, msg))

    def fixed(self, pid, msg):
        self.items.append(("fixed", pid, msg))


def fold(text, has_media):
    """What shows before "...see more": about 140 characters on a phone, or the first 3 lines
    with media, whichever comes first."""
    cut = text[:P.FOLD_MOBILE]
    lines = text.split("\n")
    if has_media and len(lines) > P.FOLD_LINES:
        three = "\n".join(lines[:P.FOLD_LINES])
        if len(three) < len(cut):
            cut = three
    return cut


def check_text(post, rep, voice):
    pid, text = post["id"], post.get("text", "")
    media = P.media_of(post)
    if not text.strip():
        (rep.warn if media else rep.error)(pid, "no text" + (": a post without words gets little reach; say what the media shows and why it matters" if media else ""))
        return
    if len(text) > P.TEXT_MAX:
        rep.error(pid, f"the text is {len(text)} characters (LinkedIn's limit is {P.TEXT_MAX:,})")
    first = text.strip().split("\n")[0]
    shown = fold(text.strip(), bool(media or post.get("link")))
    if len(first) > P.FOLD_MOBILE:
        rep.warn(pid, f"the first line is {len(first)} characters; on a phone only about {P.FOLD_MOBILE} show before \"...see more\", so the hook gets cut")
    if len(shown.strip()) < 40:
        rep.warn(pid, "very little shows before \"...see more\"; put the point in the first line")
    if BAIT.search(text):
        rep.warn(pid, f"engagement bait (\"{BAIT.search(text).group(0).strip()}\"): LinkedIn cuts reach for it; ask a real question instead")
    low = text.lower().replace("\u2019", "'").replace("\u2018", "'")
    found = [ph for ph in AI_PHRASES if ph in low]
    if found:
        rep.warn(pid, f"stock phrasing ({', '.join(found[:4])}): reads as generic AI text; say it in the user's own words")
    if "\u2014" in text or re.search(r"(?<!\d)\s?\u2013\s?(?!\d)", text):
        if not (voice or {}).get("uses_dashes"):
            rep.warn(pid, "long dashes: the user doesn't use them in their own posts, and readers take them as an AI tell")
    if BOLD.search(text):
        rep.warn(pid, "Unicode bold or italic letters: screen readers spell them out and LinkedIn search can't read them")
    tags = re.findall(r"(?<![\w&])#[^\W\d_]\w*", text)
    if len(tags) > 3:
        rep.warn(pid, f"{len(tags)} hashtags: they no longer spread a post; 0 to 3 that name the topic at most")
    if re.search(r"(?<![\w.])@[A-Za-z][\w.-]+", text):
        rep.warn(pid, "@names don't tag anyone through the posting API; write the name, and tag in the app if it matters")
    if URL.search(text):
        rep.warn(pid, "a URL in the text: use the post's link card (\"link\"), or leave the link out (see the trade-off below)")
    lines = [l for l in text.strip().split("\n") if l.strip() and not re.match(r"\s*(\d+[.)]|[-*\u2022])\s", l)]
    short = [l for l in lines if len(l.split()) <= 12 and re.search(r"[.!?:]\s*$", l.strip())]
    if len(lines) >= 6 and len(short) / len(lines) > 0.75:
        rep.warn(pid, "most lines are one short sentence (\"broetry\"): group sentences into real paragraphs")
    if voice:
        L = voice.get("length") or {}
        if L.get("high") and len(text) > L["high"] * 1.2:
            rep.warn(pid, f"{len(text)} characters: longer than any of the user's own posts (theirs run about {L.get('median')}, at most {L['high']})")
        if voice.get("first_person", 0) >= 0.6 and not re.search(r"\b(i|i'm|i've|i'd|my|me|we|our|us)\b", low):
            rep.warn(pid, "no I, my, we or our: the user writes in the first person; this reads like a press release")
        if voice.get("emoji_per_post", 1) == 0 and re.search("[\U0001F300-\U0001FAFF☀-➿]", text):
            rep.warn(pid, "emoji: the user never uses them in their own posts")
        if voice.get("hashtags_per_post", 1) == 0 and tags:
            rep.warn(pid, "hashtags: the user never uses them in their own posts")


def check_image(post, path, rep, fix, base, i):
    from PIL import Image
    pid = post["id"]
    try:
        with Image.open(path) as im:
            fmt, (w, h), mode = im.format, im.size, im.mode
    except Exception:
        fmt, w, h, mode = ("HEIC" if path.lower().endswith((".heic", ".heif")) else None), 0, 0, ""
        if not fmt:
            rep.error(pid, f"{os.path.basename(path)} can't be opened as an image")
            return
    problems = []
    if fmt == "MPO":      # phone JPEGs with a depth map: plain JPEG to LinkedIn
        fmt = "JPEG"
    if fmt not in P.IMAGE_TYPES:
        problems.append(f"{fmt} isn't accepted (JPEG, PNG or GIF)")
    if os.path.getsize(path) > P.IMAGE_MAX_MB * 1e6:
        problems.append(f"{os.path.getsize(path) / 1e6:.1f} MB is over {P.IMAGE_MAX_MB} MB")
    if w * h > P.IMAGE_MAX_PIXELS:
        problems.append(f"{w}x{h} is over LinkedIn's 36 megapixels")
    if mode in ("CMYK", "I;16", "I;16B", "I", "LAB"):
        problems.append(f"{mode} colours don't show right on screens (needs RGB)")
    if problems:
        if fix:
            out = os.path.join(base, "fixed", f"{pid}-{i + 1}.jpg")
            os.makedirs(os.path.dirname(out), exist_ok=True)
            im = P.open_image(path)
            im.thumbnail((2400, 3000))
            q = 88
            im.save(out, "JPEG", quality=q, optimize=True)
            while os.path.getsize(out) > P.IMAGE_MAX_MB * 1e6 and q > 60:
                q -= 8
                im.save(out, "JPEG", quality=q, optimize=True)
            post["media"][i] = P.rel(out, base)
            rep.fixed(pid, "; ".join(problems) + f": saved an RGB JPEG copy as {post['media'][i]}")
            return check_image(post, out, rep, False, base, i)
        for p in problems:
            rep.error(pid, f"{os.path.basename(path)}: {p} (run with --fix)")
        if not w:
            return
    try:
        with Image.open(path) as im:
            if (im.getexif() or {}).get(0x0112) in (5, 6, 7, 8):
                w, h = h, w      # shown rotated
    except Exception:
        pass
    if w < P.IMAGE_MIN_W or h < P.IMAGE_MIN_H:
        rep.error(pid, f"{os.path.basename(path)} is {w}x{h}; LinkedIn needs at least {P.IMAGE_MIN_W}x{P.IMAGE_MIN_H}")
    r = w / h
    if r < 0.8 - 0.01:
        rep.warn(pid, f"{os.path.basename(path)} is {w}x{h}, taller than 4:5: LinkedIn crops it in the feed. Render it at 1080x1350")
    elif r > 3:
        rep.warn(pid, f"{os.path.basename(path)} is wider than 3:1: LinkedIn crops it")
    elif r > 1.2:
        rep.warn(pid, f"{os.path.basename(path)} is landscape: it gets less room in the feed than 4:5 or 1:1")
    elif w < 1080 and h < 1080:
        rep.warn(pid, f"{os.path.basename(path)} is {w}x{h}: it may look soft; 1080 px wide is recommended")


def check_video(post, path, rep, fix, base):
    pid = post["id"]
    info = P.ffprobe(path)
    if info is None:
        rep.warn(pid, "ffprobe isn't installed, so the video wasn't checked (python3 scripts/check_setup.py)")
        return
    v = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
    if not v:
        rep.error(pid, "no video stream found")
        return
    dur, mb = P.duration(info), os.path.getsize(path) / 1e6
    w, h = int(v.get("width", 0) or 0), int(v.get("height", 0) or 0)
    rot = 0
    for sd in v.get("side_data_list", []) or []:
        try:
            rot = abs(int(float(sd.get("rotation", 0) or 0)))
        except (TypeError, ValueError):
            pass
    if rot % 180 == 90:
        w, h = h, w
    problems = []
    if not path.lower().endswith((".mp4", ".mov", ".m4v")):
        problems.append("the file isn't MP4 or MOV")
    if v.get("codec_name") not in ("h264", "hevc"):
        problems.append(f"the video codec is {v.get('codec_name')} (H.264 plays everywhere)")
    if v.get("pix_fmt", "yuv420p") not in ("yuv420p", "yuvj420p"):
        problems.append(f"the pixel format is {v.get('pix_fmt')} (8-bit 4:2:0 plays everywhere)")
    if problems and fix and shutil.which("ffmpeg"):
        out = os.path.join(base, "fixed", f"{pid}.mp4")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", path, "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out], check=True)
        post["media"] = [P.rel(out, base)]
        rep.fixed(pid, "; ".join(problems) + f": re-encoded as {post['media'][0]}")
        return check_video(post, out, rep, False, base)
    for p in problems:
        rep.error(pid, p + " (run with --fix)")
    if not dur:
        rep.warn(pid, "couldn't read the video's length")
    elif dur < P.VIDEO_MIN_S:
        rep.error(pid, f"{dur:.1f} s is shorter than LinkedIn's 3 s minimum")
    elif dur > P.VIDEO_MAX_S:
        rep.error(pid, f"{dur / 60:.1f} min is longer than LinkedIn's 15 min")
    elif dur > 90:
        rep.warn(pid, f"{dur:.0f} s: most people watch short videos in the feed; put the point in the first seconds")
    if mb > P.VIDEO_MAX_MB:
        rep.error(pid, f"{mb:.0f} MB is over 5 GB")
    r = w / h if h else 0
    if r and not (1 / 2.4 <= r <= 2.4):
        rep.error(pid, f"{w}x{h} is outside LinkedIn's 1:2.4 to 2.4:1")
    elif r > 1.2:
        rep.warn(pid, "landscape video gets less room in the feed; 4:5 or 1:1 (video.py fit) shows bigger")
    if max(w, h) > 4096:
        rep.error(pid, f"{w}x{h} is bigger than LinkedIn's 4096x2304")


def load_manifests(plan, base):
    out = {}
    for mf in plan.get("manifests", []) or []:
        mp = P.resolve(base, mf)
        try:
            entries = json.load(open(mp, encoding="utf-8")).get("images", [])
        except Exception:
            continue
        for m in entries:
            spec_dir = os.path.normpath(os.path.join(os.path.dirname(mp), m.get("spec_dir") or ".."))
            out[os.path.normpath(P.resolve(spec_dir, m["file"]))] = m
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("plan")
    ap.add_argument("--fix", action="store_true")
    ap.add_argument("--log", help="posts already published (default: posts-log.jsonl next to plan.json)")
    a = ap.parse_args()
    base = os.path.dirname(os.path.abspath(a.plan))
    plan = P.load_plan(a.plan)
    accounts, posts = plan["accounts"], plan["posts"]
    rules = dict({"max_per_week": 7}, **(plan.get("rules") or {}))
    if not posts:
        sys.exit("plan.json has no posts")
    if not accounts:
        sys.exit("plan.json has no accounts (references/plan-json.md)")
    P.check_ids(posts)
    posted = P.read_log(a.log or os.path.join(base, "posts-log.jsonl"))
    manifest = load_manifests(plan, base)
    rep = Report()
    voices = {}
    tz_of = lambda k: (accounts.get(k) or {}).get("timezone") or plan.get("timezone")
    prints = {}
    now = datetime.now()

    for post in posts:
        pid = post["id"]
        acc = accounts.get(post.get("account"))
        if not acc:
            rep.error(pid, f"account '{post.get('account')}' isn't in accounts ({', '.join(accounts)})")
            acc = {}
        elif acc.get("kind") not in ("profile", "page"):
            rep.error(pid, f"accounts.{post.get('account')}.kind must be profile or page")
        vpath = acc.get("voice")
        if vpath and vpath not in voices:
            try:
                voices[vpath] = json.load(open(P.resolve(base, vpath), encoding="utf-8"))
            except Exception:
                voices[vpath] = None
                rep.warn(pid, f"voice file {vpath} can't be read (voice.py makes it)")
        check_text(post, rep, voices.get(vpath))

        media = P.media_of(post)
        post["media"] = media
        kind = P.fmt_of(post)
        if media and post.get("link"):
            rep.error(pid, "a post has either media or a link card, not both: LinkedIn shows one or the other")
        videos = [m for m in media if m.lower().endswith(P.VIDEO_EXT)]
        if videos and len(media) > 1:
            rep.error(pid, "one video per post, and never mixed with images")
        if len(media) > P.IMAGES_MAX:
            rep.error(pid, f"{len(media)} images: LinkedIn takes 2 to {P.IMAGES_MAX}")
        prints[pid] = []
        sources = set()
        for i, m in enumerate(list(media)):
            path = P.resolve(base, m)
            if not os.path.exists(path):
                rep.error(pid, f"media file not found: {m}")
                continue
            if path.lower().endswith(P.VIDEO_EXT):
                check_video(post, path, rep, a.fix, base)
            else:
                check_image(post, path, rep, a.fix, base, i)
            path = P.resolve(base, post["media"][i] if i < len(post["media"]) else m)
            fp = P.media_fingerprint(path)
            if fp:
                prints[pid].append(fp)
            mf = manifest.get(os.path.normpath(path))
            if mf:
                sources |= set(mf.get("images", []))
                for w in mf.get("warnings", []):
                    (rep.error if "can't draw" in w else rep.warn)(pid, "render: " + w)
                if mf.get("headline_px_in_feed") and mf["headline_px_in_feed"] < 13:
                    rep.warn(pid, f"text on {os.path.basename(path)} is {mf['headline_px_in_feed']} px tall on a phone: too small to read")
        if len(media) > 1:
            ratios = set()
            for m in post["media"]:
                try:
                    from PIL import Image
                    with Image.open(P.resolve(base, m)) as im:
                        ratios.add(round(im.width / im.height, 2))
                except Exception:
                    pass
            if len(ratios) > 1:
                rep.warn(pid, "the images have different shapes; LinkedIn lays a set out by the first one, so others get cropped")
        dupes = [(j + 1, i + 1) for i in range(len(prints[pid])) for j in range(i) if P.same_picture(prints[pid][i], prints[pid][j])]
        if dupes:
            rep.warn(pid, f"images look the same: {', '.join(f'{a} and {b}' for a, b in dupes[:4])}{' and more' if len(dupes) > 4 else ''}")

        url, err = P.link_of(post)
        if err:
            rep.error(pid, err)
        elif url:
            if len(url) > P.LINK_MAX:
                rep.error(pid, f"link is {len(url)} characters (max {P.LINK_MAX})")
            if P.domain(url) in P.SHORTENERS:
                rep.error(pid, f"{P.domain(url)} is a link shortener: people can't see where it goes; use the page's own URL")
            page = None
            if post.get("page") and os.path.exists(P.resolve(base, post["page"])):
                try:
                    page = json.load(open(P.resolve(base, post["page"]), encoding="utf-8"))
                except Exception:
                    page = None
            if page:
                if page.get("final_url") and P.canonical(page["final_url"]) != P.canonical(url):
                    rep.warn(pid, f"the link redirects to {page['final_url']}; use the final URL")
                if (page.get("status") or 200) >= 400:
                    rep.error(pid, f"the page answers HTTP {page['status']}")
                if not page.get("image"):
                    rep.warn(pid, "the page has no preview image (og:image), so the link card may show none")
            rep.warn(pid, "link card: many practitioners measure less reach for posts with links (LinkedIn has never "
                          "confirmed it, and \"link in the first comment\" no longer seems to avoid it). Keep it if the "
                          "click is the point; otherwise leave the link out")

        at = P.parse_local(post.get("at"), tz_of(post.get("account")))
        if post.get("at") and not at:
            rep.error(pid, f"'at' must be a local time like 2026-11-16T08:30, not {post.get('at')!r}")
        elif at and at < datetime.now(P.zone(tz_of(post.get("account")))).replace(tzinfo=None) and not post.get("postId"):
            rep.warn(pid, f"{post['at']} is in the past; schedule.py will move it (remove 'at' and run it again)")
        if post.get("ai"):
            rep.warn(pid, "AI-made media: LinkedIn shows a Content Credentials label when the file carries its "
                          "C2PA data, which re-rendering removes; post the generator's original file and say so in the text")
        post["_sources"] = sources

    # same text or media on two accounts the same day
    ids = [p["id"] for p in posts]
    byid = {p["id"]: p for p in posts}
    for i, pid in enumerate(ids):
        for qid in ids[:i]:
            p, q = byid[pid], byid[qid]
            dp = P.parse_local(p.get("at"), tz_of(p.get("account")))
            dq = P.parse_local(q.get("at"), tz_of(q.get("account")))
            same_text = p.get("text", "").strip() and p.get("text", "").strip()[:200] == q.get("text", "").strip()[:200]
            same_media = any(P.same_picture(x, y) for x in prints.get(pid, []) for y in prints.get(qid, []))
            same_day = bool(dp and dq and dp.date() == dq.date())
            if p.get("account") != q.get("account") and (same_text or same_media) and same_day:
                rep.error(pid, f"same {'text' if same_text else 'media'} as {qid} on another account the same day: "
                               "space them out (schedule.py does it) or write each account its own post")
            elif p.get("account") != q.get("account") and same_text:
                rep.warn(pid, f"same text as {qid} on another account: write each account its own post (or reshare "
                              "the first one with a sentence of your own)")
            elif p.get("account") == q.get("account") and same_text:
                rep.error(pid, f"same opening as {qid} on the same account")

    # questions at the end: against the user's habit, per account
    for acc_key, acc in accounts.items():
        v = voices.get(acc.get("voice"))
        mine = [p for p in posts if p.get("account") == acc_key and (p.get("text") or "").strip()]
        if v and len(mine) >= 2:
            q = sum(1 for p in mine if p["text"].rstrip().endswith("?"))
            share = v.get("questions_at_end", 0)
            if q >= 2 and q / len(mine) > max(2 * share, share + 0.25):
                rep.warn(mine[-1]["id"], f"{q} of {len(mine)} posts for {acc_key} end on a question; the user does that in "
                                         f"{int(share * 100)}% of their posts. End most on a plain last line")

    # against the log: repeats on the same account
    for pid in ids:
        p = byid[pid]
        opening = P.fold(p.get("text", "").strip().split("\n")[0])
        for old in posted:
            if old.get("account") != p.get("account"):
                continue
            if opening.strip() and opening == P.fold(old.get("first_line", "")) and old.get("postId") != p.get("postId"):
                rep.warn(pid, f"opens with the same line as {old.get('id')} posted on {str(old.get('at') or '?')[:10]}")
            if any(P.same_picture(x, y) for x in prints.get(pid, []) for y in old.get("prints") or []) and old.get("postId") != p.get("postId"):
                rep.warn(pid, f"uses a picture already posted on {str(old.get('at') or '?')[:10]} ({old.get('id')})")

    # cadence
    per_day, per_week = defaultdict(list), defaultdict(list)
    plan_posts = {p.get("postId") for p in posts if p.get("postId")}
    events = [(p.get("account"), P.parse_local(p.get("at"), tz_of(p.get("account"))), p["id"]) for p in posts]
    events += [(o.get("account"), P.parse_local(o.get("at"), tz_of(o.get("account"))), f"{o.get('id')} (posted)")
               for o in posted if o.get("postId") not in plan_posts]
    for acc, d, pid in events:
        if d:
            per_day[(acc, d.date())].append(pid)
            per_week[(acc, d.isocalendar()[:2])].append(pid)
    for (acc, day), group in per_day.items():
        fresh = [g for g in group if not g.endswith("(posted)")]
        if len(group) > 1 and fresh:
            rep.warn(fresh[-1], f"{len(group)} posts on {day} for {acc}: one a day per account, so each gets its first hours")
    for (acc, wk), group in per_week.items():
        fresh = [g for g in group if not g.endswith("(posted)")]
        cap = P.int_or(rules.get("max_per_week"), 7, "rules.max_per_week")
        if len(group) > cap and fresh:
            rep.warn(fresh[-1], f"{len(group)} posts in week {wk[1]} for {acc}: more than {cap}; only post more if each one is as good")

    for p in posts:
        p.pop("_sources", None)
    if a.fix:
        P.save_plan(a.plan, plan)
    order = {"error": 0, "fixed": 1, "warning": 2}
    for kind, pid, msg in sorted(rep.items, key=lambda i: (order[i[0]], str(i[1]))):
        print(f"[{kind}] {pid}: {msg}")
    n_err = sum(1 for i in rep.items if i[0] == "error")
    n_warn = sum(1 for i in rep.items if i[0] == "warning")
    print(f"\n{len(posts)} posts checked: {n_err} error(s), {n_warn} warning(s)"
          + (". Nothing blocks." if not n_err else ". Fix the errors and run again."))
    with open(os.path.join(base, "check.json"), "w", encoding="utf-8") as f:
        json.dump({"errors": n_err, "warnings": n_warn,
                   "items": [{"kind": k, "post": p, "message": m} for k, p, m in rep.items]}, f, indent=1, ensure_ascii=False)
    sys.exit(1 if n_err else 0)


if __name__ == "__main__":
    main()
