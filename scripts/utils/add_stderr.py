with open('/home/bcaddy/uconsole-k7bat/plugins/reaver/reaver_ui.py', 'r') as f:
    content = f.read()

# Replace the subprocess.run calls to add stderr=subprocess.DEVNULL
content = content.replace(
    '''result = subprocess.run(
            ["iwconfig"],
            capture_output=True,
            text=True
        )''',
    '''result = subprocess.run(
            ["iwconfig"],
            capture_output=True,
            text=True,
            stderr=subprocess.DEVNULL
        )'''
)

with open('/home/bcaddy/uconsole-k7bat/plugins/reaver/reaver_ui.py', 'w') as f:
    f.write(content)

print('Added stderr suppression!')
