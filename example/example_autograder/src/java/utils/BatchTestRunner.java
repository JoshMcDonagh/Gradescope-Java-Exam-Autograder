package utils;

import org.junit.platform.engine.discovery.DiscoverySelectors;
import org.junit.platform.launcher.Launcher;
import org.junit.platform.launcher.LauncherDiscoveryRequest;
import org.junit.platform.launcher.core.LauncherDiscoveryRequestBuilder;
import org.junit.platform.launcher.core.LauncherFactory;
import org.junit.platform.reporting.legacy.xml.LegacyXmlReportGeneratingListener;

import java.io.PrintWriter;
import java.io.StringWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.Callable;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;

/**
 * Runs a batch of JUnit 5 test classes in a single JVM.
 *
 * Each class is launched via its own {@link Launcher} execution on a
 * worker thread with a per-class timeout, so a failing, erroring, or
 * hanging class does not prevent the remaining classes from running.
 *
 * For each fully-qualified class name (FQCN) the runner creates a
 * subdirectory beneath {@code --reports-dir} named after the FQCN (with
 * dots replaced by underscores) and attaches a
 * {@link LegacyXmlReportGeneratingListener} that writes a standard
 * {@code TEST-*.xml} report into that subdirectory. This mirrors the
 * layout produced by the per-class {@code ConsoleLauncher} approach, so
 * the Python side of the autograder can consume either output
 * interchangeably.
 *
 * If a class times out, throws out of {@link Launcher#execute}, or
 * cannot be discovered (e.g. no such class), a synthetic
 * {@code TEST-<fqcn>.xml} is written marking the class as errored and
 * the runner carries on. On fatal failures unrelated to any particular
 * class (e.g. missing JUnit engine on the classpath) the runner exits
 * with a non-zero status so the caller can retry per-class in fresh
 * JVMs.
 *
 * CLI:
 *   java -cp <classpath> utils.BatchTestRunner
 *        --reports-dir <dir>
 *        [--timeout <seconds>]
 *        [--class-list <file>]
 *        [FQCN ...]
 *
 * Exit codes:
 *   0 — every class produced a normal report
 *   3 — at least one class timed out or crashed the runner thread
 *   2 — fatal CLI / IO error before any class was attempted
 */
public final class BatchTestRunner {

    private static final long DEFAULT_TIMEOUT_SECONDS = 60;

    private BatchTestRunner() { /* no instances */ }

    public static void main(String[] args) {
        Path reportsDir = null;
        long timeoutSeconds = DEFAULT_TIMEOUT_SECONDS;
        Path classListFile = null;
        List<String> classes = new ArrayList<>();

        try {
            for (int i = 0; i < args.length; i++) {
                switch (args[i]) {
                    case "--reports-dir":
                        reportsDir = Paths.get(requireArg(args, ++i, "--reports-dir"));
                        break;
                    case "--timeout":
                        timeoutSeconds = Long.parseLong(requireArg(args, ++i, "--timeout"));
                        break;
                    case "--class-list":
                        classListFile = Paths.get(requireArg(args, ++i, "--class-list"));
                        break;
                    default:
                        classes.add(args[i]);
                }
            }

            if (reportsDir == null) {
                System.err.println("[BatchTestRunner] --reports-dir is required");
                System.exit(2);
            }

            if (classListFile != null) {
                for (String line : Files.readAllLines(classListFile, StandardCharsets.UTF_8)) {
                    String trimmed = line.trim();
                    if (!trimmed.isEmpty() && !trimmed.startsWith("#")) {
                        classes.add(trimmed);
                    }
                }
            }

            Files.createDirectories(reportsDir);
        } catch (Exception bootstrapFailure) {
            System.err.println("[BatchTestRunner] fatal bootstrap error: " + bootstrapFailure);
            bootstrapFailure.printStackTrace();
            System.exit(2);
            return;
        }

        if (classes.isEmpty()) {
            System.out.println("[BatchTestRunner] no classes supplied; nothing to do");
            System.exit(0);
            return;
        }

        System.out.println("[BatchTestRunner] running " + classes.size()
                + " class(es) with per-class timeout " + timeoutSeconds + "s");

        ExecutorService executor = Executors.newSingleThreadExecutor(r -> {
            Thread t = new Thread(r, "batch-test-worker");
            t.setDaemon(true);
            return t;
        });

        int crashed = 0;
        try {
            for (String fqcn : classes) {
                Path perClassDir = reportsDir.resolve(fqcn.replace(".", "_"));
                Files.createDirectories(perClassDir);

                System.out.println("[BatchTestRunner] >> " + fqcn);

                boolean ok = runOneClass(fqcn, perClassDir, executor, timeoutSeconds);
                if (!ok) crashed++;
            }
        } catch (Throwable t) {
            System.err.println("[BatchTestRunner] unexpected error during batch loop: " + t);
            t.printStackTrace();
            crashed++;
        } finally {
            executor.shutdownNow();
        }

        System.out.println("[BatchTestRunner] done: " + classes.size()
                + " class(es), " + crashed + " crashed/timed out");
        System.exit(crashed > 0 ? 3 : 0);
    }

