import json
import os

transcript_path = r"C:\Users\LEKE_TECH\.gemini\antigravity-ide\brain\f071e017-5204-4b25-bc32-1b272241f3ef\.system_generated\logs\transcript_full.jsonl"
out_dir = r"c:\Users\LEKE_TECH\.gemini\antigravity\scratch\video_recoverer"

file_contents = {}

with open(transcript_path, 'r', encoding='utf-8') as f:
    for line in f:
        try:
            entry = json.loads(line)
        except:
            continue
            
        if "tool_calls" in entry:
            for call in entry["tool_calls"]:
                name = call.get("name", "")
                args = call.get("arguments", call.get("args", {}))
                
                # Check for default_api: prefix or just the name
                if "write_to_file" in name:
                    target = args.get("TargetFile")
                    content = args.get("CodeContent")
                    if target and content and 'src' in target:
                        file_contents[target] = content
                        
                elif "replace_file_content" in name and "multi" not in name:
                    target = args.get("TargetFile")
                    if target and target in file_contents:
                        content = file_contents[target]
                        target_content = args.get("TargetContent")
                        replacement = args.get("ReplacementContent")
                        if target_content and replacement:
                            file_contents[target] = content.replace(target_content, replacement)

                elif "multi_replace_file_content" in name:
                    target = args.get("TargetFile")
                    chunks = args.get("ReplacementChunks", [])
                    if target and target in file_contents:
                        content = file_contents[target]
                        lines = content.split('\n')
                        chunks.sort(key=lambda x: x["StartLine"], reverse=True)
                        for chunk in chunks:
                            start = chunk["StartLine"] - 1
                            end = chunk["EndLine"]
                            replacement = chunk["ReplacementContent"].split('\n')
                            lines = lines[:start] + replacement + lines[end:]
                        file_contents[target] = '\n'.join(lines)

for path, content in file_contents.items():
    print(f"Recovering {path}")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

print("Done recovering files.")
