#!/usr/bin/env python3
"""End-to-end test: voice, render, video, page reading, check (and every way it should fail),
schedule, preview, log and results, on a copy of the example in a work folder.

    python3 tests/run_pipeline.py work
"""
import http.server, json, os, shutil, socketserver, subprocess, sys, threading
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "skills", "linkedin-skill")
SCRIPTS = os.path.join(SKILL, "scripts")
PY = sys.executable
FF = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def run(*args, ok=True):
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONUTF8", "PYTHONIOENCODING")}
    r = subprocess.run([PY, os.path.join(SCRIPTS, args[0])] + list(args[1:]), capture_output=True, text=True,
                       cwd=WORK, encoding="utf-8", errors="replace", env=env)
    out = r.stdout + r.stderr
    print(f"$ {' '.join(args)}\n{out.strip()[:1500]}\n")
    if ok is True:
        assert r.returncode == 0, f"{args[0]} failed:\n{out}"
    elif ok is False:
        assert r.returncode != 0, f"{args[0]} should have failed:\n{out}"
    return out


def plan():
    return json.load(open(os.path.join(WORK, "plan.json"), encoding="utf-8"))


def write_plan(p, name="plan.json"):
    json.dump(p, open(os.path.join(WORK, name), "w", encoding="utf-8"), indent=1, ensure_ascii=False)


def expect(out, *needles):
    for n in needles:
        assert n in out, f"expected '{n}' in output"