    private static String requireArg(String[] args, int idx, String flag) {
        if (idx >= args.length) {
            throw new IllegalArgumentException("Missing value for " + flag);
        }
        return args[idx];
    }

    /**
     * Runs a single class under the shared worker thread with a timeout.
     * Returns true if JUnit completed normally (even if tests failed);
     * false if the class timed out or the runner thread threw. In the
     * false case, a synthetic XML is written to {@code perClassDir}.
     */
    private static boolean runOneClass(String fqcn,
                                       Path perClassDir,
                                       ExecutorService executor,
                                       long timeoutSeconds) {
        Callable<Void> task = () -> {
            LauncherDiscoveryRequest request = LauncherDiscoveryRequestBuilder.request()
                    .selectors(DiscoverySelectors.selectClass(fqcn))
                    .build();
            Launcher launcher = LauncherFactory.create();
            PrintWriter sink = new PrintWriter(new StringWriter());
            LegacyXmlReportGeneratingListener xml =
                    new LegacyXmlReportGeneratingListener(perClassDir, sink);
            launcher.registerTestExecutionListeners(xml);
            launcher.execute(request);
            return null;
        };

        Future<Void> future = executor.submit(task);
        try {
            future.get(timeoutSeconds, TimeUnit.SECONDS);
            return true;
        } catch (TimeoutException te) {
            future.cancel(true);
            writeSyntheticXml(perClassDir, fqcn,
                    "Test class did not finish within " + timeoutSeconds + " seconds.");
            System.err.println("[BatchTestRunner] TIMEOUT: " + fqcn);
            return false;
        } catch (Throwable t) {
            writeSyntheticXml(perClassDir, fqcn,
                    "Runner error: " + t.getClass().getSimpleName()
                    + (t.getMessage() == null ? "" : ": " + t.getMessage()));
            System.err.println("[BatchTestRunner] CRASH: " + fqcn + " -- " + t);
            return false;
        }
    }

    /**
     * Emits a minimal JUnit-compatible XML so downstream parsers see
     * the class as errored rather than missing entirely.
     */
    private static void writeSyntheticXml(Path perClassDir, String fqcn, String message) {
        try {
            Files.createDirectories(perClassDir);
            String safeName = fqcn.replaceAll("[^A-Za-z0-9_.-]", "_");
            Path xml = perClassDir.resolve("TEST-" + safeName + ".xml");
            String escapedMsg = escapeXml(message);
            String escapedClass = escapeXml(fqcn);
            String body = ""
                    + "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
                    + "<testsuite name=\"" + escapedClass + "\" "
                    + "tests=\"1\" failures=\"0\" errors=\"1\" skipped=\"0\" time=\"0\">\n"
                    + "  <testcase name=\"classLevelError\" classname=\"" + escapedClass + "\" time=\"0\">\n"
                    + "    <error message=\"" + escapedMsg + "\" type=\"RunnerError\">" + escapedMsg + "</error>\n"
                    + "  </testcase>\n"
                    + "</testsuite>\n";
            Files.writeString(xml, body, StandardCharsets.UTF_8);
        } catch (Exception e) {
            System.err.println("[BatchTestRunner] failed to write synthetic XML for "
                    + fqcn + ": " + e);
        }
    }

    private static String escapeXml(String s) {
        if (s == null) return "";
        return s.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("\"", "&quot;")
                .replace("'", "&apos;");
    }
}
