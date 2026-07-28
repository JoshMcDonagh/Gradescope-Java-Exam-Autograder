# Exam helpers

Java classes placed here are compiled onto the test classpath *before* the test suites, so any test can import them. They are part of the exam kit: each exam carries its own copies, and the framework never needs to know they exist.

This directory is a source root, so file paths must mirror package names (`helpers/structural/StructuralHelper.java` declares `package structural;`).

What belongs here:

- **`StructuralHelper` and `AccessType`** — the reflection utilities used by structure-checking tests. Copy them from `example/example_autograder/autograder_config/helpers/structural/` as your starting point; they are exam-agnostic in content but deliberately vendored per exam so a kit is self-contained.
- **Bespoke helpers** — shared builders, custom assertions, or anything several test classes want to reuse.

Helpers may import the framework utilities in the `utils` package (`FallbackChecker`, `BatchTestRunner`), which are compiled first from `src/java/`. Give helpers a package that is not the students' package (to avoid collisions with submitted code) and that is not referenced by the mark scheme. Helpers are never treated as tests — test discovery only looks at `junit_tests/`.

An exam with no bespoke helpers can leave this directory out entirely, but almost every exam will at least want the structural pair.
