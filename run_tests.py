#!/usr/bin/env python
"""测试运行脚本"""

import sys
import subprocess

# 运行测试
test_file = sys.argv[1] if len(sys.argv) > 1 else "tests/test_core/test_event_bus.py"

result = subprocess.run(
    [sys.executable, "-m", "pytest", test_file, "-v", "--tb=short"],
    cwd="e:/VScode(study)/Project/AI-Novels",
    capture_output=True,
    text=True
)

print("=== STDOUT ===")
print(result.stdout)
print("=== STDERR ===")
print(result.stderr)
print("=== EXIT CODE ===")
print(result.returncode)
