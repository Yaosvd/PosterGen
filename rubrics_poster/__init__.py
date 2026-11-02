"""Independent Rubrics poster sample generator."""
import sys
from pathlib import Path

# Prefer this checkout even when launched from another checkout's directory.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if not sys.path or sys.path[0] != str(PROJECT_ROOT):
    sys.path.insert(0, str(PROJECT_ROOT))
