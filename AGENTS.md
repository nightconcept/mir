# MIR
# ⚠ This file is hard-limited to ≤100 lines. Update spokes, not the hub.

## Intent
MIR (**M**edium **I**nternal **R**epresentation) is a lightweight JIT compiler project: a
portable IR plus an interpreter/generator pipeline, a small C11-to-MIR compiler (`c2m`), and
supporting tools (`mir2c`, `m2b`/`b2m`, `b2ctab`). This fork ("zmirc") is overhauling the repo
while aiming to keep changes upstreamable to `vnmakarov/mir` — see
[Branches](docs/branches.md) before assuming what "the repo" is for; behavior differs by branch.

## Stack
- C (gnu11); non-test sources live under `src/`, test/bench sources under `test/`
- Three build routes, all reading out of `src/` and `test/`: GNU Make (canonical, CI uses it),
  CMake, and a parallel Zig build (`build.zig` at repo root) — see [Build & Test](docs/build.md)
- Targets: x86_64, aarch64, ppc64le, s390x, riscv64 Linux; x86_64/aarch64 macOS
- `just` (task runner, pinned via `.mise.toml` along with `zig`) wraps the common Make and Zig
  targets

## Essential Commands
- **Setup**: `mise install` (installs `just`, `zig`; the C toolchain itself is system-provided)
- **Build**: `just build` (release, make) / `just debug` (unoptimized) / `just zbuild` (zig,
  host-only) / `just zbuild-all` (zig, cross-compiles all 3 CI platforms)
- **Test**: `just test` (core suite, make) / `just test-all` (adds adt/simplify/io/scan/mir2c/l2m)
  / `just zbuild-test` (core suite, zig)
- **Bench**: `just bench`
- **Format**: `clang-format` (config in `src/.clang-format`) — run before committing `.c`/`.h`
  changes
- **Clean**: `just clean` (removes `out/`) / `just clean-all-tests` (removes `.test-runs/`)

Full command list (individual test suites, out-of-tree invocations, etc.) is in
[Build & Test](docs/build.md).

## Spoke Index
- [Branches](docs/branches.md) — the `dev` / `mc` / `mir` branch strategy; read this first, it
  determines what kind of change you're making
- [Architecture](docs/architecture.md) — component breakdown, repo layout, why `src/` exists,
  JIT pipeline stages
- [Build & Test](docs/build.md) — full make/cmake/zig commands
- [CI](docs/ci.md) — workflow files and what each covers
- [Code style](docs/code-style.md) — formatting and cross-target change conventions
- [MIR.md](src/MIR.md) — authoritative reference for the MIR IR format and API; consult before
  touching `src/mir.c`/`src/mir.h` or the text/binary I/O format
- [CUSTOM-ALLOCATORS.md](src/CUSTOM-ALLOCATORS.md) — `MIR_alloc`/`MIR_code_alloc` allocator
  hooks; direct `malloc`/`free`/mmap calls in the core should generally go through these instead
- [HOW-TO-PORT-MIR.md](src/HOW-TO-PORT-MIR.md) — what's involved in porting MIR to a new target
