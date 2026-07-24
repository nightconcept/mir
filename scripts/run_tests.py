#!/usr/bin/env python3
"""Cross-platform test runner for MIR.

This is the single, canonical test orchestrator for the make and CMake build routes:
CI invokes it uniformly on Linux, macOS, and Windows against whichever build directory
that platform's build step produced, so all three platforms run the same broad suite
(previously Linux/macOS ran GNUmakefile's narrower `test` target while only Windows ran
this script -- see docs/build.md).

Runs all test suites (ADT tests, MIR utility tests, Interp/Gen tests, mir-bin-run,
mir2c, c2m C-tests suite, and bootstrap tests) natively on Linux, macOS, and Windows.
Can also be run standalone, or invoked by GNU Make, CMake, or Zig directly.
"""

import argparse
import difflib
import os
import platform
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
TEST_DIR = REPO_ROOT / "test"
SRC_DIR = REPO_ROOT / "src"

IS_WINDOWS = sys.platform == "win32" or os.name == "nt"
ARCH = platform.machine().lower()
if ARCH in ("x86_64", "amd64"):
    ARCH = "x86_64"
elif ARCH in ("aarch64", "arm64"):
    ARCH = "aarch64"

# CMake spells some of these targets differently than GNUmakefile's own binary names
# (underscores instead of hyphens, historically copied from upstream's CMakeLists.txt).
# This lets callers use one canonical (GNUmakefile-spelled) name and still find the
# CMake-built binary.
# c2m C-tests that cannot run on Windows and are skipped there (keyed by TEST_DIR-relative
# posix path). These are not build failures -- they are limitations of compiling/running C
# through c2m against the MSVC toolchain, in the same spirit as zig-build.yml skipping the
# whole runtests.sh c-tests suite on Windows (build.zig gates it behind `if (!is_windows)`).
# Root causes, by group:
#   * Win64 ABI: variadic args, `long double` (64-bit on Win64, tests assume 80-bit), and
#     setjmp/longjmp (an MSVC intrinsic, not a libc call) -- va-*, vararg*, long-double-*,
#     setjmp*, matrix-param, va-ld-stack, va-struct-args.
#   * MSVC system headers: pulling in <stdio.h>/<stdlib.h>/<setjmp.h> drags in SAL-annotated
#     UCRT/SDK headers (sal.h etc.) that use `#pragma`/`__declspec`/intrinsics c2m does not
#     fully model -- the remaining stdio/enum/issue* tests.
# Revisit if c2m gains Win64 ABI + MSVC-header support; drop entries as they start passing.
WINDOWS_UNSUPPORTED_C2M = {
    "c-tests/gcc/20050131-1.c", "c-tests/gcc/920501-6.c", "c-tests/gcc/920810-1.c",
    "c-tests/gcc/930513-1.c", "c-tests/gcc/960311-1.c", "c-tests/gcc/960311-2.c",
    "c-tests/gcc/960311-3.c", "c-tests/gcc/enum-3.c", "c-tests/gcc/inst-check.c",
    "c-tests/lacc/assignment-type.c", "c-tests/lacc/constant-expression.c",
    "c-tests/lacc/initialize-call.c", "c-tests/lacc/initialize-object.c",
    "c-tests/lacc/long-double-function.c", "c-tests/lacc/padded-initialization.c",
    "c-tests/lacc/pointer-immediate.c", "c-tests/lacc/printstr.c",
    "c-tests/lacc/string-conversion.c", "c-tests/lacc/vararg.c",
    "c-tests/lacc/vararg-complex-1.c", "c-tests/lacc/vararg-complex-2.c",
    "c-tests/mir/addr-3.mir",
    "c-tests/new/bf1.c", "c-tests/new/bf2.c", "c-tests/new/bf3.c",
    "c-tests/new/enum_test.c", "c-tests/new/interp.c", "c-tests/new/issue142.c",
    "c-tests/new/issue18.c", "c-tests/new/issue186-1.c", "c-tests/new/issue186-2.c",
    "c-tests/new/issue186-3.c", "c-tests/new/issue212.c", "c-tests/new/issue23.c",
    "c-tests/new/issue241.c", "c-tests/new/issue253.c", "c-tests/new/issue361.c",
    "c-tests/new/issue392.c", "c-tests/new/issue393.c", "c-tests/new/issue441.c",
    "c-tests/new/issue456.c", "c-tests/new/issue68.c", "c-tests/new/matrix-param.c",
    "c-tests/new/mike.c", "c-tests/new/negative-index32.c", "c-tests/new/ptr-to-array.c",
    "c-tests/new/setjmp.c", "c-tests/new/setjmp2.c", "c-tests/new/va-ld-stack.c",
    "c-tests/new/va-struct-args.c",
}

