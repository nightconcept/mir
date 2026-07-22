#!/bin/sh
# Run a make test target and print an aggregate pass/total count.
#
# c-tests/runtests.sh's own "Success tests" counter isn't usable for this:
# it increments twice per passing test (once for the stdout match, once for
# stderr), so it doesn't mean "count of tests that passed". Instead, sum the
# "Tests N" totals it prints (once per invocation -- c2mir-test runs it
# several times, once per mode) and derive passes by counting FAIL lines.
set -e

out=$(mktemp)
trap 'rm -f "$out"' EXIT

"$@" 2>&1 | tee "$out"

total=$(grep -oE 'Tests [0-9]+' "$out" | awk '{s+=$2} END {print s+0}')
failed=$(grep -c 'FAIL' "$out")

if [ "$total" -gt 0 ]; then
  printf 'test summary: %d/%d test files passed\n' "$((total - failed))" "$total"
fi
