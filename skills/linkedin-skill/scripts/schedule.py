#!/usr/bin/env python3
"""Give every post a day and time per account, and write the WoopSocial request for each.

    python3 scripts/schedule.py plan.json --start 2026-11-16
    python3 scripts/schedule.py plan.json --bodies-only      # times already set; just (re)write requests

Each account posts on its own `days` (default Monday to Friday) at its own `times` in its own
`timezone`, one post a day at most, up to `per_week` (default 3) a week, counting posts already in
the log. Posts on one subject (the same `topic`, text or picture) never land on the same day, on any
account. Set `times` to when the user is free to answer comments. On LinkedIn the
hour matters less than being there to answer comments in the first hour; the default 08:30 local is a
placeholder until the account's own numbers say otherwise.

Writes schedule.md (the table to show the user, with the first-hour plan) and requests/<post>.json:
the exact body for WoopSocial's posts_validate and posts_create (LINKEDIN for a profile,
LINKEDIN_PAGES for a Page). Posts without a date get no request, so nothing goes out by mistake.
Needs Python 3.9+ (zoneinfo); Windows: pip install tzdata.
"""
import argparse, json, os, sys
from collections import defaultdict
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lilib as P  # noqa: E402

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DEFAULT_TIME = "08:30"
PLATFORM = {"profile": "LINKEDIN", "page": "LINKEDIN_PAGES"}


def times_of(acc):
    out = []
    for x in acc.get("times") or [DEFAULT_TIME]:
        try:
            hh, mm = (int(v) for v in str(x).strip().split(":"))
            assert 0 <= hh < 24 and 0 <= mm < 60
        except (ValueError, AssertionError):
            sys.exit(f"posting time '{x}' must look like 08:30")
        out.append((hh, mm))
    return sorted(out)


def days_of(acc):
    days = acc.get("days", DAYS[:5])
    if isinstance(days, str) or not days:
        sys.exit("days must be a list like [\"tue\", \"wed\", \"thu\"] (leave it out for Monday to Friday)")
    d = [str(x).strip().lower()[:3] for x in days]
    bad = [x for x in d if x not in DAYS]
    if bad:
        sys.exit(f"days {bad} must be mon, tue, wed, thu, fri, sat or sun")
    return set(d)


