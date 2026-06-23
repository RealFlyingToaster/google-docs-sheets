#!/usr/bin/env python3
"""gsheet — fluent Google Sheets CLI (create, read, write, style).

Common operations have first-class subcommands; anything the API can do is
reachable via `gsheet batch <id> --requests-json '[...]'`. See
references/sheets-api.md for request shapes. Pass --dry-run on any command to
print the request JSON instead of calling the API.

Examples:
  gsheet create --title "Q3 Budget" --tabs "Summary,Data"
  gsheet info   <id>
  gsheet read   <id> --range "Data!A1:D20"
  gsheet write  <id> --range "Data!A1" --values-json '[["Name","Total"],["Acme",1200]]'
  gsheet append <id> --range "Data!A1" --csv rows.csv
  gsheet format <id> --range "Data!A1:D1" --bold --bg "#1f2937" --color "#ffffff" --h-align CENTER
  gsheet format <id> --range "Data!D2:D20" --number-format "$#,##0.00"
  gsheet freeze <id> --range "Data" --rows 1
  gsheet merge  <id> --range "Summary!A1:D1"
  gsheet width  <id> --range "Data!A:A" --pixels 220
  gsheet batch  <id> --requests-json '[{"repeatCell": ...}]'
"""
import argparse
import csv
import json
import re
import sys

import google_auth as ga

SHEETS = "https://sheets.googleapis.com/v4/spreadsheets"

# ---------------------------------------------------------------- helpers ----

def col_to_index(letters):
    n = 0
    for ch in letters.upper():
        n = n * 26 + (ord(ch) - ord("A") + 1)
    return n - 1


def parse_a1(a1):
    """'Sheet1!A1:C3' -> (title_or_None, gridrange_without_sheetId).

    Indices follow the API: start inclusive, end exclusive. Omitted bounds are
    left out so they default to the whole row/column span.
    """
    title = None
    if "!" in a1:
        title, a1 = a1.split("!", 1)
        title = title.strip().strip("'")
    a1 = a1.strip()
    if not a1:
        return title, {}

    def parse_cell(cell):
        m = re.match(r"^([A-Za-z]*)(\d*)$", cell)
        col, row = m.group(1), m.group(2)
        return (col_to_index(col) if col else None,
                int(row) - 1 if row else None)

    if ":" in a1:
        start, end = a1.split(":", 1)
        sc, sr = parse_cell(start)
        ec, er = parse_cell(end)
    else:
        sc, sr = parse_cell(a1)
        ec, er = sc, sr

    gr = {}
    if sr is not None:
        gr["startRowIndex"] = sr
    if er is not None:
        gr["endRowIndex"] = er + 1
    if sc is not None:
        gr["startColumnIndex"] = sc
    if ec is not None:
        gr["endColumnIndex"] = ec + 1
    return title, gr


def hex_to_color(h):
    if h is None:
        return None
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return {"red": r, "green": g, "blue": b}


_META_CACHE = {}


def get_meta(sid):
    if sid not in _META_CACHE:
        _META_CACHE[sid] = ga.api(
            "GET", f"{SHEETS}/{sid}",
            params={"fields": "spreadsheetId,properties.title,"
                              "sheets.properties(sheetId,title,index,gridProperties)"})
    return _META_CACHE[sid]


def resolve_sheet_id(sid, title):
    if ga.DRY_RUN:
        return 0
    meta = get_meta(sid)
    sheets = meta.get("sheets", [])
    if title is None:
        return sheets[0]["properties"]["sheetId"]
    for s in sheets:
        if s["properties"]["title"] == title:
            return s["properties"]["sheetId"]
    raise SystemExit(f"No tab named {title!r} in spreadsheet {sid}")


def grid_range(sid, a1):
    title, gr = parse_a1(a1)
    gr["sheetId"] = resolve_sheet_id(sid, title)
    return gr


def load_values(args):
    if args.values_json:
        return json.loads(args.values_json)
    if args.csv:
        with open(args.csv, newline="") as f:
            return [row for row in csv.reader(f)]
    if args.tsv:
        src = sys.stdin if args.tsv == "-" else open(args.tsv)
        return [line.rstrip("\n").split("\t") for line in src]
    raise SystemExit("Provide --values-json, --csv, or --tsv")


def batch_update(sid, requests):
    return ga.api("POST", f"{SHEETS}/{sid}:batchUpdate",
                  json_body={"requests": requests})


# --------------------------------------------------------------- commands ----

