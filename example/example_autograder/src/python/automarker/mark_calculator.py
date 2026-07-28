from __future__ import annotations

from decimal import Decimal
from typing import Any

from . import match_tests_to_scheme_items


class TestMatchingError(ValueError):
    pass


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
    missing = [test_name for _, item_matches in matched_items for test_name, result in item_matches if result is None]

    if missing:
        import logging
        log = logging.getLogger(__name__)
        log.warning(
            'Test output expected based on mark scheme but not found (treating as failed):\n'
            + '\n'.join(f'    {name}' for name in missing)
        )

    if extra_results:
        extra_text = '\n'.join(
            f"    {result.get('fqn', result.get('name'))}" for result in extra_results
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

        graded_items.append({
            'item': item,
            'matches': item_matches,
            'passed': passed,
            'representative_result': representative,
            'failures': failures,
            'score': score,
            'max_score': max_score,
        })

    return {
        'graded_items': graded_items,
        'total_score': total_score,
        'total_max_score': total_max,
        'extra_results': extra_results,
    }
