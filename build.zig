const std = @import("std");

// Zig build for MIR, parallel to the canonical GNUmakefile / CMakeLists.txt
// routes (both of which now live under src/, see CLAUDE.md). All C sources
// stay in src/ untouched -- this file only orchestrates the compiler.
//
// mir.c and mir-gen.c #include their own per-target file internally
// (mir-<target>.c / mir-gen-<target>.c, selected by #ifdef on the compile
// target's arch), so, like the Makefile/CMake builds, we compile them as
// single translation units and never need to enumerate per-arch sources here.

const cflags: []const []const u8 = &.{
    "-std=gnu11",
    "-fsigned-char",
};

fn addCoreModule(b: *std.Build, target: std.Build.ResolvedTarget, optimize: std.builtin.OptimizeMode) *std.Build.Module {
    const mod = b.createModule(.{
        .target = target,
        .optimize = optimize,
        .link_libc = true,
        .sanitize_c = .off,
    });
    mod.addIncludePath(b.path("src"));
    mod.addCSourceFiles(.{
        .root = b.path("src"),
        .files = &.{ "mir.c", "mir-gen.c", "c2mir/c2mir.c" },
        .flags = cflags,
    });
    return mod;
}

// ---- data-driven test cases, shared with GNUmakefile via test/tests.json ----
// (see test/README.md; scripts/check-test-manifest.py diffs the manifest's names against
// GNUmakefile's own targets so the two lists can't silently drift apart)

const AdtOrUtilityCase = struct {
    name: []const u8,
    source: []const u8,
    run_args: []const []const u8 = &.{},
};

const DefineCase = struct {
    name: []const u8,
    source: []const u8,
    defines: []const []const u8 = &.{},
};

const RunTestMirCase = struct {
    name: []const u8,
    flag: []const u8,
    fixture: []const u8,
    skip_on_windows: bool = false,
};

const C2mirRuntestsCase = struct {
    name: []const u8,
    mode_file: []const u8,
};

const TestManifest = struct {
    adt_tests: []const AdtOrUtilityCase,
    mir_utility_tests: []const AdtOrUtilityCase,
    interp_tests: []const DefineCase,
    gen_tests: []const DefineCase,
    run_test_mir_cases: []const RunTestMirCase,
    c2mir_runtests: []const C2mirRuntestsCase,
};

fn addManifestTestExe(
    b: *std.Build,
    target: std.Build.ResolvedTarget,
    optimize: std.builtin.OptimizeMode,
    core_lib: ?*std.Build.Step.Compile,
    name: []const u8,
    source: []const u8,
    defines: []const []const u8,
) *std.Build.Step.Compile {
    const mod = b.createModule(.{ .target = target, .optimize = optimize, .link_libc = true, .sanitize_c = .off });
    mod.addIncludePath(b.path("src"));
    mod.addIncludePath(b.path("test"));
    const define_flags = b.allocator.alloc([]const u8, defines.len) catch @panic("OOM");
    for (defines, 0..) |d, i| define_flags[i] = b.fmt("-D{s}", .{d});
    const flags = std.mem.concat(b.allocator, []const u8, &.{ cflags, define_flags }) catch @panic("OOM");
    mod.addCSourceFiles(.{ .root = b.path("test"), .files = &.{source}, .flags = flags });
    if (core_lib) |core| mod.linkLibrary(core);
    return b.addExecutable(.{ .name = name, .root_module = mod });
}

