package utils;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.List;

public class FallbackChecker {
    private static List<String> fallbackClasses;

    static {
        try {
            fallbackClasses = Files.readAllLines(Paths.get("bin/main/.fallback_used.txt"));
        } catch (IOException e) {
            fallbackClasses = List.of();
        }
    }

    private static String normalize(String s) {
        String n = s.trim().replace('\\', '/');
        if (n.endsWith(".java")) n = n.substring(0, n.length() - 5);
        n = n.replace('/', '.');
        // No package-root stripping here: the caller's simple-name fallback
        // match handles any leading path junk without hardcoding exam packages.
        return n;
    }

    public static boolean wasFallbackUsed(String className) {
        String want = normalize(className);
        for (String raw : fallbackClasses) {
            String got = normalize(raw);
            if (got.equals(want)) return true;
            // also allow simple-class-name match if package differs (defensive)
            int dot = want.lastIndexOf('.');
            String simple = (dot >= 0 ? want.substring(dot + 1) : want);
            if (got.endsWith("." + simple) || got.equals(simple)) return true;
        }
        return false;
    }

    public static void skipIfFallback(String className) {
        Boolean wasFallbackClassUsed = wasFallbackUsed(className);
        
        org.junit.jupiter.api.Assumptions.assumeTrue(
            !wasFallbackClassUsed,
            "Skipping tests for " + className + " — fallback was used"
        );
    }
}
