#!/usr/bin/env python3
"""Keep a log of every post published (so nothing is repeated) and learn what works for this account.

    python3 scripts/log.py record plan.json                                   # add published posts
    python3 scripts/log.py results --plan plan.json --metrics metrics.json    # Page numbers from WoopSocial
    python3 scripts/log.py results --plan plan.json --csv numbers.csv         # numbers copied from LinkedIn

record: every post in the plan with a WoopSocial `postId` (set it from posts_create) is appended once
  to posts-log.jsonl next to the plan, with its first line and fingerprints of its pictures, so
  li_check.py can spot repeats. Placeholder ids and posts marked "status": "FAILED" are skipped.
results: metrics.json is one or more saved responses of WoopSocial's social_account_posts_list
  (company Pages: impressions, clicks, reactions, comments, shares). Personal profiles: LinkedIn
  doesn't give post numbers to posting apps, so copy them from the post's analytics into a CSV:
  post,measured,impressions,reactions,comments,reposts,saves,sends,profile_views,followers
  (post = the plan id; measured = YYYY-MM-DD; any subset of columns; comma or semicolon separated;
  "1.2K" and "1,234" are read).

How it judges, so it doesn't mislead:
- A post is judged from day 2 (most of its reach comes in the first day or two) and again at day 7.
- Each post is compared with the same account's own posts, never a benchmark: impressions against
  the account's median, then conversation (comments, reposts, saves, sends) per 1,000 impressions.
- A best post is named once an account has 6 posts past day 2; numbers that weren't reported are
  "not reported", never estimated.
Python 3.9+, standard library only.
"""
import argparse, csv, json, os, re, statistics, sys
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lilib as P  # noqa: E402

ALIASES = {"impressions": "impressions", "uniqueimpressions": "reached",
           "membersreached": "reached", "reached": "reached", "likes": "reactions", "reactions": "reactions",
           "comments": "comments", "shares": "reposts", "reposts": "reposts", "saves": "saves", "sends": "sends",
           "clicks": "clicks", "profileviews": "profile_views", "followers": "followers",
           "followersgained": "followers", "engagementrate": "engagement_rate"}
TALK = ("comments", "reposts", "saves", "sends")
JUDGE_DAY, MIN_RANKED = 2, 6


def number(v):
    t = str(v or "").strip().replace(" ", "").replace(" ", "")
    if not t or t.lower() in ("n/a", "na", "-", "--"):
        return None
    mult = 1
    if t[-1:].lower() in ("k", "m"):
        mult, t = (1000 if t[-1].lower() == "k" else 1_000_000), t[:-1]
    if re.fullmatch(r"\d{1,3}(,\d{3})+(\.\d+)?", t):
        t = t.replace(",", "")
    elif re.fullmatch(r"\d+,\d+", t):
        t = t.replace(",", ".")
    try:
        return float(t) * mult
    except ValueError:
        return None


def norm(k):
    return ALIASES.get(re.sub(r"[^a-z]", "", (k or "").lower()))


def cmd_record(a):
    base = os.path.dirname(os.path.abspath(a.plan))
    log = a.log or os.path.join(base, "posts-log.jsonl")
    plan = P.load_plan(a.plan)
    have = {r.get("postId") for r in P.read_log(log)}
    added, skipped = 0, []
    with open(log, "a", encoding="utf-8") as f:
        for p in plan["posts"]:
            pid = str(p.get("postId") or "")
            if not pid or pid.startswith("<") or pid in have or not p.get("id"):
                continue
            if str(p.get("status", "")).upper() == "FAILED":
                skipped.append(p["id"])
                continue
            acc = plan["accounts"].get(p.get("account"), {})
            prints = [fp for fp in (P.media_fingerprint(P.resolve(base, m)) for m in P.media_of(p)
                                    if os.path.exists(P.resolve(base, m))) if fp]
            f.write(json.dumps({
                "type": "post", "logged": datetime.now().isoformat(timespec="seconds"), "id": p["id"],
                "postId": pid, "account": p.get("account"), "kind": acc.get("kind"),
                "timezone": acc.get("timezone") or plan.get("timezone"),
                "at": p.get("at") or datetime.now().isoformat(timespec="minutes"),
                "format": P.fmt_of(p), "first_line": (p.get("text") or "").strip().split("\n")[0][:200],
                "chars": len(p.get("text") or ""), "link": bool(p.get("link")), "prints": prints,
            }, ensure_ascii=False) + "\n")
            added += 1
    print(f"logged {added} new post(s) to {P.rel(log, os.getcwd())}")
    if skipped:
        print("not logged (status FAILED): " + ", ".join(skipped))


def latest(v):
    if isinstance(v, (int, float)):
        return None, v
    best = None
    for x in v if isinstance(v, list) else []:
        if isinstance(x, dict) and isinstance(x.get("value"), (int, float)):
            d = (x.get("date") or x.get("collectedAt") or "")[:10]
            if best is None or d >= best[0]:
                best = (d, x["value"])
    return best or (None, None)


