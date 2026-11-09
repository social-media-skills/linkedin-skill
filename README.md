# LinkedIn Skill for Claude Code, Codex, Cursor and OpenClaw

**LinkedIn Skill** is a free, open-source LinkedIn skill for Claude Code and other AI agents that writes, makes, checks, previews and schedules LinkedIn posts for your personal profile and your company Pages, in your own voice. You give your agent your notes, a changelog, a photo or a video. It learns how you write from your own past posts, drafts posts with the point above "...see more", makes the images or captioned video, checks every post against LinkedIn's limits and the patterns that cost reach, shows each post the way the feed will, and schedules it through [WoopSocial](https://woopsocial.com/?utm_source=linkedin-skill&utm_medium=readme) after you say yes:

- your voice, learned from 5 to 20 of your own posts: length, openers, habits, the words you use and never use;
- the hook in the first line, checked against what a phone shows before "...see more";
- images from your photos (4:5 or 1:1), quote, number and list cards, 2 to 20 image sets, or slides as a PDF for a document post;
- video fitted to 4:5 or 1:1 with captions burned in, because videos start muted in the feed;
- engagement bait, stock AI phrasing, Unicode bold, hashtag walls and pasted URLs flagged;
- one post a day per account, 3 a week by default, profile and Page never saying the same thing on the same day;
- results compared with your own posts: Page numbers read back automatically, profile numbers pasted in.

Everything up to scheduling runs locally with Python and Pillow (ffmpeg for video). No paid API, no LinkedIn developer app, no browser automation. MIT licensed.

```bash
npx skills add social-media-skills/linkedin-skill -g -a claude-code -y
```

