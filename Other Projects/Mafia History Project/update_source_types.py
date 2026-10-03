import json
import os
import shutil
from typing import Dict, Any

# --- CONFIGURATION (Ensure paths are correct) ---
# Assuming this script is run from the project root (F:\IC Mafia Bot\)
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FOLDER = os.path.join(PROJECT_DIR, "output")

# Define input/output files
INPUT_FILENAME = "new_discord_history.jsonl"
TEMP_FILENAME = "new_discord_history_temp.jsonl"

INPUT_PATH = os.path.join(OUTPUT_FOLDER, INPUT_FILENAME)
TEMP_PATH = os.path.join(OUTPUT_FOLDER, TEMP_FILENAME)

# Define the old and new values
OLD_SOURCE_TYPE = "Discord-Archive"
NEW_SOURCE_TYPE = "Discord-Live"

def update_source_types(input_path: str, temp_path: str, old_value: str, new_value: str):
    """Reads the JSONL file, updates a specific field, and saves to a new file."""
    
    print(f"--- Starting source type update for {INPUT_FILENAME} ---")
    
    records_updated = 0
    records_processed = 0
    
    if not os.path.exists(input_path):
        print(f"ERROR: Input file not found at {input_path}. Aborting.")
        return

    try:
        # 1. Read from INPUT and write to TEMP
        with open(input_path, 'r', encoding='utf-8') as infile, \
             open(temp_path, 'w', encoding='utf-8') as outfile:
            
            for line in infile:
                records_processed += 1
                try:
                    record: Dict[str, Any] = json.loads(line)
                    
                    # 2. Check and Modify the Source Type
                    if record.get("source_type") == old_value:
                        record["source_type"] = new_value
                        records_updated += 1
                    
                    # 3. Write the modified record to the temporary file
                    outfile.write(json.dumps(record, ensure_ascii=False) + '\n')
                    
                except json.JSONDecodeError:
                    print(f"WARNING: Skipping malformed JSON line in {INPUT_FILENAME}.")
                    outfile.write(line) # Preserve the original line

        # 4. Success: Replace the original file with the corrected file
        os.remove(input_path)
        os.rename(temp_path, input_path)
        
        print("\n-------------------------------------------------------------")
        print(f"SUCCESS! File {INPUT_FILENAME} successfully updated.")
        print(f"Total Records Processed: {records_processed}")
        print(f"Total 'source_type' fields updated: {records_updated}")
        print("-------------------------------------------------------------")

    except Exception as e:
        print(f"FATAL ERROR during file processing: {e}")
        # Clean up the temp file if the operation failed mid-way
        if os.path.exists(temp_path):
            os.remove(temp_path)

if __name__ == "__main__":
    update_source_types(INPUT_PATH, TEMP_PATH, OLD_SOURCE_TYPE, NEW_SOURCE_TYPE)