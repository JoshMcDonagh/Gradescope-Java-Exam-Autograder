from __future__ import annotations

import re
from decimal import Decimal, ROUND_CEILING, localcontext
from typing import Any


# Recognised per-section display modes (see results_display.json ->
# "section_display" and the README). Generalising these replaced the
# previous hard-coded assumption that section 1 was the only visible
# section and that aggregation only ever applied to section 2.
#
#   "detail"  - every test is reported individually and is visible to
#               the student.
#   "summary" - the individual tests are suppressed and replaced by one
#               visible per-question-part aggregate; the raw tests are
#               not shown to the student.
#   "hidden"  - every test is reported individually but kept hidden from
#               the student (instructor-only / debugging view).
SECTION_DISPLAY_MODES = frozenset({'detail', 'summary', 'hidden'})


def _section_tag_for(section_number: Any) -> str:
    return f"section{section_number}"


def _legacy_section_mode(display: dict[str, Any], section_number: Any) -> str:
    """Reproduce the pre-generalisation behaviour for configs that do not
    yet declare a ``section_display`` block.

    Historically per-item visibility was ``visible`` only for section 1,
    and ``show_section_<n>_detail`` toggled between keeping the individual
    (hidden) tests and aggregating them into visible per-question
    summaries.
    """
    show_detail = display.get(f'show_section_{section_number}_detail', True)
    if not show_detail:
        return 'summary'
    return 'detail' if str(section_number) == '1' else 'hidden'


def resolve_section_mode(display: dict[str, Any], section_number: Any) -> str:
    """Return the display mode for a section.

    When a ``section_display`` block is present it is authoritative;
    otherwise the legacy ``show_section_<n>_detail`` keys are honoured so
    that older configs keep working unchanged.
    """
    config = display.get('section_display')
    if isinstance(config, dict):
        modes = config.get('modes', {}) or {}
        mode = modes.get(
            _section_tag_for(section_number),
            config.get('default_mode', 'detail'),
        )
        if mode not in SECTION_DISPLAY_MODES:
            raise ValueError(
                f"Unknown section display mode {mode!r} for "
                f"{_section_tag_for(section_number)}; expected one of "
                f"{sorted(SECTION_DISPLAY_MODES)}"
            )
        return mode
    return _legacy_section_mode(display, section_number)


def _visibility_for_mode(mode: str) -> str:
    """Per-item Gradescope visibility implied by a section mode.

    Only ``detail`` exposes the individual tests to the student; in
    ``summary`` mode they are replaced by visible per-question aggregates,
    and in ``hidden`` mode they remain instructor-only.
    """
    return 'visible' if mode == 'detail' else 'hidden'


def _question_tag(item: dict[str, Any]) -> str:
    return f"section{item['section_number']}.question{item['question_number']}{item['part_id']}"


def _escape_html(text: str) -> str:
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _build_test_output_text(graded_item: dict[str, Any]) -> str:
    if graded_item['passed']:
        return 'Test passed'
    failures = graded_item['failures']
    if not failures:
        crash_message = graded_item.get('crash_message')
        if crash_message:
            return _escape_html(crash_message)
        return 'No test output found. Possible compilation error?'
    first_failure = failures[0]
    failing_name = first_failure.get('fqn', first_failure.get('name', ''))
    extra = first_failure.get('extra', [])
    parts = [first_failure.get('output', 'Test failed')]
    # if failing_name:
    #     parts.append(f"Failing test: {failing_name}")
    if extra:
        parts.extend(extra if len(extra) > 1 else [extra[0]])
    return _escape_html('\n'.join(str(p) for p in parts))


def graded_item_to_json_obj(
    graded_item: dict[str, Any],
    display: dict[str, Any] | None = None,
) -> dict[str, Any]:
    item = graded_item['item']
    representative = graded_item['representative_result']
    if representative is None:
        package = f"unknown.section{item['section_number']}.question{item['question_number']}"
        class_name = item['bundle_id']
        name = item['bundle_id']
        filename = None
        line_no = None
        extra = []
    else:
        package = representative['package']
        class_name = representative['class_name']
        name = representative['name']
        filename = representative.get('filename')
        line_no = representative.get('line_no')
        extra = representative.get('extra', [])

    # Tag with the test tree's top-level grouping, if the exam uses one
    # (e.g. a structural/functional split). Layouts whose test packages
    # start straight at the section level get no grouping tag.
    # Tag order is deterministic: section first, question second, then the
    # test tree's top-level grouping (e.g. a structural/functional split) if
    # the exam uses one. Layouts whose test packages start straight at the
    # section level get no grouping tag.
    tags = [f"section{item['section_number']}", _question_tag(item)]
    if item['tests']:
        top_level = item['tests'][0].split('.', 1)[0]
        if top_level != f"section{item['section_number']}":
            tags.append(top_level)

    # Use the first failing test name when the bundle failed, otherwise the first test
    if graded_item['passed'] or not graded_item['failures']:
        display_name = item['tests'][0] if item['tests'] else name
    else:
        first_fail = graded_item['failures'][0]
        display_name = first_fail.get('fqn', item['tests'][0] if item['tests'] else name)

    if display is None:
        # Backwards-compatible default for callers that do not pass the
        # display config: historically section 1 was the only visible
        # section.
        visibility = 'visible' if item['section_number'] == 1 else 'hidden'
    else:
        visibility = _visibility_for_mode(
            resolve_section_mode(display, item['section_number'])
        )

    result = {
        'name': display_name,
        'output': _build_test_output_text(graded_item),
        'output_format': 'simple_format',
        'score': float(graded_item['score']),
        'max_score': float(graded_item['max_score']),
        'visibility': visibility,
        'tags': tags,
        'extra_data': {
            'package': package,
            'class_name': class_name,
            'test_name': name,
            'bundle_id': item['bundle_id'],
            'bundle_tests': item['tests'],
            'extra': extra,
        },
    }
    if filename is not None:
        result['extra_data']['filename'] = filename
    if line_no is not None:
        result['extra_data']['line_no'] = line_no
    return result


