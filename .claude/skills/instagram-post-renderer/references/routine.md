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

## Setup status

All of this lives outside the repo, on the routine and its environment.

| | State |
|---|---|
| Notion connector attached to the routine | **Done**, 5 Sep 2026. Without it a fired session gets no Notion tools at all and every run dies at step 2. |
| `graph.facebook.com` allowed in the environment's network policy | **Done**, 5 Sep 2026. Verified reachable from a session; before the change the proxy refused the tunnel outright. `prod-files-secure.s3.us-west-2.amazonaws.com`, where Notion serves the image, is allowed alongside it. |
| `IG_BUSINESS_ACCOUNT_ID` | **Done**, 5 Sep 2026. Read straight off the Business Portfolio, which displays it — steps 5-8 of `meta-setup.md` are not the only way to get it. |
| `IG_ACCESS_TOKEN` | **Outstanding.** Blocked on Meta for Developers registration, which is a Meta-side problem rather than anything here. Goes in as an API credential, not an environment variable — see [`meta-setup.md`](meta-setup.md#step-9--hand-the-two-values-over). |

Until the token is in place the routine runs, finds nothing approved or reports
the missing credential, and posts nothing. That is the intended failure mode,
not a fault to work around.

## Checking on it

`CronList` / the Routines UI shows the last run and its outcome. A run that
reports "nothing approved and due today" is working correctly.

To pause it, disable the routine — do not delete it, or the trigger ID above
stops matching.
