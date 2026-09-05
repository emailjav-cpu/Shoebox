#!/usr/bin/env python3
"""Publish one already-approved image to Instagram via the Meta Graph API.

This is the only step that talks to Meta. It is deliberately dumb: it posts
exactly the image URL and caption it is handed, and it has no idea what
"approved" means. The approval gate lives in Notion, and the routine is
responsible for only ever calling this with a row a human marked approved.

The access token can reach Meta two ways, and the script uses whichever is
available:

    Proxy credential   Leave IG_ACCESS_TOKEN unset and store the token as an
    (preferred)        API credential on the cloud environment, scoped to
                       graph.facebook.com with an "Authorization: Bearer"
                       header. The proxy attaches it after the request leaves
                       the container, so the token never lands in a variable,
                       a log, or a shared session.

    Environment        Set IG_ACCESS_TOKEN and it travels in the request as a
    variable           normal parameter. Simpler, but readable by any session
                       in the environment.

Environment:
    IG_BUSINESS_ACCOUNT_ID   Instagram professional account ID. Required.
    IG_ACCESS_TOKEN          Long-lived Page access token. Optional; see above.
    IG_API_VERSION           Optional, defaults to v23.0

    python3 post_to_instagram.py --image-url "https://..." --caption "..."
    python3 post_to_instagram.py --dry-run     # check the credentials alone
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

GRAPH = "https://graph.facebook.com"
DEFAULT_VERSION = "v23.0"

# Instagram accepts 4:5 (0.8) through 1.91:1. A 1080x1350 post sits at the
# 4:5 floor, which is exactly what the renderer produces.
MIN_RATIO, MAX_RATIO = 0.8, 1.91

# Substrings that mark a Graph error as an authentication problem rather than
# a problem with the post itself. Matched case-insensitively. "Provide valid
# app ID" is what Meta says when no token reached it at all, which is exactly
# how an unattached proxy credential presents.
AUTH_MARKERS = ("access token", "oauthexception", "code 190", "code 104",
                "provide valid app id", "code 200")

HINT_PROXY = (
    "IG_ACCESS_TOKEN is not set, so this run expected the environment's proxy "
    "to attach an API credential. Check that credential on the cloud "
    "environment: host graph.facebook.com, header 'Authorization' with prefix "
    "'Bearer'. The environment dialog marks a credential it cannot send as "
    "'Not sent'. To fall back, set IG_ACCESS_TOKEN as an environment variable "
    "instead."
)
HINT_ENV = (
    "IG_ACCESS_TOKEN is set, so the token travelled in the request and Meta "
    "rejected it. Regenerate it with steps 5-7 of references/meta-setup.md."
)


class GraphError(RuntimeError):
    pass


def _request(url, data=None, timeout=60):
    """Call the Graph API and raise a readable error instead of an HTTPError."""
    body = urllib.parse.urlencode(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode(errors="replace")
        try:
            err = json.loads(raw).get("error", {})
            msg = err.get("message", raw)
            # Meta's own hints are far more useful than anything we could invent.
            for key in ("error_user_title", "error_user_msg"):
                if err.get(key):
                    msg += " | %s" % err[key]
            if err.get("code"):
                msg += " (code %s)" % err["code"]
        except ValueError:
            msg = raw
        raise GraphError("Graph API %s: %s" % (exc.code, msg)) from None
    except urllib.error.URLError as exc:
        raise GraphError(
            "Could not reach %s (%s). If this is a scheduled cloud run, the "
            "environment's network policy must allow graph.facebook.com."
            % (GRAPH, exc.reason)
        ) from None


def _base(version):
    return "%s/%s" % (GRAPH, version)


def _params(token, fields):
    """POST body, carrying the token only when we hold it ourselves.

    With no token the request goes out bare and the proxy adds the header, so
    omitting the key is what selects proxy-credential auth.
    """
    params = dict(fields)
    if token:
        params["access_token"] = token
    return params


def _query(token, fields):
    """The same rule for a GET, returned as an encoded query string."""
    return urllib.parse.urlencode(_params(token, fields))


def auth_mode(token):
    return "environment variable" if token else "proxy API credential"


def auth_hint(message, token):
    """Explain an authentication failure in terms of the mode actually used."""
    if not any(marker in message.lower() for marker in AUTH_MARKERS):
        return ""
    return HINT_ENV if token else HINT_PROXY


def check_auth(ig_id, token, version):
    """Confirm we can authenticate as this Instagram account.

    This is the one call that proves a proxy-credential setup is wired
    correctly, because it fails the same way a real post would but costs
    nothing and publishes nothing.
    """
    info = _request("%s/%s?%s" % (_base(version), ig_id,
                                  _query(token, {"fields": "id,username"})))
    return {"id": info.get("id", ""), "username": info.get("username", "")}


def check_image(url, timeout=45):
    """Confirm Meta will be able to fetch this URL, and that the shape is legal.

    Meta downloads the image server-side, so a URL that 404s or needs a cookie
    fails with an opaque error. Checking here turns that into a clear message.
    """
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            ctype = resp.headers.get("Content-Type", "")
            payload = resp.read(2 * 1024 * 1024)
    except Exception as exc:  # noqa: BLE001 - any failure here is disqualifying
        raise GraphError(
            "Image URL is not publicly fetchable (%s). Meta downloads it from "
            "its own servers, so it cannot be behind auth and must not expire "
            "before this call." % exc
        ) from None

    if "image" not in ctype.lower():
        raise GraphError("Image URL returned Content-Type %r, expected an image." % ctype)
    if "jpeg" not in ctype.lower() and "jpg" not in ctype.lower():
        # Instagram only publishes JPEG for feed images.
        raise GraphError("Instagram requires JPEG; this URL served %r." % ctype)

    try:
        from PIL import Image
        import io

        with Image.open(io.BytesIO(payload)) as im:
            w, h = im.size
        ratio = w / float(h)
        if not (MIN_RATIO <= ratio <= MAX_RATIO):
            raise GraphError(
                "Aspect ratio %.3f (%dx%d) is outside Instagram's 0.8-1.91 range." % (ratio, w, h)
            )
        return {"width": w, "height": h, "ratio": round(ratio, 3)}
    except ImportError:
        return {}
    except GraphError:
        raise
    except Exception:
        # Partial read of a large file; the shape check is best-effort only.
        return {}


def publish(ig_id, token, image_url, caption, version, poll_seconds=90):
    base = _base(version)

    # 1. Create the media container. Meta fetches image_url at this moment.
    container = _request(
        "%s/%s/media" % (base, ig_id),
        _params(token, {"image_url": image_url, "caption": caption}),
    )
    creation_id = container.get("id")
    if not creation_id:
        raise GraphError("No container id in response: %s" % json.dumps(container))

    # 2. Wait for the container to finish processing before publishing.
    deadline = time.time() + poll_seconds
    status = None
    while time.time() < deadline:
        info = _request(
            "%s/%s?%s" % (base, creation_id,
                          _query(token, {"fields": "status_code,status"}))
        )
        status = info.get("status_code")
        if status == "FINISHED":
            break
        if status == "ERROR":
            raise GraphError("Container failed: %s" % info.get("status", info))
        time.sleep(3)
    else:
        raise GraphError("Container %s still %s after %ds." % (creation_id, status, poll_seconds))

    # 3. Publish it.
    published = _request(
        "%s/%s/media_publish" % (base, ig_id),
        _params(token, {"creation_id": creation_id}),
    )
    media_id = published.get("id")
    if not media_id:
        raise GraphError("No media id in response: %s" % json.dumps(published))

    # 4. Fetch the permalink for the audit trail. Non-fatal if it fails.
    permalink = ""
    try:
        permalink = _request(
            "%s/%s?%s" % (base, media_id, _query(token, {"fields": "permalink"}))
        ).get("permalink", "")
    except GraphError:
        pass

    return {"media_id": media_id, "creation_id": creation_id, "permalink": permalink}


def main(argv=None):
    p = argparse.ArgumentParser(description="Post one image to Instagram.")
    p.add_argument("--image-url", default="",
                   help="Publicly fetchable JPEG URL. Optional with --dry-run.")
    p.add_argument("--caption", default="", help="Caption text.")
    p.add_argument("--caption-file", default="", help="Read the caption from a file instead.")
    p.add_argument("--ig-id", default=os.environ.get("IG_BUSINESS_ACCOUNT_ID", ""))
    p.add_argument("--token", default=os.environ.get("IG_ACCESS_TOKEN", ""),
                   help="Omit to let the environment's proxy credential supply it.")
    p.add_argument("--version", default=os.environ.get("IG_API_VERSION", DEFAULT_VERSION))
    p.add_argument("--dry-run", action="store_true",
                   help="Validate credentials and image, but do not post.")
    opts = p.parse_args(argv if argv is not None else sys.argv[1:])

    caption = opts.caption
    if opts.caption_file:
        with open(opts.caption_file, encoding="utf-8") as fh:
            caption = fh.read().strip()

    # The token is deliberately not checked here: an empty one means the proxy
    # is expected to supply it, and only Meta can tell us whether it did.
    if not opts.ig_id:
        print("Missing required credential: IG_BUSINESS_ACCOUNT_ID", file=sys.stderr)
        return 2
    if not opts.image_url and not opts.dry_run:
        print("--image-url is required unless you pass --dry-run.", file=sys.stderr)
        return 2

    # Instagram truncates hard at 2200 characters.
    if len(caption) > 2200:
        print("Caption is %d characters; Instagram's limit is 2200." % len(caption), file=sys.stderr)
        return 2

    try:
        account = check_auth(opts.ig_id, opts.token, opts.version)
        shape = check_image(opts.image_url) if opts.image_url else {}
        if opts.dry_run:
            print(json.dumps({"dry_run": True, "auth": auth_mode(opts.token),
                              "account": account, "image": shape,
                              "caption_chars": len(caption), "ok": True}))
            return 0
        result = publish(opts.ig_id, opts.token, opts.image_url, caption, opts.version)
    except GraphError as exc:
        print(str(exc), file=sys.stderr)
        hint = auth_hint(str(exc), opts.token)
        if hint:
            print(hint, file=sys.stderr)
        return 1

    result["image"] = shape
    result["auth"] = auth_mode(opts.token)
    result["account"] = account
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
