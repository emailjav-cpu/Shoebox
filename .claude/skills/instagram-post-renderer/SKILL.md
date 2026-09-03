---
name: instagram-post-renderer
description: Renders finished 1080x1350 Instagram post images for @javierdiaz.design from HTML/CSS with headless Chromium — no paid image generation — and files each one into the "Instagram content calendar" Notion database with its caption, pillar, project, and the image attached, at status "ready for review". Use this whenever Javier has post copy ready and wants the actual image made, mentions rendering, "make the image", "the post image", the instagram-kit, or asks to push a drafted post into Notion for review. It owns image production and the Notion handoff only; instagram-content-engine owns the rotation and caption drafting, and brand-strategist owns voice and visual rules — read those before writing any copy or on-image text.
---

# Instagram post renderer — @javierdiaz.design

Turns approved post copy into a finished 1080x1350 JPEG and files it in Notion
for review. This skill replaces the old local image renderer.

**It never posts to Instagram.** Publishing is a separate, scheduled step that
only ever touches rows Javier has manually marked `approved` in Notion. See
[Approve before post](#approve-before-post).

## Where this sits

| Skill | Owns |
|---|---|
| `brand-strategist` | Voice and visual identity. The source of truth. |
| `instagram-content-engine` | The Mon–Sat rotation, source material, caption drafting. |
| **this skill** | Rendering the image, and filing it into Notion. |

Before writing any on-image text, read
`brand-strategist/references/identity.md`. Before writing or editing a caption,
read `brand-strategist/references/voice.md`. The template already encodes the
palette and type rules — do not restate them in CSS, and do not override them
per post.

## Rendering

```bash
python3 scripts/render_post.py \
  --pillar "design tip" \
  --headline "Your homepage does not need a slider." \
  --deck "Visitors decide in about a second. A rotating banner spends that second showing them something they did not ask for." \
  --out build/2026-09-08-tue.jpg
```

Key flags:

| Flag | Notes |
|---|---|
| `--pillar` | `project showcase`, `design tip`, or `philosophy`. Sets the eyebrow label and the type ceiling. |
| `--headline` | The on-image display line. Keep it to one idea. |
| `--deck` | Optional supporting line. Omit it when the headline stands alone. |
| `--project` | Project name. Printed in the footer on project showcases only. |
| `--screenshot` | A real screenshot of real work. There is no stock imagery slot and there will not be one. |
| `--eyebrow` | Overrides the default pillar label. Rarely needed. |
| `--out` | `.jpg` for anything headed to Instagram. `.png` only to inspect. |
| `--keep-html` | Writes the rendered HTML beside the image, for debugging layout. |
| `--json` | Machine-readable result line. |

The headline auto-fits: the script binary-searches the largest size that still
leaves a 10% air margin, then reports the size and line count it settled on.

**Heed the warnings.** If it says the headline wrapped past five lines, the fix
is editorial, not typographic — cut the headline down and move the detail into
the caption. Do not raise the ceiling in the template to make long copy fit.

### What the template guarantees

- Exactly 1080x1350 (4:5, Instagram's tallest allowed feed ratio).
- Paper `#FAF9F5`, ink `#17150F`, one ochre accent mark and no more.
- Fraunces for display, Instrument Sans for everything else, both bundled in
  `resources/fonts/` and inlined as base64 — rendering never touches the network.
- JPEG under Instagram's 8 MB cap, quality stepped down automatically if needed.

### The logo

Drop a PNG or SVG into `resources/logo/` and it replaces the `javierdiaz.design`
wordmark in the footer automatically. Until then the wordmark is used. Nothing
else needs to change.

## Filing into Notion

After rendering, create the calendar row. Use the Notion tools directly:

1. `notion-create-file-upload` with the rendered filename, then POST the JPEG
   as multipart `file` to the returned `upload_url` with the returned
   `upload_headers`.
2. `notion-create-pages` into the **Instagram content calendar** data source
   (`collection://e275ceeb-c069-4876-bcbb-42e816b8c560`), setting `Name`,
   `Pillar`, `Project`, `Caption`, `Schedule date`, and `Status`.
3. Attach the upload to the row's `Image` property, and put the same image in
   the page body so it is visible when the row is opened.

Full property list and the exact option strings are in
[`references/notion-calendar.md`](references/notion-calendar.md).

**Always create rows at `Status = ready for review`.** Never `approved`. That
field is Javier's, and setting it is the whole safety mechanism.

If the caption still has an open question in it — an unconfirmed number, a
client detail nobody has verified — say so when you hand over the row rather
than filing it as if it were finished. `instagram-content-engine`'s rule against
inventing client outcomes applies here too: a gap in a draft stays a visible gap.

## Approve before post

```
render  →  Notion row @ "ready for review"
                     ↓   (Javier flips it by hand — the only manual gate)
              "approved"
                     ↓   (daily routine, Mon–Sat 9am ET)
        oldest approved row dated today or earlier  →  Instagram  →  "posted"
```

The scheduled routine is the only thing that posts, and it will not invent,
draft, edit, or approve content. If nothing is approved, it does nothing and
says so. That is a normal outcome, not a failure.

## Posting (used by the routine, not by hand)

`scripts/post_to_instagram.py` publishes one image through the Meta Graph API.
It has no notion of approval — it posts exactly what it is given — so only the
routine should call it, and only after confirming the row is `approved`.

```bash
python3 scripts/post_to_instagram.py \
  --image-url "https://<fresh Notion file URL>" \
  --caption-file caption.txt
```

Reads `IG_BUSINESS_ACCOUNT_ID` and `IG_ACCESS_TOKEN` from the environment.
`--dry-run` validates the credentials, the URL, the format and the aspect ratio
without posting — use it to check a setup change.

Meta fetches `image_url` from its own servers, so it must be publicly reachable
at that moment. Notion's file URLs are signed and expire in about an hour, which
is fine: fetch the row and post in the same run, and never store the URL for
later.

Setting up the two credentials is a one-time job on Meta's side, written up in
[`references/meta-setup.md`](references/meta-setup.md).

## Guardrails

- Never post to Instagram from this skill, and never set a row to `approved`.
- Never invent client outcomes, numbers, or project details for on-image text.
- Never name the specific tech stack publicly — "modern AI tools" is the ceiling.
- No stock or lifestyle imagery. Real screenshots or type alone.
- One ochre accent per canvas. Emphasis comes from size, weight, and space.
- Do not add a second accent colour, a gradient, or rounded cards to the
  template to make a post "pop". That is the drift identity.md exists to prevent.

## Requirements

- Python 3.9+ and [Pillow](https://pypi.org/project/Pillow/) (`pip install Pillow`).
- Chrome or Chromium. Auto-detected; set `CHROME_BIN` to override.
