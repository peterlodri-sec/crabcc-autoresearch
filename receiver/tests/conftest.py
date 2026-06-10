import os
import tempfile

# Must run before any import of main — pytest loads conftest before test files
os.environ["CRABCC_DB"] = tempfile.mktemp(suffix=".db")
