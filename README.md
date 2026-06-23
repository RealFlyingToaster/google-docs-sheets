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

Then set up credentials — see **[SETUP.md](SETUP.md)** — and install runtime deps:

```bash
pip install -r requirements.txt
```

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
- **Docs:** create, get (text / per-paragraph index ranges / raw), append, insert,
  find-and-replace, character styling (bold/italic/underline/strike/font/size/
  color/highlight/link), paragraph styling (named styles/headings, alignment),
  bullet & numbered lists, tables, and raw `batch` (images, page breaks, table
  cell styling, …).

See `skills/google-docs-sheets/references/` for the exact `batchUpdate` request
shapes behind the `batch` command.

## License

MIT — see [LICENSE](LICENSE).
