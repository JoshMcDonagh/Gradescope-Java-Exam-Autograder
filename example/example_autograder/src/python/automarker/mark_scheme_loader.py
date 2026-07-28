from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class MarkSchemeLoadError(RuntimeError):
    pass


def _get_autograder_root() -> Path:
    """
    Walk upwards until we find the autograder root, identified by run_autograder.
    """
    current = Path(__file__).resolve()

    for parent in [current.parent] + list(current.parents):
        if (parent / 'run_autograder').exists():
            return parent

    raise MarkSchemeLoadError(
        'Could not locate autograder root containing run_autograder'
    )


def _load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open('r', encoding='utf-8') as handle:
            data = json.load(handle)
    except FileNotFoundError as exc:
        raise MarkSchemeLoadError(f'Mark scheme file not found: {path}') from exc
    except json.JSONDecodeError as exc:
        raise MarkSchemeLoadError(f'Invalid JSON in {path}: {exc}') from exc

    if not isinstance(data, dict):
        raise MarkSchemeLoadError(
            f'Expected JSON object in {path}, got: {type(data).__name__}'
        )

    return data


def _get_mark_allocation_root(mark_allocation_root: str | Path | None = None) -> Path:
    if mark_allocation_root is not None:
        return Path(mark_allocation_root)

    autograder_root = _get_autograder_root()
    return autograder_root / 'autograder_config' / 'mark_allocation'


def load_results_display(mark_allocation_root: str | Path | None = None) -> dict[str, Any]:
    root = _get_mark_allocation_root(mark_allocation_root)
    return _load_json(root / 'results_display.json')


def load_mark_scheme(mark_allocation_root: str | Path | None = None) -> dict[str, Any]:
    root = _get_mark_allocation_root(mark_allocation_root)

    manifest = _load_json(root / 'mark_scheme_manifest.json')

    scheme_dir = root / 'mark_scheme'
    display = load_results_display(root)

    sections: list[dict[str, Any]] = []
    for section_entry in manifest.get('sections', []):
        if not isinstance(section_entry, str):
            raise MarkSchemeLoadError(
                f"Invalid section entry in mark_scheme_manifest.json: "
                f"expected string, got {type(section_entry).__name__}"
            )

        section_name = Path(section_entry).stem
        section_file = scheme_dir / section_name / 'section_manifest.json'
        section_data = _load_json(section_file)

        questions: list[dict[str, Any]] = []
        for question_manifest in section_data.get('questions', []):
            if not isinstance(question_manifest, dict):
                raise MarkSchemeLoadError(
                    f"Invalid question entry in section file {section_file}: "
                    f"expected object, got {type(question_manifest).__name__}"
                )

            try:
                question_file = question_manifest['file']
            except KeyError as exc:
                raise MarkSchemeLoadError(
                    f"Question manifest entry missing 'file' in {section_file}: "
                    f"{question_manifest}"
                ) from exc

            question_path = scheme_dir / question_file
            question_data = _load_json(question_path)
            questions.append(question_data)

        sections.append(section_data | {'questions': questions})

    flat_items: list[dict[str, Any]] = []
    for section in sections:
        for question in section['questions']:
            for part in question.get('parts', []):
                for bundle in part.get('bundles', []):
                    flat_items.append({
                        'section_id': section['section_id'],
                        'section_number': section['section_number'],
                        'section_title': section['title'],
                        'question_id': question['question_id'],
                        'question_number': question['question_number'],
                        'question_title': question.get(
                            'title',
                            f"Question {question['question_number']}"
                        ),
                        'part_id': part['part_id'],
                        'part_title': part.get('title', f"Part {part['part_id']}"),
                        'bundle_id': bundle['bundle_id'],
                        'bundle_number': bundle['bundle_number'],
                        'marks': bundle['marks'],
                        'tests': bundle['tests'],
                        'scoring': bundle.get(
                            'scoring',
                            manifest.get('scoring_defaults', {}).get(
                                'bundle_scoring',
                                'all_or_nothing'
                            )
                        ),
                    })

    return {
        'assessment': manifest.get('assessment', 'gradescope_autograder'),
        'total_marks': manifest['total_marks'],
        'mark_allocation_root': str(root),
        'display': display,
        'manifest': manifest,
        'sections': sections,
        'items': flat_items,
    }