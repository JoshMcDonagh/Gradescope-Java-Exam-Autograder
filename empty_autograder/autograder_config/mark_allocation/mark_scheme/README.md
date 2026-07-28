# Mark scheme

The scheme is a hierarchy of JSON files:

```
mark_scheme_manifest.json                (one level up)
  └─ sectionN/
       ├─ section_manifest.json          lists the section's questions
       └─ questionN.json                 defines one question's parts and bundles
```

Each entry in the manifest's `sections` list (e.g. `"section1.json"`) resolves to `sectionN/section_manifest.json`, whose `questions[].file` paths (e.g. `"section1/question1.json"`) are relative to this directory.

A question file contains **parts** (sub-questions a, b, c, …), each holding **bundles**: groups of tests sharing a mark allocation. Under `all_or_nothing` scoring, a bundle awards its marks only if *every* listed test passes. A bundle may group any of a part's tests — structure checks and behaviour checks alike — and its tests may span classes.

Each bundle's `tests` list holds fully qualified test names — package, class, and method, exactly as they appear in the JUnit output:

```
section1.question1.a.PastryTypeTest.testEnumExists
section2.question2.b.BakeryTest.testTotalStockValueSumsPrices
```

Rules to keep in mind:

- Marks must sum correctly at every level (bundles → part, parts → question, questions → section, sections → manifest total); the validator rejects mismatches before marking starts.
- All IDs (`section_id`, `question_id`, `bundle_id` within a part, and so on) must be unique at their level.
- A test referenced here but missing from the output is logged as a warning and treated as failed, so one broken test class cannot prevent the rest of a submission from scoring. A test that ran but is referenced nowhere is an error — add it to a bundle or delete the test.

A complete worked scheme is in `example/example_autograder/autograder_config/mark_allocation/`.
