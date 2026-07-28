import itertools
import logging
import os
import pathlib

from .config import (
    EXPECTED_PACKAGE,
    EXPECTED_PACKAGE_STATEMENT,
    SKIP_DIRS,
    SKIP_FILES,
    init_logging,
    rule_enabled
)
from .rewrite import insert_at_start, rewrite_line

init_logging()


def _get_expected_package_dirs(path: str):
    """
    Return a list of absolute package directories expected to exist.
    """
    if isinstance(EXPECTED_PACKAGE, str):
        return [os.path.join(path, EXPECTED_PACKAGE.replace(".", os.sep))]

    return sorted(set(
        os.path.join(path, package_name.replace(".", os.sep))
        for package_name in EXPECTED_PACKAGE.values()
    ))


def _get_expected_top_level_dirs():
    """
    Return the set of top-level directories that are valid in the submission root.
    """
    expected_dirs = set(SKIP_DIRS)

    if isinstance(EXPECTED_PACKAGE, str):
        expected_dirs.add(EXPECTED_PACKAGE.split(".")[0])
    elif isinstance(EXPECTED_PACKAGE, dict):
        expected_dirs.update(
            package_name.split(".")[0]
            for package_name in EXPECTED_PACKAGE.values()
        )
    else:
        expected_dirs.update(EXPECTED_PACKAGE)

    return expected_dirs


def _class_name_from_filename(filename: str) -> str:
    if filename.lower().endswith(".java"):
        return filename[:-5]
    return filename


def _destination_for_top_level_file(root_path: str, filename: str) -> str:
    class_name = _class_name_from_filename(filename)

    if isinstance(EXPECTED_PACKAGE, dict) and class_name in EXPECTED_PACKAGE:
        package_name = EXPECTED_PACKAGE[class_name]
        return os.path.join(root_path, package_name.replace(".", os.sep), filename)

    package_dirs = _get_expected_package_dirs(root_path)
    return os.path.join(package_dirs[0], filename)


def fix_directory_structure(path, submission_id=None):
    changed = False

    if not submission_id:
        submission_id = os.path.basename(path)

    expected_package_dirs = _get_expected_package_dirs(path)
    expected_top_level_dirs = _get_expected_top_level_dirs()

    unexpected_subdirs = [
        os.path.abspath(f.path)
        for f in os.scandir(path)
        if (
            f.is_dir()
            and os.path.basename(f) not in expected_top_level_dirs
            and os.path.basename(f) != f"{submission_id}_orig"
        )
    ]

    if rule_enabled("move_misplaced_subpackage_dirs", True) and isinstance(EXPECTED_PACKAGE, dict):
        package_subdirs = [
            tuple(package_name.split(".")[0:2])
            for package_name in EXPECTED_PACKAGE.values()
            if "." in package_name
        ]
        package_subdirs.sort()
        package_subdirs = list(
            package_subdir for package_subdir, _ in itertools.groupby(package_subdirs)
        )

        misplaced_subdirs = []

        for f in os.scandir(path):
            if not f.is_dir() or os.path.basename(f) == f"{submission_id}_orig":
                continue

            for top_level_package, subpackage in package_subdirs:
                if os.path.basename(f.path) == subpackage:
                    correct_subdir = os.path.join(path, top_level_package, subpackage)

                    if not os.path.exists(correct_subdir):
                        changed = True
                        os.makedirs(correct_subdir)

                    misplaced_subdirs.append((f.path, correct_subdir))

        for misplaced_subdir, correct_subdir in misplaced_subdirs:
            for misplaced_file in os.scandir(misplaced_subdir):
                if misplaced_file.is_file():
                    expected_file = os.path.join(
                        correct_subdir,
                        os.path.basename(misplaced_file.path)
                    )

                    if not os.path.exists(expected_file):
                        changed = True
                        logging.debug(
                            "Moving misplaced subpackage file: src=%s, dest=%s",
                            misplaced_file.path,
                            expected_file
                        )
                        os.rename(misplaced_file.path, expected_file)
                    else:
                        logging.warning(
                            "Did not move %s to %s as destination already exists",
                            misplaced_file.path,
                            expected_file
                        )

            if not os.listdir(misplaced_subdir):
                changed = True
                os.rmdir(misplaced_subdir)
                try:
                    unexpected_subdirs.remove(os.path.abspath(misplaced_subdir))
                except ValueError:
                    pass

    if (
        rule_enabled("rename_single_unexpected_top_level_dir", True)
        and len(unexpected_subdirs) == 1
        and len(expected_package_dirs) == 1
    ):
        src = unexpected_subdirs[0]
        dest = expected_package_dirs[0]

        if not os.path.exists(dest):
            changed = True
            logging.info(
                "Submission %s has incorrectly named subdirectory...", submission_id
            )
            logging.info("    Renaming directory: src=%s, dest=%s", src, dest)
            os.rename(src, dest)

    if rule_enabled("create_missing_package_dirs", True):
        for package_dir in expected_package_dirs:
            if not os.path.exists(package_dir):
                changed = True
                logging.info(
                    "Submission %s has no %s directory...",
                    submission_id,
                    package_dir
                )
                logging.info("    Creating directory: %s", package_dir)
                os.makedirs(package_dir)

    if rule_enabled("append_java_extension_to_extensionless_files", True):
        for file in get_files(path):
            if "." not in os.path.basename(file)[-5:]:
                changed = True
                dest = f"{file}.java"
                logging.info("    Moving file: src=%s, dest=%s", file, dest)
                os.rename(file, dest)

    if rule_enabled("capitalise_java_filenames", True):
        for file in get_files(path):
            basename = os.path.basename(file)
            if basename.endswith(".java") and not basename[0].isupper():
                changed = True
                dest = os.path.join(
                    os.path.dirname(file),
                    basename[0].upper() + basename[1:]
                )
                logging.info("    Moving file: src=%s, dest=%s", file, dest)
                os.rename(file, dest)

    if rule_enabled("move_loose_java_files", True):
        unexpected_files_at_top_level_dir = [
            f.path
            for f in os.scandir(path)
            if f.is_file() and os.path.basename(f.path) not in SKIP_FILES
        ]

        for file in unexpected_files_at_top_level_dir:
            filename = os.path.basename(file)
            dest = _destination_for_top_level_file(path, filename)

            if os.path.exists(dest):
                logging.warning(
                    "    Cannot move file because destination exists: src=%s, dest=%s",
                    file,
                    dest
                )
            else:
                changed = True
                logging.info("    Moving file: src=%s, dest=%s", file, dest)
                os.rename(file, dest)

    return changed


