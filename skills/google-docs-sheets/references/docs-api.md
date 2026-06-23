# Docs API — `documents.batchUpdate` request shapes

Reference for composing `gdoc batch <id> --requests-json '[ ... ]'`. Endpoint:
`POST https://docs.googleapis.com/v1/documents/{id}:batchUpdate`
with body `{"requests": [ ... ]}`. Requests apply in order; **earlier inserts
shift later indices**, so order matters (or run a fresh `gdoc get --ranges`
between mutating and styling).

## Locations, ranges, color

- A `location` is `{"index": N, "segmentId": ""}` (segmentId "" = document body).
- `endOfSegmentLocation` `{"segmentId": ""}` targets the end of the body — use it
  to append without computing indices.
- A `range` is `{"startIndex": S, "endIndex": E, "segmentId": ""}` — half-open,
  1-based (index 1 is the first character).
- Color (OptionalColor) is **nested**, unlike Sheets:
  `{"color": {"rgbColor": {"red":0.1,"green":0.2,"blue":0.3}}}`.

## insertText

```json
{ "insertText": { "text": "Hello\n", "location": {"index": 1} } }
```
Or append: `{ "insertText": { "text": "Hello\n", "endOfSegmentLocation": {"segmentId": ""} } }`.
Text must be inserted inside an existing paragraph.

## updateTextStyle — character styling

```json
{ "updateTextStyle": {
    "range": {"startIndex":1,"endIndex":18},
    "textStyle": {
      "bold": true, "italic": false, "underline": true, "strikethrough": false,
      "fontSize": {"magnitude": 18, "unit": "PT"},
      "weightedFontFamily": {"fontFamily": "Roboto"},
      "foregroundColor": {"color":{"rgbColor":{"red":0.1,"green":0.45,"blue":0.9}}},
      "backgroundColor": {"color":{"rgbColor":{"red":1,"green":1,"blue":0.6}}},
      "link": {"url": "https://example.org"}
    },
    "fields": "bold,underline,fontSize,weightedFontFamily,foregroundColor,link"
}}
```
`fields` is a comma-separated mask of the `textStyle` leaves to write.

## updateParagraphStyle — headings, alignment, spacing

```json
{ "updateParagraphStyle": {
    "range": {"startIndex":40,"endIndex":120},
    "paragraphStyle": {
      "namedStyleType": "HEADING_1",
      "alignment": "CENTER",
      "lineSpacing": 115,
      "spaceAbove": {"magnitude": 6, "unit": "PT"},
      "indentStart": {"magnitude": 18, "unit": "PT"}
    },
    "fields": "namedStyleType,alignment"
}}
```
- `namedStyleType`: `NORMAL_TEXT`, `TITLE`, `SUBTITLE`, `HEADING_1` … `HEADING_6`.
  Headings drive the document outline automatically.
- `alignment`: `START`, `CENTER`, `END`, `JUSTIFIED`.

## createParagraphBullets / deleteParagraphBullets

```json
{ "createParagraphBullets": {
    "range": {"startIndex":40,"endIndex":120},
    "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE" } }
```
Common presets: `BULLET_DISC_CIRCLE_SQUARE`, `BULLET_ARROW_DIAMOND_DISC`,
`BULLET_CHECKBOX`, `NUMBERED_DECIMAL_ALPHA_ROMAN`, `NUMBERED_DECIMAL_NESTED`.
Nesting follows the leading tabs of each paragraph.

## replaceAllText — template fill

```json
{ "replaceAllText": {
    "containsText": {"text": "{{client}}", "matchCase": true},
    "replaceText": "Acme Corp" } }
```
Great for template docs: write `{{tokens}}`, then replace each.

## insertTable + filling cells

```json
{ "insertTable": { "rows": 3, "columns": 4,
                   "endOfSegmentLocation": {"segmentId": ""} } }
```
After inserting, the table's cells contain empty paragraphs. To fill them, run
`gdoc get <id> --json`, read the table cell `startIndex` values, then
`insertText` into each (work bottom-to-top / right-to-left so indices don't shift
under you). Style cell backgrounds with `updateTableCellStyle`.

## Structural & media requests

- `deleteContentRange` — `{"range": {...}}` removes text.
- `insertPageBreak` — `{"location": {"index": N}}`.
- `insertInlineImage` — `{"uri": "...png", "location": {...},
  "objectSize": {"height":{"magnitude":200,"unit":"PT"}, "width":{...}}}`
  (the image URL must be publicly fetchable).
- `createNamedRange` / `deleteNamedRange`.
- `updateDocumentStyle` — page size, margins, default headers/footers.
- `updateTableCellStyle`, `mergeTableCells`, `insertTableRow`, `insertTableColumn`.

Full reference: Google "documents.batchUpdate" and the `Request` union type.
Validate any composed request with `--dry-run` before sending.
