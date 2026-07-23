
cmake_minimum_required (VERSION 3.8)

#set(CMAKE_C_COMPILER "clang-cl")

project ("MIR")

if(NOT DEFINED CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE "RelWithDebInfo")
endif()

#set(CMAKE_VERBOSE_MAKEFILE ON)

if(NOT WIN32)
  add_compile_options(
    $<$<CONFIG:RELEASE>:-O3>
    $<$<CONFIG:RelWithDebInfo>:-O3>
  )
  add_compile_options(-std=gnu11 -Wno-abi -fsigned-char -fPIC)
endif()

include(CheckCCompilerFlag)
if(CMAKE_COMPILER_IS_GNUCC)
  check_c_compiler_flag(-fno-tree-sra NO_TREE_SRA)
  if (NO_TREE_SRA)
    add_compile_options(-fno-tree-sra)
  endif()
  check_c_compiler_flag(-fno-ipa-cp-clone NO_IPA_CP_CLONE)
  if (NO_IPA_CP_CLONE)
    add_compile_options(-fno-ipa-cp-clone)
  endif()
endif()

include(FindThreads)
if(Threads_FOUND)
  link_libraries(${CMAKE_THREAD_LIBS_INIT})
endif()

message("C compiler flags: ${CMAKE_C_FLAGS}")

option(BUILD_TESTING "" ON)
include(CTest)

add_library(mir OBJECT mir.c mir-gen.c c2mir/c2mir.c mir.h mir-gen.h c2mir/c2mir.h)
target_include_directories(mir PRIVATE ${PROJECT_SOURCE_DIR})
if(Threads_FOUND)
  target_compile_definitions(mir PUBLIC "MIR_PARALLEL_GEN")
endif()
if(UNIX)
	target_link_libraries(mir m)
endif()

if(WIN32)
  # MSVC's own CRT/SDK headers (stdio.h, stdlib.h, ...) live wherever vcvarsall
  # set up $ENV{INCLUDE} for this toolchain -- c2mir.c's init_include_dirs only
  # knows __APPLE__/__unix__ default locations, so without this, c2m compiling
  # any C source that includes system headers can't find them. Mirrors
  # GNUmakefile's ADDITIONAL_INCLUDE_PATH handling for the mingw route; the CI
  # workflow runs ilammy/msvc-dev-cmd before configuring so $ENV{INCLUDE} is
  # populated here. c2mir.c's ADDITIONAL_INCLUDE_PATH parsing already expects a
  # ';'-separated list on _WIN32, matching $ENV{INCLUDE}'s own format.
  #
  # This is written to a force-included header rather than passed via
  # target_compile_definitions: the Visual Studio generator re-escapes
  # PreprocessorDefinitions when writing the .vcxproj, which mangles a
  # backslash-heavy path list into an invalid string literal (MSVC C7772).
  # A plain text file isn't subject to that XML/command-line re-escaping.
  if(DEFINED ENV{INCLUDE} AND NOT "$ENV{INCLUDE}" STREQUAL "")
    string(REPLACE "\\" "\\\\" MIR_WIN_INCLUDE_PATH "$ENV{INCLUDE}")
    set(MIR_WIN_INCLUDE_HEADER "${CMAKE_CURRENT_BINARY_DIR}/mir_win_include_path.h")
    file(WRITE "${MIR_WIN_INCLUDE_HEADER}"
         "#define ADDITIONAL_INCLUDE_PATH \"${MIR_WIN_INCLUDE_PATH}\"\n")
    if(MSVC)
      target_compile_options(mir PRIVATE "/FI${MIR_WIN_INCLUDE_HEADER}")
    else()
      target_compile_options(mir PRIVATE -include "${MIR_WIN_INCLUDE_HEADER}")
    endif()
  endif()
endif()

# ------------------ LIBMIR -----------------------
add_library(mir_static STATIC)
target_link_libraries(mir_static PRIVATE mir)