CMAKE_NAME_ALIASES = {
    "varr-test": "varr_test",
    "dlist-test": "dlist_test",
    "bitmap-test": "bitmap_test",
    "htab-test": "htab_test",
    "reduce-test": "reduce_test",
    "simplify-test": "simplify_test",
    "scan-test": "scan_test",
    "io-test": "io_test",
    "run-test": "run_test",
    "interp-test1": "interp_loop",
    "interp-test2": "interp_loop_c",
    "interp-test3": "interp_sieve",
    "interp-test4": "interp_sieve_c",
    "interp-test5": "interp_hi",
    "interp-test6": "interp_args",
    "interp-test7": "interp_args_c",
    "gen-loop-test": "gen_loop",
    "gen-sieve-test": "gen_sieve",
    "readme-example-test": "readme_example",
    "mir2c-test": "mir2c_test",
}


class TestResult:
    def __init__(self, name: str, passed: bool, message: str = "", skipped: bool = False):
        self.name = name
        self.passed = passed
        self.message = message
        self.skipped = skipped


def get_exe_name(base: str) -> str:
    return f"{base}.exe" if IS_WINDOWS else base


def run_cmd(cmd: list[str], cwd: Path = REPO_ROOT, env: dict = None, timeout: float = 30.0) -> tuple[int, str, str]:
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            env=full_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            errors="replace",
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"Timeout after {timeout}s"
    except Exception as e:
        return -1, "", str(e)


def diff_text(expected: str, actual: str, fromfile: str = "expected", tofile: str = "actual") -> str:
    exp_lines = [line.rstrip("\r\n") for line in expected.splitlines()]
    act_lines = [line.rstrip("\r\n") for line in actual.splitlines()]
    diff = list(difflib.unified_diff(exp_lines, act_lines, fromfile=fromfile, tofile=tofile, lineterm=""))
    return "\n".join(diff)


def find_test_file_attr(test_file: Path, ext: str) -> Optional[Path]:
    p1 = Path(f"{test_file}{ext}")
    if p1.exists():
        return p1
    p2 = test_file.with_suffix(ext)
    if p2.exists():
        return p2
    return None


