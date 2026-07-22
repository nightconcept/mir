# MIR
# ⚠ This file is hard-limited to ≤100 lines. Update spokes, not the hub.

## Intent
MIR (**M**edium **I**nternal **R**epresentation) is a lightweight JIT compiler project: a
portable IR plus an interpreter/generator pipeline, a small C11-to-MIR compiler (`c2m`), and
supporting tools (`mir2c`, `m2b`/`b2m`, `b2ctab`).

## Stack
- C (gnu11), built with GNU Make (canonical) or CMake
- Targets: x86_64, aarch64, ppc64le, s390x, riscv64 Linux; x86_64/aarch64 macOS
- `just` (task runner, pinned via `.mise.toml`) wraps the common Make targets

## Essential Commands
- **Commits**: Use Conventional Commits for commit messages
- **Setup**: `mise install` (installs `just`; the C toolchain itself is system-provided)
- **Build**: `just build` (release) / `just debug` (unoptimized)
- **Test**: `just test` (core suite, prints an aggregate pass/total summary) / `just test-all`
  (adds adt/simplify/io/scan/mir2c/l2m tests)
- **Individual suites**: `just adt-test`, `just gen-test`, `just interp-test`,
  `just c2mir-test`, `just c2mir-bootstrap-test` (or `make <target>` directly — see
  `GNUmakefile` for the full list, e.g. `interp-test1..16`, `gen-test1..16`)
- **Bench**: `just bench`
- **Format**: `clang-format` (config in `.clang-format`) — run before committing `.c`/`.h` changes
- **Clean**: `just clean` (removes `out/`) / `just clean-all-tests` (removes `.test-runs/`)

## Repo layout (spokes)
- [CLAUDE.md](CLAUDE.md) — full project overview, JIT pipeline stages, build/test details,
  code style, and porting scope; read this first for anything non-trivial
- [MIR.md](MIR.md) — authoritative reference for the MIR IR format and API; consult before
  touching `mir.c`/`mir.h` or the text/binary I/O format
- [CUSTOM-ALLOCATORS.md](CUSTOM-ALLOCATORS.md) — `MIR_alloc`/`MIR_code_alloc` allocator hooks;
  direct `malloc`/`free`/mmap calls in the core should generally go through these instead
- [HOW-TO-PORT-MIR.md](HOW-TO-PORT-MIR.md) — what's involved in porting MIR to a new target;
  relevant context for any `mir-<target>.*` / `mir-gen-<target>.c` / `c2mir/<target>` work
- `mir-tests/`, `adt-tests/`, `c-tests/`, `c-benchmarks/` — test/bench sources
- `.github/workflows/` — CI (see below)

## CI (this fork)
This fork's `dev` branch is scoped for local/fork-only CI changes not meant to be upstreamed
(diverges from `vnmakarov/mir`). Workflows only trigger on push to `dev` (plus manual
`workflow_dispatch`); upstream's self-hosted-runner workflows (riscv64/s390x/ppc64le/aarch64)
were removed here since this fork has no access to those runners — they'd otherwise hang for
24h and get force-cancelled. `multi-os-test.yml` and `multi-os-bench.yml` are named/labeled for
what they actually run (GitHub-hosted `ubuntu-latest`/`windows-latest` are x86_64,
`macos-latest` is arm64); `apple-aarch64-test.yml` covers Apple Silicon separately.
