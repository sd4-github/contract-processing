import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FLASK_ROOT = PROJECT_ROOT / "flask"
for path in (FLASK_ROOT, PROJECT_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