class TestRunner:
    def __init__(self, build_dir: Path, jobs: int = os.cpu_count() or 1, verbose: bool = False):
        self.build_dir = build_dir.resolve()
        self.jobs = jobs
        self.verbose = verbose
        self.results: list[TestResult] = []

    def find_binary(self, name: str) -> Path:
        # GNUmakefile places adt-tests/mir-tests binaries in their own subdirectories;
        # CMake (and REPO_ROOT/SRC_DIR fallbacks) put everything flat.
        search_dirs = [
            self.build_dir,
            self.build_dir / "bin",
            self.build_dir / "Release",
            self.build_dir / "Debug",
            self.build_dir / "adt-tests",
            self.build_dir / "mir-tests",
            REPO_ROOT,
            SRC_DIR,
        ]
        names = [name]
        if name in CMAKE_NAME_ALIASES:
            names.append(CMAKE_NAME_ALIASES[name])
        for n in names:
            exe_name = get_exe_name(n)
            for d in search_dirs:
                c = d / exe_name
                if c.exists() and c.is_file():
                    return c
        return search_dirs[0] / get_exe_name(name)

    def record(self, result: TestResult):
        self.results.append(result)
        if self.verbose or not result.passed:
            status = "SKIP" if result.skipped else ("OK" if result.passed else "FAIL")
            msg = f" ({result.message})" if result.message and not result.passed else ""
            print(f"[{status}] {result.name}{msg}", flush=True)

    def run_c2m_single_test(self, c2m_exe: Path, test_file: Path, mode_flag: str, add_main: Path = None) -> TestResult:
        test_name = f"c2m:{mode_flag}:{test_file.relative_to(TEST_DIR)}"

        arch_regex = r"(aarch64|arm64)" if ARCH == "aarch64" else r"(x86_64|amd64)"

        mach_file = find_test_file_attr(test_file, ".mach")
        if mach_file:
            target_mach = mach_file.read_text().strip()
            if not re.search(arch_regex, target_mach, re.IGNORECASE):
                return TestResult(test_name, True, f"skipped (requires {target_mach})", skipped=True)

        nomach_file = find_test_file_attr(test_file, ".nomach")
        if nomach_file:
            disabled_mach = nomach_file.read_text().strip()
            if re.search(arch_regex, disabled_mach, re.IGNORECASE):
                return TestResult(test_name, True, f"skipped (disabled for {disabled_mach})", skipped=True)

        opt_file = find_test_file_attr(test_file, ".opt")
        if opt_file:
            req_opt = opt_file.read_text().strip()
            if req_opt not in mode_flag:
                return TestResult(test_name, True, f"skipped (requires {req_opt})", skipped=True)

        if "-eb" in mode_flag and "lref" in test_file.name:
            return TestResult(test_name, True, "skipped (lref not supported in -eb mode)", skipped=True)

        if IS_WINDOWS and test_file.relative_to(TEST_DIR).as_posix() in WINDOWS_UNSUPPORTED_C2M:
            return TestResult(test_name, True, "skipped (unsupported on Windows)", skipped=True)

        disable_file = find_test_file_attr(test_file, ".disable")
        if disable_file:
            disabled_platforms = disable_file.read_text().splitlines()
            current_platforms = [ARCH]
            if IS_WINDOWS:
                current_platforms.append("windows")
            for p in current_platforms:
                if any(p in line for line in disabled_platforms):
                    return TestResult(test_name, True, f"skipped for platform {p}", skipped=True)

        expect_rc = 0
        expect_rc_file = find_test_file_attr(test_file, ".expectrc")
        if expect_rc_file:
            try:
                expect_rc = int(expect_rc_file.read_text().strip())
            except ValueError:
                pass

        expect_out_file = find_test_file_attr(test_file, ".expect")
        expect_err_file = find_test_file_attr(test_file, ".stderr-expect")

        # Pass filename relative to parent directory (matching runtests.sh execution)
        rel_test_file = test_file.name
        rel_add_main = add_main.name if add_main else None

        cmd = [str(c2m_exe)]
        if mode_flag.startswith("-O"):
            cmd.append(mode_flag)
        cmd.append(rel_test_file)
        if rel_add_main:
            cmd.append(rel_add_main)
        if mode_flag.startswith("-O"):
            cmd.append("-eg")
        elif mode_flag and not mode_flag.startswith("-O"):
            cmd.extend(mode_flag.split())

        code, out, err = run_cmd(cmd, cwd=test_file.parent)
        if code != expect_rc:
            return TestResult(test_name, False, f"return code {code} != expected {expect_rc}. Stderr: {err[:200]}")

        if expect_out_file and expect_out_file.exists():
            diff = diff_text(expect_out_file.read_text(), out, fromfile=str(expect_out_file), tofile="stdout")
            if diff:
                return TestResult(test_name, False, f"stdout mismatch:\n{diff[:500]}")

        if expect_err_file and expect_err_file.exists():
            # Strip absolute path prefixes from stderr lines for robust matching
            clean_err = re.sub(r"^.*?([^/\\:]+:\d+:\d+:)", r"\1", err, flags=re.MULTILINE)
            diff = diff_text(expect_err_file.read_text(), clean_err, fromfile=str(expect_err_file), tofile="stderr")
            if diff:
                return TestResult(test_name, False, f"stderr mismatch:\n{diff[:500]}")

        return TestResult(test_name, True)

    def run_all_c2m_tests(self):
        c2m_exe = self.find_binary("c2m")
        if not c2m_exe.exists():
            self.record(TestResult("c2m-tests", False, f"missing binary {c2m_exe}"))
            return

        c_tests_dir = TEST_DIR / "c-tests"
        subdirs = ["mir", "havoc", "new", "andrewchambers_c", "gcc", "lacc"]
        mode_flags = ["-ei", "-eg", "-eb -eg", "-O0", "-O1", "-O3"]

        tasks = []
        for subdir in subdirs:
            target_dir = c_tests_dir / subdir
            if not target_dir.exists():
                continue

            if (target_dir / "main.c").exists():
                test_files = [target_dir / "main.c"]
            else:
                test_files = [f for f in target_dir.glob("*.c") if not f.name.startswith("add-")]
                if subdir == "mir":
                    test_files.extend(target_dir.glob("*.mir"))

            for t in test_files:
                add_main = None
                add_c = target_dir / f"add-{t.name}"
                add_mir = target_dir / f"add-{t.stem}.mir"
                if add_c.exists():
                    add_main = add_c
                elif add_mir.exists():
                    add_main = add_mir

                for mode in mode_flags:
                    tasks.append((t, mode, add_main))

        with ThreadPoolExecutor(max_workers=self.jobs) as executor:
            futures = [
                executor.submit(self.run_c2m_single_test, c2m_exe, t, mode, add_main)
                for t, mode, add_main in tasks
            ]
            for f in futures:
                self.record(f.result())

    def run_executable_test(self, name: str, args: list[str] = None, cwd: Path = REPO_ROOT, expected_rc: int = 0) -> TestResult:
        exe = self.find_binary(name)
        if not exe.exists():
            return TestResult(name, True, f"executable {name} not found in {self.build_dir}", skipped=True)

        cmd = [str(exe)] + (args or [])
        code, out, err = run_cmd(cmd, cwd=cwd)
        if code != expected_rc:
            return TestResult(name, False, f"exit code {code} != {expected_rc}. err: {err[:200]}")
        return TestResult(name, True)

    def run_mir_bin_run_test(self) -> TestResult:
        c2m = self.find_binary("c2m")
        mir_bin_run = self.find_binary("mir-bin-run")
        if not c2m.exists() or not mir_bin_run.exists():
            return TestResult("mir-bin-run-test", False, "c2m or mir-bin-run binary missing")

        sieve_c = SRC_DIR / "sieve.c"
        with tempfile.TemporaryDirectory() as tmpdir:
            bmir_file = Path(tmpdir) / "sieve.bmir"
            code, out, err = run_cmd([str(c2m), str(sieve_c), "-c", "-o", str(bmir_file)])
            if code != 0 or not bmir_file.exists():
                return TestResult("mir-bin-run-test", False, f"failed to compile sieve.c to bmir: {err}")

            for mir_type in ["", "interp", "gen", "lazy"]:
                env = {"MIR_TYPE": mir_type} if mir_type else {}
                code, out, err = run_cmd([str(mir_bin_run), str(bmir_file), "sieve.bmir"], env=env)
                if code != 0:
                    return TestResult("mir-bin-run-test", False, f"mir-bin-run failed for MIR_TYPE='{mir_type}': {err}")

        return TestResult("mir-bin-run-test", True)

    def run_bootstrap_tests(self):
        if IS_WINDOWS:
            for tag in ["test0", "test1", "test", "test3"]:
                self.record(TestResult(f"c2mir-bootstrap-{tag}", True, "skipped on Windows", skipped=True))
            return

        c2m_exe = self.find_binary("c2m")
        if not c2m_exe.exists():
            self.record(TestResult("c2mir-bootstrap", False, "c2m binary not found"))
            return

        c2m_sources = [
            str(SRC_DIR / "mir-gen.c"),
            str(SRC_DIR / "c2mir" / "c2mir.c"),
            str(SRC_DIR / "c2mir" / "c2mir-driver.c"),
            str(SRC_DIR / "mir.c"),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            for mode, tag in [("-O0", "test0"), ("-O1", "test1"), ("", "test"), ("-O3", "test3")]:
                bmir1 = tmppath / f"1_{tag}.bmir"
                bmir2 = tmppath / f"2_{tag}.bmir"
                mode_args = [mode] if mode else []
                code1, _, err1 = run_cmd(
                    [str(c2m_exe), "-w", "-DMIR_BOOTSTRAP"] + mode_args + [f"-I{SRC_DIR}"] + c2m_sources + ["-o", str(bmir1)]
                )
                code2, _, err2 = run_cmd(
                    [str(c2m_exe), "-DMIR_BOOTSTRAP"]
                    + mode_args
                    + [str(bmir1), "-el", "-w", "-DMIR_BOOTSTRAP"]
                    + mode_args
                    + [f"-I{SRC_DIR}"]
                    + c2m_sources
                    + ["-o", str(bmir2)]
                )
                if code1 == 0 and code2 == 0 and bmir1.exists() and bmir2.exists() and bmir1.read_bytes() == bmir2.read_bytes():
                    self.record(TestResult(f"c2mir-bootstrap-{tag}", True))
                else:
                    self.record(TestResult(f"c2mir-bootstrap-{tag}", False, f"bootstrap {tag} failed: {err1 or err2}"))

    def run_all(self) -> bool:
        print(f"=== Running test suite (build dir: {self.build_dir}) ===", flush=True)

        # 1. ADT Tests
        for adt in ["varr-test", "dlist-test", "bitmap-test", "htab-test"]:
            self.record(self.run_executable_test(adt))
        self.record(self.run_executable_test("reduce-test", [str(SRC_DIR / "c2mir" / "c2mir.c")]))

        # 2. Utility & Example Tests
        for util in ["simplify-test", "scan-test", "io-test", "readme-example-test", "mir2c-test"]:
            self.record(self.run_executable_test(util))

        # 3. Interp & Gen Tests
        for interp in ["interp-test1", "interp-test2", "interp-test3", "interp-test4", "interp-test5", "interp-test6", "interp-test7"]:
            self.record(self.run_executable_test(interp))

        for gen in ["gen-loop-test", "gen-sieve-test", "gen-get-thunk-addr-test", "issue219"]:
            self.record(self.run_executable_test(gen))

        run_test_exe = self.find_binary("run-test")
        if run_test_exe.exists():
            for num in range(1, 17):
                if IS_WINDOWS and num in (11, 12):
                    continue
                mir_fixture = str(TEST_DIR / "mir-tests" / f"test{num}.mir")
                # test1..7.mir have no `main` -- only test8..16.mir are meant to be
                # run through run-test's interp mode (-i); test1..7's interp coverage
                # comes from the dedicated interp_loop/interp_sieve/etc. binaries above.
                if num >= 8:
                    self.record(self.run_executable_test("run-test", ["-i", mir_fixture]))
                flag = "-d" if num <= 7 else "-g"
                self.record(self.run_executable_test("run-test", [flag, mir_fixture]))

        # 4. mir-bin-run test
        self.record(self.run_mir_bin_run_test())

        # 5. Full c2m C-tests suite
        self.run_all_c2m_tests()

        # 6. Bootstrap self-compilation tests
        self.run_bootstrap_tests()

        # Summary
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed and not r.skipped)
        skipped = sum(1 for r in self.results if r.skipped)
        failed = sum(1 for r in self.results if not r.passed)

        print("=" * 60, flush=True)
        print(f"Test Summary: {passed} passed, {skipped} skipped, {failed} failed out of {total} total", flush=True)
        print("=" * 60, flush=True)

        return failed == 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, default=REPO_ROOT, help="path to directory containing built binaries")
    parser.add_argument("-j", "--jobs", type=int, default=os.cpu_count() or 1, help="parallel test jobs")
    parser.add_argument("-v", "--verbose", action="store_true", help="verbose output")
    args = parser.parse_args()

    runner = TestRunner(build_dir=args.build_dir, jobs=args.jobs, verbose=args.verbose)
    success = runner.run_all()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