![Five LinkedIn posts the skill made about NASA's Artemis II mission, each shown as the feed shows it on a phone: a captioned liftoff video and a splashdown photo on a company Page, and an Earthset photo, a four-photo set and a link post on a personal profile](skills/linkedin-skill/examples/showcase.png)

*The example in [`examples/artemis-ii/`](skills/linkedin-skill/examples/artemis-ii/): a week of posts about Artemis II for a placeholder profile and an astronomy club's Page, made only from NASA photos and video. Every image, check, preview, schedule and request in it was made by the skill's scripts. See [CREDITS](skills/linkedin-skill/examples/artemis-ii/CREDITS.md).*

## Contents

- [What the LinkedIn skill does](#what-the-linkedin-skill-does)
- [Requirements](#requirements)
- [Install](#install)
- [Example: write and schedule LinkedIn posts with Claude Code](#example-write-and-schedule-linkedin-posts-with-claude-code)
- [What it checks](#what-it-checks)
- [Posting to profiles and company Pages](#posting-to-profiles-and-company-pages)
- [What it won't do](#what-it-wont-do)
- [FAQ](#faq)
- [What's inside](#whats-inside)

## What the LinkedIn skill does

Tell your agent "write this week's LinkedIn posts from these notes", "post our launch to the company page", "turn this talk into a LinkedIn video" or "what worked on my LinkedIn", and it does the whole job:

1. **Learns your voice** with `voice.py` from your own past posts.
2. **Plans** one idea per post from your material, mixing stories, insights, how-tos, proof and pointers, with profile and Page posts written differently.
3. **Writes** with the specific thing in the first line and whole sentences after it.
4. **Makes the media** with `render_images.py` and `video.py` from your files.
5. **Checks** every post with `li_check.py`.
6. **Picks the dates** with `schedule.py`: your days and the hour you can answer comments, one a day, 3 a week by default.
7. **Uploads and validates** with WoopSocial.
8. **Shows a preview** of each post on a phone, cut at "...see more", and waits for one clear yes.
9. **Schedules** and logs every post, so the same picture or opening line isn't used twice.
10. **Learns** from day 2: impressions against your own median, then conversation per 1,000 impressions.

## Requirements

- Python 3.9 or newer with Pillow (`pip install pillow`); on Windows also `pip install tzdata`.
- ffmpeg for video. Text and image posts work without it.
- An agent that can run commands on your computer (Claude Code, Codex, Cursor, OpenClaw or similar).

`python3 scripts/check_setup.py` tells you what's missing and the install command for your system. A CI workflow runs the full pipeline on macOS, Windows and Ubuntu.

## Install

**Claude Code**

```bash
npx skills add social-media-skills/linkedin-skill -g -a claude-code -y
```

**Codex, Cursor and other agents:** run `npx skills add social-media-skills/linkedin-skill` and pick your agent, or copy `skills/linkedin-skill/` into your agent's skills directory.

**OpenClaw (ClawHub):** `openclaw skills install @social-media-skills/linkedin-skill`

**GitHub CLI:** `gh skill install social-media-skills/linkedin-skill linkedin-skill`

**Gemini CLI:** `gemini extensions install https://github.com/social-media-skills/linkedin-skill`

## Example: write and schedule LinkedIn posts with Claude Code

```
You:   Write next week's LinkedIn posts about Artemis II, using NASA's
       photos and video. Three on my profile, two on our company Page.
       My past posts are in past-posts.txt.

Agent: Your posts run about 300 characters, no emoji, no hashtags,
       plain openers, rarely a question. Five posts, one subject per
       day so profile and Page never overlap:
       Page: the liftoff seen from Orion (30 s, 4:5, captions burned
       in) and the crew on the raft after splashdown, with a line
       or two for the club to reshare.
       Profile: Earthset, the flyby in four photos, and NASA's
       mission page as a link card (I've noted the link trade-off).
       Every hook fits above "...see more". Checks pass, WoopSocial
       validated all five. Preview: preview/index.html. Schedule them?

You:   Yes.

Agent: Scheduled Mon 23 Nov to Tue 1 Dec, New York time. Be around for
       the first hour after each one to answer comments.
```

The images, video, check report, preview, schedule and WoopSocial requests from this run are in [`examples/artemis-ii/`](skills/linkedin-skill/examples/artemis-ii/).

## What it checks

| Check | Rule | Why |
|---|---|---|
| Length | Up to 3,000 characters | LinkedIn's limit |
| Hook | The first line under about 140 characters | About that much shows on a phone before "...see more" |
| Bait | "Comment YES", "like if you agree", "tag someone" | LinkedIn cuts reach for engagement bait |
| Stock phrasing | A list of phrases readers take as generic AI text, long dashes the user never uses | LinkedIn down-ranks low-quality AI text |
| Formatting | Unicode bold letters, one-line-per-sentence posts, more than 3 hashtags, @names, pasted URLs | Unreadable for screen readers, no effect on reach, or not possible through the API |
| Voice | Length, emoji and hashtags against the user's own posts | Drafts should sound like the user |
| Images | JPEG, PNG or GIF, up to 5 MB, at least 552x276, 3:1 to 4:5 | LinkedIn's limits; taller is cropped |
| Image sets | 2 to 20, the same shape | LinkedIn lays a set out by the first image |
| Video | MP4/MOV, 3 s to 15 min, up to 5 GB, 1:2.4 to 2.4:1 | LinkedIn's limits |
| Link card | Full https address, no shorteners, no redirects, a preview image; never with media | A post shows one or the other |
| Accounts | Same post on profile and Page the same day, more than one a day, the week's count, a repeated picture or opening | Each post needs its own first hours |

Each rule, with its source, is in [`references/linkedin-specs.md`](skills/linkedin-skill/references/linkedin-specs.md).

## Posting to profiles and company Pages

Scheduling goes through [WoopSocial's LinkedIn API](https://woopsocial.com/social-media-mcp/linkedin-mcp?utm_source=linkedin-skill&utm_medium=readme), a social media API and MCP server for AI agents. Disclosure: this skill is maintained by Frank Heijdenrijk and the team behind WoopSocial. The free plan covers 2 social accounts. Setup steps for every agent are at [woopsocial.com/agents](https://woopsocial.com/agents?utm_source=linkedin-skill&utm_medium=readme).

Posting to a company Page through LinkedIn's API normally needs Community Management API access, which LinkedIn grants to registered organisations after a review. WoopSocial has that access, so you connect your profile and the Pages you administer and post to them. It uses LinkedIn's official API, not your browser session.

The agent uploads each file, writes one request per post, validates them with WoopSocial, and only then shows you the preview and the schedule. It schedules only after a clear yes. Through WoopSocial it posts text, one image, 2 to 20 images, video and link cards. Documents (PDF carousels), polls, @mentions and comments aren't sent; the skill prepares them for you to add in the app. WoopSocial reads Page results back; personal profile numbers are copied from LinkedIn, which doesn't share them with posting apps. WoopSocial doesn't write posts or edit media; the skill does that on your computer and you approve it.

## What it won't do

- Invent numbers, results, quotes or stories. Every claim needs to be yours or sourced.
- Post anything without your yes on the preview.
- Write engagement bait, comment on other people's posts, join pods or send messages.
- Copy a past post, or post the same thing to your profile and Page on the same day.
- Promise reach. LinkedIn reach has fallen for most accounts; the skill compares you with yourself.

## FAQ

**What is a LinkedIn skill?** An agent skill (a folder with a `SKILL.md`) that teaches an AI agent such as Claude Code how to do a job on LinkedIn. This one includes the scripts that make and check the posts, so the agent produces finished posts, not just drafts.

**Can Claude post to LinkedIn?** Yes. With this skill and WoopSocial connected, Claude Code, Claude Desktop, Codex, Cursor and OpenClaw can schedule posts to your profile and your company Pages after you approve each batch.

**Is this a LinkedIn MCP?** The skill schedules through WoopSocial's MCP server. The skill adds what an MCP alone doesn't: your voice, the writing, the media, the checks, the phone preview and the learning loop.

**Do I need a LinkedIn developer app or API key?** No. You connect your LinkedIn account to WoopSocial and the skill schedules through it.

**Does it post PDF carousels?** Not through the API: WoopSocial doesn't send documents. The skill renders the slides and gives you a PDF to upload, or posts them as a 2 to 20 image set.

**Should links go in the first comment?** The skill can't post comments, and the trick no longer seems to help. Many people measure less reach for posts with links; LinkedIn has never confirmed it. Use a link card when the click is the point.

**Does scheduling hurt reach?** No independent data shows it does; LinkedIn has its own scheduler. What costs reach is nobody answering comments in the first hour.

**Does it work without WoopSocial?** Yes. Everything up to the schedule is local; without it you post the text and files yourself.

## What's inside

```
skills/linkedin-skill/
  SKILL.md                 the workflow the agent follows
  scripts/
    check_setup.py         what's installed, and how to add what isn't
    voice.py               learns the user's voice from their own past posts
    page.py                reads a linked page: final URL, title, preview image
    render_images.py       images in five layouts (4:5 or 1:1), contact sheet, manifest, PDF slides
    video.py               fit a clip, burn in captions, photos to video, frame sheet
    li_check.py            checks every post's text, media, link and account rules; fixes files
    schedule.py            days and times per account, one a day, WoopSocial requests, schedule.md
    preview.py             each post as the feed shows it on a phone, cut at "...see more"
    upload_parts.py        uploads files to WoopSocial
    log.py                 post log (stops repeats) and results against your own posts
    lilib.py               shared limits and helpers
  references/              LinkedIn specs, writing, plan.json, scheduling
  fonts/                   Inter and Instrument Serif (SIL Open Font License)
  examples/artemis-ii/     a full week of posts with every output
  evals/evals.json         14 test prompts
```

The NASA photos and video in the example are credited in [CREDITS](skills/linkedin-skill/examples/artemis-ii/CREDITS.md); their use doesn't imply endorsement by NASA.

More free skills for social media from the same team: [social-media-skills.com](https://social-media-skills.com/?utm_source=linkedin-skill&utm_medium=readme).