def cmd_create(args):
    body = {"properties": {"title": args.title}}
    if args.tabs:
        body["sheets"] = [{"properties": {"title": t.strip()}}
                          for t in args.tabs.split(",") if t.strip()]
    res = ga.api("POST", SHEETS, json_body=body)
    sid = res["spreadsheetId"]
    if args.parent:
        ga.api("PATCH", f"https://www.googleapis.com/drive/v3/files/{sid}",
               params={"addParents": args.parent, "supportsAllDrives": "true",
                       "fields": "id,parents"})
    ga.out({"spreadsheetId": sid,
            "url": f"https://docs.google.com/spreadsheets/d/{sid}/edit"})


def cmd_info(args):
    meta = get_meta(args.id)
    tabs = [{"sheetId": s["properties"]["sheetId"],
             "title": s["properties"]["title"],
             "index": s["properties"].get("index"),
             "grid": s["properties"].get("gridProperties")}
            for s in meta.get("sheets", [])]
    ga.out({"spreadsheetId": meta["spreadsheetId"],
            "title": meta["properties"]["title"],
            "url": f"https://docs.google.com/spreadsheets/d/{args.id}/edit",
            "tabs": tabs})


def cmd_read(args):
    res = ga.api("GET", f"{SHEETS}/{args.id}/values/{args.range}",
                 params={"valueRenderOption": args.render,
                         "majorDimension": args.major})
    ga.out(res.get("values", []))


def cmd_write(args):
    res = ga.api("PUT", f"{SHEETS}/{args.id}/values/{args.range}",
                 params={"valueInputOption": args.input},
                 json_body={"values": load_values(args)})
    ga.out({"updatedRange": res.get("updatedRange"),
            "updatedCells": res.get("updatedCells")})


def cmd_append(args):
    res = ga.api("POST", f"{SHEETS}/{args.id}/values/{args.range}:append",
                 params={"valueInputOption": args.input,
                         "insertDataOption": "INSERT_ROWS"},
                 json_body={"values": load_values(args)})
    ga.out({"updates": res.get("updates")})


def cmd_clear(args):
    res = ga.api("POST", f"{SHEETS}/{args.id}/values/{args.range}:clear")
    ga.out({"clearedRange": res.get("clearedRange")})


def cmd_add_sheet(args):
    props = {"title": args.title}
    if args.rows or args.cols:
        props["gridProperties"] = {}
        if args.rows:
            props["gridProperties"]["rowCount"] = args.rows
        if args.cols:
            props["gridProperties"]["columnCount"] = args.cols
    res = batch_update(args.id, [{"addSheet": {"properties": props}}])
    new = res["replies"][0].get("addSheet", {}).get("properties", props)
    ga.out({"sheetId": new.get("sheetId"), "title": new.get("title")})


def cmd_delete_sheet(args):
    sheet_id = args.sheet_id
    if sheet_id is None:
        sheet_id = resolve_sheet_id(args.id, args.title)
    batch_update(args.id, [{"deleteSheet": {"sheetId": sheet_id}}])
    ga.out({"deletedSheetId": sheet_id})


def cmd_format(args):
    gr = grid_range(args.id, args.range)
    fmt, fields = {}, []
    text_format = {}
    if args.bold:
        text_format["bold"] = True
        fields.append("textFormat.bold")
    if args.italic:
        text_format["italic"] = True
        fields.append("textFormat.italic")
    if args.strikethrough:
        text_format["strikethrough"] = True
        fields.append("textFormat.strikethrough")
    if args.font_size:
        text_format["fontSize"] = args.font_size
        fields.append("textFormat.fontSize")
    if args.font:
        text_format["fontFamily"] = args.font
        fields.append("textFormat.fontFamily")
    if args.color:
        text_format["foregroundColor"] = hex_to_color(args.color)
        fields.append("textFormat.foregroundColor")
    if text_format:
        fmt["textFormat"] = text_format
    if args.bg:
        fmt["backgroundColor"] = hex_to_color(args.bg)
        fields.append("backgroundColor")
    if args.h_align:
        fmt["horizontalAlignment"] = args.h_align
        fields.append("horizontalAlignment")
    if args.v_align:
        fmt["verticalAlignment"] = args.v_align
        fields.append("verticalAlignment")
    if args.wrap:
        fmt["wrapStrategy"] = "WRAP"
        fields.append("wrapStrategy")
    if args.number_format:
        ntype = args.number_type or _guess_number_type(args.number_format)
        fmt["numberFormat"] = {"type": ntype, "pattern": args.number_format}
        fields.append("numberFormat")
    if not fields:
        raise SystemExit("format: nothing to do — pass at least one style flag")

    requests = [{"repeatCell": {
        "range": gr,
        "cell": {"userEnteredFormat": fmt},
        "fields": "userEnteredFormat(" + ",".join(fields) + ")"}}]
    if args.border:
        requests.append({"updateBorders": _all_borders(gr, args.border)})
    batch_update(args.id, requests)
    ga.out({"formatted": args.range, "fields": fields, "border": bool(args.border)})


