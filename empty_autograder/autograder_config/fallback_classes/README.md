# Fallback classes

This directory holds a complete, correct reference implementation of every class the students are asked to write, arranged one subdirectory per package (e.g. `fallback_classes/bakery/Bakery.java` for a class in package `bakery`).

The fallbacks serve three roles:

1. **Substitution.** If a student fails to submit a class, or their version does not compile, the reference implementation is copied in so that tests depending on it can still run. Any class substituted this way is recorded in `bin/main/.fallback_used.txt`, and `FallbackChecker` then skips the tests that target it — students never earn marks for reference code.
2. **Isolation.** After the first test run, the fallback comparison step re-runs each failing test class with every class *except* its class under test replaced by the fallback version. A student with one broken class is still marked fairly on the classes that work.
3. **Defining the exam's packages.** The pipeline derives the fallback directories, and the set of expected packages, from the subdirectories found here. Each subdirectory name must have a matching entry (by basename) in `settings.json`'s `source_dirs`; the pipeline warns loudly if one is missing, because an unmatched package would be wholly substituted and score zero.

Every expected class needs a fallback — the marking model depends on it. A worked set can be found in `example/example_autograder/autograder_config/fallback_classes/`.
