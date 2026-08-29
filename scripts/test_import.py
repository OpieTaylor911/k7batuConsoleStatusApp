import sys
sys.path.insert(0, "/home/bcaddy/uconsole-k7bat/app/plugins")
try:
    import pineapple_ui
    print("USER_APP_DIR:", pineapple_ui.USER_APP_DIR)
    print("ACTIVE_MODULES_DIR:", pineapple_ui.ACTIVE_MODULES_DIR)
    print("DEBUG_LOG:", pineapple_ui.DEBUG_LOG)
    print("Import successful!")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
