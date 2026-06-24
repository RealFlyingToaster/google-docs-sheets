# Google Docs & Sheets — a Claude Code plugin

Give Claude full fluency with **Google Sheets** and **Google Docs**: create, read,
edit, and *style* live Google files — values, formulas, number formats, colors,
borders, frozen headers, merged cells, headings, bullets, tables, hyperlinks, and
find-and-replace — plus a raw `batchUpdate` escape hatch for anything the APIs
support.

Built for agencies and consultants to offer nonprofit clients a headless,
service-account–based document automation capability.

## How it works

A Skill teaches Claude to drive two small Python CLIs that call the Google Sheets
v4 and Docs v1 REST APIs directly:

- `gsheet` — spreadsheets
- `gdoc` — documents

Only dependencies: Python 3 + `requests` (and `google-auth` for the
service-account auth path). No Google client libraries to wrestle with, no MCP
server to run.

## Install (Claude Code)

```text
/plugin marketplace add RealFlyingToaster/google-docs-sheets
/plugin install google-docs-sheets@eightfold-plugins
```

(Or, while developing locally, point the marketplace at this directory:
`/plugin marketplace add ./plugins/google-docs-sheets`.)

Then set up credentials (below) and install runtime deps:

```bash
pip install -r requirements.txt
```

## Authentication

The CLIs read credentials from the environment — no flags at call time. Set **one**
of the following (first match wins); see **[SETUP.md](SETUP.md)** for the full
walkthrough.

```bash
# Recommended: service-account JSON key (path or inline JSON)
export GOOGLE_SERVICE_ACCOUNT_KEY="/secure/path/docs-bot.json"

# Optional — Workspace domain-wide delegation: act AS a user, so files land in
# their Drive instead of the service account's (quota-limited) Drive.
export GOOGLE_IMPERSONATE_SUBJECT="staff@client.org"

# Or, instead of a service account:
export GOOGLE_ACCESS_TOKEN="ya29...."          # a ready OAuth access token
export GOOGLE_OAUTH_REFRESH_TOKEN="1//0...."   # an OAuth refresh token
```

Two access models (detailed in SETUP.md):

- **Tier 1 — shared access (default).** The service account only touches files/
  folders explicitly shared with its email. No Workspace admin needed. Files it
  *creates* are owned by the SA, so create them in a **Shared Drive** the account
  belongs to (`--parent <sharedDriveFolderId>`).
- **Tier 2 — domain-wide delegation.** A Workspace Super Admin authorizes the SA's
  **Client ID** for the `spreadsheets`, `documents`, and `drive` scopes; then set
  `GOOGLE_IMPERSONATE_SUBJECT` to act as a user. Required if the SA must operate
  org-wide or write into users' personal Drives.

In Claude Code, set these in your `settings.json` `env` block so every session
picks them up. Verify wiring without touching data:

```bash
python3 "$CLAUDE_PLUGIN_ROOT/skills/google-docs-sheets/scripts/gsheet.py" \
        create --title "Test" --dry-run
```

> Treat the JSON key like a password: store it outside the repo and never commit it.

## Quick start

```bash
SCRIPTS="$CLAUDE_PLUGIN_ROOT/skills/google-docs-sheets/scripts"

# Spreadsheet
python3 "$SCRIPTS/gsheet.py" create --title "Q3 Budget" --tabs "Summary,Data"
python3 "$SCRIPTS/gsheet.py" write  <id> --range "Data!A1" \
        --values-json '[["Item","Amount"],["Rent",1800],["Stipends",4200]]'
python3 "$SCRIPTS/gsheet.py" format <id> --range "Data!A1:B1" \
        --bold --bg "#1f2937" --color "#ffffff"
python3 "$SCRIPTS/gsheet.py" format <id> --range "Data!B2:B3" --number-format '$#,##0'
python3 "$SCRIPTS/gsheet.py" freeze <id> --range "Data" --rows 1

# Document
python3 "$SCRIPTS/gdoc.py" create --title "Board Brief"
python3 "$SCRIPTS/gdoc.py" append <id> --text "Board Brief\nQ3 highlights below.\n"
python3 "$SCRIPTS/gdoc.py" get    <id> --ranges          # learn the indices
python3 "$SCRIPTS/gdoc.py" para   <id> --start 1 --end 11 --named-style TITLE
```

Add `--dry-run` to any command to print the request JSON without calling the API.

## Capabilities

- **Sheets:** create, info, read, write, append, clear, add/delete tabs, cell
  formatting (bold/italic/font/size/color/background/alignment/wrap), number &
  currency & date formats, borders, frozen rows/cols, merged cells, column/row
  sizing, and raw `batch` (conditional formatting, charts, validation, …).
- **Docs:** create, get (text / per-paragraph index ranges / raw), append, insert
  (text inline or from a UTF-8 file/stdin via `--text-file`), find-and-replace,
  character styling (bold/italic/underline/strike/font/size/color/highlight/link),
  paragraph styling (named styles/headings, alignment), bullet & numbered &
  **checkbox** lists (`--bullet-preset BULLET_CHECKBOX` for to-do worksheets),
  tables, Drive **comments** (list/add/reply/resolve), and raw `batch` (images,
  page breaks, table cell styling, …).

See `skills/google-docs-sheets/references/` for the exact `batchUpdate` request
shapes behind the `batch` command.

## License

MIT — see [LICENSE](LICENSE).
