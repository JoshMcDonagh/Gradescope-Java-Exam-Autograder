from pathlib import Path
import shutil
import re
import os
import argparse
import subprocess


def initial_bulk_compile(source_dir: Path, classpath: str, output_dir: Path, compile_output_path: Path):
    print(f">>> Initial bulk compilation of student files in '{source_dir}'...")
    all_java_files = list(source_dir.rglob("*.java"))
    if not all_java_files:
        print(f"[WARNING] No Java files found in source directory: {source_dir}")
        return

    javac_cmd = [
        "javac",
        "-cp", classpath,
        "-d", str(output_dir),
        "-XDrawDiagnostics",
        *[str(p) for p in all_java_files],
    ]
    print(f"[DEBUG] Running: {' '.join(javac_cmd)}")
    with open(compile_output_path, 'a') as out:
        subprocess.run(javac_cmd, stderr=out)


def recompile_all_sources(source_dir: Path, classpath: str, output_dir: Path, compile_output_path: Path):
    print(f">>> Recompiling all source files after fallbacks for '{source_dir}'...")
    all_java_files = list(source_dir.rglob("*.java"))
    if not all_java_files:
        print(f"[WARNING] No Java files found in source directory (recompile phase): {source_dir}")
        return
    javac_cmd = [
        "javac",
        "-cp", classpath,
        "-d", str(output_dir),
        "-XDrawDiagnostics",
        *[str(p) for p in all_java_files],
    ]
    print(f"[DEBUG] Running: {' '.join(javac_cmd)}")
    with open(compile_output_path, 'a') as out:
        subprocess.run(javac_cmd, stdout=out, stderr=out)


def _rel_path_for_source_root(rel_from_fallback: Path, source_dir: Path) -> Path:
    if rel_from_fallback.parts and rel_from_fallback.parts[0] == source_dir.name:
        return Path(*rel_from_fallback.parts[1:])
    return rel_from_fallback


def detect_missing_files(source_dir: Path, fallback_dirs: list[Path], missing_log: Path):
    print(f">>> Checking for missing files in '{source_dir}'...")
    missing_files = []
    all_fallbacks = []

    for fallback_dir in fallback_dirs:
        for fallback_file in fallback_dir.rglob("*.java"):
            rel_path = fallback_file.relative_to(fallback_dir)
            all_fallbacks.append(rel_path)

            target_rel = _rel_path_for_source_root(rel_path, source_dir)
            target_file = source_dir / target_rel

            print(f"[DEBUG] Checking if exists: {target_file}")
            if not target_file.exists():
                print(f"[MISSING] Using fallback for: {rel_path} -> {target_file}")
                target_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(fallback_file, target_file)
                missing_files.append(str(rel_path))
            else:
                print(f"[DEBUG] Already exists: {rel_path}")

    with open(missing_log, 'a') as f:
        for item in sorted(set(missing_files)):
            f.write(item + "\n")

    # Combined list of all eligible fallbacks (relative to their roots)
    eligible_fallbacks_path = Path("eligible_fallbacks.txt")
    with open(eligible_fallbacks_path, 'w') as f:
        for item in sorted(set(all_fallbacks)):
            f.write(str(item) + "\n")

    print(f"[DEBUG] Total missing files detected in '{source_dir}': {len(set(missing_files))}")
    print(f"[DEBUG] Total eligible fallbacks available: {len(set(all_fallbacks))}")
    return set(missing_files)