// Reads test/tests.json and emits the Run steps it describes into test_step, reaching parity
// with the corresponding subset of GNUmakefile's test-all targets (adt-tests, mir-utility-tests,
// interp-test1..16, gen-test1..16, and the standard-mode c2m runtests.sh suites). Deliberately
// NOT full parity yet: the -O0/-O1/-O3 runtests.sh variants and the 6 c2mir-bootstrap
// self-compile tests aren't covered (bootstrap needs recompiling MIR's own sources through c2m
// mid-build, real new plumbing rather than another manifest entry -- left as follow-up).
fn addManifestTests(
    b: *std.Build,
    target: std.Build.ResolvedTarget,
    optimize: std.builtin.OptimizeMode,
    core_lib: *std.Build.Step.Compile,
    c2m: *std.Build.Step.Compile,
    test_step: *std.Build.Step,
) void {
    const data = b.build_root.handle.readFileAlloc(b.graph.io, "test/tests.json", b.allocator, .limited(1 << 20)) catch |err| {
        std.debug.panic("failed to read test/tests.json: {t}", .{err});
    };
    // intentionally never deinit'd: build.zig is a one-shot process and the parsed strings are
    // referenced by build steps for the lifetime of the run.
    const parsed = std.json.parseFromSlice(TestManifest, b.allocator, data, .{ .ignore_unknown_fields = true }) catch |err| {
        std.debug.panic("failed to parse test/tests.json: {t}", .{err});
    };
    const manifest = parsed.value;
    const is_windows = target.result.os.tag == .windows;

    for (manifest.adt_tests) |case| {
        const exe = addManifestTestExe(b, target, optimize, null, case.name, case.source, &.{});
        const run = b.addRunArtifact(exe);
        for (case.run_args) |arg| run.addFileArg(b.path(arg));
        test_step.dependOn(&run.step);
    }

    for (manifest.mir_utility_tests) |case| {
        const exe = addManifestTestExe(b, target, optimize, core_lib, case.name, case.source, &.{});
        const run = b.addRunArtifact(exe);
        test_step.dependOn(&run.step);
    }

    for (manifest.interp_tests) |case| {
        const exe = addManifestTestExe(b, target, optimize, core_lib, case.name, case.source, case.defines);
        const run = b.addRunArtifact(exe);
        test_step.dependOn(&run.step);
    }

    for (manifest.gen_tests) |case| {
        const exe = addManifestTestExe(b, target, optimize, core_lib, case.name, case.source, case.defines);
        const run = b.addRunArtifact(exe);
        test_step.dependOn(&run.step);
    }

    // run_test_mir_cases all share one run-test executable (mir-tests/run-test.c), invoked
    // repeatedly with different dispatch flags and .mir fixtures, matching GNUmakefile.
    const run_test_exe = addManifestTestExe(b, target, optimize, core_lib, "run-test", "mir-tests/run-test.c", &.{});
    for (manifest.run_test_mir_cases) |case| {
        if (case.skip_on_windows and is_windows) continue;
        const run = b.addRunArtifact(run_test_exe);
        run.addArg(case.flag);
        run.addFileArg(b.path(b.fmt("test/mir-tests/{s}", .{case.fixture})));
        test_step.dependOn(&run.step);
    }

    // c2mir_runtests: standard-mode c-tests suite via runtests.sh, skipped on Windows pending a
    // portable `sh` there (see test/tests.json's _c2mir_runtests_comment).
    if (!is_windows) {
        for (manifest.c2mir_runtests) |case| {
            const run = b.addSystemCommand(&.{"sh"});
            run.addFileArg(b.path("test/c-tests/runtests.sh"));
            run.addFileArg(b.path(b.fmt("test/c-tests/{s}", .{case.mode_file})));
            run.addArtifactArg(c2m);
            test_step.dependOn(&run.step);
        }
    }
}

fn addTool(
    b: *std.Build,
    target: std.Build.ResolvedTarget,
    optimize: std.builtin.OptimizeMode,
    core_lib: *std.Build.Step.Compile,
    name: []const u8,
    files: []const []const u8,
) *std.Build.Step.Compile {
    const mod = b.createModule(.{
        .target = target,
        .optimize = optimize,
        .link_libc = true,
        .sanitize_c = .off,
    });
    mod.addIncludePath(b.path("src"));
    mod.addCSourceFiles(.{ .root = b.path("src"), .files = files, .flags = cflags });
    mod.linkLibrary(core_lib);
    return b.addExecutable(.{ .name = name, .root_module = mod });
}

