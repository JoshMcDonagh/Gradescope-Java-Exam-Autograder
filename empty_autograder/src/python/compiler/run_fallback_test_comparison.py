"""
Class-Under-Test (CUT) based fallback comparison.

For every failing test class we identify the single class it was really
written to exercise (its "class under test"), then retry the test
against a source tree where every OTHER class has been swapped for its
fallback copy where one is available. The test therefore exercises
only the student's implementation of that one class, so a student whose
e.g. Bakery.java is broken is still marked fairly for their working
Pastry.java.

Compared to the previous per-(test, fallback) Cartesian sweep, this is
one compile + one test run per unique CUT group — O(tests), not
O(tests * fallbacks).

CLI is compatible with the previous script so run_autograder does not
need to change, with one addition: --test-src-dir (defaults to
'autograder_config/junit_tests'), used to parse the test sources and
discover each test's CUT.
"""
import argparse
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path


# ---------------------------------------------------------------------------
# CUT extraction from test sources
# ---------------------------------------------------------------------------

FQCN_FIELD_RE = re.compile(
    r'static\s+(?:final\s+)?String\s+(\w+)\s*=\s*"([^"]+)"\s*;'
)
SKIP_CALL_RE = re.compile(
    r'FallbackChecker\s*\.\s*skipIfFallback\s*\(\s*([^)\n]+?)\s*\)'
)
STRING_LITERAL_RE = re.compile(r'^"([^"]+)"$')


def extract_cut_from_source(java_file: Path) -> str | None:
    """Return the FQCN passed to FallbackChecker.skipIfFallback(...),
    or None if we can't determine it."""
    try:
        text = java_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    fields = {m.group(1): m.group(2) for m in FQCN_FIELD_RE.finditer(text)}

    m = SKIP_CALL_RE.search(text)
    if not m:
        return None
    arg = m.group(1).strip()

    lit = STRING_LITERAL_RE.match(arg)
    if lit:
        return lit.group(1)

    if arg in fields:
        return fields[arg]

    return None


def test_fqcn_for_source(source_root: Path, java_file: Path) -> str:
    return ".".join(java_file.relative_to(source_root).with_suffix("").parts)


def build_test_to_cut_map(test_src_dir: Path) -> dict[str, str]:
    """Map test FQCN -> CUT FQCN. Every source under test_src_dir is a test
    class; anything without a recognisable FQCN field is simply skipped."""
    mapping = {}
    for java in test_src_dir.rglob("*.java"):
        fqcn = test_fqcn_for_source(test_src_dir, java)
        cut = extract_cut_from_source(java)
        if cut:
            mapping[fqcn] = cut
    return mapping


# ---------------------------------------------------------------------------
# Pass-1 results parsing
# ---------------------------------------------------------------------------

PASS_TOTAL_RE = re.compile(
    r'(\d+)\s+tests\s+found.*?(\d+)\s+tests\s+successful',
    re.DOTALL,
)


def read_pass1_result(txt_path: Path) -> dict:
    if not txt_path.exists():
        return {"passed": 0, "total": 0}
    try:
        content = txt_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"passed": 0, "total": 0}
    m = PASS_TOTAL_RE.search(content)
    if not m:
        return {"passed": 0, "total": 0}
    return {"total": int(m.group(1)), "passed": int(m.group(2))}


def xml_report_in(report_dir: Path):
    if not report_dir.is_dir():
        return None
    xmls = sorted(report_dir.glob("TEST-*.xml"))
    return xmls[0] if xmls else None


def result_from_xml(xml_path: Path) -> dict:
    try:
        tree = ET.parse(xml_path)
    except (ET.ParseError, OSError):
        return {"passed": 0, "total": 0}
    root = tree.getroot()
    total = int(root.get("tests", "0"))
    failed = int(root.get("failures", "0")) + int(root.get("errors", "0"))
    skipped = int(root.get("skipped", "0"))
    return {"passed": max(0, total - failed - skipped), "total": total}


# ---------------------------------------------------------------------------
# Source tree manipulation for a CUT group
# ---------------------------------------------------------------------------

def find_fallback_for_simple(simple_name: str, fallback_dirs: list[Path]) -> Path | None:
    """Find a fallback .java file by simple class name, searching each
    fallback root recursively."""
    for fdir in fallback_dirs:
        for candidate in fdir.rglob(f"{simple_name}.java"):
            return candidate
    return None


def find_source_for_simple(simple_name: str, source_dirs: list[Path]) -> Path | None:
    for sd in source_dirs:
        for candidate in sd.rglob(f"{simple_name}.java"):
            return candidate
    return None


def cut_simple_name(cut_fqcn: str) -> str:
    return cut_fqcn.split(".")[-1]


