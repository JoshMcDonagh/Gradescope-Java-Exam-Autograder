# JUnit tests

Every `.java` file under this directory is a test class — the pipeline discovers tests from this tree, so the framework carries no knowledge of your package names and helper classes elsewhere are never mistaken for tests.

## Layout and naming

Tests live in a `{section}/{question}/{part}/` hierarchy, one test class per part, for example:

```
junit_tests/section1/question1/a/PastryTypeTest.java
junit_tests/section2/question2/b/BakeryTest.java
```

A single class can freely mix reflection-based structure checks (via `StructuralHelper`) with behavioural JUnit 5 tests that instantiate student code; the mark scheme's bundles decide how its tests split into mark groups. The framework imposes no layout at all — every `.java` file under this directory is discovered as a test wherever it sits, so an exam may add extra top-level grouping (for instance a structural/functional split) if it prefers. The top-level directories, whatever they are, compile independently: a compilation error in one cannot stop the others from building.

A test's fully qualified name, as referenced by the mark scheme, is its package plus class plus method: `section1.question1.a.PastryTypeTest.testEnumExists`. These strings are matched exactly against the JUnit output, so keep the mark scheme and this tree in lock-step.

## Required pattern

Every test class must identify its class under test and skip itself when that class was substituted with a fallback:

```java
public class PastryTest {

    static String FQCN = "bakery.Pastry";

    @BeforeAll
    public static void fallbackCheck() {
        FallbackChecker.skipIfFallback(FQCN);
    }

    // @Test methods ...
}
```

The `FQCN` field does double duty: `skipIfFallback` reads it at run time, and the fallback comparison step parses it from the source to learn which class each test exercises. Worked examples of both structural and functional tests are in `example/example_autograder/autograder_config/junit_tests/`.
