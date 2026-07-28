# Gradescope Java Exam Autograder

An autograder for Java practical programming exams on Gradescope. It repairs common packaging mistakes in student submissions, compiles the code, runs JUnit 5 test suites covering both code structure and behaviour, substitutes reference implementations for missing or broken classes so that one mistake cannot sink a whole submission, and scores the results against a JSON mark scheme to produce Gradescope's `results.json`.

Developed by Joshua McDonagh (joshua.mcdonagh@manchester.ac.uk). The submission checker and automarker are built on foundations created by Dr. Sarah Clinch (sarah.clinch@manchester.ac.uk).

## Repository layout

- **`empty_autograder/`** — a ready-to-fill skeleton: the complete framework plus a blank exam kit. Start here when authoring a new exam; its [README](empty_autograder/README.md) contains the step-by-step checklist.
- **`example/`** — a complete, runnable worked example (a small invented 10-mark "bakery" exam) showing every part of the system in use. It holds two things:
  - **`example_autograder/`** — the autograder for the example exam. Its [README](example/example_autograder/README.md) is a guided tour, and its files are the reference for what each artefact should look like.
  - **`example_submission/`** — a ready-made sample student submission (a perfect-scoring `bakery/` upload) to feed through the autograder. See its [README](example/example_submission/README.md).

Each autograder directory is self-contained and splits into two halves:

- **The framework** — `run_autograder`, `run_tests_autograder.sh`, `setup.sh`, the Python tooling in `src/python/`, the Java helpers in `src/java/`, and the JUnit library in `libs/`. Identical for every exam; never needs editing.
- **The exam kit** — everything under `autograder_config/`: reference implementations, test suites, exam helpers, the mark scheme, submission rules, and one small settings file. Authoring an exam means filling this in. Every directory in the kit carries its own README.

The framework is deliberately ignorant of the exam's content: it discovers the test classes from the `junit_tests/` tree, derives the expected packages from the `fallback_classes/` subdirectories, and reads exactly one setting — `source_dirs` in `settings.json`, which says where the code to be marked lives.

## How a submission is marked

`setup.sh` runs once when Gradescope builds the container (installing OpenJDK 21, Python 3, and the `levenshtein` package). Then, per submission, `run_autograder` copies the upload into place and hands over to `run_tests_autograder.sh`, which:

1. Reads `source_dirs` from `autograder_config/settings.json` and derives the fallback directories from `autograder_config/fallback_classes/`.
2. Repairs the submission — Windows path separators, nested directories, then the **submission checker**, which fixes packaging errors (wrong `package` statements, loose files, misnamed files) according to `submission_rules.json`.
3. Compiles the student code, substituting a reference implementation for any class that is missing or fails to compile, and recording each substitution in `bin/main/.fallback_used.txt`.
4. Compiles the helpers (framework first, then the exam's) and the test suites, each test group independently so one group's compile error cannot block the others.
5. Runs every test class — a fast single-JVM batch pass with per-class timeouts, falling back to individual JUnit console launches where needed. A test class whose class under test was substituted skips itself, so students never earn marks for reference code.
6. Runs the **fallback comparison**: each failing test class is retried with every class *except* its class under test swapped for the fallback, so a student is marked on each class in isolation and one broken class cannot fail the others' tests.

Finally the **automarker** validates the mark scheme, matches the test results to its bundles (all-or-nothing groups of tests sharing a mark allocation), applies the display configuration, and writes `results.json`, which `run_autograder` copies to Gradescope.

## Writing tests

Tests live in `autograder_config/junit_tests/{section}/{question}/{part}/`, one class per part, freely mixing reflection-based structure checks (via the vendored `StructuralHelper`) with behavioural JUnit tests — the mark scheme's bundles decide how a class's tests split into mark groups. The framework discovers tests from whatever tree the kit provides, so an exam may add extra top-level grouping if it wishes; the top-level directories compile independently either way. Every test class declares its class under test and skips itself when that class was a fallback:

```java
static String FQCN = "bakery.Pastry";

@BeforeAll
public static void fallbackCheck() {
    FallbackChecker.skipIfFallback(FQCN);
}
```

The mark scheme references tests by exact fully qualified name (`section1.question1.a.PastryTypeTest.testEnumExists`), so the scheme and the test tree must be kept in lock-step. Full details are in `empty_autograder/autograder_config/junit_tests/README.md` and `.../mark_allocation/README.md`.

## Testing an exam locally

With OpenJDK 21, Python 3, and `levenshtein` installed, run the pipeline from an autograder directory using the reference implementations as a perfect submission:

```bash
cp -r autograder_config/fallback_classes/<package> ./<package>
bash run_tests_autograder.sh
PYTHONPATH=./src/python python3 -m automarker.automark
python3 -m json.tool results.json | head
```

A perfect submission should score full marks with no fallbacks reported; deleting a class and re-running should drop the score and name the class in the fallback summary. The example autograder's README walks through exactly this. For a faithful container test, mount the directory into an Ubuntu image and run `setup.sh` followed by `run_autograder` against `/autograder/submission/`.

## Uploading to Gradescope

From inside the exam's autograder directory:

```bash
zip -r autograder.zip setup.sh run_autograder run_tests_autograder.sh autograder_config/ libs/ src/
```

Upload the zip under the assignment's **Configure Autograder**. Gradescope builds the image once and runs `run_autograder` for each submission.

## Troubleshooting

**Mark scheme validation error** — marks do not sum correctly somewhere in the hierarchy (bundles → part → question → section → total), or an ID is duplicated. The error names the level; fix the JSON and re-run.

**A scheme test is "expected but not found"** — the fully qualified name in a bundle matches nothing in the JUnit output. Check for typos and confirm the test class compiled (see `test_compile_output.txt`). Missing tests are treated as failed, so the rest of the submission still scores.

**Test output "not matched to mark scheme"** — a test ran but no bundle references it. Add it to the scheme or remove the test.

**A student scores 0 on a class they submitted** — check `bin/main/.fallback_used.txt` and `compile_output.txt`: their file probably failed to compile, so the fallback was substituted and the tests skipped.

**A helper or `BatchTestRunner` cannot be found** — helpers compile automatically from `src/java/` and then `autograder_config/helpers/`; a missing class means a compile error in one of those trees (see `test_compile_output.txt`) or a file whose path does not match its `package` declaration.

**Tests time out** — the batch runner allows 60 seconds per class and 15 minutes overall; the constants are at the top of `src/python/compiler/run_tests_and_log.py`.
