import os
import tempfile

# Must run before any import of main — pytest loads conftest before test files
fd, _tmp_db = tempfile.mkstemp(suffix=".db")
os.close(fd)
os.environ["CRABCC_DB"] = _tmp_db
