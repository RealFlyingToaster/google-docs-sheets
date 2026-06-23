#!/usr/bin/env python3
"""Shared Google auth + HTTP helpers for the google-docs-sheets plugin.

Auth model:  credentials  ->  access_token  ->  call Sheets / Docs / Drive APIs

Resolution order (first hit wins):
  1. $GOOGLE_ACCESS_TOKEN            — a ready-to-use OAuth access token.
  2. $GOOGLE_SERVICE_ACCOUNT_KEY     — a service-account JSON key (file path OR
                                       inline JSON). Optional
                                       $GOOGLE_IMPERSONATE_SUBJECT enables
                                       Workspace domain-wide delegation (act as a
                                       user). Requires the `google-auth` package.
  3. $GOOGLE_OAUTH_REFRESH_TOKEN     — a refresh token, exchanged here using the
     / --token-file / $GOOGLE_TOKEN_FILE  OAuth client at
                                       $GOOGLE_OAUTH_CREDENTIALS (default
                                       ~/.config/gogcli/credentials.json).
  4. gog keyring export              — convenience fallback for the Figaro host:
                                       `gog auth tokens export $GOG_ACCOUNT`.

Scopes requested for the service account:
  https://www.googleapis.com/auth/spreadsheets
  https://www.googleapis.com/auth/documents
  https://www.googleapis.com/auth/drive

Set $GSUITE_DRY_RUN=1 (or pass --dry-run on the CLIs) to print the request that
WOULD be sent instead of calling the API — useful for validation without creds.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.parse

import requests

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
]

# OAuth client used for the refresh-token path. gog stores one here.
CREDS_PATH = os.path.expanduser(
    os.environ.get("GOOGLE_OAUTH_CREDENTIALS",
                   os.environ.get("GOG_CREDENTIALS",
                                  "~/.config/gogcli/credentials.json"))
)
DEFAULT_ACCOUNT = os.environ.get("GOG_ACCOUNT", "")
GOG_BIN = os.environ.get("GOG", os.path.expanduser("~/.local/bin/gog"))

DRY_RUN = os.environ.get("GSUITE_DRY_RUN", "") not in ("", "0", "false", "False")

_CACHED_TOKEN = None


def set_dry_run(value):
    global DRY_RUN
    DRY_RUN = bool(value)


# ---------------------------------------------------------------- auth paths --

def _token_from_service_account():
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_KEY")
    if not raw:
        return None
    try:
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request
    except ImportError:
        raise SystemExit(
            "GOOGLE_SERVICE_ACCOUNT_KEY is set but the `google-auth` package is "
            "not installed. Run:  pip install -r requirements.txt"
        )
    if raw.lstrip().startswith("{"):
        info = json.loads(raw)
        creds = service_account.Credentials.from_service_account_info(
            info, scopes=SCOPES)
    else:
        creds = service_account.Credentials.from_service_account_file(
            os.path.expanduser(raw), scopes=SCOPES)
    subject = os.environ.get("GOOGLE_IMPERSONATE_SUBJECT")
    if subject:
        creds = creds.with_subject(subject)
    creds.refresh(Request())
    return creds.token


def _exchange_refresh_token(refresh_token):
    with open(CREDS_PATH) as f:
        creds = json.load(f)
    creds = creds.get("installed", creds.get("web", creds))
    r = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": creds["client_id"],
            "client_secret": creds["client_secret"],
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    if r.status_code != 200:
        raise SystemExit(
            f"Token exchange failed ({r.status_code}): {r.text}\n"
            f"Check the OAuth client at {CREDS_PATH} and that the refresh token "
            "is still valid."
        )
    return r.json()["access_token"]


def _refresh_token_from_gog(account=None):
    account = account or DEFAULT_ACCOUNT
    if not account or not os.path.exists(GOG_BIN):
        return None
    tmp = tempfile.NamedTemporaryFile("r", suffix=".json", delete=False)
    tmp.close()
    try:
        subprocess.run(
            [GOG_BIN, "auth", "tokens", "export", account, "--out", tmp.name],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        with open(tmp.name) as f:
            return json.load(f).get("refresh_token")
    except Exception:
        return None
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def get_access_token(token_file=None, account=None):
    """Return a usable OAuth access token, minting one if needed."""
    global _CACHED_TOKEN
    if _CACHED_TOKEN:
        return _CACHED_TOKEN
    if DRY_RUN:
        return "DRY_RUN_TOKEN"

    # 1. Ready access token
    tok = os.environ.get("GOOGLE_ACCESS_TOKEN")
    if tok:
        _CACHED_TOKEN = tok
        return tok

    # 2. Service account
    tok = _token_from_service_account()
    if tok:
        _CACHED_TOKEN = tok
        return tok

    # 3. Refresh token (env, then file)
    refresh = (os.environ.get("GOOGLE_OAUTH_REFRESH_TOKEN")
               or os.environ.get("GOG_REFRESH_TOKEN"))
    if not refresh:
        tf = (token_file or os.environ.get("GOOGLE_TOKEN_FILE")
              or os.environ.get("GOG_TOKEN_FILE"))
        if tf and os.path.exists(tf):
            with open(tf) as f:
                refresh = json.load(f).get("refresh_token")

    # 4. gog keyring (Figaro host only)
    if not refresh:
        refresh = _refresh_token_from_gog(account)

    if not refresh:
        raise SystemExit(
            "No Google credentials found. Set one of:\n"
            "  - GOOGLE_ACCESS_TOKEN          (a ready access token)\n"
            "  - GOOGLE_SERVICE_ACCOUNT_KEY   (service-account JSON; recommended)\n"
            "  - GOOGLE_OAUTH_REFRESH_TOKEN / --token-file (OAuth refresh token)\n"
            "See SETUP.md for the service-account walkthrough."
        )
    _CACHED_TOKEN = _exchange_refresh_token(refresh)
    return _CACHED_TOKEN


# ----------------------------------------------------------------- dry-run ----

def _dry_response(method, url, body):
    """Synthesize a structurally-valid response so dry-run CLIs can finish."""
    if "batchUpdate" in url:
        n = len((body or {}).get("requests", []))
        return {"replies": [{} for _ in range(n)]}
    if url.rstrip("/").endswith("/documents") and method == "POST":
        return {"documentId": "DRY_RUN_DOC_ID", "title": (body or {}).get("title")}
    if url.rstrip("?").endswith("/spreadsheets") and method == "POST":
        return {"spreadsheetId": "DRY_RUN_SHEET_ID"}
    if "/values/" in url and method == "GET":
        return {"values": []}
    if "/values/" in url:  # write / append / clear
        return {"updatedRange": "(dry-run)", "updatedCells": 0,
                "updates": {}, "clearedRange": "(dry-run)"}
    if "/spreadsheets/" in url and method == "GET":
        return {"spreadsheetId": "DRY_RUN_SHEET_ID",
                "properties": {"title": "(dry-run)"},
                "sheets": [{"properties": {"sheetId": 0, "title": "Sheet1",
                                           "index": 0, "gridProperties": {}}}]}
    if "/documents/" in url and method == "GET":
        return {"documentId": "DRY_RUN_DOC_ID", "title": "(dry-run)",
                "body": {"content": [{"startIndex": 1, "endIndex": 1,
                                      "paragraph": {"elements": []}}]}}
    return {}


# -------------------------------------------------------------------- http ----

def api(method, url, token=None, json_body=None, params=None, retries=3):
    """Call a Google REST endpoint and return parsed JSON.

    In dry-run mode, print the request and return a synthetic response.
    """
    if params:
        url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)

    if DRY_RUN:
        record = {"DRY_RUN": True, "method": method, "url": url}
        if json_body is not None:
            record["body"] = json_body
        print(json.dumps(record, indent=2, ensure_ascii=False), file=sys.stderr)
        return _dry_response(method, url, json_body)

    if token is None:
        token = get_access_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    last = None
    for attempt in range(retries):
        r = requests.request(method, url, headers=headers, json=json_body, timeout=60)
        if r.status_code in (429, 500, 502, 503, 504):
            last = r
            time.sleep(2 ** attempt)
            continue
        if r.status_code >= 400:
            raise SystemExit(f"{method} {url}\nHTTP {r.status_code}: {r.text}")
        return r.json() if r.text else {}
    raise SystemExit(
        f"{method} {url}\nGave up after {retries} retries. "
        f"Last: HTTP {last.status_code}: {last.text}")


def out(obj):
    print(json.dumps(obj, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "token":
        print(get_access_token())
    else:
        print("usage: google_auth.py token", file=sys.stderr)
        sys.exit(1)