# ------------------ LIBMIR SO --------------------
add_library(mir_shared SHARED)
if(WIN32)
  set_target_properties(mir_shared PROPERTIES WINDOWS_EXPORT_ALL_SYMBOLS TRUE)
endif()
target_link_libraries(mir_shared PRIVATE mir)

# ------------------ C2M --------------------------
add_executable (c2m "c2mir/c2mir-driver.c")
target_include_directories(c2m PRIVATE ${PROJECT_SOURCE_DIR})
target_link_libraries(c2m mir ${CMAKE_DL_LIBS} )

# ------------------ MIR BIN RUN -------------------
# Loads/runs .bmir files via dlopen'd std libs; mirrors GNUmakefile's mir-bin-run
# target (src/mir-bin-run.c) -- scripts/run_tests.py's mir-bin-run-test needs this.
add_executable (mir-bin-run "mir-bin-run.c")
target_include_directories(mir-bin-run PRIVATE ${PROJECT_SOURCE_DIR})
target_link_libraries(mir-bin-run mir ${CMAKE_DL_LIBS})

# ------------------ MIR RUN ----------------------

#add_executable (mir-run "mir-run.c")
#target_include_directories (mir-run PRIVATE ${PROJECT_SOURCE_DIR})
#target_link_libraries(mir-run mir ${CMAKE_DL_LIBS} )

# ------------------ MIR utils --------------------
add_executable (m2b "mir-utils/m2b.c")
target_include_directories(m2b PRIVATE ${PROJECT_SOURCE_DIR})
target_link_libraries(m2b mir)

add_executable (b2m "mir-utils/b2m.c")
target_include_directories(b2m PRIVATE ${PROJECT_SOURCE_DIR})
target_link_libraries(b2m mir)

add_executable (b2ctab "mir-utils/b2ctab.c")
target_include_directories(b2ctab PRIVATE ${PROJECT_SOURCE_DIR})
target_link_libraries(b2ctab mir)

# ------------------ L2M --------------------------
find_package(LLVM)
if(LLVM_FOUND)
  add_executable (l2m "llvm2mir/llvm2mir.c" "llvm2mir/llvm2mir-driver.c" "llvm2mir/llvm2mir.h")
  target_include_directories(l2m PRIVATE ${PROJECT_SOURCE_DIR} ${LLVM_INCLUDE_DIRS})
  target_link_libraries(l2m mir m ${CMAKE_DL_LIBS} LLVM)
endif()

# test/bench fixtures (mir-tests/, adt-tests/, c-benchmarks/) live in a top-level test/ dir,
# a sibling of this CMakeLists.txt's own PROJECT_SOURCE_DIR -- see test/README.md
set(TEST_DIR ${PROJECT_SOURCE_DIR}/../test)

# ------------------ ADT tests --------------------------
add_executable (varr_test "${TEST_DIR}/adt-tests/mir-varr-test.c")
target_include_directories(varr_test PRIVATE ${PROJECT_SOURCE_DIR})

add_executable (dlist_test "${TEST_DIR}/adt-tests/mir-dlist-test.c")
target_include_directories(dlist_test PRIVATE ${PROJECT_SOURCE_DIR})

add_executable (bitmap_test "${TEST_DIR}/adt-tests/mir-bitmap-test.c")
target_include_directories(bitmap_test PRIVATE ${PROJECT_SOURCE_DIR})

add_executable (htab_test "${TEST_DIR}/adt-tests/mir-htab-test.c")
target_include_directories(htab_test PRIVATE ${PROJECT_SOURCE_DIR})

add_executable (reduce_test "${TEST_DIR}/adt-tests/mir-reduce-test.c")
target_include_directories(reduce_test PRIVATE ${PROJECT_SOURCE_DIR})

add_test(varr-test varr_test)
add_test(dlist-test dlist_test)
add_test(bitmap-test bitmap_test)
add_test(htab-test htab_test)
add_test(reduce-test reduce_test ${PROJECT_SOURCE_DIR}/c2mir/c2mir.c)

