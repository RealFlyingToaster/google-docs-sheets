---
name: google-docs-sheets
description: Create, edit, and style Google Sheets and Google Docs with full fluency — build spreadsheets (values, formulas, bold/colors/number formats/borders/frozen headers/merged cells) and documents (headings, bold/italic/links/fonts, bullet lists, tables, find-and-replace). Use whenever the user wants to make, update, format, or style a Google Sheet or Google Doc, generate a report/budget/agenda/brief as a live Google file, or fill a Doc/Sheet template.
---

# Google Docs & Sheets

Two CLIs back this skill, talking directly to the Google Sheets v4 and Docs v1
REST APIs:

- `gsheet` — spreadsheets: `scripts/gsheet.py`
- `gdoc` — documents: `scripts/gdoc.py`

Run them with the plugin root prefix:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/google-docs-sheets/scripts/gsheet.py" <cmd> ...
python3 "${CLAUDE_PLUGIN_ROOT}/skills/google-docs-sheets/scripts/gdoc.py"   <cmd> ...
```

Every command prints JSON. Add `--dry-run` to any command to print the request
that *would* be sent without calling the API (great for checking a complex
`batch` before running it).

## Auth (one-time, per environment)

Credentials are read from the environment — no flags needed at call time. See
`SETUP.md` for the full walkthrough. In order of preference:

- `GOOGLE_SERVICE_ACCOUNT_KEY` — path to (or inline JSON of) a service-account
  key. For Workspace, set `GOOGLE_IMPERSONATE_SUBJECT=user@org.org` to act as a
  user (domain-wide delegation); otherwise share the target file/Shared Drive
  with the service-account email.
- `GOOGLE_ACCESS_TOKEN` — a ready OAuth access token.
- `GOOGLE_OAUTH_REFRESH_TOKEN` (or `--token-file`) — an OAuth refresh token.

If none are set the CLIs exit with a clear message pointing to `SETUP.md`.

## Sheets — `gsheet`

| Command | Purpose |
|---|---|
| `create --title T [--tabs "A,B"] [--parent FOLDER]` | new spreadsheet |
| `info <id>` | list tabs, sheetIds, grid sizes |
| `read <id> --range "Tab!A1:D20" [--render FORMULA]` | read values |
| `write <id> --range "Tab!A1" --values-json '[[...]]'` | overwrite (also `--csv`, `--tsv -`) |
| `append <id> --range "Tab!A1" --csv rows.csv` | append rows |
| `clear <id> --range "Tab!A1:D9"` | clear values |
| `add-sheet <id> --title T` / `delete-sheet <id> --title T` | manage tabs |
| `format <id> --range R [flags]` | style cells (below) |
| `freeze <id> --range "Tab" --rows 1` | freeze header rows/cols |
| `merge <id> --range "Tab!A1:D1"` | merge cells |
| `width <id> --range "Tab!A:A" --pixels 220` (or `--auto`) | size columns/rows |
| `batch <id> --requests-json '[...]'` | raw `spreadsheets.batchUpdate` |

`format` flags: `--bold --italic --strikethrough --font-size N --font NAME
--color #hex --bg #hex --h-align LEFT|CENTER|RIGHT --v-align TOP|MIDDLE|BOTTOM
--wrap --number-format "$#,##0.00" --border #hex`. The number-format *type*
(CURRENCY/PERCENT/DATE/NUMBER) is auto-guessed from the pattern; override with
`--number-type`.

Ranges accept A1 with an optional tab prefix (`"Data!A1:D1"`, `"A:A"`, `"2:5"`,
`"Data"`). The CLI resolves tab name → sheetId for you.

## Docs — `gdoc`

| Command | Purpose |
|---|---|
| `create --title T [--parent FOLDER]` | new document |
| `get <id> [--ranges] [--json]` | plain text / per-paragraph indices / raw |
| `append <id> --text "...\n"` (or `--text-file F`) | add text to end of body |
| `insert <id> --index N --text "..."` (or `--text-file F`) | insert at an index |
| `replace <id> --find X --replace Y [--match-case]` | find & replace all |
| `style <id> --start S --end E [flags]` | character styling (below) |
| `para <id> --start S --end E [flags]` | paragraph styling / headings / bullets |
| `table <id> --rows R --cols C [--index N]` | insert a table |
| `comments <id> [--add T] [--reply-to CID] [--resolve CID]` | list/add/reply/resolve comments |
| `batch <id> --requests-json '[...]'` | raw `documents.batchUpdate` |

`para` bullets do checkbox to-do lists with `--bullet --bullet-preset
BULLET_CHECKBOX` (other presets: `BULLET_DISC_CIRCLE_SQUARE`,
`NUMBERED_DECIMAL_ALPHA_ROMAN`).

For body text with non-ASCII characters (em-dashes, smart quotes, accents,
emoji), prefer `--text-file` (a UTF-8 file, or `-` for stdin) over `--text`: it
bypasses the shell command line, which on Windows/Git Bash mangles non-ASCII
before the CLI sees it.

`comments` uses the Drive API (not Docs `batchUpdate`); the account needs at
least comment access to the file. `--reply-to`/`--resolve` take a comment id and
read reply text from `--text`/`--text-file`.

`style` flags: `--bold --italic --underline --strikethrough --font-size N
--font NAME --color #hex --bg #hex --link URL`.
`para` flags: `--named-style HEADING_1|TITLE|SUBTITLE|NORMAL_TEXT|...
--align START|CENTER|END|JUSTIFIED --bullet [--bullet-preset ...]`.

### The index model (important)

Docs styling targets character index ranges, not text. **Always
`gdoc get <id> --ranges` first** to see each paragraph's `startIndex`/`endIndex`
and text, then pass those indices to `style`/`para`. Note:
- Text can only be inserted *inside* an existing paragraph (not at a table
  boundary). Prefer `append` (uses `endOfSegmentLocation`) when adding to the end.
- Inserting text shifts the indices of everything after it. When building a doc,
  insert content first, then re-`get --ranges` before styling.

## Building anything else

The first-class commands cover the common cases. For everything else (conditional
formatting, charts, named ranges, data validation, images, page breaks, nested
list levels, table cell styling…) compose requests yourself and send via `batch`.
The exact request JSON shapes are in:

- `references/sheets-api.md`
- `references/docs-api.md`

Workflow for a styled artifact: create → write/append content → `info` or
`get --ranges` to learn the layout → `format`/`style`/`para` (or `batch`) to style
→ return the file URL.
