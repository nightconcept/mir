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
    const mir2c_test_mod = b.createModule(.{ .target = target, .optimize = optimize, .link_libc = true, .sanitize_c = .off });
    mir2c_test_mod.addIncludePath(b.path("src"));
    mir2c_test_mod.addCSourceFiles(.{
        .root = b.path("src"),
        .files = &.{ "mir.c", "mir2c/mir2c.c" },
        .flags = cflags ++ &[_][]const u8{"-DTEST_MIR2C"},
    });
    const mir2c_test = b.addExecutable(.{ .name = "mir2c-test", .root_module = mir2c_test_mod });

    // ---- readme-example-test, matching GNUmakefile's readme-example-test ----
    const readme_mod = b.createModule(.{ .target = target, .optimize = optimize, .link_libc = true, .sanitize_c = .off });
    readme_mod.addIncludePath(b.path("src"));
    readme_mod.addCSourceFiles(.{
        .root = b.path("src"),
        .files = &.{ "mir.c", "mir-gen.c", "mir-tests/readme-example.c" },
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
}
