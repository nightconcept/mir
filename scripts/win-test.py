#!/usr/bin/env python3
"""Run the GNUmakefile test suite on Windows via a native MSYS2 MinGW64 toolchain.

Mirrors what `make test` / `make test-all` do on Linux/macOS in CI, so all
three platforms run the *same* unfiltered Makefile targets -- no test
filtering, no alternate toolchain (see GNUmakefile's existing
`ifeq ($(OS),Windows_NT)` / `MINGW` branch, which this exercises).

Why not just run `make` directly from this shell? Mixing git-for-Windows'
bundled MSYS runtime (git-bash) with MSYS2-proper's gcc.exe/make.exe corrupts
the TMP/TEMP env vars across the runtime boundary, and cc1 fails with
"Cannot create temporary file in C:\\WINDOWS\\: Permission denied". Shelling
everything out through MSYS2's own bash.exe keeps one consistent runtime end
to end and avoids that.

Usage:
  python3 scripts/win-test.py test
  python3 scripts/win-test.py test-all
  python3 scripts/win-test.py <any other make target, e.g. c2mir-test>
"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from test_summary import summarize

REPO_ROOT = Path(__file__).resolve().parent.parent


def find_msys2_root() -> Path:
    env_root = os.environ.get("MSYS2_ROOT")
    if env_root:
        return Path(env_root)
    default = Path("C:/msys64")
    if default.exists():
        return default
    sys.exit(
        "Could not find an MSYS2 install. Set MSYS2_ROOT to point at one "
        "(expects <root>/usr/bin/bash.exe and <root>/mingw64/bin/gcc.exe)."
    )


def find_git_dir() -> str | None:
    git = shutil.which("git")
    return str(Path(git).parent) if git else None


def to_msys_path(p: Path) -> str:
    # MSYS2 bash understands drive-letter paths as /c/... .
    drive, rest = os.path.splitdrive(str(p))
    rest = rest.replace("\\", "/")
    return f"/{drive[0].lower()}{rest}"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("target", nargs="?", default="test", help="make target to run (default: test)")
    parser.add_argument("--build-dir", type=Path, default=REPO_ROOT, help="out-of-tree build directory")
    parser.add_argument("-j", "--jobs", type=int, default=os.cpu_count() or 1, help="parallel jobs for the build")
    parser.add_argument("-k", "--keep-going", action="store_true", help="pass -k to make so all gaps surface in one run")
    args = parser.parse_args()
    build_dir = args.build_dir.resolve()
    build_dir.mkdir(parents=True, exist_ok=True)

    msys2_root = find_msys2_root()
    bash = msys2_root / "usr" / "bin" / "bash.exe"
    gcc = msys2_root / "mingw64" / "bin" / "gcc.exe"
    make = msys2_root / "usr" / "bin" / "make.exe"
    for exe, label in ((bash, "usr/bin/bash.exe"), (gcc, "mingw64/bin/gcc.exe"), (make, "usr/bin/make.exe")):
        if not exe.exists():
            sys.exit(f"missing {label} under {msys2_root} -- install the mingw-w64-x86_64-gcc and make packages")

    # PATH inside the MSYS2 bash: its own mingw64 + usr/bin first (consistent
    # runtime), plus git-for-Windows' git.exe so GITCOMMIT can be embedded.
    path_entries = ["/mingw64/bin", "/usr/bin"]
    git_dir = find_git_dir()
    if git_dir:
        path_entries.append(to_msys_path(Path(git_dir)))

    keep_going = " -k" if args.keep_going else ""
    inner_cmd = (
        f'export PATH="{":".join(path_entries)}"; '
        f'export CC=gcc; '
        f'cd "{to_msys_path(build_dir)}" && '
        f'make -f "{to_msys_path(REPO_ROOT / "src" / "GNUmakefile")}" '
        f'SRC_DIR="{to_msys_path(REPO_ROOT / "src")}" -j{args.jobs}{keep_going} {args.target}'
    )

    print(f"+ {bash} -lc '{inner_cmd}'", flush=True)
    result = subprocess.run([str(bash), "-lc", inner_cmd], capture_output=True, text=True)
    output = result.stdout + result.stderr
    print(output)

    summary = summarize(output)
    if summary:
        print(summary)

    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
