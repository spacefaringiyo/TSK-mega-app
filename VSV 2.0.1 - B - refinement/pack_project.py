import os
from pathlib import Path

# Files/Folders to ignore
IGNORE = {
    '__pycache__', '.git', '.vscode', '.idea', 'node_modules',
    'lightweight-charts.js', 'v2_config.json', 'pack_project.py',
    '.DS_Store', 'venv', 'env'
}

# EXTENSIONS to include (add more if needed, e.g., .json, .html, .css)
INCLUDE_EXTS = {'.py', '.js', '.html', '.css', '.json', '.md'}

# Max characters per output file (approx 1 token = 4 chars)
# 50,000 chars is roughly 12.5k tokens, safe for most LLMs.
MAX_CHARS_PER_FILE = 125000

def get_structure_tree(root):
    tree_str = "PROJECT STRUCTURE:\n"
    for path in sorted(root.rglob("*")):
        # Check ignores
        if any(part in IGNORE for part in path.parts): continue
        if path.is_dir(): continue
        
        rel_path = path.relative_to(root)
        tree_str += f"- {rel_path}\n"
    tree_str += "\n" + "="*50 + "\n\n"
    return tree_str

def pack():
    root = Path(__file__).parent
    
    # Clean up old context files first
    for old_file in root.glob("_project_context_part_*.txt"):
        try: os.remove(old_file)
        except: pass

    # Prepare file list
    files_to_process = []
    for path in sorted(root.rglob("*")):
        if any(part in IGNORE for part in path.parts): continue
        if path.is_dir(): continue
        if path.suffix not in INCLUDE_EXTS: continue
        if path.name == "pack_project.py": continue
        files_to_process.append(path)

    part_num = 1
    current_content = ""
    
    # Add structure tree to the very first part only
    current_content += get_structure_tree(root)

    for path in files_to_process:
        rel_path = path.relative_to(root)
        file_header = f"--- START OF FILE: {rel_path} ---\n"
        file_footer = f"\n--- END OF FILE: {rel_path} ---\n\n"
        
        try:
            with open(path, "r", encoding="utf-8", errors='ignore') as f:
                file_body = f.read()
        except Exception as e:
            file_body = f"Error reading file: {e}"

        full_entry = file_header + file_body + file_footer
        
        # Check if adding this file exceeds the limit
        if len(current_content) + len(full_entry) > MAX_CHARS_PER_FILE:
            # Save current chunk
            write_chunk(root, part_num, current_content)
            part_num += 1
            current_content = "" # Reset buffer
            
            # If a SINGLE file is massive and larger than MAX_CHARS alone, 
            # we just put it in the new file anyway (overflowing slightly), 
            # otherwise it never gets written.
        
        current_content += full_entry

    # Write the remaining content (last part)
    if current_content:
        write_chunk(root, part_num, current_content)

    print(f"Done! Project packed into {part_num} file(s).")

def write_chunk(root, part_num, content):
    filename = root / f"_project_context_part_{part_num}.txt"
    with open(filename, "w", encoding="utf-8") as out:
        out.write(f"// PART {part_num} //\n\n")
        out.write(content)
    print(f"Created: {filename.name} ({len(content)} chars)")

if __name__ == "__main__":
    pack()