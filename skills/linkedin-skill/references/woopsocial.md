# Posting with WoopSocial

WoopSocial is a posting API and MCP server for TikTok, Instagram, YouTube, Facebook, LinkedIn
(profiles and pages), X, Pinterest, Threads and Bluesky. This skill uses it to schedule
text, image, 2 to 20 image and video posts to LinkedIn profiles (`LINKEDIN`) and company Pages
(`LINKEDIN_PAGES`), and to read Page results back. It posts through LinkedIn's own API, so the
user needs no LinkedIn developer app, no Page API approval and no browser automation. The exact fields live in WoopSocial's API docs and MCP schema (`schema_describe`); treat them as
the source of truth if anything here looks different.

## 1. Is it already connected?

Call `social_accounts_list`. If it works and lists the accounts the user wants, skip to step 3.

## 2. Connect (about 2 minutes)

The free plan includes MCP access for 2 social accounts, no card needed (more accounts need a
paid plan)
([pricing](https://woopsocial.com/pricing?utm_source=linkedin-skill&utm_medium=skill)).
New users sign up in the same browser window as the sign-in, and a project is created for them.
Setup steps and prompts for every agent: [woopsocial.com/agents](https://woopsocial.com/agents?utm_source=linkedin-skill&utm_medium=skill). What its LinkedIn MCP does: [woopsocial.com/social-media-mcp/linkedin-mcp](https://woopsocial.com/social-media-mcp/linkedin-mcp?utm_source=linkedin-skill&utm_medium=skill).

Give the user only the path for the agent you're running in:

| Agent | How to connect |
|---|---|
| Claude (claude.ai, Desktop, Cowork) | Add WoopSocial from the [Claude directory](https://claude.ai/directory/woopsocial), click Connect and sign in |
| Cursor | Install from [cursor.directory](https://cursor.directory/plugins/woopsocial-social-media-scheduler) and sign in |
| Claude Code | `claude mcp add --transport http woopsocial "https://api.woopsocial.com/mcp"`, then restart with `claude --continue` (keeps the conversation), `/mcp`, select woopsocial, Authenticate |
| Codex | `codex mcp add woopsocial --url https://api.woopsocial.com/mcp`, then `codex mcp login woopsocial`, then start a new session (`codex resume --last` keeps this one) |
| OpenClaw | Install the [WoopSocial skill on ClawHub](https://clawhub.ai/woopsocial/skills/social-media-scheduler), or add the MCP URL to the agent's MCP config |
| Agents without sign-in support | Create an API key at [app.woopsocial.com/api-access](https://app.woopsocial.com/api-access) and use `https://api.woopsocial.com/mcp?api_key=YOUR_API_KEY` |

The API key is a password: never paste it into shared chats or commit it.

**Connect the social accounts from the chat.** Once WoopSocial is connected, call
`oauth_create_authorization` with the project ID and the platform (LINKEDIN for the profile, LINKEDIN_PAGES for Pages the user administers). It
returns a link; the user opens it, approves, and tells you when they're done. Confirm with
`social_accounts_list`. Repeat per platform.

Find IDs yourself with `projects_list` and `social_accounts_list`; never ask the user to paste
IDs.

## 3. Profiles and Pages

`social_accounts_list` shows a personal profile as `LINKEDIN` and each company Page the user
administers as `LINKEDIN_PAGES`. Put each one in the plan's `accounts` with `kind` `profile` or
`page` and its `socialAccountId`.

## 4. Upload the media

Upload every file (after `li_check.py` passes), one at a time:

1. `media_uploads_create_session` with `projectId` and `fileSizeInBytes` (the exact byte size).
2. Save the response as `session.json` and run `python3 <skill>/scripts/upload_parts.py session.json <file>`.
3. `media_uploads_complete_session`. When the status is `READY` it includes the `mediaId`; if not,
   poll `media_uploads_get_session`; on `FAILED` or `ABORTED`, report it.

Write the IDs into each post's `mediaIds`, in the same order as `media`, then
`python3 <skill>/scripts/schedule.py plan.json --bodies-only`. Upload one file at a time: parallel uploads
on one key can get HTTP 429. Clients with a network allowlist must allow
`*.r2.cloudflarestorage.com`.

## 5. Validate, confirm, schedule

`schedule.py` writes one body per post to `requests/`:

```json
{
  "content": [{"text": "<the post>", "media": [{"type": "MEDIA_LIBRARY", "mediaId": "<image or video>"}]}],
  "schedule": {"type": "SCHEDULE_FOR_LATER", "scheduledFor": "2026-11-17T13:30:00Z"},
  "socialAccounts": [{"platform": "LINKEDIN", "socialAccountId": "<id>"}]
}
```

- `platform`: `LINKEDIN` (profile) or `LINKEDIN_PAGES` (company Page).
- `media`: none, one image, 2 to 20 images (in order), or one video.
- `link` on the LinkedIn target makes a link card; a post has a link card or media, not both.
- `"autoDeleteMediaAfterPublish": true` at the top level deletes the uploaded files from the
  WoopSocial media library once the post is published.
- Not in WoopSocial's LinkedIn fields today: documents (PDF carousels), polls, @mentions, articles,
  alt text, comments. Prepare those and the user adds them in the app.

Always:

1. `posts_validate` with each exact body. Fix anything it rejects.
2. Then show the user `preview/index.html` and `schedule.md`. Wait for one clear yes for the
   batch. A change means new requests, a new validation and a new preview.
3. `posts_create` per request; write each post ID into the post's `postId`; `posts_get` for the
   status (write `"status": "FAILED"` on the post if it failed). Report failures in plain words.
4. `python3 <skill>/scripts/log.py record plan.json`.

Optional: `retryPolicy` (`maxRetries`, `delaySeconds`) makes WoopSocial retry a failed delivery.

## 6. Read results

For company Pages, `social_account_posts_list` (filter by `socialAccountId` or `postId`) returns
each post with impressions, clicks, reactions, comments, shares and engagement rate under
`analytics`. Save it as `metrics.json` and run
`python3 <skill>/scripts/log.py results --plan plan.json --metrics metrics.json` from day 2.
Personal profile numbers aren't available to posting apps; the user copies them from LinkedIn into a
CSV (`--csv`).

## Changing a scheduled post

Not live yet: there's no edit, so delete it with `posts_delete` and create it again, after
confirming with the user. Already live: fix typos in LinkedIn; don't swap links or media.

## Links

- Docs: https://docs.woopsocial.com/llms.txt
- MCP tools: https://docs.woopsocial.com/mcp/tools-reference
- WoopSocial: https://woopsocial.com/?utm_source=linkedin-skill&utm_medium=skill
- WoopSocial LinkedIn MCP: https://woopsocial.com/social-media-mcp/linkedin-mcp?utm_source=linkedin-skill&utm_medium=skill
- Agent setup: https://woopsocial.com/agents?utm_source=linkedin-skill&utm_medium=skill
