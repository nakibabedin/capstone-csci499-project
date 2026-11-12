# Blood report formatting variants

Three selectable-text PDFs using exactly the same 26 normalized results and patient metadata as sample_10_mixed_precision from the original fixture set. These isolate layout handling from value variation. All are fictional software fixtures.

## Included layouts
1. Compact landscape: one page; reordered columns, abbreviated headings, row shading.
2. Sectioned cards: two pages; labeled blocks rather than a table; wrapped names; clinical sections change display order.
3. Dense multipage: two pages; deliberate page break inside red-cell results, repeated headers/footers, reference intervals below values, short H/L flags.

## Expected JSON
Each PDF has a matching `.expected.json`, using the original schema. Only fixture identifiers, scenario and source filename differ from the baseline. All 26 result objects, including precision, units, ranges, notes and flags, are identical. Match results by exact test name rather than display order: the cards reorder sections. Normalize H to High and L to Low. A blank flag is null; do not infer flags from formatting alone. Blank reference intervals are null, distinct from `Not Estab.`. Preserve zeros and printed decimal precision in `value_text`. Dates normalize to ISO format. Prior result/date are blank/null throughout. Lab codes are separate from test names. Fixture/scenario metadata and derived `range_status` are not fields that must appear in the PDF.

`manifest.json` indexes files and layout expectations. `validation.json` records PDF text extraction checks against all 78 result instances and unchanged baseline results. These checks verify fixture construction, not the application's parser accuracy. All five pages were rendered for visual review.

## Deferred OCR round
Future work: image-only scanned PDFs, modest rotation/skew, reduced resolution and scan noise. Keep the same underlying result data and expected JSON to isolate OCR effects. No scanned or skewed variant is included in this batch.

## Reproduce
Run `generate.py` from the repository root with Python containing reportlab, pdfplumber and Pillow. The original sample_10 expected JSON must remain at the sibling blood_test_samples path. Outputs are written beside the generator. Temporary review PNGs go to /private/tmp/blood_format_review.
