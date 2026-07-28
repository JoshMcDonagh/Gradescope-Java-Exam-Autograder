# Empty autograder

A ready-to-fill skeleton for a new exam. The framework is complete and untouched — the shell scripts, the Python tooling under `src/python/`, the framework Java helpers under `src/java/`, and the JUnit library in `libs/`. What is empty is the exam kit under `autograder_config/`: the configuration files hold blank placeholder values, and the test, fallback, and helper directories hold only their READMEs.

## What you supply

Everything an exam needs lives in `autograder_config/` — see the README in each directory for detail. In outline:

1. **Copy this directory** and rename it for your exam.
2. **Write the reference implementations** in `autograder_config/fallback_classes/`, one subdirectory per package. Their subdirectory names define the exam's expected packages.
3. **Fill `autograder_config/settings.json`** — set `source_dirs` to the location(s) of the code students submit, matching each fallback package by basename. If your tests or helpers need extra system or Python packages, list them under the optional `extra_packages` block (see `autograder_config/README.md`).
4. **Fill `autograder_config/submission_rules.json`** — map every expected class to its package in `expected_packages`, and set `submission_root` (or leave it `null`) depending on how students' uploads are wrapped.
5. **Copy the structural helpers** (`StructuralHelper.java`, `AccessType.java`) from `example/example_autograder/autograder_config/helpers/structural/` into `autograder_config/helpers/structural/`, and add any bespoke helpers your tests want.
6. **Write the tests** in `autograder_config/junit_tests/`, following the layout and the `FQCN` / `skipIfFallback` pattern described in that directory's README.
7. **Write the mark scheme** in `autograder_config/mark_allocation/`, keeping the test names in exact step with the tests, and set the display modes in `results_display.json`.
8. **Test locally** before uploading — see below.

Do not modify `src/`, `run_autograder`, or `setup.sh`; they are shared framework code and need no per-exam changes.

## Testing locally

The grading pipeline lives inside `run_autograder`, which is the single entry point Gradescope runs. It reads and writes the container's absolute paths (`/autograder/source` for the kit, `/autograder/submission` for the upload, `/autograder/results` for the output), so a local smoke test mirrors that layout. Treat your own reference implementations as a perfect submission:

```bash
sudo mkdir -p /autograder/source /autograder/submission /autograder/results
sudo chown -R "$(id -un)" /autograder
rm -rf /autograder/source/* /autograder/submission/* && cp -r . /autograder/source/
cp -r autograder_config/fallback_classes/<package> /autograder/submission/<package>
( cd /autograder/source && bash run_autograder )
python3 -c "import json; print(json.load(open('/autograder/results/results.json'))['score'])"
```

A perfect submission should score full marks with no fallbacks listed in the summary. Then delete or break a class in `/autograder/submission/<package>/` and re-run (refreshing the source copy first with `rm -rf /autograder/source/* && cp -r . /autograder/source/`). The affected tests should be skipped or fail, the score should drop accordingly, and `/autograder/source/bin/main/.fallback_used.txt` should name the substituted class. This requires OpenJDK 21, Python 3, and the `levenshtein` package (`pip install levenshtein`) — on Gradescope. `setup.sh` installs all of these, plus any `extra_packages` you declare, into the container.

## Uploading to Gradescope

From this directory, zip the autograder and upload it under the assignment's **Configure Autograder**:

```bash
zip -r autograder.zip setup.sh run_autograder autograder_config/ libs/ src/
```

Gradescope builds the Docker image (running `setup.sh`) once, then runs `run_autograder` per submission.
