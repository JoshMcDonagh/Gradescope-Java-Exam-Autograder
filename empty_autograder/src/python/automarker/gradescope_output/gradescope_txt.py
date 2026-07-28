import os.path
import re

EXPECTED_MIN_NUMBER_OF_PARTS = 7

SECTION_RE = re.compile(r'^section(\d+)$')
QUESTION_RE = re.compile(r'^question(\d+)$')

SHOW_PASSES = 'Test passed'
SHOW_FAILS = 'Test failed'
SHOW_ERRORS = 'Failed to compile'


def extract_question(filename):
    """Derive test metadata from an output filename.

    Output filenames are the test class's fully qualified name with dots
    replaced by underscores (e.g. section1_question1_a_PastryTest.txt, or
    structural_section1_question1_a_PastryTest.txt for an exam whose test
    tree has a grouping level). Nothing here assumes a particular layout:
    the section and question values are located by pattern rather than by
    position, and are None if the exam's packages do not follow the
    sectionN/questionN naming convention. test_type is the tree's grouping
    prefix, if the exam uses one, and empty otherwise.
    """
    path_parts = filename.split(os.path.sep)[-1].split('_')

    section = None
    section_idx = next(
        (i for i, p in enumerate(path_parts) if SECTION_RE.match(p)), None)
    if section_idx is not None:
        section = int(SECTION_RE.match(path_parts[section_idx]).group(1))

    question = None
    question_idx = next(
        (i for i, p in enumerate(path_parts) if QUESTION_RE.match(p)), None)
    if question_idx is not None:
        question = [int(QUESTION_RE.match(path_parts[question_idx]).group(1)),
                    *path_parts[question_idx + 1:-1]]
        if len(question) == 1:
            question = question[0]

    test_type = '_'.join(path_parts[:section_idx]) if section_idx else ''

    return {
        'filename': filename,
        'test_type': test_type,
        'section': section,
        'question': question,
        'class_name': path_parts[-1].split('.')[0],
        'package': '.'.join(path_parts[:-1]),
    }


def extract_tests(filename, filter_by=None):
    question = extract_question(filename)
    tests = list()
    with open(filename, mode="r", encoding="utf-8") as txt:
        (end_flag, fail_count) = (False, False)
        for i, line in enumerate(txt.readlines()):
            line = line.replace('', ' ').strip()

            if end_flag:
                if line.startswith('Failures'):
                    fail_count = int(line.split("(")[-1].split(')')[0])
                    failures = list()
                    failure = list()
                    continue
                if not fail_count:
                    continue
                if line.startswith("JUnit Jupiter"):
                    if failure:
                        failures.append(failure)
                    failure = [line[14:]]
                    continue
                if line.startswith('Test run finished after'):
                    if failure:
                        failures.append(failure)
                        assert len(failures) == fail_count
                        for failure in failures:
                            method_name = ""
                            try:
                                class_name = failure[1][failure[1].index(
                                    'MethodSource [className = '
                                ) + 27:]
                                method_name = class_name[class_name.index(
                                    'methodName = '
                                ) + 14:].split("'")[0]
                                method_name = f'.{method_name}'
                            except ValueError:
                                class_name = failure[1][failure[1].index(
                                    'ClassSource [className = '
                                ) + 26:]
                            fqn = class_name.split("'")[0] + method_name

                            matches = [
                                (j, t) for (j, t) in enumerate(tests)
                                if t['fqn'] == fqn
                            ]
                            if len(matches) == 1:
                                j = matches[0][0]
                                if isinstance(tests[j], dict):
                                    tests[j]['extra'].extend(failure)
                                else:
                                    tests[j][1]['extra'].extend(failure)
                            elif len(method_name):
                                print(f"WARNING -- found failure without matching test: {fqn}")
                            else:
                                print(f"WARNING -- found entire test file failure: {fqn}")
                    break
                if line.strip():
                    failure.append(line)
                continue

            if line.startswith('['):
                parts = line.split('[')
                if len(parts) < EXPECTED_MIN_NUMBER_OF_PARTS:
                    continue

                (test_name, outcome, extra) = (
                    parts[3], parts[5][3],
                    parts[EXPECTED_MIN_NUMBER_OF_PARTS:]
                )
                test_name = test_name.split('(')[0]
                test_name = test_name[3:] if test_name[2] == 'm' else test_name[2:]

                if test_name.startswith('JUnit Jupiter'):
                    continue
                if test_name.strip() == question['class_name']:
                    continue
                if test_name.startswith('JUnit Vintage'):
                    end_flag = True
                    continue

                test = question | {
                    'line_no': i,
                    'name': f"{question['class_name']}.{test_name}",
                    'fqn': f"{question['package']}.{question['class_name']}.{test_name}",
                    'output': 'Test passed' if outcome == '✔' else 'Test failed',
                    'extra': [e[3:] if e.startswith('31m') else e for e in extra[:-1]],
                }
                tests.append(test)

        if filter_by is None:
            return tests

        return [
            t for t in tests if t['output'].startswith(filter_by)
        ]
