from __future__ import annotations

import glob
import json
import logging
import os
from pathlib import Path

from . import assert_no_duplicate_test_names
from .gradescope_output.gradescope_txt import extract_tests
from .mark_calculator import calculate_marks
from .mark_scheme_loader import load_mark_scheme
from .mark_scheme_validator import validate_mark_scheme
from .results_formatter import build_results_json
from .subprocess_grep import grep_for_java_comment

from submission_checker.config import EXPECTED_PACKAGE

SOURCE_DIR = 'test-outputs'

log = logging.getLogger()
logging.basicConfig(
    filename='automark.log', encoding='utf-8',
    level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s'
)
log.setLevel(logging.DEBUG)


def _collect_all_results(source_dir: str) -> list[dict]:
    all_results = []
    for file in glob.glob(f'{source_dir}/*Test.txt'):
        all_results.extend(extract_tests(file))
    return all_results


def _find_fixes(source_dir: str) -> list[list[str]]:
    fixes: list[list[str]] = []
    if isinstance(EXPECTED_PACKAGE, str):
        fixes = grep_for_java_comment(
            os.path.join(os.path.dirname(source_dir), EXPECTED_PACKAGE)
        )
    elif isinstance(EXPECTED_PACKAGE, dict):
        dirs = [value.replace('.', os.sep) for value in set(EXPECTED_PACKAGE.values())]
        for package_dir in dirs:
            fixes += grep_for_java_comment(
                os.path.join(os.path.dirname(source_dir), package_dir)
            )
    return fixes


def main() -> None:
    all_results = _collect_all_results(SOURCE_DIR)
    assert_no_duplicate_test_names(all_results)

    scheme = load_mark_scheme()
    validate_mark_scheme(scheme)

    scored = calculate_marks(all_results, scheme)
    fixes = _find_fixes(SOURCE_DIR)
    try:
        results_json = build_results_json(scored, scheme, fixes)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise

    with open('results.json', 'w', encoding='utf-8') as handle:
        json.dump(results_json, handle)

    print(f"results.json written successfully ({len(scored['graded_items'])} items, "
        f"score={scored['total_score']}/{scored['total_max_score']})")
    

if __name__ == '__main__':
    main()