# ------------------ MIR utility tests ------------------------
add_executable (simplify_test "${TEST_DIR}/mir-tests/simplify.c")
target_link_libraries(simplify_test mir)

add_executable (scan_test "${TEST_DIR}/mir-tests/scan-test.c")
target_link_libraries(scan_test mir)

add_executable (io_test "${TEST_DIR}/mir-tests/io.c")
target_link_libraries(io_test mir)

add_test(simplify-test simplify_test)
add_test(scan-test scan_test)
add_test(io-test io_test)

# ------------------ Common for MIR tests ----------------------
add_executable (run_test "${TEST_DIR}/mir-tests/run-test.c")
target_include_directories(run_test PRIVATE ${PROJECT_SOURCE_DIR})
target_link_libraries(run_test mir)

# ------------------ MIR interp tests --------------------------
add_executable (interp_loop "${TEST_DIR}/mir-tests/loop-interp.c")
target_include_directories(interp_loop PRIVATE ${PROJECT_SOURCE_DIR})
target_compile_definitions(interp_loop PRIVATE MIR_INTERP_DEBUG=1)
target_link_libraries(interp_loop mir)

add_executable (interp_loop_c "${TEST_DIR}/mir-tests/loop-interp.c")
target_include_directories(interp_loop_c PRIVATE ${PROJECT_SOURCE_DIR})
target_compile_definitions(interp_loop_c PRIVATE MIR_INTERP_DEBUG=1 MIR_C_INTERFACE=1)
target_link_libraries(interp_loop_c mir)

add_executable (interp_sieve "${TEST_DIR}/mir-tests/sieve-interp.c")
target_include_directories(interp_sieve PRIVATE ${PROJECT_SOURCE_DIR})
target_compile_definitions(interp_sieve PRIVATE MIR_INTERP_DEBUG=1)
target_link_libraries(interp_sieve mir)

add_executable (interp_sieve_c "${TEST_DIR}/mir-tests/sieve-interp.c")
target_include_directories(interp_sieve_c PRIVATE ${PROJECT_SOURCE_DIR})
target_compile_definitions(interp_sieve_c PRIVATE MIR_INTERP_DEBUG=1 MIR_C_INTERFACE=1)
target_link_libraries(interp_sieve_c mir)

add_executable (interp_hi "${TEST_DIR}/mir-tests/hi-interp.c")
target_include_directories(interp_hi PRIVATE ${PROJECT_SOURCE_DIR})
target_compile_definitions(interp_hi PRIVATE MIR_INTERP_DEBUG=1)
target_link_libraries(interp_hi mir)

add_executable (interp_args "${TEST_DIR}/mir-tests/args-interp.c")
target_include_directories(interp_args PRIVATE ${PROJECT_SOURCE_DIR})
target_link_libraries(interp_args mir)

add_executable (interp_args_c "${TEST_DIR}/mir-tests/args-interp.c")
target_include_directories(interp_args_c PRIVATE ${PROJECT_SOURCE_DIR})
target_compile_definitions(interp_args_c PRIVATE MIR_C_INTERFACE=1)
target_link_libraries(interp_args_c mir)

add_executable (run_test_d "${TEST_DIR}/mir-tests/run-test.c")
target_include_directories(run_test_d PRIVATE ${PROJECT_SOURCE_DIR})
target_compile_definitions(run_test_d PRIVATE TEST_GEN_DEBUG=1)
target_link_libraries(run_test_d mir)

add_test(interp-test1 interp_loop)
add_test(interp-test2 interp_loop_c)
add_test(interp-test3 interp_sieve)
add_test(interp-test4 interp_sieve_c)
add_test(interp-test5 interp_hi)
add_test(interp-test6 interp_args)
add_test(interp-test7 interp_args_c)

foreach (num 8 9 10)
  add_test(interp-test${num} run_test -i ${TEST_DIR}/mir-tests/test${num}.mir)