def serve(folder):
    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=folder, **k)

        def log_message(self, *a):
            pass

        def do_GET(self):
            if self.path == "/old":
                self.send_response(301)
                self.send_header("Location", "/post.html")
                self.end_headers()
                return
            super().do_GET()
    srv = socketserver.TCPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def main():
    global WORK
    WORK = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "work")
    shutil.rmtree(WORK, ignore_errors=True)
    shutil.copytree(os.path.join(SKILL, "examples", "artemis-ii"), WORK,
                    ignore=shutil.ignore_patterns("preview", "images", "*.bak", "check.json", "posts-log.jsonl", "results.md"))
    from PIL import Image

    # 1. voice
    out = run("voice.py", "past-posts.txt", "--out", "voice.json")
    expect(out, "6 of the user's own posts", "Emoji: 0.0")
    open(os.path.join(WORK, "one.txt"), "w").write("Only one post")
    run("voice.py", "one.txt", "--out", "v1.json", ok=False)

    # 2. render, PDF, hostile inputs
    out = run("render_images.py", "images.json", "--out", "images/", "--pdf", "images/carousel.pdf")
    expect(out, "earthset.jpg", "splashdown.jpg", "carousel.pdf (6 pages)")
    run("render_images.py", "images.json", "--out", "images/", "--only", "earthset")
    with Image.open(os.path.join(WORK, "images", "contact-sheet.jpg")) as im:
        assert im.width > 1500, "--only must keep every image on the contact sheet"
    with Image.open(os.path.join(WORK, "images", "earthset.jpg")) as im:
        assert im.size == (1080, 1350) and not im.getexif()
    Image.new("RGBA", (400, 100), (0, 0, 0, 0)).save(os.path.join(WORK, "logo.png"))
    hostile = {"brand": {"name": "x", "logo": "logo.png", "font": "Sans"},
               "images": [{"id": "q", "layout": "quote", "quote": "Specific beats clever \U0001F680", "by": "Jane", "role": "Founder",
                           "image": "media/launch.jpg", "size": "1:1"},
                          {"id": "l", "layout": "list", "headline": "What we changed", "items": ["One", "Two", "Three"]},
                          {"id": "p", "layout": "photo", "image": "media/launch.jpg", "headline": "Supercalifragilisticexpialidocious-launches"}]}
    json.dump(hostile, open(os.path.join(WORK, "hostile.json"), "w"))
    out = run("render_images.py", "hostile.json", "--out", "hostile/")
    expect(out, "can't draw")
    with Image.open(os.path.join(WORK, "hostile", "q.jpg")) as im:
        assert im.size == (1080, 1080)
    json.dump({"images": [{"id": "../x", "layout": "plain", "image": "media/launch.jpg"}]}, open(os.path.join(WORK, "bad.json"), "w"))
    expect(run("render_images.py", "bad.json", ok=False), "becomes a file name")

    # 3. video
    if FF:
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=1280x720:rate=25:duration=6",
                        "-f", "lavfi", "-i", "sine=frequency=440:duration=6", "-shortest", "-c:v", "mpeg4", "-c:a", "aac",
                        os.path.join(WORK, "land.mov")], check=True)
        expect(run("video.py", "fit", "land.mov", "--ratio", "4:5", "--x", "0.4", "--out", "video/fit.mp4"), "1080x1350")
        expect(run("video.py", "fit", "land.mov", "--ratio", "1:1", "--fit", "pad", "--bg", "black", "--out", "video/sq.mp4"), "1080x1080")
        open(os.path.join(WORK, "t.srt"), "w").write("1\n00:00:00,500 --> 00:00:02,500\n[music] Hello from the <i>test</i>\n\n2\n00:00:03,000 --> 00:00:05,000\nSecond line\n")
        expect(run("video.py", "captions", "video/fit.mp4", "--srt", "t.srt", "--out", "video/cap.mp4"), "2 captions")
        open(os.path.join(WORK, "e.srt"), "w", encoding="utf-8").write("1\n00:00:00,500 --> 00:00:02,500\nLaunch \U0001F680 \u6708\n\n2\n00:01:00,000 --> 00:01:02,000\nAfter the end\n")
        expect(run("video.py", "captions", "video/fit.mp4", "--srt", "e.srt", "--out", "video/cap2.mp4", ok=False), "can't draw", "start after the video ends")
        many = "".join(f"{i + 1}\n00:00:0{i // 20},{(i % 20) * 50:03d} --> 00:00:0{i // 20},{(i % 20) * 50 + 40:03d}\nCue {i}\n\n" for i in range(110))
        open(os.path.join(WORK, "many.srt"), "w").write(many)
        expect(run("video.py", "captions", "video/fit.mp4", "--srt", "many.srt", "--out", "video/cap3.mp4"), "110 captions")
        expect(run("video.py", "stills", "media/launch.jpg", "media/earthset.jpg", "--seconds", "2", "--out", "video/st.mp4"), "1080x1350")
        run("video.py", "frames", "video/cap.mp4", "--out", "video/")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=navy:size=1080x1350:rate=30:duration=2",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", os.path.join(WORK, "short.mp4")], check=True)

    # 4. the example passes
    out = run("li_check.py", "plan.json")
    expect(out, "0 error(s)", "link card: many practitioners")

    # 5. every failure the check must catch
    p = plan()
    Image.open(os.path.join(WORK, "media", "launch.jpg")).resize((800, 1600)).save(os.path.join(WORK, "tall.jpg"))
    Image.open(os.path.join(WORK, "media", "launch.jpg")).resize((400, 200)).save(os.path.join(WORK, "tiny.jpg"))
    Image.open(os.path.join(WORK, "images", "earthset.jpg")).save(os.path.join(WORK, "earth.webp"))
    bad = json.loads(json.dumps(p))
    po = {x["id"]: x for x in bad["posts"]}
    po["earthset"]["text"] = "x" * 3100
    po["flyby-in-four"]["text"] += "\n\nComment YES if you agree! #space #moon #nasa #artemis #rockets"
    po["mission-page"]["text"] = ("In today's fast-paced world, this is a game-changer \U0001D5D5\U0001D5FC\U0001D5F9\U0001D5F1. "
                                  "Thanks @nasa, read it at https://bit.ly/x")
    po["mission-page"]["link"] = "https://bit.ly/abc"
    po["splashdown"]["media"] = ["images/splashdown.jpg", "video/liftoff.mp4"]
    po["liftoff-video"]["media"] = ["short.mp4"] if FF else ["video/liftoff.mp4"]
    bad["posts"].append({"id": "tall", "account": "me", "text": "A tall image post with a normal first line here.", "media": ["tall.jpg", "tiny.jpg"]})
    bad["posts"].append({"id": "webp", "account": "page", "text": "A webp image post with a normal first line.", "media": ["earth.webp"]})
    bad["posts"].append({"id": "both", "account": "me", "text": "Media and a link together in one post here.", "media": ["images/earthset.jpg"], "link": "https://www.nasa.gov/"})
    bad["posts"].append({"id": "many", "account": "page", "text": "Too many images in one post for LinkedIn.", "media": ["images/earthset.jpg"] * 21})
    bad["posts"].append({"id": "broetry", "account": "me", "text": "\n\n".join(["This changed everything."] * 9)})
    bad["posts"].append({"id": "copy", "account": "page", "text": p["posts"][0]["text"], "media": ["images/earthset.jpg"]})
    bad["posts"][0]["at"] = "2030-12-02T08:30"
    bad["posts"][-1]["at"] = "2030-12-02T12:00"
    write_plan(bad)
    out = run("li_check.py", "plan.json", ok=False)
    expect(out, "the text is 3100 characters", "engagement bait", "hashtags: they no longer",
           "stock phrasing (in today's fast-paced, game-changer)", "Unicode bold", "@names don't tag", "a URL in the text",
           "is a link shortener", "one video per post", "taller than 4:5", "LinkedIn needs at least 552x276",
           "WEBP isn't accepted", "either media or a link card", "21 images", "broetry",
           "same media as earthset on another account the same day")
    if FF:
        expect(out, "shorter than LinkedIn's 3 s")
    out = run("li_check.py", "plan.json", "--fix", ok=False)
    expect(out, "[fixed] webp")
    assert any(m.startswith("fixed/") for x in plan()["posts"] for m in x.get("media", []))

    # two posts on one day for one account, and too many in a week
    busy = json.loads(json.dumps(p))
    busy["rules"]["max_per_week"] = 3
    for i, x in enumerate(busy["posts"]):
        x["account"] = "me"
        x["at"] = f"2030-12-0{2 + (i // 2)}T0{8 + i % 2}:30"
    busy["posts"][3]["text"] = "Different first line so the copy check stays quiet here, and we keep it short.\n\nAnd more."
    write_plan(busy)
    out = run("li_check.py", "plan.json")
    expect(out, "2 posts on 2030-12-02 for me", "posts in week")

    # 6. schedule: days, one a day, topic on different days, per_week, stale requests, past start, Z
    for x in p["posts"]:
        x.pop("at", None)
    write_plan(p)
    os.makedirs(os.path.join(WORK, "requests"), exist_ok=True)
    open(os.path.join(WORK, "requests", "removed.json"), "w").write("{}")
    out = run("schedule.py", "plan.json", "--start", "2030-03-04")
    assert not os.path.exists(os.path.join(WORK, "requests", "removed.json"))
    sp = plan()
    days = [date.fromisoformat(x["at"][:10]) for x in sp["posts"]]
    assert len(set(days)) == len(days), f"topic posts must land on different days: {days}"
    twin = json.loads(json.dumps(p))
    for x in twin["posts"]:
        x.pop("topic", None)
    twin["posts"].append(dict(twin["posts"][0], id="twin", account="page"))
    write_plan(twin)
    run("schedule.py", "plan.json", "--start", "2030-03-04")
    tw = {x["id"]: x["at"][:10] for x in plan()["posts"]}
    assert tw["twin"] != tw["earthset"], "the same text on two accounts must not land on one day"
    bad_kind = json.loads(json.dumps(p))
    bad_kind["accounts"]["page"]["kind"] = "company"
    write_plan(bad_kind)
    expect(run("schedule.py", "plan.json", ok=False), "kind must be profile or page")
    both = json.loads(json.dumps(p))
    both["posts"][0]["link"] = "https://www.nasa.gov/"
    write_plan(both)
    expect(run("schedule.py", "plan.json", ok=False), "media and a link card can't go in one post")
    write_plan(p)
    run("schedule.py", "plan.json", "--start", "2030-03-04")
    sp = plan()
    for x in sp["posts"]:
        d = date.fromisoformat(x["at"][:10])
        allowed = sp["accounts"][x["account"]]["days"]
        assert ["mon", "tue", "wed", "thu", "fri", "sat", "sun"][d.weekday()] in allowed, (x["id"], d)
    me_week = {}
    for x in sp["posts"]:
        if x["account"] == "me":
            wk = date.fromisoformat(x["at"][:10]).isocalendar()[:2]
            me_week[wk] = me_week.get(wk, 0) + 1
    assert max(me_week.values()) <= 3
    body = json.load(open(os.path.join(WORK, "requests", "liftoff-video.json"), encoding="utf-8"))
    assert body["socialAccounts"][0]["platform"] == "LINKEDIN_PAGES" and body["schedule"]["scheduledFor"].endswith("Z")
    link = json.load(open(os.path.join(WORK, "requests", "mission-page.json"), encoding="utf-8"))
    assert link["socialAccounts"][0]["link"].startswith("https://www.nasa.gov") and "media" not in link["content"][0]
    sets = json.load(open(os.path.join(WORK, "requests", "flyby-in-four.json"), encoding="utf-8"))
    assert len(sets["content"][0]["media"]) == 4 and sets["socialAccounts"][0]["platform"] == "LINKEDIN"
    past = json.loads(json.dumps(p))
    write_plan(past)
    expect(run("schedule.py", "plan.json", "--start", "2020-01-01"), "is in the past; scheduling from today")
    z = plan()
    z["posts"][0]["at"] = "2030-06-01T12:00Z"
    write_plan(z)
    run("schedule.py", "plan.json", "--bodies-only")
    b = json.load(open(os.path.join(WORK, "requests", z["posts"][0]["id"] + ".json"), encoding="utf-8"))
    assert b["schedule"]["scheduledFor"] == "2030-06-01T12:00:00Z", b["schedule"]
    typo = json.loads(json.dumps(p))
    typo["posts"][4]["link"] = "nasa"
    write_plan(typo)
    expect(run("schedule.py", "plan.json", ok=False), "isn't a full https:// address")

    # 7. preview
    write_plan(p)
    run("schedule.py", "plan.json", "--start", "2030-03-04")
    bad_id = plan()
    bad_id["posts"][0]["id"] = "../../escaped"
    write_plan(bad_id, "plan-badid.json")
    expect(run("preview.py", "plan-badid.json", "--out", "preview-bad/", ok=False), "becomes a file name")
    run("preview.py", "plan.json", "--out", "preview/")
    html = open(os.path.join(WORK, "preview", "index.html"), encoding="utf-8").read()
    assert "Your Astronomy Club" in html and os.path.exists(os.path.join(WORK, "preview", "preview.png"))
    assert "<video" in html

    # 8. log, repeats, results
    lp = plan()
    for i, x in enumerate(lp["posts"]):
        x["postId"] = f"post-{i}"
        x["at"] = (date.today() - timedelta(days=3 + i)).isoformat() + "T08:30"
    lp["posts"][0]["postId"] = "<from posts_create>"
    write_plan(lp)
    with open(os.path.join(WORK, "posts-log.jsonl"), "w", encoding="utf-8") as f:
        f.write('[1]\n"x"\nnot json\n{"type": "post", "postId": "y"}\n{"type": "post", "postId": "z", "id": "orphan"}\n')
    expect(run("log.py", "record", "plan.json"), "logged 4 new post(s)")
    again = plan()
    again["posts"] = [dict(again["posts"][1], id="again", postId=None, at=None)]
    write_plan(again, "plan2.json")
    expect(run("li_check.py", "plan2.json"), "opens with the same line as flyby-in-four", "uses a picture already posted")
    metrics = {"socialAccountPosts": [
        {"postId": f"post-{i}", "analytics": {
            "impressions": [{"date": date.today().isoformat(), "collectedAt": "", "value": 1000 * (i + 1)}],
            "comments": [{"date": date.today().isoformat(), "collectedAt": "", "value": 5 + i}],
            "shares": [{"date": date.today().isoformat(), "collectedAt": "", "value": 2}]}} for i in range(1, 5)]}
    json.dump(metrics, open(os.path.join(WORK, "metrics.json"), "w"))
    open(os.path.join(WORK, "numbers.csv"), "w").write(f"post;measured;impressions;reactions;comments;saves\nflyby-in-four;{date.today().isoformat()};1.2K;40;n/a;3\n")
    out = run("log.py", "results", "--plan", "plan.json", "--metrics", "metrics.json", "--csv", "numbers.csv")
    expect(out, "## page", "## me", "1,200", "too few to name a best post")
    run("log.py", "results", "--metrics", "nope.json", "--plan", "plan.json", ok=False)
    json.dump({"socialAccountPosts": None}, open(os.path.join(WORK, "null.json"), "w"))
    run("log.py", "results", "--metrics", "null.json", "--plan", "plan.json")
    run("log.py", "results", "--csv", "missing.csv", "--plan", "plan.json", ok=False)

    # questions at the end against the user's habit
    qs = plan()
    for x in qs["posts"]:
        if x["account"] == "me":
            x["text"] = x["text"].rstrip(".") + " What do you think?"
    write_plan(qs, "plan-q.json")
    expect(run("li_check.py", "plan-q.json"), "end on a question; the user does that in 17%")

    # the same picture under another file name never lands on one day for two accounts
    shutil.copyfile(os.path.join(WORK, "images", "earthset.jpg"), os.path.join(WORK, "earth-copy.jpg"))
    pic = plan()
    for x in pic["posts"]:
        x.pop("at", None); x.pop("postId", None); x.pop("topic", None)
    pic["posts"].append({"id": "pic-twin", "account": "page", "text": "Another post with a different text altogether, about the photo.", "media": ["earth-copy.jpg"]})
    write_plan(pic, "plan-pic.json")
    run("schedule.py", "plan-pic.json", "--start", "2030-05-06")
    pp = {x["id"]: x["at"][:10] for x in json.load(open(os.path.join(WORK, "plan-pic.json"), encoding="utf-8"))["posts"]}
    assert pp["pic-twin"] != pp["earthset"], pp

    # bait rules: no false alarms on ordinary sentences
    calm = plan()
    calm["posts"] = [dict(calm["posts"][0], id="calm", postId=None, at=None, media=[],
                          text="Comment below if you have questions, I'm happy to share if you're interested. Do you agree? I\u2019m in 9\u20135 meetings.")]
    write_plan(calm, "plan-calm.json")
    out = run("li_check.py", "plan-calm.json")
    assert "engagement bait" not in out and "long dashes" not in out, out

    # 9. page.py
    site = os.path.join(WORK, "site")
    os.makedirs(site, exist_ok=True)
    open(os.path.join(site, "post.html"), "w").write(
        "<html><head><title>Launch</title><meta property=\"og:title\" content=\"Baker's launch notes\">"
        "<meta property='og:image' content='file:///etc/hosts'></head><body><main><h1>Launch notes</h1><p>"
        + "We launched the thing and here is what happened next. " * 6 + "</p><img src='file:///etc/passwd'></main></body></html>")
    srv = serve(site)
    url = f"http://127.0.0.1:{srv.server_address[1]}"
    expect(run("page.py", url + "/old", "--out", "page-test.json", "--images", "pageimgs"), "redirects to")
    pg = json.load(open(os.path.join(WORK, "page-test.json"), encoding="utf-8"))
    assert pg["title"].startswith("Baker's") and not os.listdir(os.path.join(WORK, "pageimgs"))
    srv.shutdown()

    print("ALL PIPELINE CHECKS PASSED")


if __name__ == "__main__":
    main()
