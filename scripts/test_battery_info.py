#!/usr/bin/env python3
"""Test battery info output."""
import sys
sys.path.insert(0, "/home/bcaddy/uconsole-k7bat/app/plugins")

from battery_diag_ui import get_battery_info

battery_data = get_battery_info()
print("=== Battery Info ===")
for name, data in battery_data.items():
    print(f"\n{name}:")
    for key, value in data.items():
        print(f"  {key}: {value}")
