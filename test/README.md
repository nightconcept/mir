# test/

Fork-local location (`dev`/`mc` branches only — see `docs/branches.md`) for every test/bench
source and fixture, shared uniformly across all three build routes (GNU Make, CMake, Zig):

- `mir-tests/` — interpreter/generator/API tests and `.mir` text IR fixtures
- `adt-tests/` — container tests (varr, dlist, bitmap, htab, reduce)
- `c-tests/` — C programs run through `c2m` (and `runtests.sh`, the diff-based test runner used
  by both `c2mir-*-test` and `l2m-*-test` targets)
- `c-benchmarks/` — C benchmark programs run through `c2m`/gcc/clang/tcc for perf comparison

This directory is a sibling of `src/`, not a subdirectory of it, because upstream `vnmakarov/mir`
keeps everything at repo root and this fork's `src/`-move (see `docs/architecture.md`) only
wanted to relocate the C sources, not fork the test suite's content — but `src/GNUmakefile` and
`src/CMakeLists.txt` still need to find these fixtures, so both were given a `TEST_DIR` variable
pointing here (`$(SRC_DIR)/../test` / `${PROJECT_SOURCE_DIR}/../test`). This is the one place
where those two build files are no longer verbatim upstream — see `docs/build.md` for what to
do about it when upstreaming a change.

`build.zig` (repo root) reads test/bench sources from here directly (`test/mir-tests/...`, etc.)
to reach the same coverage make/cmake get.

Do not add test-only C sources anywhere under `src/` — they belong here instead, so the three
build routes keep exercising the same test set.