def body_for(post, plan, tz):
    acc = plan["accounts"].get(post.get("account"), {})
    media = P.media_of(post)
    ids = post.get("mediaIds") or []
    refs = [{"type": "MEDIA_LIBRARY", "mediaId": (ids[i] if i < len(ids) and ids[i] else f"<mediaId for {os.path.basename(m)}>")}
            for i, m in enumerate(media)]
    sa = {"platform": PLATFORM.get(acc.get("kind"), "LINKEDIN"),
          "socialAccountId": acc.get("socialAccountId") or f"<socialAccountId for {post.get('account')}>"}
    url, _ = P.link_of(post)
    if url:
        sa["link"] = url
    item = {"text": post.get("text", "")}
    if refs:
        item["media"] = refs
    body = {"content": [item], "socialAccounts": [sa]}
    if post.get("now"):
        body["schedule"] = {"type": "PUBLISH_NOW"}
    else:
        body["schedule"] = {"type": "SCHEDULE_FOR_LATER", "scheduledFor": P.to_utc(post["at"], tz)}
    return body


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("plan")
    ap.add_argument("--start", help="first day, YYYY-MM-DD (default: tomorrow)")
    ap.add_argument("--log", help="posts already published (default: posts-log.jsonl next to plan.json)")
    ap.add_argument("--bodies-only", action="store_true")
    a = ap.parse_args()
    base = os.path.dirname(os.path.abspath(a.plan))
    plan = P.load_plan(a.plan)
    accounts, posts = plan["accounts"], plan["posts"]
    rules = plan.get("rules") or {}
    if not accounts:
        sys.exit("plan.json has no accounts (references/plan-json.md)")
    P.check_ids(posts)
    default_tz = plan.get("timezone")
    for k, acc in accounts.items():
        P.zone(acc.get("timezone") or default_tz)
    tz_of = lambda k: (accounts.get(k) or {}).get("timezone") or default_tz
    bad = [f"{p['id']}: account '{p.get('account')}' isn't in accounts" for p in posts if p.get("account") not in accounts]
    bad += [f"{p['id']}: {e}" for p in posts for e in [P.link_of(p)[1]] if e]
    bad += [f"accounts.{k}.kind must be profile or page, not {acc.get('kind')!r}" for k, acc in accounts.items()
            if acc.get("kind") not in PLATFORM]
    bad += [f"{p['id']}: media and a link card can't go in one post" for p in posts if P.media_of(p) and p.get("link")]
    bad += [f"{p['id']}: 'at' must be a local time like 2026-11-17T08:30, not {p.get('at')!r}" for p in posts
            if p.get("at") and not P.parse_local(p.get("at"))]
    if bad:
        sys.exit("fix these first (li_check.py explains more):\n  " + "\n  ".join(bad))
    notes = []

    if not a.bodies_only:
        try:
            start = date.fromisoformat(a.start) if a.start else date.today() + timedelta(days=1)
        except ValueError:
            sys.exit(f"--start must be a date like 2026-11-16, not {a.start}")
        if start < date.today():
            notes.append(f"--start {start} is in the past; scheduling from today instead")
            start = date.today()
        used = defaultdict(int)          # (account, day)
        week = defaultdict(int)          # (account, iso week)
        topic_days = defaultdict(set)    # topic -> days used on any account
        plan_posts = {p.get("postId") for p in posts if p.get("postId")}

        prints, pics = {}, {}

        def topics(p):
            """Posts on one subject never land on one day: the post's topic, or its text and pictures."""
            t = {p["topic"]} if p.get("topic") else set()
            t.add("text:" + P.fold((p.get("text") or "")[:200]))
            for m in P.media_of(p):
                fp = prints.setdefault(m, P.media_fingerprint(P.resolve(base, m)) if os.path.exists(P.resolve(base, m)) else None)
                key = next((k for k, v in pics.items() if fp and P.same_picture(fp, v)), None)
                if key is None:
                    key = f"pic{len(pics)}"
                    pics[key] = fp
                t.add("media:" + key)
            return t

        def seen(acc, d, topic=None):
            used[(acc, d)] += 1
            week[(acc, d.isocalendar()[:2])] += 1
            if topic:
                topic_days[topic].add(d)
        for old in P.read_log(a.log or os.path.join(base, "posts-log.jsonl")):
            d = P.parse_local(old.get("at"), tz_of(old.get("account")))
            if d and old.get("postId") not in plan_posts:
                seen(old.get("account"), d.date())
        for p in posts:
            d = P.parse_local(p.get("at"), tz_of(p.get("account")))
            if d:
                seen(p.get("account"), d.date())
                for t in topics(p):
                    topic_days[t].add(d.date())
        for p in posts:
            if p.get("at") or p.get("now"):
                continue
            acct = p.get("account")
            acc = accounts[acct]
            cap = P.int_or(acc.get("per_week", rules.get("per_week")), 3, f"per_week for {acct}")
            days, times = days_of(acc), times_of(acc)
            now = datetime.now(P.zone(tz_of(acct))).replace(tzinfo=None)
            day = start
            for _ in range(400):
                h, mi = times[0]
                slot = datetime(day.year, day.month, day.day, h, mi)
                ok = (DAYS[day.weekday()] in days and used[(acct, day)] == 0
                      and week[(acct, day.isocalendar()[:2])] < cap and slot >= now + timedelta(minutes=30)
                      and not any(day in topic_days[t] for t in topics(p)))
                if ok:
                    break
                day += timedelta(days=1)
            else:
                sys.exit(f"{p['id']}: no free day found in 400 days; check days, per_week and times for {acct}")
            p["at"] = slot.isoformat(timespec="minutes")
            seen(acct, day)
            for t in topics(p):
                topic_days[t].add(day)
        P.save_plan(a.plan, plan)

    rdir = os.path.join(base, "requests")
    os.makedirs(rdir, exist_ok=True)
    sendable = lambda p: (p.get("at") or p.get("now")) and not p.get("postId")    # created posts: no second request
    keep = {f"{p['id']}.json" for p in posts if sendable(p)}
    for old in os.listdir(rdir):
        if old.endswith(".json") and old not in keep:
            os.remove(os.path.join(rdir, old))
    rows, missing, unscheduled = [], set(), []
    created = [p["id"] for p in posts if p.get("postId")]
    for p in posts:
        if p.get("postId"):
            continue
        if not (p.get("at") or p.get("now")):
            unscheduled.append(p["id"])
            continue
        tz = tz_of(p.get("account"))
        body = body_for(p, plan, tz)
        with open(os.path.join(rdir, f"{p['id']}.json"), "w", encoding="utf-8") as f:
            json.dump(body, f, indent=1, ensure_ascii=False)
        if P.PLACEHOLDER.search(json.dumps(body)):
            missing.add(p["id"])
        rows.append((p.get("at") or "", tz, p))
    rows.sort(key=lambda r: r[0])
    lines = ["# LinkedIn schedule", ""]
    if not all(accounts[p.get("account")].get("times") for _, _, p in rows):
        lines += [f"Times are {DEFAULT_TIME} local. The hour matters less than being there to reply in the first hour; "
                  "set `times` per account once its own numbers show a better one.", ""]
    lines += ["| Goes live (local time) | Post | Account | Format | First line |", "|---|---|---|---|---|"]
    for at, tz, p in rows:
        d = P.parse_local(at, tz)
        when = (d.strftime("%a %d %b %Y %H:%M") + f" ({tz.split('/')[-1].replace('_', ' ')})") if d else "now"
        acc = accounts[p.get("account")]
        first = (p.get("text") or "").strip().split("\n")[0].replace("|", "/")
        lines.append(f"| {when} | {p['id']} | {acc.get('name') or p.get('account')} ({acc.get('kind')}) | {P.fmt_of(p)} | {first[:80]} |")
    if unscheduled:
        notes.append("not scheduled (no request written): " + ", ".join(unscheduled))
    if created:
        notes.append("already created in WoopSocial (no new request): " + ", ".join(created))
    kits = [(p, p["reshare"]) for _, _, p in rows if isinstance(p.get("reshare"), list) and p["reshare"]]
    if notes:
        lines += ["", "## Notes", ""] + [f"- {n}" for n in notes]
    if kits:
        lines += ["", "## Reshare starters for the team", "",
                  "Send these to the people in or behind each Page post; they rewrite one in their own words and reshare.", ""]
        for p, k in kits:
            lines.append(f"- **{p['id']}**: " + " / ".join(f'"{x}"' for x in k))
    lines += ["", "## The first hour after each post", ""]
    for at, tz, p in rows:
        d = P.parse_local(at, tz)
        if d:
            lines.append(f"- {p['id']}: be there {d.strftime('%a %d %b %H:%M')} to {(d + timedelta(hours=1)).strftime('%H:%M')} "
                         f"to answer comments; check its numbers on {(d + timedelta(days=2)).strftime('%a %d %b')} and "
                         f"{(d + timedelta(days=7)).strftime('%a %d %b')}.")
    lines += ["- Answer comments with a real reply; nobody answering is what costs reach.",
              "- Page posts: the people in them, or the team, reshare with a sentence of their own, not a bare repost.",
              "- Don't edit the link or swap media after posting; fix typos only."]
    with open(os.path.join(base, "schedule.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines[: lines.index("## The first hour after each post")]))
    print(f"wrote {len(rows)} request bodies to {P.rel(rdir, os.getcwd())} and schedule.md")
    if missing:
        print("Still placeholders (upload the media, put the IDs in mediaIds, set socialAccountId, "
              "then run again with --bodies-only): " + ", ".join(sorted(missing)))


if __name__ == "__main__":
    main()
