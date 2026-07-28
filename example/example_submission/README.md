# Example submission

A ready-made sample student submission for the bakery exam — a root-level `bakery/` package, exactly as a student would upload it. Use it to run the [example autograder](../example_autograder/README.md) end to end without hand-assembling a submission.

The three files are byte-for-byte identical to the reference implementations in `../example_autograder/autograder_config/fallback_classes/bakery/`, so this is a **perfect submission**: fed through the autograder unmodified it scores the full **10 marks** with no fallbacks reported.

To see the fallback model in action, delete one class (for example `bakery/Pastry.java`) before running. The score drops to 6: `Pastry` is substituted with its fallback and both `Pastry` test classes skip, while the `Bakery` tests still pass against the fallback, so a Question 1 mistake does not cost Question 2 marks. The autograder's [README](../example_autograder/README.md) walks through both runs.
