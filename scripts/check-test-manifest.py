#!/usr/bin/env python3
"""Check that every test/tests.json case still names a real src/GNUmakefile target.

test/tests.json drives build.zig's `zig build test` step; src/GNUmakefile keeps its own
hand-written targets (see test/README.md for why they aren't generated from one file). This
script is the guard against the two lists silently drifting apart -- run it in CI alongside
`zig build test` and `make test-all`.
"""
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = REPO_ROOT / "test" / "tests.json"
GNUMAKEFILE = REPO_ROOT / "src" / "GNUmakefile"

TARGET_RE = re.compile(r"^([A-Za-z0-9_.-]+)\s*:(?!=)", re.MULTILINE)


def manifest_names(manifest: dict) -> list[str]:
    names = []
    for key in ("adt_tests", "mir_utility_tests", "interp_tests", "gen_tests", "run_test_mir_cases"):
        names.extend(case["name"] for case in manifest[key])
    names.extend(case["name"] for case in manifest["c2mir_runtests"])
    return names


def main() -> int:
    manifest = json.loads(MANIFEST.read_text())
    make_targets = set(TARGET_RE.findall(GNUMAKEFILE.read_text()))

    missing = [name for name in manifest_names(manifest) if name not in make_targets]
    if missing:
        print(f"error: {len(missing)} test/tests.json case(s) have no matching GNUmakefile target:", file=sys.stderr)
        for name in missing:
            print(f"  - {name}", file=sys.stderr)
        print(
            "\nEither the manifest entry's name is wrong, or GNUmakefile's target was renamed/removed"
            " without updating test/tests.json to match.",
            file=sys.stderr,
        )
        return 1

    print(f"OK: all {len(manifest_names(manifest))} test/tests.json cases have a matching GNUmakefile target")
    return 0


if __name__ == "__main__":
    sys.exit(main())
