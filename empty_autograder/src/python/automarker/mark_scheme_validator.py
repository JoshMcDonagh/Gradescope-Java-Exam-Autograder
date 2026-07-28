from __future__ import annotations

import math
from collections import Counter
from decimal import Decimal
from typing import Any

from .results_formatter import SECTION_DISPLAY_MODES


class MarkSchemeValidationError(ValueError):
    pass


def _require_keys(data: dict[str, Any], keys: list[str], context: str) -> None:
    missing = [key for key in keys if key not in data]
    if missing:
        raise MarkSchemeValidationError(f"Missing required keys in {context}: {', '.join(missing)}")


def _validate_section_display(display: dict[str, Any]) -> None:
    """Validate the optional ``section_display`` block in results_display.json.

    Absent block -> nothing to check (legacy ``show_section_<n>_detail`` keys
    are tolerated). When present, every declared mode must be recognised.
    """
    config = display.get('section_display')
    if config is None:
        return
    if not isinstance(config, dict):
        raise MarkSchemeValidationError("'section_display' must be an object")

    modes = config.get('modes', {})
    if not isinstance(modes, dict):
        raise MarkSchemeValidationError("'section_display.modes' must be an object")

    declared = {'default_mode': config.get('default_mode', 'detail')}
    declared.update(modes)
    for where, mode in declared.items():
        if mode not in SECTION_DISPLAY_MODES:
            raise MarkSchemeValidationError(
                f"Invalid section display mode {mode!r} for {where}; "
                f"expected one of {sorted(SECTION_DISPLAY_MODES)}"
            )


def validate_mark_scheme(scheme: dict[str, Any]) -> None:
    _require_keys(scheme, ['total_marks', 'sections', 'items', 'display'], 'scheme root')

    _validate_section_display(scheme['display'])

    section_ids = []
    question_keys = []
    bundle_ids = []
    all_tests = []

    overall_total = Decimal('0')
    for section in scheme['sections']:
        _require_keys(section, ['section_id', 'section_number', 'title', 'total_marks', 'questions'], f"section {section}")
        section_ids.append(section['section_id'])
        section_total = Decimal('0')
        for question in section['questions']:
            _require_keys(question, ['section_id', 'question_id', 'question_number', 'total_marks', 'parts'], f"question {question}")
            question_keys.append((question['section_id'], question['question_id']))
            question_total = Decimal('0')
            for part in question['parts']:
                _require_keys(part, ['part_id', 'total_marks', 'bundles'], f"part {part}")
                part_total = Decimal('0')
                for bundle in part['bundles']:
                    _require_keys(bundle, ['bundle_id', 'bundle_number', 'marks', 'tests'], f"bundle {bundle}")
                    bundle_ids.append((question['section_id'], question['question_id'], part['part_id'], bundle['bundle_id']))
                    if not isinstance(bundle['tests'], list) or not bundle['tests']:
                        raise MarkSchemeValidationError(f"Bundle {bundle['bundle_id']} must contain a non-empty test list")
                    if bundle.get('scoring', 'all_or_nothing') != 'all_or_nothing':
                        raise MarkSchemeValidationError(f"Unsupported scoring mode in bundle {bundle['bundle_id']}: {bundle.get('scoring')}")
                    for test_name in bundle['tests']:
                        if not isinstance(test_name, str):
                            raise MarkSchemeValidationError(f"Non-string test name found in bundle {bundle['bundle_id']}")
                        all_tests.append(test_name)
                    part_total += Decimal(str(bundle['marks']))
                declared_part_total = Decimal(str(part['total_marks']))
                if not math.isclose(float(part_total), float(declared_part_total), rel_tol=1e-9, abs_tol=1e-9):
                    raise MarkSchemeValidationError(
                        f"Part total mismatch for {question['section_id']}.{question['question_id']}.{part['part_id']}: declared {declared_part_total}, calculated {part_total}"
                    )
                question_total += part_total
            declared_question_total = Decimal(str(question['total_marks']))
            if not math.isclose(float(question_total), float(declared_question_total), rel_tol=1e-9, abs_tol=1e-9):
                raise MarkSchemeValidationError(
                    f"Question total mismatch for {question['section_id']}.{question['question_id']}: declared {declared_question_total}, calculated {question_total}"
                )
            section_total += question_total
        declared_section_total = Decimal(str(section['total_marks']))
        if not math.isclose(float(section_total), float(declared_section_total), rel_tol=1e-9, abs_tol=1e-9):
            raise MarkSchemeValidationError(
                f"Section total mismatch for {section['section_id']}: declared {declared_section_total}, calculated {section_total}"
            )
        overall_total += section_total

    declared_overall_total = Decimal(str(scheme['total_marks']))
    if not math.isclose(float(overall_total), float(declared_overall_total), rel_tol=1e-9, abs_tol=1e-9):
        raise MarkSchemeValidationError(
            f"Overall total mismatch: declared {declared_overall_total}, calculated {overall_total}"
        )

    for name, values in {
        'section ids': section_ids,
        'question ids': question_keys,
        'bundle ids': bundle_ids,
    }.items():
        duplicates = [item for item, count in Counter(values).items() if count > 1]
        if duplicates:
            raise MarkSchemeValidationError(f"Duplicate {name} found: {duplicates}")
