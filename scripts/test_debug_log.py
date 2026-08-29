import sys
sys.path.insert(0, "/home/bcaddy/uconsole-k7bat/app")
from pathlib import Path

USER_APP_DIR = Path("/home/bcaddy/uconsole-k7bat")
DEBUG_LOG = USER_APP_DIR / "pineapple_debug.log"
DEBUG_LOG.parent.mkdir(parents=True, exist_ok=True)
DEBUG_LOG.write_text("Test log entry\n", encoding="utf-8")

# Verify
print(f"Log file: {DEBUG_LOG}")
print(f"Content:\n{DEBUG_LOG.read_text()}")