def detect_failing_files(compile_output: Path, source_dir: Path):
    print(f">>> Parsing compile output for failing files (root='{source_dir}')...")
    root_cause_files = set()
    src_root = source_dir.resolve()
    src_name = source_dir.name

    with open(compile_output, 'r') as f:
        for raw_line in f:
            line = raw_line.strip()
            match = re.search(r'([A-Za-z0-9_/\\.\-]+\.java):\d+:\d+:', line)
            if match:
                raw_path = match.group(1)
                raw_path_posix = Path(raw_path).as_posix()
                p = Path(raw_path_posix)

                if p.is_absolute():
                    abs_path = p
                else:
                    if p.parts and p.parts[0] == src_name:
                        abs_path = (src_root.parent / p).resolve()
                    else:
                        abs_path = (src_root / p).resolve()

                # javac -XDrawDiagnostics may normalise the source path based on
                # the declared package rather than the actual filesystem location.
                # E.g. bakery/pastries/Pastry.java with 'package bakery;' gets
                # reported as bakery/Pastry.java.  When the resolved path doesn't
                # exist, search for the real file under the source root.
                if not abs_path.exists():
                    filename = abs_path.name
                    candidates = [c.resolve() for c in src_root.rglob(filename)]
                    if len(candidates) == 1:
                        print(f"[DEBUG] Corrected path {abs_path} -> {candidates[0]}")
                        abs_path = candidates[0]
                    elif len(candidates) > 1:
                        print(f"[WARNING] Multiple candidates for {filename}: {candidates}")

                print(f"[COMPILE ERROR] Matched failing file: {abs_path}")
                root_cause_files.add(str(abs_path))
            else:
                print(f"[DEBUG] Unmatched line: {line}")

    print(f"[DEBUG] Total failing files detected for '{source_dir}': {len(root_cause_files)}")
    return set(root_cause_files)


