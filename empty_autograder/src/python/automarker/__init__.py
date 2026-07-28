from __future__ import annotations

from typing import Any, Iterable


def assert_no_duplicate_test_names(all_results: list[dict[str, Any]]) -> None:
    all_test_names = {
        result.get('fqn') or result.get('name')
        for result in all_results
    }
    assert len(all_results) == len(all_test_names)


def match_tests_to_scheme_items(
    all_results: list[dict[str, Any]],
    scheme_items: Iterable[dict[str, Any]],
) -> tuple[list[tuple[dict[str, Any], list[tuple[str, dict[str, Any] | None]]]], list[dict[str, Any]]]:
    remaining = list(range(len(all_results)))
    all_test_names = [result.get('fqn') or result.get('name') for result in all_results]
    matched: list[tuple[dict[str, Any], list[tuple[str, dict[str, Any] | None]]]] = []

    for item in scheme_items:
        expected_tests = item['tests']
        item_matches: list[tuple[str, dict[str, Any] | None]] = []
        for expected_test in expected_tests:
            try:
                idx = all_test_names.index(expected_test)
                result = all_results[idx]
                if idx in remaining:
                    remaining.remove(idx)
                item_matches.append((expected_test, result))
            except ValueError:
                item_matches.append((expected_test, None))
        matched.append((item, item_matches))

    extra = [all_results[idx] for idx in remaining]
    return matched, extra


def count_expected_tests_not_found(
    all_results: list[dict[str, Any]],
    scheme_items: Iterable[dict[str, Any]],
) -> int:
    matched, _ = match_tests_to_scheme_items(all_results, scheme_items)
    return sum(1 for _, item_matches in matched for _, result in item_matches if result is None)


def count_extra_tests(
    all_results: list[dict[str, Any]],
    scheme_items: Iterable[dict[str, Any]],
) -> int:
    _, extra = match_tests_to_scheme_items(all_results, scheme_items)
    return len(extra)
