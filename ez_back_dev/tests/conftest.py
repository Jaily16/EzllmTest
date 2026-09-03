import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

TEST_SUPPORT_ROOT = Path(__file__).resolve().parent / "support"
if str(TEST_SUPPORT_ROOT) not in sys.path:
    sys.path.insert(0, str(TEST_SUPPORT_ROOT))