def replace_failing_with_fallbacks(
    failing_files,
    source_dir: Path,
    fallback_dirs: list[Path],
    failing_log: Path,
    output_dir: Path,
    classpath: str,
):
    print(f">>> Replacing failing files with fallbacks (root='{source_dir}')...")
    src_root = source_dir.resolve()
    src_name = source_dir.name

    # --- Phase 1: identify all replaceable files and their fallbacks ---
    replacements = []  # (failing_path, src_path, fallback_path, rel_inside_root)

    for failing in sorted(set(failing_files)):
        failing_path = Path(failing)
        if not failing_path.is_absolute():
            if failing_path.parts and failing_path.parts[0] == src_name:
                failing_path = (src_root.parent / failing_path).resolve()
            else:
                failing_path = (src_root / failing_path).resolve()

        try:
            rel_inside_root = failing_path.relative_to(src_root)
        except ValueError:
            if failing_path.parts and src_name in failing_path.parts:
                idx = failing_path.parts.index(src_name)
                rel_inside_root = Path(*failing_path.parts[idx + 1:])
            else:
                rel_inside_root = Path(failing_path.name) if failing_path.name else Path(failing_path)

        # Search all fallback dirs in order
        fallback_path = None
        for fdir in fallback_dirs:
            candidate = fdir / src_name / rel_inside_root
            if candidate.exists():
                fallback_path = candidate
                break
            candidate = fdir / rel_inside_root
            if candidate.exists():
                fallback_path = candidate
                break

        print(f"[DEBUG] Source file path: {failing_path}")
        print(f"[DEBUG] Looking for fallback: {fallback_path}")

        if fallback_path and fallback_path.exists():
            src_path = src_root / rel_inside_root
            replacements.append((failing_path, src_path, fallback_path, rel_inside_root))
        else:
            print(f"[MISSING] No fallback for {failing_path}")

    if not replacements:
        print("[DEBUG] No replacements to make.")
        print(f"[DEBUG] Total files replaced with validated fallbacks for '{source_dir}': 0")
        return set()

    # --- Phase 2: swap in ALL fallbacks at once, keeping backups ---
    backups = {}  # src_path -> backup_path
    for failing_path, src_path, fallback_path, rel_inside_root in replacements:
        if src_path.exists():
            backup_path = src_path.with_suffix(".student_backup")
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_path, backup_path)
            backups[src_path] = backup_path
            print(f"[DEBUG] Backed up original to: {backup_path}")

        print(f"[REPLACE] Replacing {failing_path} with fallback {fallback_path}.")
        src_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(fallback_path, src_path)

    # --- Phase 2b: remove student files that duplicate a replaced fallback ---
    # A student may have placed e.g. Bakery.java in bakery/stock/
    # with 'package bakery;', clashing with the fallback at bakery/.
    # These won't be in the failing set (javac normalised the path to the
    # fallback location), so they survive replacement and break the batch
    # compile with a duplicate-class error.
    replaced_names = {sp.name for _, sp, _, _ in replacements}
    for java_file in list(source_dir.rglob("*.java")):
        if java_file.name in replaced_names:
            resolved = java_file.resolve()
            # Skip files that ARE one of the replacements
            if any(resolved == sp.resolve() for _, sp, _, _ in replacements):
                continue
            # This is a student file with the same class name at a different
            # path — back it up and remove it so it can't cause a duplicate.
            dup_backup = java_file.with_suffix(".student_backup")
            shutil.copy2(java_file, dup_backup)
            backups[java_file] = dup_backup
            os.remove(java_file)
            print(f"[DEDUP] Removed duplicate student file: {java_file} (backed up)")

    # --- Phase 3: validate the batch by recompiling all sources together ---
    all_java_files = list(source_dir.rglob("*.java"))
    compile_cmd = [
        "javac", "-cp", classpath, "-d", str(output_dir),
        *[str(p) for p in all_java_files],
    ]
    compile_result = subprocess.run(compile_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    replaced_files = []
    if compile_result.returncode == 0:
        print("[VALID] Batch fallback replacement compiled successfully.")
        with open(failing_log, 'a') as f:
            for failing_path, src_path, fallback_path, rel_inside_root in replacements:
                replaced_files.append(str(rel_inside_root))
                f.write(str(rel_inside_root) + "\n")
        # Clean up all backups (replacements + deduped files)
        for bk_path in backups.values():
            if bk_path.exists():
                os.remove(bk_path)
    else:
        print("[INVALID] Batch fallback replacement failed to compile. Reverting all.")
        for src_path, backup_path in backups.items():
            if backup_path.exists():
                shutil.move(backup_path, src_path)
                print(f"[DEBUG] Restored original from: {backup_path}")
            else:
                try:
                    os.remove(src_path)
                except FileNotFoundError:
                    pass

    print(f"[DEBUG] Total files replaced with validated fallbacks for '{source_dir}': {len(set(replaced_files))}")
    return set(replaced_files)


def record_all_fallback_usage(missing_set, replaced_set, track_file: Path):
    print(">>> Recording all fallback usage...")
    all_used = sorted(missing_set.union(replaced_set))
    with open(track_file, 'w') as f:
        for rel_path in all_used:
            classname = Path(rel_path).stem
            print(f"[USED] Fallback class recorded: {classname}")
            f.write(classname + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", action="append", required=True, type=Path,
                        help="Provide once per source root (e.g., --source-dir kingdom --source-dir creatures)")
    parser.add_argument("--fallback-dir", action="append", required=True, type=Path, dest="fallback_dirs")
    parser.add_argument("--compile-output", required=True, type=Path)
    parser.add_argument("--missing-log", required=True, type=Path)
    parser.add_argument("--failing-log", required=True, type=Path)
    parser.add_argument("--track-file", required=True, type=Path)
    parser.add_argument("--classpath", required=True)

    args = parser.parse_args()

    print("=== [student_code_compiler.py] Starting student code compilation ===")

    source_dirs = [p if isinstance(p, Path) else Path(p) for p in (args.source_dir or [])]
    fallback_dirs = [p if isinstance(p, Path) else Path(p) for p in (args.fallback_dirs or [])]

    for pth in (args.compile_output, args.missing_log, args.failing_log):
        pth.parent.mkdir(parents=True, exist_ok=True)
        with open(pth, 'w'):
            pass

    bin_main_dir = Path("./bin/main")

    # 1) Initial compile per root
    for sd in source_dirs:
        initial_bulk_compile(sd, args.classpath, bin_main_dir, args.compile_output)

    # 2) Fill in missing via fallbacks (per root)
    missing_files = set()
    for sd in source_dirs:
        missing_files |= detect_missing_files(sd, fallback_dirs, args.missing_log)

    # 3) Clear stale compile output before recompiling, so that errors from
    #    the initial (pre-fallback) compile don't contaminate the failing-file
    #    detection in step 4.
    with open(args.compile_output, 'w'):
        pass

    # 3) Recompile after pulling in missing
    for sd in source_dirs:
        recompile_all_sources(sd, args.classpath, bin_main_dir, args.compile_output)

    # 4) Parse failing files across all roots
    failing_files = set()
    for sd in source_dirs:
        failing_files |= detect_failing_files(args.compile_output, sd)

    # 5) Replace failing with validated fallbacks (per root)
    replaced_files = set()
    for sd in source_dirs:
        replaced_files |= replace_failing_with_fallbacks(
            failing_files, sd, fallback_dirs, args.failing_log, bin_main_dir, args.classpath
        )

    # 6) Record usage
    record_all_fallback_usage(missing_files, replaced_files, args.track_file)

    print("=== [student_code_compiler.py] Done ===")


if __name__ == "__main__":
    main()
