from __future__ import annotations


def insert_at_start(filepath: str, new_line: str, comment: str | None = None) -> None:
    with open(filepath, "r", encoding="utf-8") as handle:
        original = handle.read()

    parts = []
    if comment:
        parts.append(f"// {comment}\n")
    parts.append(f"{new_line}\n\n")
    parts.append(original)

    with open(filepath, "w", encoding="utf-8") as handle:
        handle.write("".join(parts))


def rewrite_line(
    filepath: str,
    line_no: int,
    new_line: str,
    remove_empty_preceding_lines: bool = False,
) -> None:
    with open(filepath, "r", encoding="utf-8") as handle:
        lines = handle.readlines()

    if line_no < 0 or line_no >= len(lines):
        raise IndexError(f"line_no {line_no} out of range for {filepath}")

    lines[line_no] = f"{new_line}\n"

    if remove_empty_preceding_lines:
        i = line_no - 1
        while i >= 0 and not lines[i].strip():
            del lines[i]
            line_no -= 1
            i -= 1

    with open(filepath, "w", encoding="utf-8") as handle:
        handle.writelines(lines)