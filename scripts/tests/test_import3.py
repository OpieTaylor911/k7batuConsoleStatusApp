import sys
sys.path.insert(0, "/home/bcaddy/uconsole-k7bat/app")
try:
    from plugins.pineapple_ui import PineappleWindow
    print("Success! PineappleWindow found.")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
