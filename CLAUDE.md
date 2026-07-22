# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

MIR (**M**edium **I**nternal **R**epresentation) is a lightweight JIT compiler
project. Core components:

- **MIR core** (`mir.c`, `mir.h`): API for building/reading/writing MIR IR (binary and
  text forms), module loading/linking, interpreter dispatch.
- **MIR interpreter** (`mir-interp.c`): included directly into `mir.c` (`#include`), never
  compiled as a separate translation unit.
- **MIR generator / JIT compiler** (`mir-gen.c`, `mir-gen.h`, plus per-arch
  `mir-gen-<target>.c`): the optimizing compiler pipeline from MIR IR to machine code.
- **Per-target machine code** (`mir-<target>.c` / `.h`): code shared between interpreter and
  generator for a given target (x86_64, aarch64, ppc64, s390x, riscv64).
- **C2MIR** (`c2mir/`): a small C11 compiler to MIR (`c2m` binary). Machine-dependent parts
  live in `c2mir/x86_64`, `c2mir/aarch64`, `c2mir/ppc64`, `c2mir/s390x`, `c2mir/riscv64`.
- **mir2c** (`mir2c/`): MIR-to-C compiler (generated C may not be portable).
- **mir-utils**: `m2b`/`b2m` (text↔binary MIR conversion), `b2ctab` (binary MIR → C byte array).
- Generic containers used throughout: `mir-varr.h` (var-length arrays), `mir-dlist.h`
  (double-linked lists), `mir-bitmap.h`, `mir-htab.h` (hash tables), `mir-hash.h` (hash
  function), `mir-reduce.h` (compression).
- `MIR.md` is the authoritative reference for the MIR IR format and API — consult it before
  changing anything in `mir.c`/`mir.h` or the text/binary I/O format.
- `CUSTOM-ALLOCATORS.md` documents the `MIR_alloc` / `MIR_code_alloc` custom allocator hooks
  passed to `MIR_init2`; any code doing direct `malloc`/`free`/mmap-style calls in the core
  should generally go through these instead.

## JIT compiler pipeline (mir-gen.c)

The generator runs (roughly, see `mir-gen.svg`): Simplify → Inline → Build CFG → Build SSA →
Address Transformation → GVN → Copy Propagation → Dead store elimination → DCE → Pressure
relief → SSA combine → Out of SSA → Jump opts → Machinize (target-specific ABI/2-op-insn
lowering) → Find Loops → Build Live Info → Build Register Conflicts → Coalesce → Register
Allocator (priority-based linear scan with live range splitting) → Rewrite → Combine (code
selection) → DCE → Generate Machine Insns (target-specific). Optimization level controls how
much of this pipeline runs (`-O0` through higher levels). Machine-specific behavior for each
pipeline stage that needs target knowledge is implemented in `mir-gen-<target>.c` and included
from `mir-gen.c`.

## Build

Two build systems are supported; the GNU Makefile is the primary/canonical one (CI uses it).

```sh
make                 # release build (optimized) in-tree
make debug            # unoptimized debug build
make SRC_DIR=<src> -f <src>/GNUmakefile   # build out-of-tree; use identical SRC_DIR/-f on every invocation
make PREFIX=/usr install
make clean            # remove all build/test/bench artifacts
```

CMake is also available (`CMakeLists.txt`), with `BUILD_TESTING` option (default ON).

## Testing

```sh
make test             # core test suite: readme-example-test, mir-bin-run-test, c2mir-test
make test-all         # test plus adt-test, simplify-test, io-test, scan-test, mir2c-test, l2m-test
make bench            # interp/gen/io/mir2c/c2mir benchmarks
```

Individual test targets can be run directly, e.g.:

```sh
make adt-test         # varr-test dlist-test bitmap-test htab-test reduce-test
make gen-test         # generator tests (gen-test1 .. gen-testN, gen-test-loop, gen-test-sieve, ...)
make interp-test      # interpreter tests (interp-test1 .. interp-test16)
make c2mir-test       # c2mir-simple-test, c2mir-full-test, c2mir-interp-test, c2mir-gen-test
make c2mir-bootstrap-test   # c2m compiling itself
```

Test/bench sources live in `mir-tests/` (interpreter/generator/API tests, `.mir` text fixtures),
`adt-tests/` (container tests), `c-tests/` and `c-benchmarks/` (C programs run through `c2m`).

`csmith-c2m.sh` / `csmith-c2m-gcc.sh` are used for csmith-based fuzz testing of `c2m` against gcc.

## Code style

- Formatted with `.clang-format` (Google-based, 100-col limit, space-before-parens, right-aligned
  pointers). Run `clang-format` before committing changes to `.c`/`.h` files.
- C code targets `gnu11`; platform macros in the Makefiles (`mir-<target>.h`) gate
  architecture-specific code — when touching machine-dependent files, changes typically need to
  be mirrored (or explicitly scoped) across all five targets: x86_64, aarch64, ppc64, s390x,
  riscv64.

## Notes on scope

- MIR is only supported/tested on x86_64, aarch64, ppc64le, s390x, riscv64 Linux, and
  x86_64/aarch64 macOS — keep this in mind when writing anything platform-dependent.
- `HOW-TO-PORT-MIR.md` describes what's involved in porting MIR to a new target, useful context
  when working on any of the `mir-<target>.*` / `mir-gen-<target>.c` / `c2mir/<target>` files.
