# A script to output the folder structure and file names
import os
from datetime import datetime
# Only print the folder structure and file names for only the IC Mafia Bot root, plus "Cogs", "Data" "game", and "utils" folders and save to a text file
def print_folder_structure(root_folder):
    with open("folder_structure.txt", "w", encoding='utf-8') as f:
        f.write(f"Folder structure generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        for dirpath, dirnames, filenames in os.walk(root_folder):
            # Only include the root folder and specific subfolders
            if dirpath == root_folder or os.path.basename(dirpath) in ["Cogs", "Data", "game", "utils", "Stats", "Tests", "Community"]:
                f.write(f"Directory: {dirpath}\n")
                for dirname in dirnames:
                    f.write(f"  Subdirectory: {dirname}\n")
                for filename in filenames:
                    f.write(f"  File: {filename}\n")
                f.write("\n")

if __name__ == "__main__":
    root_folder = os.path.dirname(os.path.abspath(__file__))
    print_folder_structure(root_folder)