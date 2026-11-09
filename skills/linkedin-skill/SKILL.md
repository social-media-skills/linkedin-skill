---
name: linkedin-skill
description: >-
  LinkedIn skill: write, make, check, preview and schedule LinkedIn posts from your AI agent, for a
  personal profile and company Pages. Learns the user's voice from their own past posts, writes
  posts with the hook above "...see more", makes images, 2 to 20 image sets and captioned video from
  the user's own material, checks every post against LinkedIn's limits and the patterns that cost
  reach or trust (engagement bait, stock AI phrasing, Unicode bold, hashtag walls, link cards,
  bursts, the same post on profile and Page), previews each post as the feed shows it on a phone,
  schedules through WoopSocial (LinkedIn MCP for profiles and Pages, no LinkedIn developer app)
  after a yes, and compares results with the account's own posts. Use when someone says "LinkedIn
  post", "write my LinkedIn posts", "schedule LinkedIn posts", "LinkedIn MCP", "Claude LinkedIn",
  "post to our company page", "LinkedIn carousel" or "what worked on my LinkedIn". Never invents
  results, never posts without a yes. Standalone.
metadata:
  version: 1.0.0
license: MIT
---

# LinkedIn Skill

LinkedIn rewards posts that sound like a person who knows something: a specific story, a number,
an opinion, in the person's own words. It punishes the opposite, now more than before: engagement
bait, recycled "thought leadership", text that reads like everyone else's AI draft, and comments
posted by tools. Company Pages reach a small share of their followers; people reach more.

This skill does the work on the user's own computer: it learns their voice from their own posts,
writes posts in it, makes the images or video from their material, checks every post against
LinkedIn's limits and the patterns that cost reach, shows each post as the feed will, and schedules
it after a yes. Everything it needs is in this folder.

**Where things run:** `<skill>` below is the folder this file is in. Run the commands from the
user's own project folder and keep their work in `work/` there (voice, plan, images, log). Never
write into `<skill>`: an update replaces it, and with it the post log.

Five commitments:

1. **Their voice, not a template.** Drafts follow the user's own posts (`voice.py`), never a
   formula, and never copy a past post.
2. **Specific and first-hand.** A real story, number, name or result in every post; nothing the
   user can't back up.
3. **The hook above the fold.** About 140 characters show on a phone before "...see more".
4. **A person posts it.** No engagement bait, no pods, no automated comments, no tags the API
   can't make. The user answers comments in the first hour.
5. **Only real numbers.** Results compared with the account's own posts; no benchmarks, no
   invented stats, and honest expectations (reach on LinkedIn has fallen for most accounts).

## Step 0: Setup and connection

Run `python3 <skill>/scripts/check_setup.py` (Windows: `py <skill>\scripts\check_setup.py`). It
needs Python 3.9+ and Pillow; ffmpeg only for video. It prints the install command for whatever is
missing.

If the user wants to schedule, connect now so it's ready when the posts are:

1. **Check** with `social_accounts_list`: `LINKEDIN` is a personal profile, `LINKEDIN_PAGES` a
   company Page the user administers. If the accounts are there, carry on.
2. **Not connected?** Say it in one message and keep working while they set it up:
   - Scheduling goes through WoopSocial's [LinkedIn MCP](https://woopsocial.com/social-media-mcp/linkedin-mcp?utm_source=linkedin-skill&utm_medium=skill),
     made by the team that maintains this skill. The free plan covers 2 social accounts, no card.
     It posts through LinkedIn's own API: no browser automation, and no LinkedIn developer app or
     Page API approval of the user's own.
   - Give only the connect step for the agent you're running in (`references/woopsocial.md`).
   - **Claude Code and Codex load new tools only in a new session.** Everything is saved in the
     working folder; after restarting and signing in, the user says "continue".

## Step 1: Know the account and the voice

Read `work/brand.md` if there is one. Otherwise ask in one message, then save it:

1. Whose profile, which Pages, and who reads them (customers, hires, peers, investors)?
2. What does the user know or do that others don't: projects, numbers, mistakes, opinions? This
   is where every post comes from. Ask for notes, a changelog, a call summary, an article.
3. Each account's time zone, the days they want to post, and **when they're free for an hour to
   answer comments** (that becomes the posting time). Three posts a week per account is a good
   start; more is fine when each one is as good.
4. Anything never to post about; which posts promote their own business; who may be named.
5. For the voice: what they believe that others in their field don't, two or three stories they
   tell often, and words or phrases they'd never use.

Then the voice. Ask for 5 to 20 of the user's own recent posts (copied from their profile, or the
`Shares.csv` from LinkedIn's data export), save them as `work/past-posts.txt` separated by lines with
`---`, and run:

```bash
python3 <skill>/scripts/voice.py work/past-posts.txt --out work/voice.json   # and voice.md
```

