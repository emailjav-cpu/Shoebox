# Getting `IG_BUSINESS_ACCOUNT_ID` and `IG_ACCESS_TOKEN`

One-time setup on Meta's side. Budget about an hour. Everything here is free —
no App Review, no third-party scheduler, no paid tier.

**You do not need App Review.** While your app is in *Development* mode, its
permissions work fully for anyone with a role on the app. You are the admin, and
you are posting to your own account, so that covers you. App Review is only for
publishing on behalf of *other people's* accounts.

---

## Step 1 — Instagram must be a Professional account

In the Instagram app: **Settings → Account type and tools → Switch to
professional account**, and choose **Business**.

Creator accounts have patchier content-publishing support. Pick Business.

## Step 2 — A Facebook Page, linked to that Instagram account

The API reaches Instagram *through* a Facebook Page. You need one even though
you may never post to it.

1. Create a Page for the business if you don't have one (facebook.com/pages/create).
2. On the Page: **Settings → Linked accounts → Instagram → Connect account.**
3. Confirm it worked in the Instagram app: **Settings → Accounts Center** should
   show the Page.

If the Page and the Instagram account are not linked, everything later returns
an empty `instagram_business_account` and the cause is not obvious. Verify now.

## Step 3 — A Business Portfolio holding both

Go to [business.facebook.com](https://business.facebook.com). Create a Business
Portfolio if you don't have one, then add **both** assets to it:

- **Accounts → Pages →** add your Page
- **Accounts → Instagram accounts →** add `@javierdiaz.design`

This is what `business_management` needs in order to see them.

## Step 4 — Create the developer app

1. [developers.facebook.com/apps](https://developers.facebook.com/apps) → **Create app**
2. Use case: **Other** → app type: **Business**
3. Name it something like `javierdiaz.design publisher`
4. Link it to the Business Portfolio from step 3 when prompted
5. In the app dashboard, add the **Instagram** product (and **Facebook Login**
   if it isn't added automatically)
6. Leave the app in **Development** mode

From **App settings → Basic**, copy the **App ID** and **App Secret**. You'll
need both in step 6. Treat the secret like a password.

## Step 5 — Generate a short-lived user token

Open the [Graph API Explorer](https://developers.facebook.com/tools/explorer/).

1. **Meta App:** your new app
2. **User or Page:** *User token*
3. **Add permissions** — tick exactly these five:
   - `pages_show_list`
   - `business_management`
   - `instagram_basic`
   - `instagram_content_publish`
   - `pages_read_engagement`
4. **Generate Access Token**, and grant everything in the popup. If it asks
   which Pages to allow, choose your Page explicitly — "opt out" here is the
   most common reason the next step returns nothing.

Copy the token. It expires in about an hour, which is fine — it is only raw
material for step 6.

## Step 6 — Exchange it for a long-lived token

In a terminal, with `APP_ID`, `APP_SECRET` and the token from step 5:

```bash
curl -s "https://graph.facebook.com/v23.0/oauth/access_token?\
grant_type=fb_exchange_token&\
client_id=APP_ID&\
client_secret=APP_SECRET&\
fb_exchange_token=SHORT_LIVED_TOKEN"
```

Returns a **long-lived user token**, good for about 60 days. Keep it for step 7.

## Step 7 — Turn that into a non-expiring Page token

```bash
curl -s "https://graph.facebook.com/v23.0/me/accounts?access_token=LONG_LIVED_USER_TOKEN"
```

Find your Page in the list. Note two things:

- its **`id`** — the Page ID, needed in step 8
- its **`access_token`** — **this is your `IG_ACCESS_TOKEN`**

A Page token derived from a long-lived user token has no expiry of its own.
Confirm it:

```bash
curl -s "https://graph.facebook.com/v23.0/debug_token?\
input_token=PAGE_TOKEN&access_token=APP_ID|APP_SECRET"
```

`"expires_at": 0` means it does not expire. It still dies if you change your
Facebook password, remove the app, or lose your role on the Page — and after
about 90 days of no API calls, which posting six days a week comfortably avoids.

## Step 8 — Get the Instagram account ID

```bash
curl -s "https://graph.facebook.com/v23.0/PAGE_ID?\
fields=instagram_business_account&access_token=PAGE_TOKEN"
```

```json
{ "instagram_business_account": { "id": "17841400000000000" } }
```

That `id` is your **`IG_BUSINESS_ACCOUNT_ID`**. It is a 17-digit number starting
`1784…`, and it is *not* the same as your Page ID or your Instagram username.

**Empty response?** The Page and Instagram account are not linked, or the
Instagram account is still Personal. Go back to steps 1–2.

---

## Step 9 — Hand the two values over

Both go on the cloud environment the routine runs in. Open it at
[claude.ai/code](https://claude.ai/code): the cloud icon in the row above the
message box, then the gear beside the environment's name. There is no settings
page or direct URL for it.

The two values go in **different boxes**, and the difference matters.

### `IG_BUSINESS_ACCOUNT_ID` → Environment variables

From step 8, in `.env` format:

```
IG_BUSINESS_ACCOUNT_ID=17841400000000000
```

It is an account identifier, not a secret, so the variables box is the right
home for it.

### `IG_ACCESS_TOKEN` → API credentials

From step 7. **Not** the variables box — that box states its contents are
visible to anyone using the environment, and this token posts as you and never
expires. Select **Add credential** and fill in:

| Field | Value |
|---|---|
| Credential type | **Bearer** (the default) |
| Name | anything, e.g. `Instagram publishing` |
| Allowed websites | `graph.facebook.com` |
| Custom headers | name `Authorization`, prefix `Bearer`, value = the token |

The proxy attaches it to Graph API requests after they leave the container, so
the token never reaches the session, an environment variable, a log, or a
shared session. `post_to_instagram.py` omits its own `access_token` parameter
when `IG_ACCESS_TOKEN` is unset, and that omission is what selects this mode.

You cannot view a credential's value after saving, and there is no edit — to
change one, delete it and add it again. API credentials need a Pro or Max plan;
on Team and Enterprise the section does not appear.

If the credential ever misbehaves, setting `IG_ACCESS_TOKEN` as an ordinary
environment variable still works and the script switches back on its own. That
fallback is the reason to prefer the credential rather than fear it.

### Network access

Allow **`graph.facebook.com`** under **Network access → Custom**, keeping
*"Also include default list of common package managers"* ticked so the existing
allowances survive. A credential's hosts become reachable on their own, but the
explicit entry costs nothing and keeps the two concerns separate.

Paste the values into the environment settings rather than into chat, and never
commit them to the repository.

## Verifying before you trust it

```bash
python3 scripts/post_to_instagram.py --dry-run
```

Authenticates against Meta and prints the account it actually reached, without
posting and without needing an image:

```json
{"dry_run": true, "auth": "proxy API credential",
 "account": {"id": "17841400000000000", "username": "javierdiaz.design"}}
```

Read the `auth` field. If it says `environment variable` when you meant to use
a credential, `IG_ACCESS_TOKEN` is still set somewhere and is taking
precedence — clear it.

Add `--image-url "https://…"` to also check that a real image is publicly
fetchable, is JPEG, and has a legal aspect ratio.

## When something breaks later

| Symptom | Cause |
|---|---|
| `Error validating access token` | Token revoked — password change, app removed, or Page role lost. Redo steps 5–7. |
| `(#200) Permissions error` | A permission was dropped. Re-grant all five in step 5. |
| `Unsupported get request` on the IG ID | Wrong ID — you used the Page ID or username instead of the `1784…` value. |
| `The Instagram account is restricted` | Meta-side account limit; check Instagram's Account Status. |
| `Media could not be fetched` | The image URL expired or wasn't public. Notion signs them for **5 minutes** — re-fetch the row and post in the same step. |
| `(#200) Provide valid app ID` | No token reached Meta at all. In proxy-credential mode that means the credential isn't attached; the environment dialog marks one it can't send as **Not sent**. |
| Unknown API version | Meta retired `v23.0`. Set `IG_API_VERSION` to a current version. |

Rate limit: 100 published posts per rolling 24 hours. One a day uses 1%.
