#!/usr/bin/env python3
"""Read the page a post will link to: where the link really lands, its title, description, preview
image and headings, so the link card shows what you expect and the post uses the page's own facts.

    python3 scripts/page.py https://example.com/post --out page.json
    python3 scripts/page.py https://example.com/post --out page.json --images media/   # also save its images

Standard library only. Follows redirects and records the final URL; flags link shorteners.
Saves only pages and images the user may use.
"""
import argparse, html, io, ipaddress, json, os, re, socket, subprocess, shutil, sys, urllib.error, urllib.parse, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lilib import SHORTENERS, domain  # noqa: E402

MAX_BYTES = 8_000_000


class WebOnly(urllib.request.HTTPRedirectHandler):
    """Follow redirects only to http(s): never file://, ftp:// or anything else."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlsplit(newurl).scheme not in ("http", "https"):
            raise urllib.error.URLError(f"refused a redirect to {newurl}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


OPENER = urllib.request.build_opener(WebOnly)


def web_url(u):
    return urllib.parse.urlsplit(u).scheme in ("http", "https")


def private_host(u):
    """True for localhost, private and link-local addresses (never fetched for images)."""
    host = urllib.parse.urlsplit(u).hostname or ""
    try:
        addrs = {ai[4][0] for ai in socket.getaddrinfo(host, None)}
    except OSError:
        return True
    for a in addrs:
        ip = ipaddress.ip_address(a.split("%")[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return True
    return False

UA = "Mozilla/5.0 (compatible; linkedin-skill/1.0; +https://github.com/social-media-skills/linkedin-skill)"


def fetch(url, binary=False):
    if not web_url(url):
        raise urllib.error.URLError(f"only http(s) addresses are read, not {url}")
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en"})
    try:
        with OPENER.open(req, timeout=30) as r:
            data = r.read(MAX_BYTES)
            return r.geturl(), r.status, data if binary else data.decode(r.headers.get_content_charset() or "utf-8", "replace")
    except urllib.error.HTTPError as e:
        body = e.read(MAX_BYTES) if hasattr(e, "read") else b""
        return e.geturl() or url, e.code, body if binary else body.decode("utf-8", "replace")
    except urllib.error.URLError as e:
        if "CERTIFICATE_VERIFY_FAILED" in str(e) and shutil.which("curl"):
            out = subprocess.run(["curl", "-sL", "--proto", "=http,https", "--proto-redir", "=http,https",
                                  "--max-filesize", str(MAX_BYTES), "-A", UA, "-w", "\n%{url_effective} %{http_code}", url],
                                 capture_output=True, timeout=60)
            body, _, tail = out.stdout.rpartition(b"\n")
            final, _, code = tail.decode().rpartition(" ")
            return final, int(code or 0), body if binary else body.decode("utf-8", "replace")
        raise


def attr(tag, name):
    m = re.search(rf'\b{name}\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s>]+))', tag, re.I)
    return html.unescape(next((g for g in m.groups() if g is not None), "")).strip() if m else ""


def meta(doc, name):
    for tag in re.findall(r"<meta\b[^>]*>", doc, re.I):
        if (attr(tag, "property") or attr(tag, "name")).lower() == name.lower():
            return attr(tag, "content")
    return ""


def text_of(fragment):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("url")
    ap.add_argument("--out", default="page.json")
    ap.add_argument("--images", help="folder to save the page's large images into")
    a = ap.parse_args()

    notes = []
    if "://" not in a.url:
        a.url = "https://" + a.url
    if not web_url(a.url):
        sys.exit("give a web address (http or https)")
    if domain(a.url) in SHORTENERS:
        notes.append(f"{domain(a.url)} is a link shortener: people can't see where it goes. Use the page's own URL.")
    try:
        final, status, doc = fetch(a.url)
    except Exception as e:
        sys.exit(f"couldn't read {a.url}: {e}")
    if final.rstrip("/") != a.url.rstrip("/"):
        notes.append(f"The link redirects to {final}. Use the final URL.")
    if status >= 400:
        notes.append(f"The page answered HTTP {status}.")
    body = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", doc, flags=re.S | re.I)
    # the page's own content, not its menus: <article> or <main> when the page has one
    for tag in ("article", "main"):
        m = re.search(rf"<{tag}[^>]*>(.*)</{tag}>", body, re.S | re.I)
        if m and len(text_of(m.group(1))) > 200:
            body = m.group(1)
            break
    else:
        body = re.sub(r"<(nav|header|footer|aside)[^>]*>.*?</\1>", " ", body, flags=re.S | re.I)
    title = text_of((re.search(r"<title[^>]*>(.*?)</title>", doc, re.S | re.I) or [None, ""])[1])
    heads = [text_of(h) for h in re.findall(r"<h[1-3][^>]*>(.*?)</h[1-3]>", body, re.S | re.I)]
    heads = [h for h in heads if 2 < len(h) < 140][:30]
    canonical = next((attr(t, "href") for t in re.findall(r"<link\b[^>]*>", doc, re.I) if attr(t, "rel").lower() == "canonical"), "")
    imgs = []
    og = meta(doc, "og:image")
    if og:
        imgs.append(og)
    for tag in re.findall(r"<img\b[^>]*>", body, re.I):
        src = attr(tag, "src") or attr(tag, "data-src")
        if not src or src.startswith("data:") or re.search(r"(sprite|icon|logo|avatar|pixel|tracking)", src, re.I):
            continue
        imgs.append({"src": urllib.parse.urljoin(final, src), "alt": attr(tag, "alt")})
    seen, images = set(), []
    for im in imgs:
        src = im if isinstance(im, str) else im["src"]
        src = urllib.parse.urljoin(final, src)
        if web_url(src) and src not in seen:
            seen.add(src)
            images.append({"src": src, "alt": "" if isinstance(im, str) else im["alt"], "og": isinstance(im, str)})
    paragraphs = [text_of(p) for p in re.findall(r"<p[^>]*>(.*?)</p>", body, re.S | re.I)]
    text = " ".join(p for p in paragraphs if len(p) > 40)[:6000]

    page = {"url": a.url, "final_url": final, "status": status, "canonical": canonical,
            "title": meta(doc, "og:title") or title, "html_title": title,
            "description": meta(doc, "og:description") or meta(doc, "description"),
            "image": og if web_url(urllib.parse.urljoin(final, og or "")) and og else "", "headings": heads, "text": text, "images": images[:40], "notes": notes,
            "open_graph": bool(meta(doc, "og:type") or meta(doc, "og:title") or og or re.search(r'application/ld\+json', doc))}

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    if a.images:
        os.makedirs(a.images, exist_ok=True)
        saved = 0
        from PIL import Image
        kinds = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp", "GIF": ".gif"}
        for i, im in enumerate(images[:20]):
            if private_host(im["src"]):
                continue
            try:
                _, code, data = fetch(im["src"], binary=True)
            except Exception:
                continue
            if code >= 400 or len(data) < 30_000 or len(data) >= MAX_BYTES:
                continue  # errors, icons and thumbnails
            try:
                with Image.open(io.BytesIO(data)) as pic:
                    ext = kinds.get(pic.format)
            except Exception:
                ext = None
            if not ext:
                continue  # not a picture
            path = os.path.join(a.images, f"page-{i + 1:02d}{ext}")
            with open(path, "wb") as f:
                f.write(data)
            im["file"] = path.replace("\\", "/")
            saved += 1
        print(f"saved {saved} large images to {a.images}")

    # the link card's image, for the preview (LinkedIn shows the page's og:image)
    if og and web_url(urllib.parse.urljoin(final, og)) and not private_host(urllib.parse.urljoin(final, og)):
        try:
            from PIL import Image
            _, code, data = fetch(urllib.parse.urljoin(final, og), binary=True)
            if code < 400 and len(data) < MAX_BYTES:
                with Image.open(io.BytesIO(data)) as pic:
                    card = os.path.splitext(a.out)[0] + "-card.jpg"
                    im = pic.convert("RGB")
                    im.thumbnail((1200, 1200))
                    im.save(card, "JPEG", quality=85)
                    page["card_file"] = os.path.basename(card)
        except Exception:
            pass
    page["text"] = page["text"][:1500]
    page["images"] = page["images"][:10]
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(page, f, indent=1, ensure_ascii=False)
    print(f"{page['title']}\n  final URL: {final}\n  {len(heads)} headings, {len(images)} images, "
          f"{'has' if page['open_graph'] else 'no'} Open Graph data, {'a' if page['image'] else 'no'} preview image")
    for n in notes:
        print("note: " + n)
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
