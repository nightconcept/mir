# zmir

zmir is a fork of [MIR](https://github.com/vnmakarov/mir) — a lightweight, portable Medium
Internal Representation, JIT/interpreter pipeline, and C11-to-MIR compiler (`c2m`) — reworked to
build with [Zig](https://ziglang.org/) as a first-class build route alongside the original GNU
Make and CMake builds.

## Why this fork

The upstream project provides the IR, interpreter/generator, and tools (`mir2c`, `m2b`/`b2m`,
`b2ctab`). zmir keeps that design intact while adding a `build.zig` build route so the project
can be built and cross-compiled with Zig's toolchain, and while tracking a leaner set of build
routes and CI targets. See `AGENTS.md` and `docs/` for details on the current architecture and
branch strategy.

## Building

- `mise install` to pick up pinned tooling (`just`, `zig`)
- `just build` / `just debug` — GNU Make release/debug builds
- `just zbuild` — Zig build (host-only) / `just zbuild-all` — cross-compile all CI platforms
- `just test` / `just test-all` — run the test suites

See `docs/build.md` for the full command reference.

## Credits

zmir is based on [MIR](https://github.com/vnmakarov/mir) by Vladimir Makarov and contributors.
All upstream design and implementation credit belongs to that project; this fork's changes are
the build/tooling overhaul and any zig-specific integration.

## License

MIT — see [LICENSE](LICENSE).
