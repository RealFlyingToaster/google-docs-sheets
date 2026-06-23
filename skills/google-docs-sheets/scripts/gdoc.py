#!/usr/bin/env python3
"""gdoc — fluent Google Docs CLI (create, read, edit, style).

Common operations have first-class subcommands; anything the API can do is
reachable via `gdoc batch <id> --requests-json '[...]'`. See
references/docs-api.md for request shapes. Pass --dry-run on any command to
print the request JSON instead of calling the API.

Index model: every character in a Doc has an index. Use `gdoc get <id> --ranges`
to see each paragraph's startIndex/endIndex and text, then target styling at
those indices. `append` adds to the end of the body without needing indices.

Examples:
  gdoc create --title "Project Brief"
  gdoc get    <id> --ranges
  gdoc append <id> --text "Executive Summary\n"
  gdoc style  <id> --start 1 --end 18 --bold --font-size 18 --color "#1a73e8"
  gdoc para   <id> --start 1 --end 18 --named-style HEADING_1
  gdoc para   <id> --start 40 --end 120 --bullet
  gdoc replace <id> --find "{{client}}" --replace "Acme Corp"
  gdoc table  <id> --rows 3 --cols 4
  gdoc batch  <id> --requests-json '[{"insertText": ...}]'
"""
import argparse
import json

import google_auth as ga

DOCS = "https://docs.googleapis.com/v1/documents"


# ---------------------------------------------------------------- helpers ----

