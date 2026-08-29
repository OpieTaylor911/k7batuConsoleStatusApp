import pathlib

p = pathlib.Path("/home/bcaddy/uconsole-k7bat/app/plugins.json")
content = p.read_text(encoding="utf-8-sig")
p.write_text(content, encoding="utf-8", newline="\n")
print("Fixed!")