endforeach()

if(NOT WIN32)
  add_test(interp-test11 run_test -i ${TEST_DIR}/mir-tests/test11.mir) # for long double >= 10 bytes
  add_test(interp-test12 run_test -i ${TEST_DIR}/mir-tests/test12.mir) # multiple return values
endif()

foreach (num 13 14 15 16)
  add_test(interp-test${num} run_test -i ${TEST_DIR}/mir-tests/test${num}.mir)
endforeach()

# ------------------ MIR gen tests --------------------------

foreach (num 1 2 3 4 5 6 7)
  add_test(gen-test${num} run_test -d ${TEST_DIR}/mir-tests/test${num}.mir)
endforeach()

foreach (num 8 9 10)
  add_test(gen-test${num} run_test -g ${TEST_DIR}/mir-tests/test${num}.mir)
endforeach()

if(NOT WIN32)
  add_test(gen-test11 run_test -g ${TEST_DIR}/mir-tests/test11.mir) # for long double >= 10 bytes
  add_test(gen-test12 run_test -g ${TEST_DIR}/mir-tests/test12.mir) # multiple return values
endif()

foreach (num 13 14 15 16)
  add_test(gen-test${num} run_test -g ${TEST_DIR}/mir-tests/test${num}.mir)
endforeach()

add_executable (gen_loop "${TEST_DIR}/mir-tests/loop-sieve-gen.c")
target_include_directories(gen_loop PRIVATE ${PROJECT_SOURCE_DIR})
target_compile_definitions(gen_loop PRIVATE TEST_GEN_DEBUG=1 TEST_GEN_LOOP)
target_link_libraries(gen_loop mir)

add_executable (gen_sieve "${TEST_DIR}/mir-tests/loop-sieve-gen.c")
target_include_directories(gen_sieve PRIVATE ${PROJECT_SOURCE_DIR})
target_compile_definitions(gen_sieve PRIVATE TEST_GEN_DEBUG=1 TEST_GEN_SIEVE)
target_link_libraries(gen_sieve mir)

add_test(gen-test-loop gen_loop)
add_test(gen-test-sieve gen_sieve)

# scripts/run_tests.py's broad suite also exercises these two GNUmakefile gen-test
# targets (gen-issue219-test, gen-test-get-thunk-addr); named to match its binary names.
add_executable (issue219 "${TEST_DIR}/mir-tests/issue219.c")
target_include_directories(issue219 PRIVATE ${PROJECT_SOURCE_DIR})
target_compile_definitions(issue219 PRIVATE TEST_GEN_DEBUG=1 TEST_GEN_SIEVE)
target_link_libraries(issue219 mir)

add_executable (gen-get-thunk-addr-test "${TEST_DIR}/mir-tests/get-thunk-addr.c")
target_include_directories(gen-get-thunk-addr-test PRIVATE ${PROJECT_SOURCE_DIR})
target_link_libraries(gen-get-thunk-addr-test mir)

add_test(gen-issue219-test issue219)
add_test(gen-test-get-thunk-addr gen-get-thunk-addr-test)

# ------------------ readme example test ----------------

add_executable (readme_example "${TEST_DIR}/mir-tests/readme-example.c")
target_include_directories(readme_example PRIVATE ${PROJECT_SOURCE_DIR})
target_link_libraries(readme_example mir)

add_test(readme-example-test readme_example)

# ------------------ mir2c test -------------------------

add_executable (mir2c_test "mir2c/mir2c.c")
target_include_directories(mir2c_test PRIVATE ${PROJECT_SOURCE_DIR} ${TEST_DIR})
target_compile_definitions(mir2c_test PRIVATE TEST_MIR2C)
target_link_libraries(mir2c_test mir)

add_test(mir2c-test mir2c_test)

# ------------------ c2m tests --------------------------

add_test(c2mir-simple-test c2m -v ${PROJECT_SOURCE_DIR}/sieve.c -ei)

