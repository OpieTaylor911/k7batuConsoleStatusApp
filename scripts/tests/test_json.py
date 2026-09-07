import json

try:
    with open('/home/bcaddy/uconsole-k7bat/app/plugins.json') as f:
        data = json.load(f)
    print("OK:", len(data), "plugins loaded")
except Exception as e:
    print("ERROR:", str(e))
