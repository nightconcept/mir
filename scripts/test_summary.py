"""Aggregate pass/total accounting for c-tests/runtests.sh output.

c-tests/runtests.sh's own "Success tests" counter isn't usable for this: it
increments twice per passing test (once for the stdout match, once for
stderr), so it doesn't mean "count of tests that passed". Instead, sum the
"Tests N" totals it prints (once per invocation -- c2mir-test runs it several
times, once per mode) and derive passes by counting FAIL lines.
"""

import re
from typing import Optional


def summarize(output: str) -> Optional[str]:
    total = sum(int(n) for n in re.findall(r"Tests (\d+)", output))
    failed = len(re.findall(r"\bFAIL\b", output))
    if total:
        return f"test summary: {total - failed}/{total} test files passed"
    return None
