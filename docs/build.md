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
ctest --test-dir build --verbose --output-on-failure   # local/manual only, not what CI runs -- see Testing below
```

## Testing (all 3 routes)

`scripts/run_tests.py` is the single, canonical test orchestrator across make, CMake, *and*
Zig — CI runs it uniformly on all 3 platforms for all 3 build routes (see [CI](ci.md)), rather
than relying on each build system's own narrower `test` target/CTest/`zig build test` separately
(that asymmetry — Linux/macOS on `make test`, Windows on this script, Zig on its own manifest —
is exactly what it replaced). It finds built binaries under a `--build-dir` (checking common
subdirectories across all three layouts: flat for CMake and Zig's `zig-out/bin`,
`adt-tests/`/`mir-tests/` for GNUmakefile's in-place layout) and runs ADT tests, MIR
utility/interp/gen tests, `mir-bin-run-test`, the full `c2m` C-tests battery
(`-ei`/`-eg`/`-eb -eg`/`-O0`/`-O1`/`-O3`), and bootstrap self-compilation tests (`-DMIR_BOOTSTRAP`,
`-O0`/`-O1`/default/`-O3`) — skipped only on Windows, since bootstrap has been verified to work
fine on macOS arm64 despite an earlier, overly-cautious skip there.

```sh
make -C src test-bins                             # build everything run_tests.py needs, nothing else (Linux/macOS)
python3 scripts/run_tests.py --build-dir src      # against that in-place build
python3 scripts/run_tests.py --build-dir build    # against a CMake build/ directory
python3 scripts/run_tests.py --build-dir zig-out  # against a `zig build` output tree
```

`test-bins` is a build-only aggregate target: each of its prerequisites is the underlying
binary (e.g. `$(BUILD_DIR)/adt-tests/varr-test$(EXE)`), not the matching phony target (e.g.
`varr-test`) that also executes it — so `make test-bins` compiles every binary
`scripts/run_tests.py` looks for without running any of them or pulling in GNUmakefile's own
`c2mir-full-test`/bootstrap recipes (reached via `test-all`'s `test` -> `c2mir-test`
dependency), which `run_tests.py` re-runs itself. `test`/`test-all`/`interp-test`/`gen-test`
still build *and run* each target's own recipe, for local dev use (`just test`/`just
test-all`).

Because GNUmakefile, `src/CMakeLists.txt`, and `build.zig`/`test/tests.json` sometimes name the
same test binary differently (e.g. `varr-test` vs. CMake's `varr_test`, or the 4 `gen-*` cases
where `tests.json` uses GNUmakefile's *target* name rather than its binary basename),
`run_tests.py` resolves the alternate spellings via `CMAKE_NAME_ALIASES`/`ZIG_NAME_ALIASES`
tables rather than any build file being renamed — GNUmakefile stays upstream-compatible, and the
other two are left alone to minimize churn. New test binaries should just use the GNUmakefile
binary name directly (no alias needed) unless there's a reason to match an existing convention.

CI still runs the native build first on each platform (`make -C src test-bins` / `cmake --build` /
`zig build`) before handing off to `run_tests.py` — on Linux/macOS this is a pure build step
(`test-bins` only compiles binaries, it doesn't execute any of them or GNUmakefile's own test
recipes), so `run_tests.py`'s exit code is the only thing that runs and gates the broad suite
on all 3 build routes.

**Known gaps** (documented, not silently missing) vs. GNUmakefile's full `test-all`: the
`l2m` tests (need `clang` to emit LLVM bitcode) and a few less-common bootstrap variants
(`c2mir-bb-bootstrap-test`, `c2mir-parallel-bootstrap-test`, `c2mir-bootstrap-test4/5`). All 3
build routes now pass with 0 failures on Windows -- the Zig and MSVC/CMake routes both at
6552 passed / 41 skipped of 6593, the MinGW make route at 6514 / 58 of 6572 (it builds a
smaller set of test binaries). The 3 Zig-route-only failures this section used to list were
real bugs, not route quirks, and are fixed:

- `setjmp.c`/`setjmp2.c` (`-ei`): `src/c2mir/x86_64/cx86_64-code.c` registered its corrected
  `setjmp.h` only for `_MSC_VER`, so a MinGW-headers build kept the real header. Against UCRT
  (zig's bundled mingw-w64 headers) that spells the call `__intrinsic_setjmpex`, a name
  `MIR_load_external` does not recognize as setjmp, so the interpreter's special-cased CALL
  never fired. Now registered for every `_WIN32` build.
- `jcall.c` (`-eb -eg`, and `-el`): the Windows lazy-function-generation wrapper
  (`_MIR_get_wrapper`/`_MIR_get_wrapper_end` in `src/mir-x86_64.c`) homed the incoming int args
  into the *caller's* shadow space at `[rsp+8..rsp+0x28)`, which is only where it lands for a
  callee reached by a `call`. `MIR_JCALL` reaches its target with a plain `jmp`, so the r9 slot
  fell one qword past the shadow area -- onto the caller's saved `rbp`. It now spills into a
  frame of its own below the entry `rsp`, like the bb wrapper's `save_pat2` already does.

## Zig (`build.zig`, repo root)

A parallel build added for this fork's overhaul, reaching parity with the tool set the
make/cmake routes produce (libmir static+shared, `c2m`, `mir-bin-run`, `m2b`, `b2m`, `b2ctab`),
installing every test binary it builds to `zig-out/bin` so `scripts/run_tests.py` (see above) can
run the same broad suite against it that make/CMake get. `mir.c`/`mir-gen.c` `#include` their own
per-target file internally (selected by `#ifdef` on the compile target's arch), so `build.zig`
never enumerates per-arch sources — it just compiles `mir.c`/`mir-gen.c`/`c2mir/c2mir.c` as
ordinary C translation units.

Because `c2mir.c`'s `init_include_dirs` only knows `__APPLE__`/`__unix__` default system-header
locations, `build.zig` also derives an `ADDITIONAL_INCLUDE_PATH` define per target the same way
GNUmakefile (mingw-gcc/`xcrun`) and `CMakeLists.txt` (MSVC's `$ENV{INCLUDE}`) do, just from what
Zig itself uses: its own bundled mingw-w64 headers on Windows, the host Xcode SDK via `xcrun` on
macOS, nothing extra on Linux.

`zig build test` (`just zbuild-test`) remains as a fast local smoke check, covering two kinds of
cases:
- Hand-written in `build.zig` itself: readme-example-test, mir2c-test, mir-bin-run-test across
  all 4 dispatch modes, c2mir-simple-test.
- Data-driven from `test/tests.json` (parsed at build-configure time via `addManifestTests` in
  `build.zig`): adt-tests, mir-utility-tests (simplify/scan/io), interp-test1..16,
  gen-test1..16, and the standard-mode `c2m` test suite (via `test/c-tests/runtests.sh`,
  skipped on Windows pending a portable `sh` there). `scripts/check-test-manifest.py` checks
  this manifest's case names against `src/GNUmakefile`'s own targets in CI so the two can't
  silently drift — see `test/README.md`.

CI itself no longer runs `zig build test` — see "Testing (all 3 routes)" above for the
`run_tests.py`-driven suite that replaced it as the authoritative gate.

- **Build (host only)**: `just zbuild`
- **Test (host only)**: `just zbuild-test`
- **Cross-compile all 3 CI platforms** (linux/windows/macos) from one host, into
  `zig-out/<triple>/`: `just zbuild-all` — these binaries can't run on the host, so there's no
  `zbuild-all-test`.
- zig version is pinned in `.mise.toml` (`mise install`).

## Format

`clang-format` (config in `src/.clang-format`, Google-based, 100-col limit, space-before-parens,
right-aligned pointers) — run before committing changes to `.c`/`.h` files.
