"""Runner script that executes all tests and outputs results."""
import subprocess
import sys

result = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/", "-v"],
    capture_output=True, text=True, cwd=sys.path[0],
)
print(result.stdout)
if result.stderr:
    print("STDERR:", result.stderr[:2000])
sys.exit(result.returncode)
