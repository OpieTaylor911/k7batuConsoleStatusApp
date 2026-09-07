#!/usr/bin/env python3
# Read the file
with open('app/k7bat-uconsole-status.py', 'r', encoding='utf-8') as f:
    content = f.read()

import re

# Find the line numbers for apply_data function start and end
lines = content.split('\n')
start_idx = None
end_idx = None

for i, line in enumerate(lines):
    if 'def apply_data(self, d):' in line:
        start_idx = i
    elif start_idx is not None and (line.strip().startswith('class ') or 
                                     (line.strip().startswith('def ') and i > start_idx) or
                                     line.strip() == 'Gtk.init([])'):
        end_idx = i
        break

if start_idx is not None:
    if end_idx is None:
        end_idx = len(lines)
    
    print(f"Found apply_data from line {start_idx+1} to {end_idx}")
    
    # Extract the function body (skip first two lines: def and self._refreshing)
    func_body_lines = []
    skip_first_two = True
    for i in range(start_idx + 1, end_idx):
        if skip_first_two:
            if 'self._refreshing = False' in lines[i]:
                skip_first_two = False
            continue
        
        # Stop at the first except block we find (the duplicate one)
        if 'except Exception as ex:' in lines[i] and i > start_idx + 10:
            break
            
        func_body_lines.append(lines[i])
    
    print(f"Function body has {len(func_body_lines)} lines")
    
    # Build the fixed version
    new_func = []
    new_func.append('    def apply_data(self, d):')
    new_func.append('        self._refreshing = False')
    new_func.append('')
    new_func.append('        try:')
    
    for line in func_body_lines:
        if line.strip():  # Only add non-empty lines
            # Indent by 8 spaces (4 more than current)
            if line.startswith('    '):
                new_func.append('    ' + line)
            else:
                new_func.append(line)
    
    new_func.append('')
    new_func.append('        except Exception as ex:')
    new_func.append('            import traceback')
    new_func.append('            try:')
    new_func.append('                debug_log = APP_DIR.parent / "data_debug.txt"')
    new_func.append('                with open(debug_log, "a") as f:')
    new_func.append('                    f.write(f"\\nEXCEPTION in apply_data: {ex}\\n")')
    new_func.append('                    f.write(traceback.format_exc())')
    new_func.append('                    f.write("\\n" + "="*60 + "\\n")')
    new_func.append('            except Exception:')
    new_func.append('                pass')
    new_func.append('            return False')
    
    # Replace the function in the content
    before = '\n'.join(lines[:start_idx])
    after = '\n'.join(lines[end_idx:])
    new_content = before + '\n' + '\n'.join(new_func) + '\n\n' + after
    
    # Write back
    with open('app/k7bat-uconsole-status.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print('Fixed apply_data function')
else:
    print("Could not find apply_data function")
