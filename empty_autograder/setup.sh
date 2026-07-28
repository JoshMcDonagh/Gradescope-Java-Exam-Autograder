#!/usr/bin/env bash

set -euo pipefail

readonly WORKSPACE="/autograder/source"
readonly RUN_ACCOUNT="student"
readonly SETTINGS_FILE="${WORKSPACE}/autograder_config/settings.json"

log() { printf '\n>>> %s\n' "$1"; }

read_extra_packages() {
    local channel="$1"
    python3 - "$SETTINGS_FILE" "$channel" <<'PY'
import json, sys

path, channel = sys.argv[1], sys.argv[2]

try:
    with open(path, encoding="utf-8") as fh:
        cfg = json.load(fh)
except FileNotFoundError:
    sys.exit(0)                      # no settings.json -> no extras
except Exception as exc:
    print(f"[ERROR] Could not parse {path}: {exc}", file=sys.stderr)
    sys.exit(1)

extras = cfg.get("extra_packages")
if extras in (None, {}):
    sys.exit(0)                      # key absent/empty -> no extras
if not isinstance(extras, dict):
    print('[ERROR] "extra_packages" must be an object with "apt"/"pip" lists, '
          f"e.g. {{'apt': ['graphviz'], 'pip': ['numpy']}} (in {path}).",
          file=sys.stderr)
    sys.exit(1)

packages = extras.get(channel)
if packages in (None, []):
    sys.exit(0)                      # this channel unused
if not isinstance(packages, list) or \
        not all(isinstance(p, str) and p.strip() for p in packages):
    print(f'[ERROR] "extra_packages.{channel}" must be a list of non-empty '
          f"strings (in {path}).", file=sys.stderr)
    sys.exit(1)

for p in packages:
    p = p.strip()
    # Reject specs that would be read as command-line options.
    if p.startswith("-"):
        print(f'[ERROR] Refusing {channel} package spec that starts with "-": '
              f"{p!r} (in {path}).", file=sys.stderr)
        sys.exit(1)
    print(p)
PY
}

install_extra_packages() {
    local channel="$1"; shift
    local installer=("$@")

    local out
    if ! out="$(read_extra_packages "$channel")"; then
        exit 1
    fi

    local packages=()
    [ -n "$out" ] && mapfile -t packages < <(printf '%s\n' "$out")

    if [ "${#packages[@]}" -gt 0 ]; then
        log "Installing ${#packages[@]} extra ${channel} package(s) from settings.json: ${packages[*]}"
        "${installer[@]}" "${packages[@]}"
    fi
}

provision_toolchain() {
    log "Installing base JDK and Python toolchain"

    export DEBIAN_FRONTEND=noninteractive

    local apt_packages=(
        openjdk-21-jdk-headless
        python3
        python3-pip
    )

    apt-get update -qq
    apt-get install -y --no-install-recommends "${apt_packages[@]}"

    install_extra_packages apt \
        apt-get install -y --no-install-recommends

    log "Installing base Python packages"

    local pip_packages=(
        levenshtein
    )

    python3 -m pip install --no-cache-dir --upgrade pip
    python3 -m pip install --no-cache-dir "${pip_packages[@]}"

    install_extra_packages pip \
        python3 -m pip install --no-cache-dir

    apt-get clean
    rm -rf /var/lib/apt/lists/*
}

create_run_account() {
    log "Creating unprivileged run account '${RUN_ACCOUNT}'"

    useradd --no-create-home --shell /bin/bash "${RUN_ACCOUNT}"
}

lock_workspace() {
    log "Locking down ${WORKSPACE}"

    chmod -R o-w "${WORKSPACE}"

    local -A grants=(
        ["junit-report"]="o+rwx"
        ["bin"]="o+rwx"
        ["src/main"]="o-w"
    )

    local rel
    for rel in "${!grants[@]}"; do
        install -d "${WORKSPACE}/${rel}"
        chmod "${grants[$rel]}" "${WORKSPACE}/${rel}"
    done

    chmod o+w "${WORKSPACE}"
}

main() {
    provision_toolchain
    create_run_account
    lock_workspace
}

main "$@"
