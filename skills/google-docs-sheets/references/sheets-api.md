# Sheets API — `spreadsheets.batchUpdate` request shapes

Reference for composing `gsheet batch <id> --requests-json '[ ... ]'`. Each item
in the array is one request object. Endpoint:
`POST https://sheets.googleapis.com/v4/spreadsheets/{id}:batchUpdate`
with body `{"requests": [ ... ]}`.

## GridRange (used by most requests)

```json
{ "sheetId": 0, "startRowIndex": 0, "endRowIndex": 1,
  "startColumnIndex": 0, "endColumnIndex": 4 }
```
- Start indices are inclusive, end indices exclusive, all 0-based.
- Omit a bound to span the whole row/column. `sheetId` is the numeric tab id
  (`gsheet info <id>` lists them; the first tab is usually `0`).

## Color

Sheets uses a flat color object: `{"red": 0.1, "green": 0.2, "blue": 0.3}`
(floats 0–1). (Docs API differs — see docs-api.md.)

## repeatCell — apply a CellFormat to a range

```json
{ "repeatCell": {
    "range": { "...GridRange..." },
    "cell": { "userEnteredFormat": {
        "backgroundColor": {"red":0.12,"green":0.16,"blue":0.21},
        "horizontalAlignment": "CENTER",
        "verticalAlignment": "MIDDLE",
        "wrapStrategy": "WRAP",
        "numberFormat": {"type":"CURRENCY","pattern":"$#,##0.00"},
        "textFormat": {
          "bold": true, "italic": false, "fontSize": 11,
          "fontFamily": "Arial",
          "foregroundColor": {"red":1,"green":1,"blue":1}
        }
    }},
    "fields": "userEnteredFormat(backgroundColor,horizontalAlignment,textFormat)"
}}
```
- `fields` is a mask: only listed sub-fields are written. Use
  `userEnteredFormat(...)` with comma-separated leaves, or `"*"` for everything.
- `numberFormat.type`: `NUMBER`, `CURRENCY`, `PERCENT`, `DATE`, `TIME`,
  `DATE_TIME`, `SCIENTIFIC`. Pattern examples: `"#,##0"`, `"0.0%"`,
  `"yyyy-mm-dd"`, `"$#,##0.00"`.

## updateCells — write values + formats together

```json
{ "updateCells": {
    "range": {"...GridRange..."},
    "rows": [ { "values": [ { "userEnteredValue": {"stringValue":"Name"},
                              "userEnteredFormat": {"textFormat":{"bold":true}} } ] } ],
    "fields": "userEnteredValue,userEnteredFormat.textFormat.bold"
}}
```
`userEnteredValue` is one of `stringValue`, `numberValue`, `boolValue`,
`formulaValue`. (For plain values, the `gsheet write/append` value endpoints are
simpler.)

## updateBorders

```json
{ "updateBorders": {
    "range": {"...GridRange..."},
    "top":    {"style":"SOLID","color":{"red":0.8,"green":0.8,"blue":0.8}},
    "bottom": {"style":"SOLID","color":{"red":0.8,"green":0.8,"blue":0.8}},
    "left":   {"...Border..."}, "right": {"...Border..."},
    "innerHorizontal": {"...Border..."}, "innerVertical": {"...Border..."}
}}
```
Border styles: `SOLID`, `SOLID_MEDIUM`, `SOLID_THICK`, `DOTTED`, `DASHED`,
`DOUBLE`, `NONE`.

## mergeCells

```json
{ "mergeCells": { "range": {"...GridRange..."}, "mergeType": "MERGE_ALL" } }
```
`mergeType`: `MERGE_ALL`, `MERGE_COLUMNS`, `MERGE_ROWS`. Unmerge with
`{"unmergeCells": {"range": {...}}}`.

## updateSheetProperties — freeze rows/cols, tab color, title

```json
{ "updateSheetProperties": {
    "properties": { "sheetId": 0,
      "gridProperties": {"frozenRowCount": 1, "frozenColumnCount": 0},
      "tabColor": {"red":0.2,"green":0.4,"blue":0.8} },
    "fields": "gridProperties.frozenRowCount,tabColor"
}}
```

## Dimension sizing

```json
{ "updateDimensionProperties": {
    "range": {"sheetId":0,"dimension":"COLUMNS","startIndex":0,"endIndex":1},
    "properties": {"pixelSize": 220}, "fields": "pixelSize" } }
```
```json
{ "autoResizeDimensions": {
    "dimensions": {"sheetId":0,"dimension":"COLUMNS","startIndex":0,"endIndex":4} } }
```
`dimension`: `ROWS` or `COLUMNS`.

## addConditionalFormatRule

```json
{ "addConditionalFormatRule": { "index": 0, "rule": {
    "ranges": [ {"...GridRange..."} ],
    "booleanRule": {
      "condition": {"type":"NUMBER_GREATER","values":[{"userEnteredValue":"100"}]},
      "format": {"backgroundColor":{"red":0.8,"green":1,"blue":0.8}}
    }
}}}
```
Gradient rules use `"gradientRule"` instead of `"booleanRule"`. Condition types
include `NUMBER_GREATER`, `NUMBER_LESS`, `TEXT_CONTAINS`, `TEXT_EQ`,
`DATE_BEFORE`, `CUSTOM_FORMULA`, `BLANK`, `NOT_BLANK`.

## Other common requests

- `addSheet` / `deleteSheet` / `duplicateSheet` — manage tabs.
- `appendDimension` / `insertDimension` / `deleteDimension` — add/remove rows/cols.
- `setDataValidation` — `{range, rule:{condition, showCustomUi, strict}}`.
- `addChart` — `{chart:{spec:{...}, position:{...}}}`.
- `addBanding` — alternating row colors.
- `addNamedRange` — `{namedRange:{name, range}}`.

Full reference: Google "Method: spreadsheets.batchUpdate" and the `Request`
union type. When unsure, build the request and check it with `--dry-run`.
