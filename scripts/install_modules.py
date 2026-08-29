#!/usr/bin/env python3
"""Install Hak5 Pineapple modules to active directory."""
import shutil
from pathlib import Path

src_dir = Path("/home/bcaddy/uconsole-k7bat/pineapple-modules")
dst_dir = Path("/home/bcaddy/uconsole-k7bat/pineapple_modules")

copied_count = 0

for module_dir in src_dir.iterdir():
    if module_dir.is_dir() and not module_dir.name.startswith("."):
        projects_dir = module_dir / "projects"
        if projects_dir.exists():
            for proj_dir in projects_dir.iterdir():
                if proj_dir.is_dir():
                    src = proj_dir / "src"
                    dst = dst_dir / module_dir.name
                    module_json = src / "module.json"
                    module_py = src / "module.py"
                    if module_json.exists() and module_py.exists():
                        print(f"Copying {module_dir.name}...")
                        try:
                            shutil.copytree(src, dst)
                            print(f"  Done: {dst}")
                            copied_count += 1
                        except Exception as e:
                            print(f"  Error: {e}")

print(f"\nTotal modules copied: {copied_count}")