def cmd_results(a):
    log = a.log or (os.path.join(os.path.dirname(os.path.abspath(a.plan)), "posts-log.jsonl") if a.plan else "posts-log.jsonl")
    if not os.path.exists(log):
        sys.exit(f"no post log at {log}: pass --plan plan.json (the log sits next to it) or --log")
    rows = P.read_log(log)
    posts = {r["postId"]: r for r in rows if r.get("type") == "post" and r.get("id")}
    by_id = {r["id"]: r for r in posts.values()}
    snaps = []
    if a.metrics:
        try:
            data = json.load(open(a.metrics, encoding="utf-8"))
        except (OSError, ValueError) as e:
            sys.exit(f"can't read {a.metrics}: {e}. Save the social_account_posts_list response as JSON")
        for page in data if isinstance(data, list) else [data]:
            for it in (page.get("socialAccountPosts") or []) if isinstance(page, dict) else []:
                post = posts.get(str(it.get("postId"))) if isinstance(it, dict) else None
                if not post:
                    continue
                vals, when = {}, ""
                for k, v in (it.get("analytics") or {}).items():
                    n = norm(k)
                    if n:
                        d, val = latest(v)
                        if val is not None:
                            vals[n] = val
                            when = max(when, d or "")
                if vals:
                    snaps.append({"type": "snapshot", "postId": post["postId"], "measured": when or date.today().isoformat(),
                                  "source": "woopsocial", **vals})
    if a.csv:
        try:
            raw = open(a.csv, encoding="utf-8-sig").read()
        except OSError as e:
            sys.exit(f"can't read {a.csv}: {e}")
        delim = ";" if raw.split("\n", 1)[0].count(";") > raw.split("\n", 1)[0].count(",") else ","
        import io
        if True:
            for r in csv.DictReader(io.StringIO(raw), delimiter=delim):
                post = by_id.get((r.get("post") or "").strip())
                if not post:
                    print(f"note: CSV row '{r.get('post')}' matches no logged post id", file=sys.stderr)
                    continue
                vals = {}
                for k, v in r.items():
                    n = norm(k)
                    if n:
                        x = number(v)
                        if x is not None:
                            vals[n] = x
                snaps.append({"type": "snapshot", "postId": post["postId"],
                              "measured": (r.get("measured") or date.today().isoformat())[:10], "source": "csv", **vals})
    seen = {(r.get("postId"), r.get("measured"), r.get("source")) for r in rows if r.get("type") == "snapshot"}
    snaps = [s for s in snaps if (s["postId"], s["measured"], s["source"]) not in seen]
    if snaps:
        with open(log, "a", encoding="utf-8") as f:
            for s in snaps:
                f.write(json.dumps(s, ensure_ascii=False) + "\n")
        rows += snaps
    now = {}
    for s in (r for r in rows if r.get("type") == "snapshot"):
        k, rank = s["postId"], (s.get("measured", ""), s.get("source") == "csv")
        if k not in now or rank >= now[k][0]:
            merged = dict(now[k][1]) if k in now and now[k][1].get("measured") == s.get("measured") else {}
            merged.update(s)
            now[k] = (rank, merged)

    table = []
    for pid, post in posts.items():
        s = now.get(pid, (None, {}))[1]
        posted = P.parse_local(post.get("at"), post.get("timezone"))
        try:
            age = (date.fromisoformat(str(s.get("measured"))[:10]) - posted.date()).days if posted and s.get("measured") else None
        except ValueError:
            age = None
        imp = s.get("impressions")
        talk = sum(s.get(k) or 0 for k in TALK) if any(s.get(k) is not None for k in TALK) else None
        table.append({"post": post, "age": age, "imp": imp, "talk": talk,
                      "talk_k": round(1000 * talk / imp, 1) if imp and talk is not None else None, "s": s})
    fmt = lambda v: "not reported" if v is None else (f"{v:,.0f}" if isinstance(v, (int, float)) and v == int(v) else str(v))
    lines = ["# LinkedIn results", "", f"Judged from day {JUDGE_DAY}, against each account's own posts. "
             "Impressions against the account's median, then conversation (comments, reposts, saves, sends) per 1,000 impressions.", ""]
    for acct in sorted({str(t["post"].get("account")) for t in table}):
        ts = [t for t in table if str(t["post"].get("account")) == acct]
        ready = [t for t in ts if t["age"] is not None and t["age"] >= JUDGE_DAY and t["imp"]]
        med = statistics.median(t["imp"] for t in ready) if ready else None
        lines += [f"## {acct}", "", "| Post | Format | Age (days) | Impressions | x median | Conversation | per 1,000 |", "|---|---|---|---|---|---|---|"]
        for t in sorted(ts, key=lambda t: (t["imp"] or 0), reverse=True):
            x = round(t["imp"] / med, 2) if med and t["imp"] else None
            lines.append(f"| {t['post']['id']} | {t['post'].get('format')} | {fmt(t['age'])} | {fmt(t['imp'])} | {fmt(x)} | "
                         f"{fmt(t['talk'])} | {fmt(t['talk_k'])} |")
        lines.append("")
        if len(ready) >= MIN_RANKED:
            top = max(ready, key=lambda t: (t["imp"] / med, t["talk_k"] or 0))
            lines.append(f"Best so far: **{top['post']['id']}** ({top['post'].get('format')}). Write the next posts in that shape, on a new subject.")
        else:
            lines.append(f"{len(ready)} post(s) past day {JUDGE_DAY}: too few to name a best post (needs {MIN_RANKED}). Keep posting a few times a week.")
        lines.append("")
    out = os.path.join(os.path.dirname(os.path.abspath(log)), "results.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"wrote {P.rel(out, os.getcwd())}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record")
    r.add_argument("plan")
    r.add_argument("--log")
    s = sub.add_parser("results")
    s.add_argument("--plan")
    s.add_argument("--metrics")
    s.add_argument("--csv")
    s.add_argument("--log")
    a = ap.parse_args()
    {"record": cmd_record, "results": cmd_results}[a.cmd](a)


if __name__ == "__main__":
    main()