def collect_student_simple_names(source_dirs: list[Path]) -> set[str]:
    names = set()
    for sd in source_dirs:
        for java in sd.rglob("*.java"):
            if java.suffix == ".java" and ".student_backup" not in java.name:
                names.add(java.stem)
    return names


def files_have_same_content(a: Path, b: Path) -> bool:
    try:
        return a.read_bytes() == b.read_bytes()
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Running tests for a CUT group (uses BatchTestRunner if available)
# ---------------------------------------------------------------------------

BATCH_RUNNER_FQCN = "utils.BatchTestRunner"
PER_CLASS_TIMEOUT_SECONDS = 60
BATCH_WALL_CLOCK_SECONDS = 10 * 60


def run_tests_batch(classes: list[str], classpath: str, reports_root: Path) -> None:
    reports_root.mkdir(parents=True, exist_ok=True)
    class_list_file = reports_root.parent / "_cut_retry_classes.txt"
    class_list_file.write_text("\n".join(classes) + "\n", encoding="utf-8")

    cmd = [
        "java", "-cp", classpath, BATCH_RUNNER_FQCN,
        "--reports-dir", str(reports_root),
        "--timeout", str(PER_CLASS_TIMEOUT_SECONDS),
        "--class-list", str(class_list_file),
    ]
    try:
        proc = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, timeout=BATCH_WALL_CLOCK_SECONDS, check=False,
        )
        if proc.stdout:
            print(proc.stdout.rstrip())
    except subprocess.TimeoutExpired:
        print(f"[cut-retry] batch wall clock exceeded")
    except FileNotFoundError:
        # Fall back to per-class ConsoleLauncher below
        for fqcn in classes:
            run_single_class(fqcn, classpath, reports_root)


def run_single_class(fqcn: str, classpath: str, reports_root: Path) -> None:
    report_dir = reports_root / fqcn.replace(".", "_")
    report_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "java", "-cp", classpath,
            "org.junit.platform.console.ConsoleLauncher",
            "--disable-banner", "--details=none",
            "--reports-dir", str(report_dir),
            "--select-class", fqcn,
        ],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    )


# ---------------------------------------------------------------------------
# Write parser-compatible text output from an XML report
# ---------------------------------------------------------------------------

ANSI_CYAN = "\x1b[36m"
ANSI_BLUE = "\x1b[34m"
ANSI_GREEN = "\x1b[32m"
ANSI_RED = "\x1b[31m"
ANSI_RESET = "\x1b[0m"


def _symbol_and_colour(testcase):
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


def write_parser_text(output_path: Path, fqcn: str, xml_path: Path) -> bool:
    class_name = fqcn.split(".")[-1]
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except (ET.ParseError, OSError):
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
            symbol, colour = _symbol_and_colour(testcase)
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


# ---------------------------------------------------------------------------
# Main CUT retry
# ---------------------------------------------------------------------------

def _rewrite_classpath_bin_main(classpath: str, old_bin_main: Path, new_bin_main: Path) -> str:
    parts = classpath.split(":")
    old = str(old_bin_main)
    new = str(new_bin_main)
    rewritten = [new if p == old else p for p in parts]
    if new not in rewritten:
        rewritten.insert(0, new)
    return ":".join(rewritten)


def load_pass1_fallback_track(track_path: Path) -> list[str]:
    if not track_path.exists():
        return []
    try:
        return [ln.strip() for ln in track_path.read_text(encoding="utf-8").splitlines()
                if ln.strip()]
    except OSError:
        return []


