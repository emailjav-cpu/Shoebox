# Instagram content calendar (Notion)

Top-level Notion database. One row per post.

- **Database:** https://app.notion.com/p/8d2001de09df42fba1a1bf5fe820b7b3
- **Data source:** `collection://e275ceeb-c069-4876-bcbb-42e816b8c560`

Pass the data source ID (not the database ID) as `data_source_id` when creating
pages, and as the table name when querying.

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
signed URLs that anyone can fetch without auth, which is exactly the "publicly
accessible image URL" the Graph API requires — no separate image host, no CDN
bill. The signature expires after roughly an hour, so the URL must be fetched
fresh in the same run that posts it, and never cached.

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
FROM "collection://e275ceeb-c069-4876-bcbb-42e816b8c560"
WHERE "Status" = 'approved'
  AND date("date:Schedule date:start") <= date('now')
ORDER BY date("date:Schedule date:start") ASC, createdTime ASC
LIMIT 1
```

Oldest first, one at a time, never a backlog flush. A row with no schedule date
is not eligible — it has not been scheduled yet.
