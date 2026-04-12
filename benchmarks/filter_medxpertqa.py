import json

input_file = "medxpertqa_text_input.jsonl"
output_file = "filter_medxpertqa.jsonl"

matches = []
with open(input_file) as f:
    for line in f:
        entry = json.loads(line)
        q = entry.get("question", "").lower()
        if "diagnosis?" in q and "temperature" in q:
            matches.append(entry)

with open(output_file, "w") as f:
    for entry in matches:
        f.write(json.dumps(entry) + "\n")

print(f"Found {len(matches)} matching cases -> {output_file}")
