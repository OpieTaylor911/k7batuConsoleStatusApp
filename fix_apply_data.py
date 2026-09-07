import re

# Read the current file with UTF-8 encoding
with open('app/k7bat-uconsole-status.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find and replace the return False at end of apply_data to add try/except wrapper
old_pattern = r'(        self\.last_update\.set_text\("Updated: " \+ datetime\.now\(\)\.strftime\("%H:%M:%S"\)\)\s+return False\s+)'

new_replacement = '''        self.last_update.set_text("Updated: " + datetime.now().strftime("%H:%M:%S"))
        
        return False
        
        except Exception as ex:
            # Log any uncaught exception to debug file
            import traceback
            try:
                debug_log = APP_DIR.parent / "data_debug.txt"
                with open(debug_log, "a") as f:
                    f.write(f"\\nEXCEPTION in apply_data: {ex}\\n")
                    f.write(traceback.format_exc())
                    f.write("\\n" + "="*60 + "\\n")
            except Exception:
                pass
            return False
'''

content = re.sub(old_pattern, new_replacement, content)

# Write back with UTF-8 encoding
with open('app/k7bat-uconsole-status.py', 'w', encoding='utf-8') as f:
    f.write(content)
    
print('Done')
