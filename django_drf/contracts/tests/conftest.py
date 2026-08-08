import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DJANGO_ROOT = PROJECT_ROOT / "django_drf"
for path in (DJANGO_ROOT, PROJECT_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
