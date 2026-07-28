# The exam kit (`autograder_config/`)

Everything specific to one exam lives in this directory — authoring a new exam means filling this in and touching nothing else. The framework (the shell scripts and `src/`) is exam-agnostic: it discovers your tests from `junit_tests/`, derives your packages from `fallback_classes/`, and reads exactly one setting.

| Item | Purpose |
|---|---|
| `settings.json` | **Required.** Declares `source_dirs`: where the student code to be marked lives. Each entry is a path relative to the autograder root whose basename must match a package (i.e. a `fallback_classes/` subdirectory). Usually just the package name (`["bakery"]`), but an entry may point elsewhere (`["submissions/bakery"]`) if an exam keeps marked code in a different location. May also carry an optional `extra_packages` block — see [Installing extra packages](#installing-extra-packages). |
| `submission_rules.json` | Drives the submission autofix step: maps every expected class to its package, and toggles rules that repair common packaging mistakes (wrong `package` statements, loose files, stray capitalisation) before compilation. Also lists files and directories the scan should ignore. |
| `fallback_classes/` | Reference implementations, one subdirectory per package. See its README. |
| `helpers/` | Exam-specific Java compiled onto the test classpath, including `StructuralHelper`. See its README. |
| `junit_tests/` | The JUnit test suites, organised by section, question, and part. See its README. |
| `mark_allocation/` | The mark scheme and results display configuration. See its README. |

## Installing extra packages

The base image ships with the JDK, Python, and the framework's own runtime dependencies. If your tests or helpers need anything more — a system tool or a Python library — declare it under the optional `extra_packages` key in `settings.json`, and `setup.sh` installs it when the autograder image is built:

```json
{
  "source_dirs": ["bakery"],
  "extra_packages": {
    "apt": ["graphviz", "libxml2-utils"],
    "pip": ["numpy", "pyyaml==6.0"]
  }
}
```

- `apt` — system packages, installed with `apt-get` (command-line tools, native libraries).
- `pip` — Python packages, installed with `pip` (version specifiers such as `numpy==1.26.0` or `requests[security]` are fine).

Both lists are optional; omit `extra_packages` entirely, or leave either list empty, to install nothing extra. These packages are installed **once at image build time**, not per submission, so they are available to every grading run without slowing it down. A malformed block (wrong types, or a spec that reads as a command-line option) fails the image build with an explanatory message rather than silently skipping the package.

For a complete, runnable exam kit to crib from, see `example/example_autograder/`.