def _guess_number_type(pattern):
    if any(s in pattern for s in ("$", "€", "£")):
        return "CURRENCY"
    if "%" in pattern:
        return "PERCENT"
    low = pattern.lower()
    if any(c in low for c in ("y", "d")) and any(c in low for c in ("y", "m", "d")):
        return "DATE"
    return "NUMBER"


def _all_borders(gr, color):
    b = {"style": "SOLID", "color": hex_to_color(color)}
    out = {"range": gr}
    for side in ("top", "bottom", "left", "right",
                 "innerHorizontal", "innerVertical"):
        out[side] = b
    return out


def cmd_freeze(args):
    title, _ = parse_a1(args.range) if args.range else (None, None)
    sheet_id = resolve_sheet_id(args.id, title)
    grid, fields = {}, []
    if args.rows is not None:
        grid["frozenRowCount"] = args.rows
        fields.append("gridProperties.frozenRowCount")
    if args.cols is not None:
        grid["frozenColumnCount"] = args.cols
        fields.append("gridProperties.frozenColumnCount")
    if not fields:
        raise SystemExit("freeze: pass --rows and/or --cols")
    batch_update(args.id, [{"updateSheetProperties": {
        "properties": {"sheetId": sheet_id, "gridProperties": grid},
        "fields": ",".join(fields)}}])
    ga.out({"frozen": {"rows": args.rows, "cols": args.cols}, "sheetId": sheet_id})


def cmd_merge(args):
    gr = grid_range(args.id, args.range)
    batch_update(args.id, [{"mergeCells": {"range": gr, "mergeType": args.type}}])
    ga.out({"merged": args.range, "type": args.type})


def cmd_width(args):
    title, gr = parse_a1(args.range)
    sheet_id = resolve_sheet_id(args.id, title)
    dim = {"sheetId": sheet_id, "dimension": args.dimension}
    if args.dimension == "COLUMNS":
        if "startColumnIndex" in gr:
            dim["startIndex"] = gr["startColumnIndex"]
        if "endColumnIndex" in gr:
            dim["endIndex"] = gr["endColumnIndex"]
    else:
        if "startRowIndex" in gr:
            dim["startIndex"] = gr["startRowIndex"]
        if "endRowIndex" in gr:
            dim["endIndex"] = gr["endRowIndex"]
    if args.auto:
        req = {"autoResizeDimensions": {"dimensions": dim}}
    else:
        if args.pixels is None:
            raise SystemExit("width: pass --pixels N or --auto")
        req = {"updateDimensionProperties": {
            "range": dim, "properties": {"pixelSize": args.pixels},
            "fields": "pixelSize"}}
    batch_update(args.id, [req])
    ga.out({"resized": args.range, "pixels": "auto" if args.auto else args.pixels})


def cmd_batch(args):
    requests = json.loads(args.requests_json) if args.requests_json else \
        json.load(open(args.requests_file))
    if isinstance(requests, dict):
        requests = [requests]
    ga.out(batch_update(args.id, requests))


# ----------------------------------------------------------------- parser ----

