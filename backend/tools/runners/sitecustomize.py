from pathlib import Path
import sys

TOOLS_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = TOOLS_DIR.parent

for path in [
    BACKEND_DIR,
    TOOLS_DIR,
    TOOLS_DIR / "analysis",
    TOOLS_DIR / "checks",
    TOOLS_DIR / "llm",
    TOOLS_DIR / "runners",
]:
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