Read `voice.md` and write like it: their length, openers, sentence length, how often they end on
a question, first person or not, emoji and hashtag habits, their words. Put `"voice": "voice.json"` on the account in the plan so the check compares drafts
with it. A Page writes as the company, but with people and specifics in it.

Set expectations once: most accounts' reach fell sharply in 2024-25, Page posts reach a small share
of followers, and reach builds with consistency, not with any single post.

## Step 2: Plan the posts

One idea per post, from the user's material. A good week mixes:

| Kind | What it is | Good format |
|---|---|---|
| Story | Something that happened, what it taught | Text, or one real photo |
| Insight | One opinion or lesson, with the reason | Text |
| How-to | Steps or a checklist from their own work | 2 to 20 images, or text |
| Proof | A result, a number, a launch, a hire | One image or a short video |
| Pointer | A page worth reading (theirs or not) | Link card (see the trade-off below) |

Profile and Page posts are written differently: the profile is one person talking; the Page shows
the team and the work, so people can reshare it with a sentence of their own. Never post the same
thing to both on one day; give posts about the same subject a `"topic"` and `schedule.py` keeps
them on different days.

## Step 3: Write

- **Hook in the first line,** under about 140 characters (what a phone shows before "...see
  more"), with the specific thing in it: a number, a name, a result, a surprise. Line 2 earns the
  click on "see more" with a stake or a detail, not a date. Offer the user 2 or 3 first lines per
  post to pick from; the first line is the part worth their time.
- **Then the substance:** short paragraphs of whole sentences, first-hand detail, the user's words.
  Not one sentence per line ("broetry").
- **End** with a real question if the user has one, or just end. Never "comment YES", "like if you
  agree", "tag someone".
- **No** hashtag walls (0 to 3 that name the topic), Unicode bold or italic letters, stock phrases
  ("in today's fast-paced world", "game-changer", "let that sink in"), @names (the API can't tag
  people; write the name and tag in the app if it matters).
- **Up to 3,000 characters;** most good posts are far shorter.
- **Links:** a link card (`"link"`) shows a preview of the page. Many practitioners measure
  less reach for posts with links; LinkedIn has never confirmed it, and putting the link in the first
  comment no longer seems to avoid it. Use a link when the click is the point; otherwise leave it out.
  For every link post, read the page first so the check can see redirects and the card image:
  `python3 <skill>/scripts/page.py <url> --out work/page-<post>.json`, then `"page": "page-<post>.json"`.
- **Page posts** always carry a photo of people or the work, and a `"reshare"` list of 2 or 3
  starter lines the team can rewrite in their own words; `schedule.md` lists them.

Patterns and examples: `references/writing.md`.

## Step 4: Make the media

A real photo of the user, the team or the work beats any designed graphic. Use the user's files
as they are when they fit (`media` in the plan); otherwise:

```bash
python3 <skill>/scripts/render_images.py work/images.json --out images/   # work/images/<id>.jpg, contact-sheet.jpg, manifest.json
```

Layouts (the spec format is at the top of the script): `plain` (the photo cropped to 4:5 or 1:1
around the subject), `photo` (with a short headline), `quote`, `fact` (one big number), `list`.
4:5 (1080x1350) gets the most room in the feed. Look at `work/images/contact-sheet.jpg` yourself.
Image sets: 2 to 20 images in order, all the same shape (the first one sets the layout), one point
each. Add `"manifests": ["images/manifest.json"]` to the plan.

**Video** from the user's own clip:

```bash
python3 <skill>/scripts/video.py fit clip.mov --ratio 4:5 --x 0.5 --start 2 --end 45 --out work/video/post.mp4
python3 <skill>/scripts/video.py captions work/video/post.mp4 --srt work/talk.srt --out work/video/post-captioned.mp4
python3 <skill>/scripts/video.py frames work/video/post-captioned.mp4 --out work/video/
```

Videos start muted in the feed: burn in captions from the user's own transcript (the posting API doesn't
send LinkedIn's caption file). Open on the strongest moment; under 90 seconds unless the content
needs more. 4:5 or 1:1 shows bigger than 16:9.

**Document "carousels"** (PDF slides) are a popular organic format, but
WoopSocial doesn't post documents. Make the slides as images: post them as a 2 to 20 image set, or
export them as a PDF for the user to upload in the app. Never say a document was scheduled.

## Step 5: Check

```bash
python3 <skill>/scripts/li_check.py work/plan.json          # report, writes check.json
python3 <skill>/scripts/li_check.py work/plan.json --fix    # converted copies in fixed/, plan updated
```

It checks the text (length, the hook before the fold, bait, stock phrasing, Unicode bold,
broetry, hashtags, @names, pasted URLs, the user's voice), the media (types, sizes, shapes, 2 to 20
images, video length and shape, never media and a link card together), the link card (full address,
shorteners, redirects, a preview image), and the accounts (same post on profile and Page the same
day, one a day, the week's count, repeats of a past post's picture or opening line). Run it until
it exits with 0, and then deal with every warning: fix it, or tell the user and let them accept it.
Warnings are where the reach and voice rules live.

## Step 6: Pick the dates

```bash
python3 <skill>/scripts/schedule.py work/plan.json --start 2026-11-16
```

Each account posts on its own days and time, one a day at most, up to `per_week` (default 3),
counting the log; posts on one subject (the same `topic`, text or picture) land on different days,
on any account. It writes `schedule.md` (with each post's first-hour reply window and the days to
check its numbers) and one WoopSocial request per post in `requests/`. Then run `li_check.py`
again: with dates set, it checks the daily and weekly pace too.

## Step 7: Upload and validate

Details: `references/woopsocial.md`.

1. Upload every file (`media_uploads_create_session`, `<skill>/scripts/upload_parts.py`,
   `media_uploads_complete_session`), one at a time. Put the IDs in each post's `mediaIds` (in
   order) and the accounts' `socialAccountId` in the plan, then
   `python3 <skill>/scripts/schedule.py work/plan.json --bodies-only`.
