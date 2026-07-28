import json
import logging
import os
import sys
from pathlib import Path


def _get_autograder_root() -> Path:
    """
    Walk upwards until we find the autograder root, identified by run_autograder.
    """
    current = Path(__file__).resolve()

    for parent in [current.parent] + list(current.parents):
        if (parent / "run_autograder").exists():
            return parent

    raise FileNotFoundError(
        "Could not locate autograder root containing run_autograder"
    )


AUTOGRADER_ROOT = _get_autograder_root()
AUTOGRADER_CONFIG_DIR = AUTOGRADER_ROOT / "autograder_config"
SUBMISSION_RULES_FILE = AUTOGRADER_CONFIG_DIR / "submission_rules.json"


def _load_submission_rules() -> dict:
    with open(SUBMISSION_RULES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


SUBMISSION_RULES = _load_submission_rules()

EXPECTED_PACKAGE = SUBMISSION_RULES["expected_packages"]
EXPECTED_PACKAGE_STATEMENT = SUBMISSION_RULES.get(
    "expected_package_statement_template",
    "package {expected_package};"
)

SUBMISSION_ROOT = SUBMISSION_RULES.get("submission_root")

SKIP_DIRS = tuple(SUBMISSION_RULES.get("skip_dirs", []))
SKIP_FILES = tuple(SUBMISSION_RULES.get("skip_files", []))

RULES = SUBMISSION_RULES.get("rules", {})
LOG_OUTPUTS = tuple(
    SUBMISSION_RULES.get("logging", {}).get("outputs", ["stdout", "file"])
)

# Kept for compatibility with any other existing code that may import these.
EXPECTED_ENUM_VALUES = dict()
EXPECTED_ATTRIBUTES = tuple()
EXPECTED_METHODS_NOARGS = dict()
EXPECTED_METHODS_ARGS = dict()
EXPECTED_METHODS = dict()
EXPECTED_ENUMS = tuple()
EXPECTED_INTERFACES = tuple()
EXPECTED_RECORDS = tuple()
EXPECTED_CLASSES = tuple(EXPECTED_PACKAGE.keys())

EXPECTED_METHODS_FLAT = tuple()
EXPECTED_METHODS_ARGS_FLAT = tuple()
EXPECTED_METHODS_NOARGS_FLAT = tuple()


def rule_enabled(rule_name: str, default: bool = False) -> bool:
    return RULES.get(rule_name, default)


def init_logging(name: str = "submission_checker"):
    log = logging.getLogger()
    handlers = []

    if "file" in LOG_OUTPUTS:
        handlers.append(logging.FileHandler(f"{name}.log"))
    if "stderr" in LOG_OUTPUTS:
        handlers.append(logging.StreamHandler())
    if "stdout" in LOG_OUTPUTS:
        handlers.append(logging.StreamHandler(sys.stdout))

    if handlers:
        logging.basicConfig(
            handlers=handlers,
            encoding="utf-8",
            level=logging.DEBUG,
            format="%(asctime)s - %(levelname)s - %(message)s",
            force=True
        )

    log.setLevel(logging.DEBUG)
    return log
