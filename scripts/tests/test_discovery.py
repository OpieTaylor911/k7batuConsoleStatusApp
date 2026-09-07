#!/usr/bin/env python3
import json
from pathlib import Path

full_repo_dir = Path("/home/bcaddy/uconsole-k7bat/app/pineapple-modules-full")
all_modules = []

for item in full_repo_dir.iterdir():
    if item.is_dir():
        projects_dir = item / "projects"
        if projects_dir.exists():
            for project_dir in projects_dir.iterdir():
                if project_dir.is_dir():
                    module_json = project_dir / "src" / "module.json"
                    if module_json.exists():
                        with open(module_json) as f:
                            meta = json.load(f)
                            all_modules.append({"name": item.name, "title": meta.get("title", item.name)})
print(f"Total modules: {len(all_modules)}")
