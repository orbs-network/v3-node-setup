import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Set a temporary BASE_DIR for the tests
if "BASE_DIR" not in os.environ:
    os.environ["BASE_DIR"] = tempfile.mkdtemp(prefix="control-tests-")

