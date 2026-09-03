# Instagram content calendar (Notion)

Top-level Notion database. One row per post.

## Finding the calendar

The database and data source IDs are **not stored in this repository** — it is
public, and where Javier's content calendar lives is not something to publish.
Resolve the ID at run time instead, in this order:

1. **A pinned local copy.** If `calendar.local.json` exists at the skill root,
   use the `data_source_id` in it. That file is gitignored; copy
   `calendar.example.json` over it and fill in the ID once.
2. **Otherwise, look it up.** Use the Notion `search` tool for the database
   titled *Instagram content calendar*, then `fetch` it — the response carries
   the `collection://…` data source URL in its `<data-source>` tag.

Pass the data source ID (not the database ID) as `data_source_id` when creating
pages, and as the table name when querying.

If the search returns more than one match, stop and ask rather than guessing.
Writing to the wrong database is not something to recover from silently.

## Properties

| Property | Type | Written by | Notes |
|---|---|---|---|
| `Name` | title | renderer | Short label, e.g. `Tue 8 Sep — design tip — sliders`. |
| `Pillar` | select | renderer | `project showcase`, `design tip`, `philosophy`. |
| `Project` | text | renderer | Client project. Blank for tips and philosophy. |
| `Caption` | text | renderer | The exact caption to post. |
| `Schedule date` | date | renderer | Earliest date this may post. |
| `Status` | select | **Javier**, then routine | `ready for review`, `approved`, `posted`. |
| `Image` | files | renderer | The rendered 1080x1350 JPEG. |
| `Instagram permalink` | url | routine | Set after a successful post. |
| `Posted at` | date | routine | Set after a successful post. |

Option strings are exact and lowercase. `ready for review`, not `Ready for review`.

## Why the image is an attachment

Notion cannot reliably render an image *inside* a table cell, so the rendered
JPEG is attached to the row's `Image` files property and also placed in the page
body. Opening the row shows the finished post; the table view stays readable.

This also gives the routine what Meta needs. Notion serves attachments from
signed S3 URLs that anyone can fetch without auth, which is exactly the
"publicly accessible image URL" the Graph API requires — no separate image
host, no CDN bill.

Two details matter, and both were verified against the live database:

**The URL comes from the page body, not the `Image` property.** Fetching the
row returns the property as an internal `file://{...}` reference that Meta
cannot resolve. The image block in the page body is what returns a real
`https://prod-files-secure.s3.…` URL. This is why the renderer puts the image
in *both* places: the property makes the row scannable, the body block is what
actually makes posting possible.

**The signature expires in 5 minutes** (`X-Amz-Expires=300`), not an hour.
Fetch the row and post in the same step, and never store the URL. If a run
stalls between fetching and posting, re-fetch the page rather than reusing
the URL.

## Creating a row

1. `notion-create-file-upload` → `{ upload_url, upload_headers, file_upload_id }`
2. `POST upload_url` as `multipart/form-data`, file in the `file` field, sending
   every header from `upload_headers`.
3. `notion-create-pages` with `parent.data_source_id` set to the data source
   above, `properties` filled in, and the image in `content`.
4. Set the `Image` property to `[{"type":"file_upload","file_upload":{"id":"<file_upload_id>"}}]`.

Always create at `Status = ready for review`.

## Querying for what is postable

The routine's selection rule, as SQL against the data source:

```sql
SELECT url, "Name", "Caption", "date:Schedule date:start"
FROM "collection://<data source ID>"   -- resolved as above
WHERE "Status" = 'approved'
  AND date("date:Schedule date:start") <= date('now')
ORDER BY date("date:Schedule date:start") ASC, createdTime ASC
LIMIT 1
```

Oldest first, one at a time, never a backlog flush. A row with no schedule date
is not eligible — it has not been scheduled yet.
