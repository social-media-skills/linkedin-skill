#!/usr/bin/env python3
"""Learn how the user writes from their own past posts, so drafts sound like them, not like AI.

    python3 scripts/voice.py past-posts.txt --out work/voice.json

past-posts.txt: 5 to 20 of the user's own LinkedIn posts, pasted as they are, separated by a line
with only --- on it. (A LinkedIn data export's Shares.csv works too: the ShareCommentary column.)

Writes voice.json (read by li_check.py) and voice.md (for the agent and the user to read): typical
length, how posts open, line and paragraph shape, emoji and hashtag habits, the words and phrases
the user actually uses, and the stock phrases they never use. Nothing leaves the computer.
"""
import argparse, csv, json, os, re, statistics, sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lilib as P  # noqa: E402

EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")
SENT = re.compile(r"(?<=[.!?])\s+")


def load_posts(path):
    if path.lower().endswith(".csv"):
        with open(path, encoding="utf-8-sig", errors="replace") as f:
            rows = list(csv.DictReader(f))
        col = next((c for c in (rows[0].keys() if rows else []) if c and "commentary" in c.lower()), None)
        if not col:
            sys.exit("no ShareCommentary column in that CSV; paste the posts into a .txt file instead")
        return [r[col].strip() for r in rows if (r.get(col) or "").strip()]
    text = open(path, encoding="utf-8", errors="replace").read().replace("\r", "")
    return [p.strip() for p in re.split(r"\n\s*-{3,}\s*\n", "\n" + text + "\n") if p.strip()]


def stats(posts):
    lens = [len(p) for p in posts]
    paras = [len([b for b in re.split(r"\n\s*\n", p) if b.strip()]) for p in posts]
    lines = [l for p in posts for l in p.split("\n") if l.strip()]
    sents = [s for p in posts for s in SENT.split(p.replace("\n", " ")) if s.strip()]
    words = [w for w in P.fold(" ".join(posts)).split()]
    content = [w for w in words if w not in P.STOP and len(w) > 2 and not w.isdigit()]
    bigrams = Counter(zip(content, content[1:]))
    first = [p.split("\n")[0].strip() for p in posts]
    return {
        "posts": len(posts),
        "length": {"median": int(statistics.median(lens)), "low": min(lens), "high": max(lens)},
        "paragraphs_median": statistics.median(paras),
        "words_per_sentence": round(statistics.mean(len(s.split()) for s in sents), 1) if sents else 0,
        "short_paragraph_share": round(sum(1 for p in posts for b in re.split(r"\n\s*\n", p) if b.strip() and len(b.split()) <= 12) / max(1, sum(paras)), 2),
        "first_line_chars_median": int(statistics.median(len(f) for f in first)),
        "emoji_per_post": round(sum(len(EMOJI.findall(p)) for p in posts) / len(posts), 2),
        "hashtags_per_post": round(sum(len(re.findall(r"(?<!\w)#[^\W\d_]\w*", p)) for p in posts) / len(posts), 2),
        "questions_at_end": round(sum(1 for p in posts if p.rstrip().endswith("?")) / len(posts), 2),
        "first_person": round(sum(1 for p in posts if re.search(r"\b(i|i'm|i've|i'd|my|me|we|our|us)\b", p.lower())) / len(posts), 2),
        "uses_dashes": any(ch in "".join(posts) for ch in "—–"),
        "openers": first,
        "top_words": [w for w, _ in Counter(content).most_common(40)],
        "phrases": [" ".join(b) for b, n in bigrams.most_common(30) if n > 1][:15],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("posts")
    ap.add_argument("--out", default="voice.json")
    a = ap.parse_args()
    posts = load_posts(a.posts)
    if len(posts) < 3:
        sys.exit(f"found {len(posts)} post(s); paste at least 5 of the user's own posts, separated by --- lines")
    v = stats(posts)
    out = a.out
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(v, f, indent=1, ensure_ascii=False)
    L = v["length"]
    md = [f"# Voice ({v['posts']} of the user's own posts)", "",
          f"- Length: usually about {L['median']} characters (from {L['low']} to {L['high']}).",
          f"- Shape: about {v['paragraphs_median']:g} paragraphs, {v['words_per_sentence']} words a sentence, "
          f"{int(v['short_paragraph_share'] * 100)}% of paragraphs are 12 words or fewer.",
          f"- First line: about {v['first_line_chars_median']} characters.",
          f"- Emoji: {v['emoji_per_post']} a post. Hashtags: {v['hashtags_per_post']} a post. "
          f"Ends on a question: {int(v['questions_at_end'] * 100)}% of posts. First person: {int(v['first_person'] * 100)}% of posts. "
          f"Dashes: {'yes' if v['uses_dashes'] else 'never'}.",
          "", "## How the posts open", ""] + [f"- {o}" for o in v["openers"][:10]] + [
          "", "## Words and phrases this person uses", "", ", ".join(v["top_words"][:25]),
          "", ", ".join(v["phrases"]) or "(no repeated phrases yet)",
          "", "Drafts follow this shape. Match the openers' style, not their words; never copy a past post.",
          "Word lists only show habits; ask the user for what they believe, the stories they tell, and words they'd never use."]
    with open(os.path.splitext(out)[0] + ".md", "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print("\n".join(md[:7]))
    print(f"wrote {P.rel(out, os.getcwd())} and {P.rel(os.path.splitext(out)[0] + '.md', os.getcwd())}")


if __name__ == "__main__":
    main()
