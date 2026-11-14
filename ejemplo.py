import json
with open("data.json", encoding="utf-8") as file:
    data = json.load(file)
print(data)
