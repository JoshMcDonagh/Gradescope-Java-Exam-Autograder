# Mark allocation

Everything the automarker needs to turn test results into a score lives here.

- **`mark_scheme_manifest.json`** — the top level: the assessment's `total_marks`, the list of sections (e.g. `["section1.json", "section2.json"]`, each resolving to `mark_scheme/sectionN/section_manifest.json`), and `scoring_defaults` (currently `"all_or_nothing"` is the only bundle scoring mode).
- **`mark_scheme/`** — the section and question files. See `mark_scheme/README.md` for the hierarchy and rules.
- **`results_display.json`** — controls what students see on Gradescope, without changing how marks are calculated.

## Results display

`section_display` assigns each section one of three modes, via a `default_mode` plus per-section overrides in `modes`:

- **`detail`** — every test is shown individually and visibly, including pass/fail output.
- **`summary`** — individual tests are hidden and replaced by one visible aggregate per question part. Useful for reporting marks while withholding test detail.
- **`hidden`** — every test is shown individually but kept instructor-only.

`question_label_style` sets the label format on aggregated parts (e.g. `question2.b`), and the `summary_output` flags control the plain-text mark summary at the top of the results: per-section and per-question subtotals, a tick on full-mark lines, and an approximate percentage otherwise.

## Validation

The mark scheme validator runs before any marking and rejects the scheme if bundle marks do not sum to their part, parts to their question, questions to their section, or sections to the manifest's `total_marks` — or if any IDs are duplicated. A validation failure stops the autograder, so run a local test after editing (see the repository README).
