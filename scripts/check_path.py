from pathlib import Path

p = Path("/home/bcaddy/uconsole-k7bat/plugins")
print(f"Path: {p}")
print(f"Exists: {p.exists()}")
if p.exists():
    print("Contents:", list(p.glob("*.py")))