def hex_to_rgb(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return {"red": int(h[0:2], 16) / 255,
            "green": int(h[2:4], 16) / 255,
            "blue": int(h[4:6], 16) / 255}


def optional_color(h):
    return {"color": {"rgbColor": hex_to_rgb(h)}}


def batch_update(doc_id, requests):
    return ga.api("POST", f"{DOCS}/{doc_id}:batchUpdate",
                  json_body={"requests": requests})


def get_doc(doc_id):
    return ga.api("GET", f"{DOCS}/{doc_id}")


def iter_paragraphs(doc):
    """Yield (startIndex, endIndex, text, namedStyleType) per paragraph."""
    for el in doc.get("body", {}).get("content", []):
        para = el.get("paragraph")
        if not para:
            continue
        text = "".join(e.get("textRun", {}).get("content", "")
                       for e in para.get("elements", []))
        style = para.get("paragraphStyle", {}).get("namedStyleType")
        yield el.get("startIndex", 0), el.get("endIndex", 0), text, style


def unescape(text):
    return text.replace("\\n", "\n").replace("\\t", "\t")


# --------------------------------------------------------------- commands ----

def cmd_create(args):
    res = ga.api("POST", DOCS, json_body={"title": args.title})
    did = res["documentId"]
    if args.parent:
        ga.api("PATCH", f"https://www.googleapis.com/drive/v3/files/{did}",
               params={"addParents": args.parent, "supportsAllDrives": "true",
                       "fields": "id,parents"})
    ga.out({"documentId": did,
            "url": f"https://docs.google.com/document/d/{did}/edit"})


def cmd_get(args):
    doc = get_doc(args.id)
    if args.json:
        ga.out(doc)
    elif args.ranges:
        rows = [{"startIndex": s, "endIndex": e, "style": st,
                 "text": t.rstrip("\n")}
                for s, e, t, st in iter_paragraphs(doc)]
        ga.out({"title": doc.get("title"), "paragraphs": rows})
    else:
        print("".join(t for _, _, t, _ in iter_paragraphs(doc)), end="")


def cmd_append(args):
    text = unescape(args.text)
    batch_update(args.id, [{"insertText": {
        "text": text, "endOfSegmentLocation": {"segmentId": ""}}}])
    ga.out({"appended": len(text)})


def cmd_insert(args):
    text = unescape(args.text)
    batch_update(args.id, [{"insertText": {
        "text": text, "location": {"index": args.index}}}])
    ga.out({"inserted": len(text), "at": args.index})


def cmd_replace(args):
    res = batch_update(args.id, [{"replaceAllText": {
        "containsText": {"text": args.find, "matchCase": args.match_case},
        "replaceText": args.replace}}])
    occ = res.get("replies", [{}])[0].get("replaceAllText", {}).get(
        "occurrencesChanged", 0)
    ga.out({"replaced": args.find, "occurrences": occ})


def cmd_style(args):
    style, fields = {}, []
    if args.bold:
        style["bold"] = True
        fields.append("bold")
    if args.italic:
        style["italic"] = True
        fields.append("italic")
    if args.underline:
        style["underline"] = True
        fields.append("underline")
    if args.strikethrough:
        style["strikethrough"] = True
        fields.append("strikethrough")
    if args.font_size:
        style["fontSize"] = {"magnitude": args.font_size, "unit": "PT"}
        fields.append("fontSize")
    if args.font:
        style["weightedFontFamily"] = {"fontFamily": args.font}
        fields.append("weightedFontFamily")
    if args.color:
        style["foregroundColor"] = optional_color(args.color)
        fields.append("foregroundColor")
    if args.bg:
        style["backgroundColor"] = optional_color(args.bg)
        fields.append("backgroundColor")
    if args.link:
        style["link"] = {"url": args.link}
        fields.append("link")
    if not fields:
        raise SystemExit("style: pass at least one style flag")
    batch_update(args.id, [{"updateTextStyle": {
        "range": {"startIndex": args.start, "endIndex": args.end},
        "textStyle": style, "fields": ",".join(fields)}}])
    ga.out({"styled": [args.start, args.end], "fields": fields})


def cmd_para(args):
    requests = []
    pstyle, fields = {}, []
    if args.named_style:
        pstyle["namedStyleType"] = args.named_style
        fields.append("namedStyleType")
    if args.align:
        pstyle["alignment"] = args.align
        fields.append("alignment")
    if fields:
        requests.append({"updateParagraphStyle": {
            "range": {"startIndex": args.start, "endIndex": args.end},
            "paragraphStyle": pstyle, "fields": ",".join(fields)}})
    if args.bullet:
        requests.append({"createParagraphBullets": {
            "range": {"startIndex": args.start, "endIndex": args.end},
            "bulletPreset": args.bullet_preset}})
    if not requests:
        raise SystemExit("para: pass --named-style, --align, and/or --bullet")
    batch_update(args.id, requests)
    ga.out({"paragraph": [args.start, args.end], "named_style": args.named_style,
            "align": args.align, "bullet": args.bullet})


def cmd_table(args):
    loc = ({"location": {"index": args.index}} if args.index is not None
           else {"endOfSegmentLocation": {"segmentId": ""}})
    batch_update(args.id, [{"insertTable": {
        "rows": args.rows, "columns": args.cols, **loc}}])
    ga.out({"table": {"rows": args.rows, "cols": args.cols}})


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
    p = argparse.ArgumentParser(prog="gdoc", description=__doc__, parents=[common],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def addp(*a, **k):
        k.setdefault("parents", [common])
        return sub.add_parser(*a, **k)

    sp = addp("create", help="create a document")
    sp.add_argument("--title", required=True)
    sp.add_argument("--parent", help="Drive folder id to place it in")
    sp.set_defaults(func=cmd_create)

    sp = addp("get", help="read a doc (plain text / ranges / raw json)")
    sp.add_argument("id")
    sp.add_argument("--json", action="store_true", help="raw document JSON")
    sp.add_argument("--ranges", action="store_true",
                    help="per-paragraph startIndex/endIndex + text")
    sp.set_defaults(func=cmd_get)

    sp = addp("append", help="append text to end of body")
    sp.add_argument("id")
    sp.add_argument("--text", required=True, help="use \\n for newlines")
    sp.set_defaults(func=cmd_append)

    sp = addp("insert", help="insert text at an index")
    sp.add_argument("id")
    sp.add_argument("--index", type=int, required=True)
    sp.add_argument("--text", required=True)
    sp.set_defaults(func=cmd_insert)

    sp = addp("replace", help="find & replace all")
    sp.add_argument("id")
    sp.add_argument("--find", required=True)
    sp.add_argument("--replace", required=True)
    sp.add_argument("--match-case", action="store_true")
    sp.set_defaults(func=cmd_replace)

    sp = addp("style", help="character styling over [start,end)")
    sp.add_argument("id")
    sp.add_argument("--start", type=int, required=True)
    sp.add_argument("--end", type=int, required=True)
    sp.add_argument("--bold", action="store_true")
    sp.add_argument("--italic", action="store_true")
    sp.add_argument("--underline", action="store_true")
    sp.add_argument("--strikethrough", action="store_true")
    sp.add_argument("--font-size", type=int, help="points")
    sp.add_argument("--font", help='font family, e.g. "Roboto"')
    sp.add_argument("--color", help="text color hex")
    sp.add_argument("--bg", help="highlight color hex")
    sp.add_argument("--link", help="make the range a hyperlink to this URL")
    sp.set_defaults(func=cmd_style)

    sp = addp("para", help="paragraph styling / headings / bullets")
    sp.add_argument("id")
    sp.add_argument("--start", type=int, required=True)
    sp.add_argument("--end", type=int, required=True)
    sp.add_argument("--named-style",
                    choices=["NORMAL_TEXT", "TITLE", "SUBTITLE",
                             "HEADING_1", "HEADING_2", "HEADING_3",
                             "HEADING_4", "HEADING_5", "HEADING_6"])
    sp.add_argument("--align", choices=["START", "CENTER", "END", "JUSTIFIED"])
    sp.add_argument("--bullet", action="store_true", help="turn lines into a list")
    sp.add_argument("--bullet-preset", default="BULLET_DISC_CIRCLE_SQUARE",
                    help="e.g. BULLET_DISC_CIRCLE_SQUARE, NUMBERED_DECIMAL_ALPHA_ROMAN")
    sp.set_defaults(func=cmd_para)

    sp = addp("table", help="insert a table")
    sp.add_argument("id")
    sp.add_argument("--rows", type=int, required=True)
    sp.add_argument("--cols", type=int, required=True)
    sp.add_argument("--index", type=int,
                    help="insert at this index (default: end of body)")
    sp.set_defaults(func=cmd_table)

    sp = addp("batch", help="raw documents.batchUpdate passthrough")
    sp.add_argument("id")
    sp.add_argument("--requests-json")
    sp.add_argument("--requests-file")
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