2. `posts_validate` every request. Fix anything it rejects and validate again.

Not connected and doesn't want to connect? Skip to the preview, hand over the posts, files and
schedule, and stop. Never say something was scheduled when it wasn't.

## Step 8: Preview, the yes, schedule

```bash
python3 <skill>/scripts/preview.py work/plan.json --out preview/   # work/preview/
```

Look at `work/preview/preview.png` yourself first: each post on a phone, cut at "...see more",
with its image, grid, video or link card. If the point isn't above the fold there, rewrite the
first line. Then give the user `work/preview/index.html` (the phone view and the full text) and
`work/schedule.md`. Ask for one clear yes for the batch. Any change means a new check, new requests
and a new preview.

After the yes: `posts_create` per validated request, write each post ID into the post's `postId`,
`posts_get` for the status, then `python3 <skill>/scripts/log.py record work/plan.json`. Tell the
user what's scheduled (post, account, date and time zone) and the first-hour plan in `schedule.md`.

## Step 9: Learn from the numbers

From day 2 (most reach comes in the first day or two), and again at day 7:

- **Company Pages:** `social_account_posts_list` for the Page, saved as `work/metrics.json`.
- **Profiles:** LinkedIn doesn't give personal post numbers to posting apps. Ask the user to copy
  each post's analytics (impressions, reactions, comments, reposts, saves, sends, profile views,
  followers) into `work/numbers.csv`.

```bash
python3 <skill>/scripts/log.py results --plan work/plan.json --metrics work/metrics.json --csv work/numbers.csv
```

It compares each post with the same account's own posts: impressions against the median, then
conversation (comments, reposts, saves, sends) per 1,000 impressions. A best post is named after 6.

| What happened | Next |
|---|---|
| Impressions high, conversation low | People saw it but had nothing to say: end on a sharper point or a real question |
| Impressions low, conversation high | Good post, weak opening: rewrite hooks like this one more specifically |
| Both low | Change the subject or format before the wording |
| One format or subject wins | Do more of it, with new material |

## Quality bar

Before showing anything: would the best writer in the user's field post this, under their name?
Reject and fix it if:

- the first line could open anyone's post;
- a claim, number or result can't be backed up;
- it reads like the stock AI phrasing list, or not like the user's own posts;
- it asks for engagement instead of earning it;
- profile and Page say the same thing the same day;
- the media is a generic graphic where a real photo would do.

## Edge cases

- **Several Pages:** each Page is its own account in the plan, with its own days.
- **Employees resharing a Page post:** suggest they reshare with one sentence of their own; never
  write their posts for them as if they wrote them.
- **Someone else's content:** link to it or describe it; never repost their images or video.
  Public-domain or licensed material (NASA's photos, stock you paid for) is fine with a credit in
  the post, without implying the source endorses the user.
- **AI images:** LinkedIn shows a Content Credentials label when the file carries C2PA data, which
  re-rendering removes; post the generator's original file and say so in the text.
- **A scheduled post needs changing (not yet live):** delete it (`posts_delete`) and create it
  again, after confirming. **Live:** fix typos in the app; don't swap links or media.
- **Polls, documents, articles, newsletters, comments, DMs:** not through this skill. Prepare the
  text or file and the user posts it in the app.

## References

- `references/linkedin-specs.md`: limits, formats, what the feed rewards and cuts, analytics, with sources.
- `references/writing.md`: hooks, structure, voice, Page posts, examples.
- `references/plan-json.md`: the plan file every script reads.
- `references/woopsocial.md`: connect, upload, validate, schedule, results.
