# The "Auto post Insta" routine

Cloud-hosted scheduled job. Runs whether or not the laptop is on.

| | |
|---|---|
| **Name** | Auto post Insta |
| **Trigger ID** | `trig_01QqS1QB49xNAEXMfKhFXkWb` |
| **Environment** | JD Design (`env_012r8USDxA5pCfmSXNNy9aWE`) |
| **Schedule** | `7 13 * * 1-6` UTC — 9:07am ET, Monday–Saturday |
| **Mode** | Fresh session per run |

## What it does each run

1. Queries the calendar for `Status = approved` **and** `Schedule date <= today`.
2. Takes the **single oldest** match. Never more, never a backlog flush.
3. Reads the signed image URL from the page body and posts it through
   `scripts/post_to_instagram.py`.
4. On success only: sets `Status = posted`, stamps `Posted at`, and stores the
   `Instagram permalink`.

Nothing approved and due means it does nothing and says so. That is a success.

## What it will never do

Draft, invent, edit, or approve content. Set any status other than `posted`.
Post a row that is not exactly `approved`. Post more than once per run.

If a post fails the row stays `approved`, so the next morning retries it.

## Daylight saving

Cron runs in UTC, so `13:07 UTC` is 9:07am **EDT**. When ET falls back to EST in
November this becomes 8:07am. To hold 9am year-round, change the hour to `14`
for the winter months and back to `13` in March.

## Setup this routine still needs

Three things, all outside the repo:

1. **Attach the Notion connector to the routine.** It was created without one —
   the API path for granting connectors is not enabled on this account, and a
   routine with no connectors fires sessions that have no Notion tools at all,
   so every run would fail at step 2. Fix it in **claude.ai → Routines → Auto
   post Insta → connectors**, and attach only Notion.
2. **Set the two environment variables** on the JD Design environment:
   `IG_BUSINESS_ACCOUNT_ID` and `IG_ACCESS_TOKEN`. See
   [`meta-setup.md`](meta-setup.md).
3. **Allow `graph.facebook.com`** in that environment's network policy. The
   default policy blocks it, and the posting step cannot reach Meta without it.
   `prod-files-secure.s3.us-west-2.amazonaws.com` (where Notion serves the
   image) is already reachable.

Until all three are done the routine runs and reports what is missing, rather
than posting anything. That is the intended failure mode.

## Checking on it

`CronList` / the Routines UI shows the last run and its outcome. A run that
reports "nothing approved and due today" is working correctly.

To pause it, disable the routine — do not delete it, or the trigger ID above
stops matching.
