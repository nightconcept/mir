# Code style

- Formatted with `clang-format` (config in `src/.clang-format`, Google-based, 100-col limit,
  space-before-parens, right-aligned pointers). Run `clang-format` before committing changes to
  `.c`/`.h` files.
- C code targets `gnu11`; platform macros in the Makefiles (`mir-<target>.h`) gate
  architecture-specific code — when touching machine-dependent files, changes typically need to
  be mirrored (or explicitly scoped) across all five targets: x86_64, aarch64, ppc64, s390x,
  riscv64.
- Use Conventional Commits for commit messages.
