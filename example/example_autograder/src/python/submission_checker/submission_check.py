from __future__ import annotations

import argparse
from pathlib import Path

from .config import SUBMISSION_ROOT
from .packaging import fix_one


def _resolve_target(path_arg: str | None) -> Path:
    if path_arg is None:
        return Path.cwd()

    path = Path(path_arg).resolve()

    if SUBMISSION_ROOT:
        candidate = path / SUBMISSION_ROOT
        if candidate.exists() and candidate.is_dir():
            return candidate

    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-s",
        "--submission-dir",
        default=".",
        help="Path to the submission root to fix",
    )
    args = parser.parse_args()

    target = _resolve_target(args.submission_dir)
    fix_one(str(target), submission_id=target.name)


if __name__ == "__main__":
    main()