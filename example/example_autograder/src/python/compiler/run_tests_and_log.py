"""
Discovers compiled JUnit 5 test classes and runs them, producing one
parser-compatible text report per class (same format the existing
automarker has always consumed).

Strategy:
  1. Try the fast path: invoke utils.BatchTestRunner once in a single
     JVM. It runs each class with a per-class timeout and writes
     TEST-*.xml into per-class subdirectories.
  2. For any class that didn't end up with a valid TEST-*.xml (timeout,
     runner crash, missing engine on classpath, etc.), fall back to the
     original per-class ConsoleLauncher invocation.
  3. For every class, convert the XML into the ANSI-flavoured text
     format the automarker expects.

The CLI matches the previous script so run_tests_autograder.sh does not
need changes.
"""
import argparse
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path


ANSI_CYAN = "\x1b[36m"
ANSI_BLUE = "\x1b[34m"
ANSI_GREEN = "\x1b[32m"
ANSI_RED = "\x1b[31m"
ANSI_RESET = "\x1b[0m"

BATCH_RUNNER_FQCN = "utils.BatchTestRunner"

PER_CLASS_TIMEOUT_SECONDS = 60
BATCH_WALL_CLOCK_SECONDS = 15 * 60


def find_test_classes(bin_test_dir: Path, test_src_dir: Path):
    """Enumerate test classes from the exam's test source tree.

    Every .java file under test_src_dir is a test class by definition, so the
    framework carries no knowledge of the tree's package names — whatever
    top-level packages an exam kit uses are discovered automatically, and
    helper classes (which live outside this tree) are never selected. Only
    classes whose compiled .class file exists in bin_test_dir are yielded; a
    missing class means its compilation group failed to build.
    """
    for java_file in sorted(test_src_dir.rglob("*.java")):
        fqcn = ".".join(java_file.relative_to(test_src_dir).with_suffix("").parts)
        class_file = bin_test_dir.joinpath(*fqcn.split(".")).with_suffix(".class")
        if class_file.exists():
            yield fqcn
        else:
            print(f"[WARNING] No compiled class for test source {fqcn} — "
                  f"skipping (check the test compile log).")


def safe_filename(fqcn: str) -> str:
    return fqcn.replace(".", "_") + ".txt"


def report_dir_for(reports_root: Path, fqcn: str) -> Path:
    return reports_root / fqcn.replace(".", "_")


def xml_report_in(report_dir: Path):
    if not report_dir.is_dir():
        return None
    xmls = sorted(report_dir.glob("TEST-*.xml"))
    return xmls[0] if xmls else None


def _symbol_and_colour_for_testcase(testcase):
    if testcase.find("failure") is not None or testcase.find("error") is not None:
        return "\u2718", ANSI_RED
    if testcase.get("skipped") is not None or testcase.find("skipped") is not None:
        return "\u21b7", ANSI_RED
    return "\u2714", ANSI_GREEN


def _first_extra_text(testcase):
    for tag in ("failure", "error"):
        node = testcase.find(tag)
        if node is None:
            continue
        msg = node.get("message")
        if msg and msg.strip():
            return " ".join(msg.strip().split())
        text = node.text
        if text and text.strip():
            return " ".join(text.strip().splitlines()[0].split())
    return None


def _write_parser_compatible_output(output_path, fqcn, xml_report_path, raw_stdout):
    class_name = fqcn.split(".")[-1]

    if xml_report_path is None or not xml_report_path.exists():
        with open(output_path, "w", encoding="utf-8") as outfile:
            outfile.write("JUnit report was not produced.\n")
            if raw_stdout and raw_stdout.strip():
                outfile.write(raw_stdout)
                if not raw_stdout.endswith("\n"):
                    outfile.write("\n")
        return False

    try:
        tree = ET.parse(xml_report_path)
        root = tree.getroot()
    except ET.ParseError:
        with open(output_path, "w", encoding="utf-8") as outfile:
            outfile.write("JUnit report could not be parsed.\n")
            if raw_stdout and raw_stdout.strip():
                outfile.write(raw_stdout)
                if not raw_stdout.endswith("\n"):
                    outfile.write("\n")
        return False

    testcases = root.findall("testcase")
    tests_attr = int(root.get("tests", "0"))
    failures_attr = int(root.get("failures", "0"))
    errors_attr = int(root.get("errors", "0"))
    skipped_attr = int(root.get("skipped", "0"))

    class_passed = (failures_attr == 0 and errors_attr == 0)

    with open(output_path, "w", encoding="utf-8") as outfile:
        outfile.write(f"{ANSI_CYAN}\u2577{ANSI_RESET}\n")
        outfile.write(f"{ANSI_CYAN}\u251c\u2500{ANSI_RESET} {ANSI_CYAN}JUnit Jupiter{ANSI_RESET} {ANSI_GREEN}\u2714{ANSI_RESET}\n")
        class_symbol = "\u2714" if class_passed else "\u2718"
        class_colour = ANSI_GREEN if class_passed else ANSI_RED
        outfile.write(
            f"{ANSI_CYAN}\u2502  \u2514\u2500{ANSI_RESET} "
            f"{ANSI_CYAN}{class_name}{ANSI_RESET} "
            f"{class_colour}{class_symbol}{ANSI_RESET}\n"
        )

        for testcase in testcases:
            test_name = testcase.get("name", "").strip()
            if not test_name:
                continue
            symbol, colour = _symbol_and_colour_for_testcase(testcase)
            extra = _first_extra_text(testcase)
            line = (
                f"{ANSI_CYAN}\u2502     \u2514\u2500{ANSI_RESET} "
                f"{ANSI_BLUE}{test_name}(){ANSI_RESET} "
                f"{colour}{symbol}{ANSI_RESET}"
            )
            if extra:
                line += f" {ANSI_RED}{extra}{ANSI_RESET}"
            outfile.write(line + "\n")

        outfile.write(f"{ANSI_CYAN}\u251c\u2500{ANSI_RESET} {ANSI_CYAN}JUnit Vintage{ANSI_RESET} {ANSI_GREEN}\u2714{ANSI_RESET}\n")
        outfile.write("\n")
        outfile.write(f"Test run finished after {root.get('time', '0')} s\n")
        outfile.write(f"[         {tests_attr} tests found           ]\n")
        outfile.write(f"[         {skipped_attr} tests skipped         ]\n")
        outfile.write(f"[         {tests_attr - skipped_attr} tests started         ]\n")
        outfile.write(f"[         {tests_attr - failures_attr - errors_attr - skipped_attr} tests successful      ]\n")
        outfile.write(f"[         {failures_attr + errors_attr} tests failed          ]\n")

    return True


