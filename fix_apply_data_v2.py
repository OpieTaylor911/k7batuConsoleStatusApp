#!/usr/bin/env python3
# Read the file
with open('app/k7bat-uconsole-status.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the apply_data function and fix its structure
output = []
i = 0
while i < len(lines):
    line = lines[i]
    
    # Check if we're at the start of apply_data
    if 'def apply_data(self, d):' in line:
        output.append(line)
        i += 1
        
        # Skip to the line after self._refreshing = False
        while i < len(lines) and 'self._refreshing = False' not in lines[i]:
            output.append(lines[i])
            i += 1
        
        if i < len(lines):
            output.append(lines[i])  # Add self._refreshing = False
            i += 1
            
            # Now add the comprehensive try/except wrapper
            output.append('\n')
            output.append('        try:\n')
            
            # Skip any existing try statements and find where to close our try block
            brace_count = 0
            while i < len(lines):
                line = lines[i]
                
                # Check if this is the end of apply_data (next function or class)
                if ((line.strip().startswith('def ') and 'apply_data' not in line) or 
                    line.strip().startswith('class ') or 
                    line.strip() == 'Gtk.init([])'):
                    # We've reached the end, add our except block before it
                    output.append('\n')
                    output.append('        except Exception as ex:\n')
                    output.append('            import traceback\n')
                    output.append('            try:\n')
                    output.append('                debug_log = APP_DIR.parent / "data_debug.txt"\n')
                    output.append('                with open(debug_log, "a") as f:\n')
                    output.append('                    f.write(f"\\nEXCEPTION in apply_data: {ex}\\n")\n')
                    output.append('                    f.write(traceback.format_exc())\n')
                    output.append('                    f.write("\\n" + "="*60 + "\\n")\n')
                    output.append('            except Exception:\n')
                    output.append('                pass\n')
                    output.append('            return False\n')
                    output.append('\n')
                    break
                
                # Add the line to output
                output.append(line)
                
                i += 1
            
            i += 1
    else:
        output.append(line)
        i += 1

# Write back
with open('app/k7bat-uconsole-status.py', 'w', encoding='utf-8') as f:
    f.writelines(output)

print('Fixed apply_data structure')