pub fn build(b: *std.Build) void {
    const target = b.standardTargetOptions(.{});
    const optimize = b.standardOptimizeOption(.{});

    // ---- libmir (static + shared), matching CMakeLists.txt's mir_static/mir_shared ----
    const mir_static = b.addLibrary(.{
        .name = "mir",
        .linkage = .static,
        .root_module = addCoreModule(b, target, optimize),
    });
    b.installArtifact(mir_static);

    const mir_shared = b.addLibrary(.{
        .name = "mir",
        .linkage = .dynamic,
        .root_module = addCoreModule(b, target, optimize),
    });
    b.installArtifact(mir_shared);

    // ---- tools that link against libmir, matching GNUmakefile's C2M/M2B/B2M/B2CTAB/MIR_RUN ----
    const c2m = addTool(b, target, optimize, mir_static, "c2m", &.{"c2mir/c2mir-driver.c"});
    b.installArtifact(c2m);

    const mir_bin_run = addTool(b, target, optimize, mir_static, "mir-bin-run", &.{"mir-bin-run.c"});
    b.installArtifact(mir_bin_run);

    const m2b = addTool(b, target, optimize, mir_static, "m2b", &.{"mir-utils/m2b.c"});
    b.installArtifact(m2b);

    const b2m = addTool(b, target, optimize, mir_static, "b2m", &.{"mir-utils/b2m.c"});
    b.installArtifact(b2m);

    const b2ctab = addTool(b, target, optimize, mir_static, "b2ctab", &.{"mir-utils/b2ctab.c"});
    b.installArtifact(b2ctab);

    // ---- mir2c-test, matching CMakeLists.txt's mir2c_test / GNUmakefile's mir2c-test ----
    // (mir2c.c is a TEST_MIR2C-guarded self-test, not a standalone CLI tool -- see mir2c/mir2c.c)
    // it quote-includes test/mir-tests/{scan-sieve,scan-hi}.h, hence the extra include path.
    const mir2c_test_mod = b.createModule(.{ .target = target, .optimize = optimize, .link_libc = true, .sanitize_c = .off });
    mir2c_test_mod.addIncludePath(b.path("src"));
    mir2c_test_mod.addIncludePath(b.path("test"));
    mir2c_test_mod.addCSourceFiles(.{
        .root = b.path("src"),
        .files = &.{ "mir.c", "mir2c/mir2c.c" },
        .flags = cflags ++ &[_][]const u8{"-DTEST_MIR2C"},
    });
    const mir2c_test = b.addExecutable(.{ .name = "mir2c-test", .root_module = mir2c_test_mod });

    // ---- readme-example-test, matching GNUmakefile's readme-example-test ----
    // readme-example.c lives in test/mir-tests/ (sibling of src/, see test/README.md), not src/.
    const readme_mod = b.createModule(.{ .target = target, .optimize = optimize, .link_libc = true, .sanitize_c = .off });
    readme_mod.addIncludePath(b.path("src"));
    readme_mod.addCSourceFiles(.{
        .root = b.path("src"),
        .files = &.{ "mir.c", "mir-gen.c" },
        .flags = cflags,
    });
    readme_mod.addCSourceFiles(.{
        .root = b.path("test/mir-tests"),
        .files = &.{"readme-example.c"},
        .flags = cflags,
    });
    const readme_example_test = b.addExecutable(.{ .name = "readme-example-test", .root_module = readme_mod });

    // ---- test step: parity subset of `make test` (readme-example-test, mir-bin-run-test, c2mir-simple-test) ----
    const test_step = b.step("test", "Run the core test suite (readme-example, mir-bin-run, c2mir-simple)");

    const run_readme = b.addRunArtifact(readme_example_test);
    test_step.dependOn(&run_readme.step);

    const run_mir2c_test = b.addRunArtifact(mir2c_test);
    test_step.dependOn(&run_mir2c_test.step);

    // mir-bin-run-test: compile src/sieve.c to MIR bytecode via c2m, then run it
    // under mir-bin-run in each of its dispatch modes (default/interp/gen/lazy),
    // matching GNUmakefile's mir-bin-run-test.
    const compile_sieve = b.addRunArtifact(c2m);
    compile_sieve.addArg("-c");
    compile_sieve.addFileArg(b.path("src/sieve.c"));
    compile_sieve.addArg("-o");
    const sieve_bmir = compile_sieve.addOutputFileArg("sieve.bmir");

    const mir_types = [_]?[]const u8{ null, "interp", "gen", "lazy" };
    for (mir_types) |mir_type| {
        const run = b.addRunArtifact(mir_bin_run);
        run.addFileArg(sieve_bmir);
        run.addArg("sieve.bmir");
        if (mir_type) |t| run.setEnvironmentVariable("MIR_TYPE", t);
        test_step.dependOn(&run.step);
    }

    // c2mir-simple-test: run sieve.c through c2m's interpreter directly.
    const c2mir_simple_test = b.addRunArtifact(c2m);
    c2mir_simple_test.addArg("-v");
    c2mir_simple_test.addFileArg(b.path("src/sieve.c"));
    c2mir_simple_test.addArg("-ei");
    test_step.dependOn(&c2mir_simple_test.step);

    // adt-tests, mir-utility-tests, interp/gen tests, and the standard c2m runtests.sh suites,
    // all data-driven from test/tests.json -- see addManifestTests's doc comment for what's
    // still missing to reach full parity with `make test-all`.
    addManifestTests(b, target, optimize, mir_static, c2m, test_step);
}
