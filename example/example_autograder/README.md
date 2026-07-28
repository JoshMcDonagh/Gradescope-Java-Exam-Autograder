# Example autograder — the bakery exam

A complete, runnable exam kit for a small invented exam, worth 10 marks. It exists to demonstrate how an autograder can be set up. The domain is deliberately unrelated to any real assessment.

## The invented exam

Students implement a `bakery` package containing three types:

- **`PastryType`** — an enum with the values `CROISSANT`, `MUFFIN`, and `SCONE`.
- **`Pastry`** — a class with private `name`, `price` (a `double`), and `type` fields, a `(String, double, PastryType)` constructor, and getters.
- **`Bakery`** — a class holding a private `List<Pastry>`, with a `(String)` constructor that initialises the list empty, plus `addPastry`, `getPastries`, and `totalStockValue` (the sum of the stock's prices).

## The mark scheme

| Section | Question | Part | Bundle | Marks | What it checks |
|---|---|---|---|---|---|
| 1 | 1 | a | a_1 | 1 | `PastryType` exists, is an enum, has the three values |
| 1 | 1 | b | b_1 | 2 | `Pastry` structure: fields, types, access, constructor, return type |
| 1 | 1 | b | b_2 | 2 | `Pastry` behaviour: constructor stores name, price, type |
| 2 | 2 | a | a_1 | 2 | `Bakery` structure **and** its constructor behaviour, bundled together |
| 2 | 2 | b | b_1 | 1 | `addPastry` stores the pastry |
| 2 | 2 | b | b_2 | 2 | `totalStockValue` for empty and stocked bakeries |

Section 1 uses the `detail` display mode (students see each test); Section 2 uses `summary` (students see one aggregate per part), demonstrating `results_display.json`.

## Where everything lives

- `autograder_config/settings.json` — `source_dirs` is `["bakery"]` (students submit a root-level `bakery/` directory); the optional `extra_packages` block is present but empty, since this exam needs nothing beyond the base toolchain.
- `autograder_config/fallback_classes/bakery/` — the reference implementations; also what defines the exam's one expected package.
- `autograder_config/helpers/structural/` — `StructuralHelper` and `AccessType`, the reflection utilities every exam vendors. Note the structure checks staying fully reflective: even the constructor-parameter check for `PastryType` resolves the class by name rather than referencing it at compile time.
- `autograder_config/junit_tests/` — four test classes, organised purely by `section/question/part` with no structural/functional split: each class covers both the structure and the behaviour of its class under test, and the bundles slice its tests into separate mark groups. The framework imposes no layout — it discovers tests from whatever tree the kit provides, and the top-level directories (here `section1/` and `section2/`) are compiled independently. Every class declares its `FQCN` and calls `FallbackChecker.skipIfFallback` in `@BeforeAll`.
- `autograder_config/mark_allocation/` — the manifest (10 marks), two section manifests, two question files whose bundles list the tests by exact fully qualified name, and the results display configuration.
- `autograder_config/submission_rules.json` — maps the three classes to `bakery` and enables the autofix rules; its `skip_files` also lists the pipeline's own log files so the submission scan never sweeps them into the student's package.

## Run it yourself

`run_autograder` is the single entry point and uses Gradescope's container paths, so mirror that layout locally. A perfect submission, using the bundled sample submission in [`../example_submission/`](../example_submission/README.md) as the student code:

```bash
sudo mkdir -p /autograder/source /autograder/submission /autograder/results
sudo chown -R "$(id -un)" /autograder
rm -rf /autograder/source/* /autograder/submission/* && cp -r . /autograder/source/
cp -r ../example_submission/bakery /autograder/submission/bakery
( cd /autograder/source && bash run_autograder )
python3 -c "import json; print(json.load(open('/autograder/results/results.json'))['score'])"   # 10.0
```

Then see the fallback model in action — drop `Pastry.java` from the submission and re-run:

```bash
rm -rf /autograder/source/* && cp -r . /autograder/source/
rm -f /autograder/submission/bakery/Pastry.java
( cd /autograder/source && bash run_autograder )
python3 -c "import json; print(json.load(open('/autograder/results/results.json'))['score'])"   # 6.0
```

The score becomes **6.0**: `Pastry` is substituted with the fallback (recorded in `bin/main/.fallback_used.txt`), so both `Pastry` test classes are skipped and Question 1 part b's 4 marks are lost — but the `Bakery` tests still pass in full against the fallback `Pastry`, because a student should not lose Question 2 marks for a Question 1 mistake. That isolation, plus the CUT-based retry for classes that are present but broken, is the heart of the marking model.
