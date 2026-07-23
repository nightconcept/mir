# Branch strategy

This fork's goal depends on which branch you're looking at — check `git branch --show-current`
before assuming what "the repo" is for.

- **`master`** — tracks upstream `vnmakarov/mir` directly. Not a working branch.
- **`dev`** — active development branch for this fork's overhaul (the "zmirc"/`src/`-move/Zig-build
  work; see [architecture.md](architecture.md), [build.md](build.md)). CI-scoped changes not
  meant to be upstreamed live here too (see [ci.md](ci.md)). Expect this branch to diverge from
  upstream more than any other.
- **`mc`** — the branch a downstream project points to for consuming MIR. Treat changes here as
  needing to stay usable/stable for that consumer, not just convenient for this fork's own
  development.
- **`mir`** (planned, not yet created) — will be kept close to upstream `vnmakarov/mir` (minimal
  divergence, no fork-local restructuring/rebrand/CI changes) so that fixes and features
  developed here can be cleanly cherry-picked or PR'd upstream. When creating it, branch from
  current `master` rather than `dev`/`mc`, and keep it that way — don't let `src/`-move or
  Zig-build changes land on it.

## Practical implications

- Before making a change, ask: does this belong on `dev` only (fork-local tooling/CI/restructure),
  does it need to also reach `mc` (the downstream consumer needs it), or is it a genuine
  upstream-quality fix/feature that should eventually go out via `mir`?
- Changes intended for upstream should be written as if `src/`'s C sources were still at repo
  root (i.e. as clean, minimal diffs against `vnmakarov/mir`'s layout) — the `src/` move,
  `build.zig`, and the CI split are fork-local scaffolding, not something upstream wants.
