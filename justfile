# Task runner for MIR. Thin wrappers around the canonical GNUmakefile targets
# (see CLAUDE.md / AGENTS.md) -- this just makes the common ones easier to type.

default:
    @just --list

# release build (optimized) in out/
build:
    python scripts/run_make.py --out all

# unoptimized debug build
debug:
    python scripts/run_make.py --out debug

# core test suite, with an aggregate pass/total summary line
test:
    python scripts/run_make.py --isolated --summary test

# core suite plus adt/simplify/io/scan/mir2c/l2m tests
test-all:
    python scripts/run_make.py --isolated --summary test-all

adt-test:
    python scripts/run_make.py --isolated adt-test

gen-test:
    python scripts/run_make.py --isolated gen-test

interp-test:
    python scripts/run_make.py --isolated interp-test

c2mir-test:
    python scripts/run_make.py --isolated --summary c2mir-test

c2mir-bootstrap-test:
    python scripts/run_make.py --isolated c2mir-bootstrap-test

bench:
    python scripts/run_make.py --out bench

# remove the stable out/ build
clean:
    python scripts/run_make.py --clean-out

# remove every isolated test run and its logs
clean-all-tests:
    python scripts/run_make.py --clean-all-tests

# zig build (see build.zig), current host platform only -- distinct from `just build` (make)
zbuild:
    zig build

# run the zig build's test suite natively (`zig build test`)
zbuild-test:
    zig build test

# cross-compile the zig build for all 3 CI platforms (linux/windows/macos) from this host,
# one artifact tree per target triple under zig-out/<triple>/ -- can't run zbuild-test against
# these since cross-compiled binaries don't execute on the host
zbuild-all:
    for triple in x86_64-linux-gnu x86_64-windows-gnu aarch64-macos; do \
        echo "=== zig build -Dtarget=$triple ==="; \
        zig build -Dtarget=$triple --prefix zig-out/$triple || exit 1; \
    done
