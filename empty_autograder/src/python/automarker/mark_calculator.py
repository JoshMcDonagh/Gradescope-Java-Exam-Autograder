from __future__ import annotations

from decimal import Decimal
from typing import Any

from . import match_tests_to_scheme_items


class TestMatchingError(ValueError):
    pass


# Method name used by BatchTestRunner's synthetic report when a whole test
# class fails to run (timeout, out-of-memory, non-terminating student code,
# or any other runner-level throwable). These markers are produced at grading
# time by a student's submission, so they must never be treated as mark-scheme
# drift: a single crashed class should cost only the marks for that class, not
# abort the whole submission.
CLASS_LEVEL_ERROR_METHOD = 'classLevelError'


def _test_identifier(result: dict[str, Any]) -> str:
    return result.get('fqn') or result.get('name') or ''


def _is_class_level_error(result: dict[str, Any]) -> bool:
    return _test_identifier(result).rsplit('.', 1)[-1] == CLASS_LEVEL_ERROR_METHOD


def _crashed_class_fqn(result: dict[str, Any]) -> str:
    """The fully-qualified test class for a class-level error marker, i.e. the
    identifier with the trailing ``.classLevelError`` removed."""
    identifier = _test_identifier(result)
    suffix = '.' + CLASS_LEVEL_ERROR_METHOD
    return identifier[: -len(suffix)] if identifier.endswith(suffix) else identifier


def _class_of_test(test_name: str) -> str:
    """The fully-qualified test class of a scheme test name, i.e. everything
    up to (but excluding) the final ``.methodName`` component."""
    return test_name.rsplit('.', 1)[0] if '.' in test_name else test_name


def _class_error_message(result: dict[str, Any]) -> str:
    """A student-facing explanation for a class-level crash, appending the
    specific runner reason (e.g. an OutOfMemoryError) when one was captured."""
    base = (
        'Test could not be run to completion.'
    )
    reason = ' '.join(str(line).strip() for line in result.get('extra', []) if str(line).strip())
    return f'{base}\n{reason}' if reason else base


def flatten_mark_breakdown(scheme: dict[str, Any]) -> list[tuple[str, Decimal]]:
    breakdown: list[tuple[str, Decimal]] = []
    for item in scheme['items']:
        mark = Decimal(str(item['marks']))
        test_count = Decimal(len(item['tests']))
        for test_name in item['tests']:
            breakdown.append((test_name, mark / test_count))
    return breakdown


def validate_test_matching(
    matched_items: list[tuple[dict[str, Any], list[tuple[str, dict[str, Any] | None]]]],
    extra_results: list[dict[str, Any]],
) -> None:
    import logging
    log = logging.getLogger(__name__)

    missing = [test_name for _, item_matches in matched_items for test_name, result in item_matches if result is None]

    if missing:
        log.warning(
            'Test output expected based on mark scheme but not found (treating as failed):\n'
            + '\n'.join(f'    {name}' for name in missing)
        )

    # Class-level crash markers are an expected runtime outcome for a broken
    # submission, not a mark-scheme mismatch. They are logged and left to score
    # zero for the affected class; they must not abort marking of everything
    # else. Only genuine unmatched output (a real test method the scheme does
    # not know about) indicates an authoring error worth failing on.
    class_level_errors = [r for r in extra_results if _is_class_level_error(r)]
    genuine_extras = [r for r in extra_results if not _is_class_level_error(r)]

    if class_level_errors:
        log.warning(
            'Test class(es) crashed at class level (timeout / out of memory / '
            'non-terminating code); their tests are scored as failed:\n'
            + '\n'.join(f'    {_crashed_class_fqn(r)}' for r in class_level_errors)
        )

    if genuine_extras:
        extra_text = '\n'.join(
            f"    {result.get('fqn', result.get('name'))}" for result in genuine_extras
        )
        raise TestMatchingError(
            'Test output found and not matched to mark scheme:\n' + extra_text
        )


def calculate_marks(
    all_results: list[dict[str, Any]],
    scheme: dict[str, Any],
) -> dict[str, Any]:
    matched_items, extra_results = match_tests_to_scheme_items(all_results, scheme['items'])
    validate_test_matching(matched_items, extra_results)

    # Map each crashed test class to a student-facing explanation, so an item
    # that scored zero purely because its test class crashed can say so rather
    # than reporting the generic "possible compilation error" fallback.
    crashed_classes = {
        _crashed_class_fqn(r): _class_error_message(r)
        for r in extra_results if _is_class_level_error(r)
    }

    graded_items: list[dict[str, Any]] = []
    total_score = Decimal('0')
    total_max = Decimal('0')

    for item, item_matches in matched_items:
        max_score = Decimal(str(item['marks']))
        total_max += max_score

        passed = all(result is not None and result.get('output') == 'Test passed' for _, result in item_matches)
        score = max_score if passed else Decimal('0')
        total_score += score

        representative = next((result for _, result in item_matches if result is not None), None)
        failures = []
        for _, result in item_matches:
            if result is not None and result.get('output') != 'Test passed':
                failures.append(result)

        # When every expected test for this item is missing and the item's test
        # class crashed, surface the crash reason.
        crash_message = None
        if not passed and representative is None:
            item_classes = {_class_of_test(name) for name in item['tests']}
            crash_message = next(
                (crashed_classes[cls] for cls in item_classes if cls in crashed_classes),
                None,
            )

        graded_items.append({
            'item': item,
            'matches': item_matches,
            'passed': passed,
            'representative_result': representative,
            'failures': failures,
            'score': score,
            'max_score': max_score,
            'crash_message': crash_message,
        })

    return {
        'graded_items': graded_items,
        'total_score': total_score,
        'total_max_score': total_max,
        'extra_results': extra_results,
    }