def fix_one(path, submission_id=None):
    if rule_enabled("remove_class_files", True):
        remove_class_files(path, submission_id)

    fix_directory_structure(path, submission_id)

    if rule_enabled("fix_package_statements", True):
        fix_package_statements(path, submission_id)


def fix_package_statements(path, submission_id=None):
    if not submission_id:
        submission_id = os.path.basename(path)

    for file in get_files(path):
        basename = os.path.basename(file)

        if not basename.lower().endswith(".java"):
            logging.warning(
                "Submission %s contains non-java file: %s",
                submission_id,
                file
            )
            continue

        with open(file, "r", encoding="utf-8") as java_src:
            try:
                multiline = False
                first_code_line = ""
                first_code_line_no = 0

                for line_no, line in enumerate(java_src):
                    stripped = line.strip()

                    if not stripped:
                        continue

                    if not multiline:
                        if stripped.startswith("//"):
                            continue
                        elif stripped.startswith("/*"):
                            multiline = True
                            if "*/" in stripped:
                                stripped = stripped.split("*/", 1)[-1].strip()
                                multiline = False
                                if not stripped:
                                    continue
                            else:
                                continue

                    if multiline:
                        if "*/" in stripped:
                            stripped = stripped.split("*/", 1)[-1].strip()
                            multiline = False
                            if not stripped:
                                continue
                        else:
                            continue

                    first_code_line = stripped
                    first_code_line_no = line_no
                    break

                expected_package = EXPECTED_PACKAGE
                if isinstance(EXPECTED_PACKAGE, dict):
                    class_name = basename[:-5]
                    if class_name not in EXPECTED_PACKAGE:
                        continue  # skip files not in the expected set
                    expected_package = EXPECTED_PACKAGE[class_name]

                expected_package_statement = EXPECTED_PACKAGE_STATEMENT.format(
                    expected_package=expected_package
                )

                if first_code_line.rstrip() == expected_package_statement:
                    continue

                if first_code_line.lower().startswith("package"):
                    rewrite_line(
                        file,
                        first_code_line_no,
                        new_line=expected_package_statement,
                        remove_empty_preceding_lines=True
                    )
                else:
                    insert_package_statement(file, expected_package_statement)

            except UnicodeDecodeError:
                logging.error("UnicodeDecodeError when reading %s", file)


def get_files(path):
    rtn = []

    for package_dir in _get_expected_package_dirs(path):
        if os.path.exists(package_dir):
            rtn.extend(
                f.path
                for f in os.scandir(package_dir)
                if f.is_file() and os.path.basename(f.path) not in SKIP_FILES
            )

    return rtn


def insert_package_statement(filepath, new_line=EXPECTED_PACKAGE_STATEMENT):
    insert_at_start(
        filepath,
        new_line,
        comment="Package statement inserted by autograder"
    )


def remove_class_files(path, submission_id=None):
    if not submission_id:
        submission_id = os.path.basename(path)

    removed = []
    for file in pathlib.Path(path).rglob("*.class"):
        removed.append(str(file))
        os.remove(file)

    if removed:
        logging.info(
            "Submission %s, removed %d class files: %s",
            submission_id,
            len(removed),
            removed
        )