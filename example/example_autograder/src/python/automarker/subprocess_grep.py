import shlex
import subprocess


def grep_for_java_comment(submission_root, regex=" .* by autograder"):
    regex = f"^.* //{regex}\s*$"
    args = [
        "grep", "-rEn", *shlex.split('--include="*.java"'), regex,
        submission_root
    ]
    proc = subprocess.Popen(
        args, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    outputs, errors = proc.communicate(input=subprocess.PIPE, timeout=15)
    if outputs:
        tmp = list()
        for line in [
            line.decode() for line in outputs.split(b'\n') if len(line.strip())
        ]:
            tmp.append(line.split(":", 2))
        return tmp
    return []
