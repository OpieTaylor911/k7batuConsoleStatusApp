import sys
sys.path.insert(0, "/home/bcaddy/uconsole-k7bat/plugins")
try:
    import reaver.reaver_ui
    print("OK: reaver module loaded")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
