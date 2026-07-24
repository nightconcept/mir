#!/usr/bin/env python3
"""Run GNUmakefile targets in stable or isolated cross-platform build directories."""

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from test_summary import summarize

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "out"
TEST_RUNS_DIR = REPO_ROOT / ".test-runs"


def remove_owned_tree(path: Path) -> None:
    resolved = path.resolve()
    allowed = {OUT_DIR.resolve(), TEST_RUNS_DIR.resolve()}
    if resolved not in allowed:
        sys.exit(f"refusing to remove non-owned path: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)
        print(f"removed {resolved}")
    else:
        print(f"already clean: {resolved}")


def run_and_log(command: list[str], cwd: Path, log_path: Path) -> int:
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
        )
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="", flush=True)
            log.write(line)
            log.flush()
        return process.wait()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", nargs="?", help="GNUmakefile target to run")
    parser.add_argument("--out", action="store_true", help="use the stable out/ build directory")
    parser.add_argument("--isolated", action="store_true", help="create a unique test-run directory")
    parser.add_argument(
        "--summary", action="store_true", help="print the aggregate c-tests pass/total summary"
    )
    parser.add_argument("--clean-out", action="store_true", help="remove the stable out/ directory")
    parser.add_argument(
        "--clean-all-tests", action="store_true", help="remove the complete .test-runs/ directory"
    )
    args = parser.parse_args()

    if args.clean_out or args.clean_all_tests:
        if args.target or args.out or args.isolated or args.summary:
            parser.error("cleanup options cannot be combined with a make target or run options")
        remove_owned_tree(OUT_DIR if args.clean_out else TEST_RUNS_DIR)
        return
    if not args.target:
        parser.error("a make target is required")
    if args.out == args.isolated:
        parser.error("select exactly one of --out or --isolated")

    started = datetime.now(timezone.utc)
    if args.isolated:
        run_id = f'{started.strftime("%Y%m%d-%H%M%S-%f")}-{os.getpid()}-{args.target}'
        run_dir = TEST_RUNS_DIR / run_id
        build_dir = run_dir / "build"
    else:
        run_dir = OUT_DIR
        build_dir = OUT_DIR
    build_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / "output.log"

    if os.name == "nt":
        command = [
            sys.executable,
            str(REPO_ROOT / "scripts" / "win-test.py"),
            "--build-dir",
            str(build_dir),
            args.target,
        ]
    else:
        command = [
            "make",
            "-f",
            str(REPO_ROOT / "src" / "GNUmakefile"),
            f"SRC_DIR={REPO_ROOT / 'src'}",
            args.target,
        ]

    print(f"run directory: {run_dir}", flush=True)
    returncode = run_and_log(command, build_dir, log_path)
    if args.summary:
        summary = summarize(log_path.read_text(encoding="utf-8", errors="replace"))
        if summary:
            print(summary, flush=True)
    metadata = {
        "target": args.target,
        "command": command,
        "commit": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True
        ).stdout.strip(),
        "platform": sys.platform,
        "started_at": started.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "exit_code": returncode,
        "build_directory": str(build_dir),
        "log": str(log_path),
    }
    (run_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(f"log: {log_path}", flush=True)
    sys.exit(returncode)


if __name__ == "__main__":
    main()
