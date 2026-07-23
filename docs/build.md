# Build & Test

Three build routes are supported. All read non-test C sources out of `src/` and all test/bench
sources out of `test/` (repo root, sibling of `src/`) — see `test/README.md` for what lives
there and why it's a shared, uniform set across all three routes.

## GNU Make (canonical; CI uses it)

The `GNUmakefile` lives in `src/`. It tracks upstream closely, but is **not** verbatim upstream:
this fork's `src/`-move relocated all test/bench fixtures to a sibling `test/` directory (see
[architecture.md](architecture.md)), which required adding a `TEST_DIR` variable (defaults to
`$(SRC_DIR)/../test`) and repointing every test/bench target at it. When upstreaming a change
that touches these targets, diff against `TEST_DIR`-prefixed paths mentally reverted to
`SRC_DIR`-prefixed `mir-tests`/`adt-tests`/`c-tests`/`c-benchmarks` paths, since upstream doesn't
have this split. It's invoked out-of-tree, exactly like upstream's own documented
`SRC_DIR`/out-of-tree flow:

```sh
make -C src test                                       # in-place (build artifacts land in src/)
make -f src/GNUmakefile SRC_DIR=src <target>            # out-of-tree, from repo root
make SRC_DIR=<src> -f <src>/GNUmakefile <target>        # fully out-of-tree, any build dir
make PREFIX=/usr install
make clean                                              # remove all build/test/bench artifacts
```

`just` (task runner, pinned via `.mise.toml`) wraps the common targets and always builds
out-of-tree (`out/` for stable builds, an isolated `.test-runs/<id>/` per invocation for tests):

- **Build**: `just build` (release) / `just debug` (unoptimized)
- **Test**: `just test` (core suite: readme-example-test, mir-bin-run-test, c2mir-test; prints
  an aggregate pass/total summary) / `just test-all` (adds adt/simplify/io/scan/mir2c/l2m tests)
- **Individual suites**: `just adt-test`, `just gen-test`, `just interp-test`,
  `just c2mir-test`, `just c2mir-bootstrap-test` (or `make <target>` directly — see
  `src/GNUmakefile` for the full list, e.g. `interp-test1..16`, `gen-test1..16`)
- **Bench**: `just bench`
- **Clean**: `just clean` (removes `out/`) / `just clean-all-tests` (removes `.test-runs/`)

Test/bench sources live in `test/mir-tests/` (interpreter/generator/API tests, `.mir` text
fixtures), `test/adt-tests/` (container tests), `test/c-tests/` and `test/c-benchmarks/` (C
programs run through `c2m`). `src/csmith-c2m.sh` / `src/csmith-c2m-gcc.sh` (these stay in `src/`,
not `test/`, since they aren't fixture data — see `test/README.md`) are used for csmith-based
fuzz testing of `c2m` against gcc.

## CMake

`src/CMakeLists.txt` — same divergence from upstream as GNUmakefile above: a `TEST_DIR`
(`${PROJECT_SOURCE_DIR}/../test`) variable was added and test/bench `add_executable`/`add_test`
sources repointed at it. `BUILD_TESTING` option (default ON):

```sh
cmake -S src -B build -DBUILD_TESTING=ON
cmake --build build
ctest --test-dir build --verbose --output-on-failure
```

## Zig (`build.zig`, repo root)

A parallel build added for this fork's overhaul, reaching parity with the tool set the
make/cmake routes produce (libmir static+shared, `c2m`, `mir-bin-run`, `m2b`, `b2m`, `b2ctab`)
plus a `zig build test` step. `mir.c`/`mir-gen.c` `#include` their own per-target file internally
(selected by `#ifdef` on the compile target's arch), so `build.zig` never enumerates per-arch
sources — it just compiles `mir.c`/`mir-gen.c`/`c2mir/c2mir.c` as ordinary C translation units.

`zig build test` covers two kinds of cases:
- Hand-written in `build.zig` itself: readme-example-test, mir2c-test, mir-bin-run-test across
  all 4 dispatch modes, c2mir-simple-test.
- Data-driven from `test/tests.json` (parsed at build-configure time via `addManifestTests` in
  `build.zig`): adt-tests, mir-utility-tests (simplify/scan/io), interp-test1..16,
  gen-test1..16, and the standard-mode `c2m` test suite (via `test/c-tests/runtests.sh`,
  skipped on Windows pending a portable `sh` there). `scripts/check-test-manifest.py` checks
  this manifest's case names against `src/GNUmakefile`'s own targets in CI so the two can't
  silently drift — see `test/README.md`.

**Not yet covered** (documented gap, not silently missing): the `-O0`/`-O1`/`-O3`
`runtests.sh` variants and the 6 `c2mir-bootstrap-*` self-compilation tests `make test-all`
runs — bootstrap needs `build.zig` to recompile MIR's own sources through `c2m` mid-build,
real new plumbing rather than another manifest entry.

- **Build (host only)**: `just zbuild`
- **Test (host only)**: `just zbuild-test`
- **Cross-compile all 3 CI platforms** (linux/windows/macos) from one host, into
  `zig-out/<triple>/`: `just zbuild-all` — these binaries can't run on the host, so there's no
  `zbuild-all-test`.
- zig version is pinned in `.mise.toml` (`mise install`).

## Format

`clang-format` (config in `src/.clang-format`, Google-based, 100-col limit, space-before-parens,
right-aligned pointers) — run before committing changes to `.c`/`.h` files.
