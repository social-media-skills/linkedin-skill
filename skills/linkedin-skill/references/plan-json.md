# plan.json

Every script reads this one file. Paths are relative to it. A full example is in
`examples/artemis-ii/plan.json`.

```json
{
  "timezone": "America/New_York",
  "rules": {"per_week": 3, "max_per_week": 7},
  "manifests": ["images/manifest.json"],
  "accounts": {
    "me": {"kind": "profile", "name": "Jane Doe", "headline": "Founder, Acme",
           "socialAccountId": "<from social_accounts_list>", "timezone": "America/New_York",
           "times": ["08:30"], "days": ["tue", "wed", "thu"], "voice": "voice.json"},
    "acme": {"kind": "page", "name": "Acme", "socialAccountId": "<from social_accounts_list>",
             "timezone": "Europe/Amsterdam", "times": ["12:00"], "per_week": 2}
  },
  "posts": [
    {"id": "onboarding", "account": "me", "topic": "onboarding",
     "text": "We cut our onboarding from 14 days to 3. The fix wasn't software.\n\n...",
     "media": ["images/team.jpg"], "at": "2026-11-17T08:30",
     "mediaIds": ["<from media_uploads_complete_session>"], "postId": "<from posts_create>"},
    {"id": "launch-page", "account": "acme", "text": "...", "link": "https://acme.com/launch", "page": "page.json"}
  ]
}
```

| Field | Meaning |
|---|---|
| `rules.per_week` | posts per account per week when scheduling (default 3; an account can set its own) |
| `rules.max_per_week` | the check warns above this many posts a week per account (default 7) |
| `manifests` | `render_images.py` manifests, so the check knows each image's text size and render warnings |
| `accounts.*.kind` | `profile` (WoopSocial `LINKEDIN`) or `page` (`LINKEDIN_PAGES`) |
| `accounts.*.days`, `times` | when this account posts (default Monday to Friday, 08:30 local); set `times` to when the user can answer comments |
| `accounts.*.voice` | `voice.py` output; the check compares drafts with it |
| `posts[].text` | the post, up to 3,000 characters |
| `posts[].media` | nothing, one image, 2 to 20 images, or one video (paths) |
| `posts[].link` | a link card (a full https:// address); never together with media |
| `posts[].page` | `page.py` output for the link (redirects, preview image) |
| `posts[].topic` | posts with the same topic (or the same text or picture) go out on different days, across accounts |
| `posts[].reshare` | Page posts: 2 or 3 starter lines the team rewrites and reshares with |
| `posts[].ai` | true when the media is AI-made |
| `posts[].at` | local time, set by `schedule.py`; `"now": true` publishes at once |
| `posts[].mediaIds` | WoopSocial media IDs, in the same order as `media` |
| `posts[].postId` | from `posts_create`; `log.py record` logs posts that have one |
| `posts[].status` | set to `FAILED` if delivery failed, so the log skips it |

`posts-log.jsonl` (next to the plan) is the history: every post published, with its first line and
picture fingerprints, plus the numbers `log.py results` collected. Keep it with the account's work.