def build_parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--token-file", help="JSON file holding a refresh_token")
    common.add_argument("--dry-run", action="store_true",
                        help="print the request JSON instead of calling the API")
    p = argparse.ArgumentParser(prog="gsheet", description=__doc__, parents=[common],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def addp(*a, **k):
        k.setdefault("parents", [common])
        return sub.add_parser(*a, **k)

    sp = addp("create", help="create a spreadsheet")
    sp.add_argument("--title", required=True)
    sp.add_argument("--tabs", help="comma-separated tab names")
    sp.add_argument("--parent", help="Drive folder id to place it in")
    sp.set_defaults(func=cmd_create)

    sp = addp("info", help="list tabs + grid sizes")
    sp.add_argument("id")
    sp.set_defaults(func=cmd_info)

    sp = addp("read", help="read a range")
    sp.add_argument("id")
    sp.add_argument("--range", required=True)
    sp.add_argument("--render", default="FORMATTED_VALUE",
                    choices=["FORMATTED_VALUE", "UNFORMATTED_VALUE", "FORMULA"])
    sp.add_argument("--major", default="ROWS", choices=["ROWS", "COLUMNS"])
    sp.set_defaults(func=cmd_read)

    for name, fn, helptext in (("write", cmd_write, "overwrite a range"),
                               ("append", cmd_append, "append rows after data")):
        sp = addp(name, help=helptext)
        sp.add_argument("id")
        sp.add_argument("--range", required=True)
        sp.add_argument("--values-json", help='e.g. [["a","b"],[1,2]]')
        sp.add_argument("--csv", help="CSV file of values")
        sp.add_argument("--tsv", help="TSV file, or - for stdin")
        sp.add_argument("--input", default="USER_ENTERED",
                        choices=["USER_ENTERED", "RAW"])
        sp.set_defaults(func=fn)

    sp = addp("clear", help="clear values in a range")
    sp.add_argument("id")
    sp.add_argument("--range", required=True)
    sp.set_defaults(func=cmd_clear)

    sp = addp("add-sheet", help="add a tab")
    sp.add_argument("id")
    sp.add_argument("--title", required=True)
    sp.add_argument("--rows", type=int)
    sp.add_argument("--cols", type=int)
    sp.set_defaults(func=cmd_add_sheet)

    sp = addp("delete-sheet", help="delete a tab")
    sp.add_argument("id")
    sp.add_argument("--sheet-id", type=int)
    sp.add_argument("--title")
    sp.set_defaults(func=cmd_delete_sheet)

    sp = addp("format", help="style a range")
    sp.add_argument("id")
    sp.add_argument("--range", required=True)
    sp.add_argument("--bold", action="store_true")
    sp.add_argument("--italic", action="store_true")
    sp.add_argument("--strikethrough", action="store_true")
    sp.add_argument("--font-size", type=int)
    sp.add_argument("--font")
    sp.add_argument("--color", help="text color hex, e.g. #ffffff")
    sp.add_argument("--bg", help="background color hex")
    sp.add_argument("--h-align", choices=["LEFT", "CENTER", "RIGHT"])
    sp.add_argument("--v-align", choices=["TOP", "MIDDLE", "BOTTOM"])
    sp.add_argument("--wrap", action="store_true")
    sp.add_argument("--number-format", help='e.g. "$#,##0.00", "0.0%", "yyyy-mm-dd"')
    sp.add_argument("--number-type",
                    choices=["NUMBER", "CURRENCY", "PERCENT", "DATE", "TIME",
                             "DATE_TIME", "SCIENTIFIC"],
                    help="override the auto-guessed number format type")
    sp.add_argument("--border", help="add solid borders in this hex color")
    sp.set_defaults(func=cmd_format)

    sp = addp("freeze", help="freeze header rows/cols")
    sp.add_argument("id")
    sp.add_argument("--range", help="tab name (or A1 with a tab prefix)")
    sp.add_argument("--rows", type=int)
    sp.add_argument("--cols", type=int)
    sp.set_defaults(func=cmd_freeze)

    sp = addp("merge", help="merge cells")
    sp.add_argument("id")
    sp.add_argument("--range", required=True)
    sp.add_argument("--type", default="MERGE_ALL",
                    choices=["MERGE_ALL", "MERGE_COLUMNS", "MERGE_ROWS"])
    sp.set_defaults(func=cmd_merge)

    sp = addp("width", help="set or auto-fit column width / row height")
    sp.add_argument("id")
    sp.add_argument("--range", required=True, help='e.g. "Data!A:C" or "Data!1:3"')
    sp.add_argument("--pixels", type=int)
    sp.add_argument("--auto", action="store_true", help="auto-resize to fit")
    sp.add_argument("--dimension", default="COLUMNS", choices=["COLUMNS", "ROWS"])
    sp.set_defaults(func=cmd_width)

    sp = addp("batch", help="raw spreadsheets.batchUpdate passthrough")
    sp.add_argument("id")
    sp.add_argument("--requests-json", help="JSON array (or single object)")
    sp.add_argument("--requests-file", help="file containing the JSON requests")
    sp.set_defaults(func=cmd_batch)

    return p


def main():
    args = build_parser().parse_args()
    if getattr(args, "dry_run", False):
        ga.set_dry_run(True)
    if getattr(args, "token_file", None):
        import os
        os.environ["GOOGLE_TOKEN_FILE"] = args.token_file
    args.func(args)


if __name__ == "__main__":
    main()