def perform_cut_retry_for_group(
    cut_fqcn: str,
    tests_in_group: list[str],
    source_dirs: list[Path],
    fallback_dirs: list[Path],
    bin_main: Path,
    bin_test: Path,
    classpath: str,
    compile_output: Path,
    pass1_fallback_track: list[str],
    fallback_track_path: Path,
    scratch_root: Path,
    results_dir: Path,
    reports_root: Path,
    pass1_results: dict[str, dict],
) -> dict[str, dict]:
    """
    Runs one CUT retry attempt: swap all non-CUT classes for fallbacks,
    recompile to a scratch bin, re-run the tests in the group, and
    return the new results keyed by test FQCN.
    """
    cut_simple = cut_simple_name(cut_fqcn)
    print(f"\n[cut-retry] CUT={cut_fqcn} ({len(tests_in_group)} test(s))")

    # If the student's CUT itself is fallback'd already, there's nothing
    # to validate — the tests will already have been assume-skipped and
    # pass1 is the best we can do.
    if cut_simple in pass1_fallback_track:
        print(f"[cut-retry] CUT '{cut_simple}' is already a fallback in pass 1; skipping")
        return {}

    # Determine which non-CUT student files have a fallback we can use
    student_simples = collect_student_simple_names(source_dirs)
    backups_made: list[tuple[Path, Path]] = []
    new_fallback_track: set[str] = set(pass1_fallback_track) - {cut_simple}

    try:
        # Overlay fallbacks onto the source tree in-place
        for simple in sorted(student_simples):
            if simple == cut_simple:
                continue  # keep the student's CUT
            student_path = find_source_for_simple(simple, source_dirs)
            if student_path is None:
                continue
            fallback_path = find_fallback_for_simple(simple, fallback_dirs)
            if fallback_path is None:
                continue  # no fallback for this class; leave student's in place
            if files_have_same_content(student_path, fallback_path):
                # Already the fallback (from pass 1); just make sure the
                # track list reflects that.
                new_fallback_track.add(simple)
                continue
            backup = student_path.with_suffix(student_path.suffix + ".cut_retry_backup")
            shutil.copy2(student_path, backup)
            shutil.copy2(fallback_path, student_path)
            backups_made.append((student_path, backup))
            new_fallback_track.add(simple)

        # Also pull in any missing fallbacks that weren't in the student tree
        # (defensive — pass 1 should already have done this).
        for fdir in fallback_dirs:
            for fb in fdir.rglob("*.java"):
                simple = fb.stem
                if simple == cut_simple:
                    continue
                present = find_source_for_simple(simple, source_dirs) is not None
                if present:
                    continue
                # Drop it into the first source dir, preserving its relative path.
                sd = source_dirs[0]
                rel = fb.relative_to(fdir)
                target = sd / rel if not (sd.name == rel.parts[0]) else sd / Path(*rel.parts[1:])
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(fb, target)
                # Track we created it so we can remove it on restore
                backups_made.append((target, None))  # None marker = delete on restore
                new_fallback_track.add(simple)

        # Back up and rewrite .fallback_used.txt so FallbackChecker sees
        # the right list for this retry.
        original_track_content = ""
        if fallback_track_path.exists():
            original_track_content = fallback_track_path.read_text(encoding="utf-8")
        fallback_track_path.parent.mkdir(parents=True, exist_ok=True)
        fallback_track_path.write_text(
            "\n".join(sorted(new_fallback_track)) + "\n", encoding="utf-8"
        )

        # Fresh scratch bin dir
        scratch_bin = scratch_root / f"bin_cut_{cut_simple}"
        shutil.rmtree(scratch_bin, ignore_errors=True)
        scratch_bin.mkdir(parents=True, exist_ok=True)

        # Collect all current source .java files
        all_java = []
        for sd in source_dirs:
            all_java.extend(str(p) for p in sd.rglob("*.java")
                            if ".student_backup" not in p.name
                            and ".cut_retry_backup" not in p.name)
        if not all_java:
            print("[cut-retry] no source files to compile")
            return {}

        # Compile to scratch_bin
        compile_cmd = ["javac", "-cp", classpath, "-d", str(scratch_bin), *all_java]
        with open(compile_output, "a", encoding="utf-8") as log:
            log.write(f"\n--- [cut-retry compile for CUT={cut_fqcn}] ---\n")
            r = subprocess.run(compile_cmd, stdout=log, stderr=log, check=False)
        if r.returncode != 0:
            print(f"[cut-retry] compile failed for CUT={cut_fqcn}; see {compile_output}")
            return {}

        # Run tests against the scratch bin
        retry_classpath = _rewrite_classpath_bin_main(classpath, bin_main, scratch_bin)
        retry_reports = scratch_root / f"reports_cut_{cut_simple}"
        shutil.rmtree(retry_reports, ignore_errors=True)
        retry_reports.mkdir(parents=True, exist_ok=True)
        run_tests_batch(tests_in_group, retry_classpath, retry_reports)

        # Compare and keep improvements
        improved: dict[str, dict] = {}
        for test_fqcn in tests_in_group:
            rd = retry_reports / test_fqcn.replace(".", "_")
            xml = xml_report_in(rd)
            if xml is None:
                continue
            new_result = result_from_xml(xml)
            old_result = pass1_results.get(test_fqcn, {"passed": 0, "total": 0})
            if new_result["passed"] > old_result["passed"]:
                # Overwrite the final per-class text output
                final_txt = results_dir / (test_fqcn.replace(".", "_") + ".txt")
                # Keep a copy of the pass1 output for auditability
                if final_txt.exists():
                    shutil.copy2(final_txt, final_txt.with_suffix(".orig.txt"))
                write_parser_text(final_txt, test_fqcn, xml)
                # Also move the XML into the canonical reports location
                final_report_dir = reports_root / test_fqcn.replace(".", "_")
                final_report_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(xml, final_report_dir / xml.name)
                improved[test_fqcn] = new_result
                print(f"[cut-retry] IMPROVED {test_fqcn}: "
                      f"{old_result['passed']}/{old_result['total']} "
                      f"-> {new_result['passed']}/{new_result['total']}")
        return improved

    finally:
        # Restore source tree
        for target, backup in backups_made:
            if backup is None:
                # File was injected by the defensive step; remove it
                try:
                    target.unlink()
                except FileNotFoundError:
                    pass
            else:
                try:
                    shutil.move(backup, target)
                except OSError:
                    pass
        # Restore original .fallback_used.txt
        try:
            fallback_track_path.write_text(original_track_content, encoding="utf-8")
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", action="append", type=Path,
                        dest="source_dirs", required=True)
    parser.add_argument("--bin-main", type=Path, required=True)
    parser.add_argument("--bin-test", type=Path, required=True)
    parser.add_argument("--fallback-dir", action="append", type=Path,
                        dest="fallback_dirs", required=True)
    parser.add_argument("--test-output-dir", type=Path, required=True)
    parser.add_argument("--classpath", required=True)
    parser.add_argument("--compile-output", type=Path, required=True)
    parser.add_argument("--original-results", type=Path, required=True)
    parser.add_argument("--final-results", type=Path, default=None)
    parser.add_argument("--test-src-dir", type=Path, default=Path("autograder_config/junit_tests"))
    args = parser.parse_args()

    print("=== [run_fallback_test_comparison.py] CUT-based retry ===")

    final_results = args.final_results or args.original_results
    final_results.mkdir(parents=True, exist_ok=True)

    # If final_results differs from originals, seed it so we have a baseline
    if final_results != args.original_results:
        for f in args.original_results.glob("*.txt"):
            dest = final_results / f.name
            if not dest.exists():
                shutil.copy2(f, dest)

    # Framework convention — matches the path FallbackChecker reads.
    fallback_track_path = Path("bin/main/.fallback_used.txt")

    pass1_track = load_pass1_fallback_track(fallback_track_path)
    print(f"[cut-retry] pass-1 fallbacks in effect: {sorted(pass1_track)}")

    # Discover every test class's CUT from the source tree
    test_to_cut = build_test_to_cut_map(args.test_src_dir)
    print(f"[cut-retry] discovered CUT for {len(test_to_cut)} test class(es)")

    # Read pass-1 per-class results
    test_classes = sorted(test_to_cut.keys())
    pass1_results: dict[str, dict] = {}
    for t in test_classes:
        txt = args.original_results / (t.replace(".", "_") + ".txt")
        pass1_results[t] = read_pass1_result(txt)

    # Which tests need a retry?
    retry_candidates: list[str] = []
    for t in test_classes:
        r = pass1_results[t]
        if r["total"] == 0:
            # Either no tests or parse failed; skip (nothing to compare).
            continue
        if r["passed"] < r["total"]:
            retry_candidates.append(t)

    if not retry_candidates:
        print("[cut-retry] every test that ran passed fully in pass 1 — nothing to do")
        print("=== [run_fallback_test_comparison.py] done ===")
        return

    # Group by CUT
    by_cut: dict[str, list[str]] = {}
    for t in retry_candidates:
        by_cut.setdefault(test_to_cut[t], []).append(t)

    print(f"[cut-retry] {len(retry_candidates)} test(s) grouped into "
          f"{len(by_cut)} CUT group(s)")

    reports_root = args.original_results / "_junit_xml"
    scratch_root = Path("./bin/_cut_retry_scratch")
    shutil.rmtree(scratch_root, ignore_errors=True)
    scratch_root.mkdir(parents=True, exist_ok=True)

    total_improved: dict[str, dict] = {}
    for cut_fqcn, tests in by_cut.items():
        improved = perform_cut_retry_for_group(
            cut_fqcn=cut_fqcn,
            tests_in_group=tests,
            source_dirs=args.source_dirs,
            fallback_dirs=args.fallback_dirs,
            bin_main=args.bin_main,
            bin_test=args.bin_test,
            classpath=args.classpath,
            compile_output=args.compile_output,
            pass1_fallback_track=pass1_track,
            fallback_track_path=fallback_track_path,
            scratch_root=scratch_root,
            results_dir=final_results,
            reports_root=reports_root,
            pass1_results=pass1_results,
        )
        total_improved.update(improved)

    print(f"\n[cut-retry] summary: {len(total_improved)} test(s) improved via CUT retry")
    for t, r in total_improved.items():
        print(f"  + {t}: {r['passed']}/{r['total']}")

    # Clean up scratch
    shutil.rmtree(scratch_root, ignore_errors=True)
    print("=== [run_fallback_test_comparison.py] done ===")


if __name__ == "__main__":
    main()
