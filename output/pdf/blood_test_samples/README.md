# Synthetic blood report parser fixtures

10 two-page PDFs and 10 matching expected JSON files, based on the supplied CD4/CD8 Ratio Profile report. All 26 test names, units, printed reference intervals, lab footnotes and test order are retained. The two-page layout is recreated, with synthetic branding, identities, laboratory details and explanatory text; it is not a pixel-identical copy. Previous-result columns remain blank.

## Use
Upload each PDF to the parser, then compare extracted fields with its `.expected.json` partner. `manifest.json` lists scenarios and expected flag counts. JSON is a new comparison contract because the current backend has an upload endpoint but no extraction schema. Fixture metadata (`scenario`, `schema_version`, `synthetic`, `source_pdf`) is not expected to be extracted from the PDF. ISO dates normalize the printed US dates. Ignore JSON property order and match tests by exact `test_name`; retain result order if your parser promises it.

## Values and flags
`value` is numeric. `value_text` preserves printed precision (for example `6.00` or `0.0`), which JSON numbers alone cannot preserve. `flag` is the printed `Low` or `High`, or null for a blank flag. Numeric intervals use inclusive endpoints; flags are computed from the displayed values. No critical/alert thresholds are invented. `range_status` is derived comparison metadata, not printed text. `unit: null` represents the unitless CD4/CD8 ratio. `reference_interval.text: "Not Estab."` is distinct from a missing interval (`null`). Both have null numeric bounds and must not be classified as normal. Null prior results represent blank fields, not numeric zero. Lab codes are superscripts in the PDFs and are not part of test names. The immature-granulocyte note `Available upon request` is preserved separately.

## Scenario design
Normal; exact lower bounds; exact upper bounds; one displayed precision step below positive lower bounds; one step above upper bounds; markedly low; markedly high; low CD4/high CD8; high ratio/low CD8; and mixed precision with zeros. No negative blood counts are generated for zero lower bounds. All five differential percentages plus immature granulocytes sum to 100 in every fixture.

Boundary cases intentionally vary analytes independently to isolate parser and comparison behavior; they are not physiologically consistent patient profiles. These are synthetic software fixtures, not diagnostic examples or clinical guidance. Reference intervals are copied from the source, not independently validated.

## Verification
Reopened all 10 PDFs: two pages each; all 260 rows checked against expected names, displayed values, units, reference text and flags. Rendered all 20 pages for visual review. No application code changed. No original patient PDF is included in the ZIP.
