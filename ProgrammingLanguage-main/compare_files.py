import os
import difflib

# Define paths
base_dir = r"c:\Users\joon3\OneDrive\바탕 화면\2-2 학습자료\프로그래밍언어\팀플 코드 모음\ProgrammingLanguage\ProgrammingLanguage-main"
dir1 = os.path.join(base_dir, "최종코드1")
dir2 = os.path.join(base_dir, "최종코드1 - 장애물,최단거리 해결 백업본")

files_to_check = ["data_structures.py", "logger.py", "pathfinding.py", "sim_core.py"]

for filename in files_to_check:
    file1 = os.path.join(dir1, filename)
    file2 = os.path.join(dir2, filename)
    
    try:
        with open(file1, 'r', encoding='utf-8') as f1:
            lines1 = f1.readlines()
        with open(file2, 'r', encoding='utf-8') as f2:
            lines2 = f2.readlines()
            
        diff = list(difflib.unified_diff(lines1, lines2, fromfile=f"Directory1/{filename}", tofile=f"Directory2/{filename}", lineterm=''))
        
        if not diff:
            print(f"[{filename}] MATCHES EXACTLY.")
        else:
            print(f"[{filename}] HASE DIFFERENCES:")
            # Print only first few diffs to avoid spam
            for line in diff[:20]:
                print(line)
            if len(diff) > 20:
                print("... (truncated)")
            print("-" * 50)
            
    except Exception as e:
        print(f"Error checking {filename}: {e}")
