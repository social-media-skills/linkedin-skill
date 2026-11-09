# LinkedIn: limits, formats, and what the feed rewards

Checked November 2026. "LinkedIn" means LinkedIn's own Help Center, API documentation or
engineering blog; "study" means a published analysis of many posts; "practitioner" means people who
write LinkedIn posts for a living. Numbers that only one tool company reports are left out or marked.

## Formats and limits

| Format | Rules | Source |
|---|---|---|
| Text | Up to 3,000 characters | LinkedIn Posts API (learn.microsoft.com/linkedin/marketing/community-management/shares/posts-api) |
| "See more" | About 140 characters show on a phone, about 210 on desktop, about 3 lines when the post has media; line breaks move the cut earlier | Observed by practitioners; LinkedIn doesn't document it |
| Image | JPG, PNG or GIF; up to 5 MB; at least 552x276; from 3:1 wide to 4:5 tall (others are cropped); under 36 megapixels; 1080 px wide recommended | LinkedIn Help "Share photos"; Images API |
| Image set | 2 to 20 images; shown at 4:5 at most; the first image sets the layout | LinkedIn MultiImage API; Help |
| Video | MP4; 3 s to 15 min (10 min in the mobile app); up to 5 GB; from 1:2.4 to 2.4:1; up to 4096x2304; 10 to 60 fps | LinkedIn Help (video specs); Videos API |
| Document | PDF, PPT(X), DOC(X); up to 100 MB and 300 pages; all pages one size. Not sent by this skill's posting API | LinkedIn Help; Documents API |
| Poll | Question up to 140 characters, 2 to 4 options of 30. Not sent by this skill's posting API | LinkedIn Poll API |
| Link card | A preview card for the page (`link`); how it looks is built by the posting service, since LinkedIn's API doesn't read the page itself | LinkedIn Posts API |

## What the feed rewards and cuts

- LinkedIn's feed is ranked by large models that read a member's long history of interactions and
  match posts by meaning, predicting dwell time and clicks as well as reactions, comments and
  shares. (LinkedIn Engineering, "Engineering the next generation of LinkedIn's Feed", March 2026)
- The March 2026 update cuts repetitive, click-driven posts, engagement bait ("comment YES if you
  agree"), videos unrelated to their caption and recycled thought leadership. (LinkedIn, reported
  by Social Media Today, March 2026)
- LinkedIn says better detection cut views of content it classes as low-quality AI text by 40%,
  and added a report option for it in August 2026. (LinkedIn, reported by CNN, October 2026)
- Comments posted by tools "without any human oversight" are hidden from Most Relevant and can be
  limited; repeat offenders can be restricted. (LinkedIn's VP Product, February 2026)
- Hashtags no longer have follow feeds; practitioners use 0 to 3 as topic labels, with no
  measured effect on reach.
- Links: many practitioners measure less reach for posts with a link card; LinkedIn has never
  confirmed it, and the measurements disagree. Putting the link in the first comment no longer
  seems to avoid it. Treat it as a trade-off, not a rule.
- Answering comments in the first hour is the habit most associated with reach; a typical post
  gets most of its reach in its first day. (Practitioner studies, 2026, directional)
- Practitioners consistently find that posting several times a week does better than once a week,
  with no sign that extra posts hurt each other. Quality and time to answer comments are the
  limits, not a cap.

## Reach expectations

- Practitioners who track many accounts report that reach per post fell sharply from mid-2024 to
  mid-2025, video most and text least.
- Company Page posts reach a small share of the Page's followers; posts by people reach several
  times more. Pages grow through employees resharing with their own comment. (Practitioner reports
  2025, second-hand)

## Analytics

- Post analytics show impressions, members reached, reactions, comments, reposts, saves, sends,
  profile viewers and followers gained; video adds views and watch time. (LinkedIn Help)
- Posting apps can read Page post numbers; personal profile post numbers are restricted, so they
  are copied from LinkedIn by hand. (LinkedIn Community Management API permissions)

## AI content

- LinkedIn shows a "CR" Content Credentials label on images and video that carry C2PA data. Text
  gets no label but low-quality AI text is down-ranked. (LinkedIn Help, Content Credentials)

## Posting without your own LinkedIn app

Posting to a profile through LinkedIn's API needs a developer app; posting to a company Page needs
Community Management API access, granted to registered organisations after a review (practically
out of reach for most individuals). This skill schedules through WoopSocial, which has that access,
so neither applies.