def run_batch(classes, classpath, reports_root):
    reports_root.mkdir(parents=True, exist_ok=True)
    class_list_file = reports_root.parent / "_batch_classes.txt"
    class_list_file.write_text("\n".join(classes) + "\n", encoding="utf-8")

    cmd = [
        "java", "-cp", classpath, BATCH_RUNNER_FQCN,
        "--reports-dir", str(reports_root),
        "--timeout", str(PER_CLASS_TIMEOUT_SECONDS),
        "--class-list", str(class_list_file),
    ]

    print(f"=== [batch] launching {BATCH_RUNNER_FQCN} for {len(classes)} class(es) ===")
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, timeout=BATCH_WALL_CLOCK_SECONDS, check=False,
        )
        if proc.stdout:
            print(proc.stdout.rstrip())
        print(f"=== [batch] exit code {proc.returncode} ===")
        return True
    except subprocess.TimeoutExpired:
        print(f"=== [batch] WALL CLOCK ({BATCH_WALL_CLOCK_SECONDS}s) exceeded — aborting ===")
        return False
    except FileNotFoundError:
        print("=== [batch] 'java' executable not found ===")
        return False


def run_single_class(fqcn, classpath, reports_root):
    report_dir = report_dir_for(reports_root, fqcn)
    report_dir.mkdir(parents=True, exist_ok=True)

    print(f"=== [per-class fallback] {fqcn} ===")
    proc = subprocess.run(
        [
            "java", "-cp", classpath,
            "org.junit.platform.console.ConsoleLauncher",
            "--disable-banner", "--details=none",
            "--reports-dir", str(report_dir),
            "--select-class", fqcn,
        ],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, check=False,
    )
    xml = xml_report_in(report_dir)
    return (xml is not None, proc.stdout or "")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bin-test", required=True, type=Path)
    parser.add_argument("--classpath", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--test-src-dir", default=Path("autograder_config/junit_tests"), type=Path,
                        help="Root of the exam's JUnit test sources. Test classes are "
                             "discovered from this tree, so the framework needs no "
                             "knowledge of the exam's test package names.")
    parser.add_argument("--no-batch", action="store_true",
                        help="Skip the batch fast path and run every class in its own JVM.")
    args = parser.parse_args()

    print("=== [run_tests_and_log.py] starting ===")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    reports_root = args.output_dir / "_junit_xml"
    reports_root.mkdir(parents=True, exist_ok=True)

    classes = list(find_test_classes(args.bin_test, args.test_src_dir))

    if not classes:
        print(f"No test classes discovered under {args.test_src_dir}.")
        print("=== [run_tests_and_log.py] done ===")
        return

    print(f"Discovered {len(classes)} test class(es).")

    if not args.no_batch:
        run_batch(classes, args.classpath, reports_root)

    missing_after_batch = [
        fqcn for fqcn in classes
        if xml_report_in(report_dir_for(reports_root, fqcn)) is None
    ]
    if missing_after_batch:
        print(f"=== [fallback] {len(missing_after_batch)} class(es) need per-class JVM ===")
    for fqcn in missing_after_batch:
        run_single_class(fqcn, args.classpath, reports_root)

    failed_classes = []
    for fqcn in classes:
        output_path = args.output_dir / safe_filename(fqcn)
        xml_path = xml_report_in(report_dir_for(reports_root, fqcn))
        ok = _write_parser_compatible_output(
            output_path=output_path, fqcn=fqcn,
            xml_report_path=xml_path, raw_stdout="",
        )
        if not ok:
            failed_classes.append(fqcn)

    print("\n=== Test Run Summary ===")
    if failed_classes:
        print("Classes without a parseable report:")
        for fqcn in failed_classes:
            print(" -", fqcn)
    else:
        print("All classes produced reports.")
    print("=== [run_tests_and_log.py] done ===")


if __name__ == "__main__":
    main()
