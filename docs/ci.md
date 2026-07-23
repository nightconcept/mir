# CI

This fork's CI is scoped for local/fork-only use, not meant to be upstreamed (diverges from
`vnmakarov/mir`, see [branches.md](branches.md) for why). All workflows trigger on push to `dev`
or `mc` (plus manual `workflow_dispatch`); upstream's self-hosted-runner workflows
(riscv64/s390x/ppc64le/aarch64) were removed here since this fork has no access to those
runners — they'd otherwise hang for 24h and get force-cancelled.

- **`make-build.yaml`**: the make/cmake route, on the same 3-platform matrix as `zig-build.yml`
  below (`ubuntu-latest`/`windows-latest` x86_64, `macos-latest` arm64) via `make -C src test`
  (Linux/macOS) or `cmake -S src -B build` + `ctest` (Windows). Also runs a separate `apple-aarch64-test` job on `macos-14` for direct
  Apple Silicon coverage (GitHub's `macos-latest` arm64 runners aren't guaranteed to be Apple
  Silicon specifically). This is a rename+merge of what were previously two files
  (`multi-os-test.yml` + `apple-aarch64-test.yml`) — same triggers/jobs, just consolidated.
- **`zig-build.yml`**: the same 3-platform matrix, running `zig build test` natively per
  platform (not the cross-compiling `zbuild-all` — CI needs to actually execute the tests on
  each runner, and cross-compiled binaries can't run on the host that built them). Also runs
  `scripts/check-test-manifest.py` (non-Windows) first, which fails the job if `test/tests.json`
  (the data `build.zig`'s test step reads — see `test/README.md`) and `src/GNUmakefile`'s own
  targets have drifted apart.
- **`multi-os-bench.yml`**: manual-only (`workflow_dispatch`) performance benchmarks via
  `make bench`, on ubuntu-latest x86_64 and macos-latest arm64. No zig equivalent yet.
