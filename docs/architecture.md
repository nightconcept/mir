# Architecture

## Project overview

MIR (**M**edium **I**nternal **R**epresentation) is a lightweight JIT compiler project. Core
components (all under `src/`):

- **MIR core** (`src/mir.c`, `src/mir.h`): API for building/reading/writing MIR IR (binary and
  text forms), module loading/linking, interpreter dispatch.
- **MIR interpreter** (`src/mir-interp.c`): included directly into `mir.c` (`#include`), never
  compiled as a separate translation unit.
- **MIR generator / JIT compiler** (`src/mir-gen.c`, `src/mir-gen.h`, plus per-arch
  `src/mir-gen-<target>.c`): the optimizing compiler pipeline from MIR IR to machine code.
- **Per-target machine code** (`src/mir-<target>.c` / `.h`): code shared between interpreter and
  generator for a given target (x86_64, aarch64, ppc64, s390x, riscv64).
- **C2MIR** (`src/c2mir/`): a small C11 compiler to MIR (`c2m` binary). Machine-dependent parts
  live in `src/c2mir/x86_64`, `src/c2mir/aarch64`, `src/c2mir/ppc64`, `src/c2mir/s390x`,
  `src/c2mir/riscv64`.
- **mir2c** (`src/mir2c/`): MIR-to-C compiler (generated C may not be portable).
- **mir-utils** (`src/mir-utils/`): `m2b`/`b2m` (text↔binary MIR conversion), `b2ctab` (binary
  MIR → C byte array).
- Generic containers used throughout: `src/mir-varr.h` (var-length arrays), `src/mir-dlist.h`
  (double-linked lists), `src/mir-bitmap.h`, `src/mir-htab.h` (hash tables), `src/mir-hash.h`
  (hash function), `src/mir-reduce.h` (compression).
- `src/MIR.md` is the authoritative reference for the MIR IR format and API — consult it before
  changing anything in `mir.c`/`mir.h` or the text/binary I/O format.
- `src/CUSTOM-ALLOCATORS.md` documents the `MIR_alloc` / `MIR_code_alloc` custom allocator hooks
  passed to `MIR_init2`; any code doing direct `malloc`/`free`/mmap-style calls in the core
  should generally go through these instead.

## Repo layout

- `src/` — all non-test C sources and the two canonical build files (`src/GNUmakefile`,
  `src/CMakeLists.txt`); see below for why they live here.
- `test/` (repo root, sibling of `src/`) — `mir-tests/`, `adt-tests/`, `c-tests/`,
  `c-benchmarks/`: every test/bench source and fixture, shared by all three build routes (make,
  cmake, zig) so the test set stays uniform across them — see [build.md](build.md) and
  `test/README.md`.
- `build.zig` / `build.zig.zon` (repo root) — the Zig build; reads sources out of `src/` and
  `test/`, but stays at the root like the other build entry points would if they weren't
  parameterized the way GNUmakefile/CMakeLists.txt are (see [build.md](build.md)).
- `.github/workflows/` — CI (see [ci.md](ci.md)).
- `docs/` — this directory; spokes off the root `AGENTS.md` hub.

Why `src/`: this fork is being overhauled (see [branches.md](branches.md)) while still aiming to
produce upstreamable changes to `vnmakarov/mir`, which keeps everything at repo root. Moving all
C sources under `src/` gives this fork room for non-source tooling (Zig build, docs, CI) at the
root without that structure leaking into anything meant to go back upstream.

## JIT compiler pipeline (mir-gen.c)

The generator runs (roughly, see `src/mir-gen.svg`): Simplify → Inline → Build CFG → Build SSA →
Address Transformation → GVN → Copy Propagation → Dead store elimination → DCE → Pressure
relief → SSA combine → Out of SSA → Jump opts → Machinize (target-specific ABI/2-op-insn
lowering) → Find Loops → Build Live Info → Build Register Conflicts → Coalesce → Register
Allocator (priority-based linear scan with live range splitting) → Rewrite → Combine (code
selection) → DCE → Generate Machine Insns (target-specific). Optimization level controls how
much of this pipeline runs (`-O0` through higher levels). Machine-specific behavior for each
pipeline stage that needs target knowledge is implemented in `mir-gen-<target>.c` and included
from `mir-gen.c`.

## Notes on scope

- MIR is only supported/tested on x86_64, aarch64, ppc64le, s390x, riscv64 Linux, and
  x86_64/aarch64 macOS — keep this in mind when writing anything platform-dependent.
- `src/HOW-TO-PORT-MIR.md` describes what's involved in porting MIR to a new target, useful
  context when working on any of the `mir-<target>.*` / `mir-gen-<target>.c` / `c2mir/<target>`
  files.