def _aggregate_question_tests(json_tests: list[dict[str, Any]], section_tag: str) -> list[dict[str, Any]]:
    question_tags = sorted({t['tags'][1] for t in json_tests if t['tags'][0] == section_tag})
    aggregated: list[dict[str, Any]] = []
    for question_tag in question_tags:
        matching = [t for t in json_tests if t['tags'][1] == question_tag]
        aggregated.append({
            # Insert the "questionX.part" separator (per question_label_style)
            # for any question number, e.g. "section2.question5a" ->
            # "section2.question5.a". Previously only question1/question2
            # were handled.
            'name': re.sub(r'(question\d+)(?=\D)', r'\1.', question_tag),
            'output': 'Mark derived from multiple tests',
            'max_score': sum(t['max_score'] for t in matching),
            'score': sum(t['score'] for t in matching),
            'visibility': 'visible',
            'tags': [section_tag, question_tag],
        })
    return aggregated


def _format_ratio(score: Decimal, max_score: Decimal, include_tick: bool, include_percentage: bool) -> str:
    text = f"{score:.2f}/{max_score:.2f}"
    if score == max_score and include_tick:
        return text + ' ✔'
    if score != max_score and include_percentage and max_score != 0:
        return text + ' (~{:.0f}%)'.format(score / max_score * 100)
    return text


def build_results_json(scored: dict[str, Any], scheme: dict[str, Any], fixes_applied: list[list[str]] | None = None) -> dict[str, Any]:
    display = scheme['display']
    json_tests = [graded_item_to_json_obj(item, display) for item in scored['graded_items']]

    # Dynamically discover which sections are present
    section_tags = sorted({t['tags'][0] for t in json_tests})

    # When a "section_display" block is present it is authoritative and the
    # per-section mode decides whether to aggregate. Otherwise we honour the
    # legacy "aggregate_hidden_detail_by_question" master switch, which gates
    # the per-section "show_section_<n>_detail" keys.
    section_display_present = isinstance(display.get('section_display'), dict)
    aggregate = (
        section_display_present
        or display.get('aggregate_hidden_detail_by_question', True)
    )

    if aggregate:
        rebuilt = []
        for section_tag in section_tags:
            section_number = section_tag.replace('section', '')
            mode = resolve_section_mode(display, section_number)
            if mode == 'summary':
                rebuilt.extend(_aggregate_question_tests(json_tests, section_tag))
            else:
                # "detail" and "hidden" both keep the individual tests; their
                # student visibility was already set per-item above.
                rebuilt.extend(t for t in json_tests if t['tags'][0] == section_tag)
        json_tests = rebuilt

    question_parts = sorted({t['tags'][1] for t in json_tests})
    question_part_scores: dict[str, dict[str, str]] = {tag: {} for tag in section_tags}
    for part in question_parts:
        section = part.split('.')[0]
        question_part_score = sum(Decimal(str(t['score'])) for t in json_tests if t['tags'][1] == part)
        question_part_maxscore = sum(Decimal(str(t['max_score'])) for t in json_tests if t['tags'][1] == part)
        question_part_scores[section]['.'.join(part.split('.')[1:])] = _format_ratio(
            question_part_score,
            question_part_maxscore,
            include_tick=display.get('summary_output', {}).get('include_tick_when_full_marks', True),
            include_percentage=display.get('summary_output', {}).get('include_percentage_when_not_full_marks', True),
        )

    section_outputs = []
    for section_tag in section_tags:
        section_score = sum(Decimal(str(t['score'])) for t in json_tests if section_tag in t['tags'])
        section_max = sum(Decimal(str(t['max_score'])) for t in json_tests if section_tag in t['tags'])
        section_outputs.append((section_tag, _format_ratio(
            section_score,
            section_max,
            include_tick=display.get('summary_output', {}).get('include_tick_when_full_marks', True),
            include_percentage=display.get('summary_output', {}).get('include_percentage_when_not_full_marks', True),
        )))

    output_lines = []
    if display.get('summary_output', {}).get('include_section_totals', True):
        for section_tag, section_summary in section_outputs:
            output_lines.append(f"=== {section_tag.replace('section', 'Section ')}:    {section_summary} ===")
            if display.get('summary_output', {}).get('include_question_totals', True):
                for key, value in question_part_scores[section_tag].items():
                    output_lines.append(key.replace('question', 'Question ') + ': ' + value)
            output_lines.append('')
    if fixes_applied:
        output_lines.append('Above mark is PROVISIONAL and will be reduced due to fixes applied by autograder')
        for file, lineno, fix in fixes_applied:
            _, fix_comment = [fragment.strip() for fragment in fix.rsplit('//', 1)]
            output_lines.append(f"	{fix_comment} ({file}:{lineno})")

    with localcontext() as ctx:
        ctx.prec = 4
        ctx.rounding = ROUND_CEILING
        result = {
            'output': '\n'.join(line for line in output_lines).strip(),
            'score': float(scored['total_score']),
            'max_score': float(scored['total_max_score']),
            'tests': json_tests,
        }
        if fixes_applied:
            result['extra_data'] = {'fixes': len(fixes_applied)}
        return result
