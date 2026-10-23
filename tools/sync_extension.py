"""Copy the shared live overlay into the extension folder (run after editing web/guard-overlay.js)."""
import shutil
from pathlib import Path

root = Path(__file__).resolve().parent.parent
shutil.copyfile(root / "web" / "guard-overlay.js", root / "extension" / "guard-overlay.js")
print("extension/guard-overlay.js updated")
