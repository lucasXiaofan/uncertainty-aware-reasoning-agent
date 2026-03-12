import json
import os

def extract_json_objects(text):
    """
    Extracts all JSON objects from a given text.
    Handles extra characters, whitespace, and concatenated JSONs.
    """
    objects = []
    decoder = json.JSONDecoder()
    idx = 0
    text = text.lstrip()
    while idx < len(text):
        try:
            obj, next_idx = decoder.raw_decode(text[idx:])
            objects.append(obj)
            idx += next_idx
            
            # Skip any whitespace or common separators (like commas/periods)
            while idx < len(text) and text[idx] in " \n\r\t.,;":
                idx += 1
        except json.JSONDecodeError:
            # If decoding fails, search for the next '{'
            next_start = text.find("{", idx + 1)
            if next_start == -1:
                break
            idx = next_start
    return objects

def main():
    # Define relative paths, assuming the script is run from experiment_highest_transfer_clusters/
    txt_path = "new_medqa_agentic/new_cases.txt"
    jsonl_path = "new_medqa_similar_cases.jsonl"

    if not os.path.exists(txt_path):
        print(f"Error: {txt_path} not found.")
        return

    with open(txt_path, "r", encoding="utf-8") as f:
        text = f.read()

    new_objects = extract_json_objects(text)
    print(f"Found {len(new_objects)} case(s) in {txt_path}.")

    existing_objects = []
    if os.path.exists(jsonl_path):
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        existing_objects.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

    # Use a set of canonical JSON strings to efficiently check for duplicates
    def hash_obj(obj):
        return json.dumps(obj, sort_keys=True)

    existing_hashes = set(hash_obj(obj) for obj in existing_objects)

    added_count = 0
    # Open jsonl file in append mode. Write individual dictionaries to JSON format iteratively.
    with open(jsonl_path, "a", encoding="utf-8") as f:
        for obj in new_objects:
            obj_hash = hash_obj(obj)
            if obj_hash not in existing_hashes:
                # Append formatted one-line json
                f.write(json.dumps(obj) + "\n")
                existing_hashes.add(obj_hash)
                added_count += 1
                
    print(f"Successfully appended {added_count} unique new case(s) to '{jsonl_path}'.")

if __name__ == "__main__":
    main()
