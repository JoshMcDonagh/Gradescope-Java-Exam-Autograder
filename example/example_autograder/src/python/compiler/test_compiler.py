import argparse
from pathlib import Path
import subprocess
import sys

def compile_java_files(java_files, classpath: str, output_dir: Path, log_file: Path):
    if not java_files:
        print("[WARNING] No Java files found to compile.")
        return

    javac_cmd = [
        "javac",
        "-cp", classpath,
        "-d", str(output_dir),
        *[str(f) for f in java_files]
    ]

    print(f"[INFO] Compiling {len(java_files)} Java file(s)...")
    print(f"[DEBUG] javac command: {' '.join(javac_cmd)}")

    with open(log_file, 'a') as log:
        subprocess.run(javac_cmd, stdout=log, stderr=log)

def main():
    parser = argparse.ArgumentParser(description="Compile Java unit tests and optional helpers.")
    parser.add_argument("--test-dir", required=True, type=Path,
                        help="Directory containing test .java files (recursively scanned)")
    parser.add_argument("--output-dir", required=True, type=Path,
                        help="Directory to place compiled .class files")
    parser.add_argument("--classpath", required=True,
                        help="Classpath string to pass to javac")
    parser.add_argument("--log-file", default="test_compile_output.txt", type=Path,
                        help="File to log compilation output")
    parser.add_argument("--helper-dir", type=Path, action="append", default=None,
                        help="Helper source root(s), compiled in order before the tests. "
                            "Defaults to src/java (framework helpers) then "
                            "autograder_config/helpers (exam-specific helpers).")

    args = parser.parse_args()

    print("=== [test_compiler.py] Starting test compilation ===")

    # Compile the helper sources first — the framework helpers under src/java,
    # then the exam kit's helpers under autograder_config/helpers — so the
    # tests can resolve them from the compiled classpath. Each directory is
    # compiled in a single javac invocation, so inter-helper dependencies
    # resolve regardless of file order. A missing directory is skipped
    # silently (an exam with no bespoke helpers is perfectly valid).
    helper_dirs = args.helper_dir or [Path("src/java"), Path("autograder_config/helpers")]
    for hd in helper_dirs:
        if hd.is_dir():
            files = sorted(hd.rglob("*.java"))
            if files:
                compile_java_files(files, args.classpath, args.output_dir, args.log_file)

    # Compile all test Java files
    
    # After finding all test files:
    test_java_files = list(args.test_dir.rglob("*.java"))

    # Group by top-level directory under test_dir
    from collections import defaultdict
    groups = defaultdict(list)
    for f in test_java_files:
        rel = f.relative_to(args.test_dir)
        top = rel.parts[0]  # whatever top-level dirs the exam kit uses, e.g. "functional"/"structural"
        groups[top].append(f)

    # Compile each group independently
    for group_name in sorted(groups):
        compile_java_files(groups[group_name], args.classpath, args.output_dir, args.log_file)

    print("=== [test_compiler.py] Done ===")

if __name__ == "__main__":
    main()
