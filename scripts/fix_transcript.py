import re
import os

srt_path = 'outputs/input/01.srt'
output_path = 'transcript_for_llm.txt'

if not os.path.exists(srt_path):
    print(f"Error: {srt_path} not found")
    exit(1)

with open(srt_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Improved parsing to handle SRT blocks without regex bugs
blocks = content.strip().split('\n\n')
matches = []
for block in blocks:
    lines = block.split('\n')
    if len(lines) >= 3 and '-->' in lines[1]:
        time_line = lines[1]
        text = ' '.join(lines[2:])
        start, end = time_line.split('-->')
        matches.append((start.strip(), end.strip(), text.strip()))

with open(output_path, 'w', encoding='utf-8') as f:
    for start, end, text in matches:
        start = start.replace(',', '.')
        end = end.replace(',', '.')
        if text:
            f.write(f'[{start} - {end}] {text}\n')

print(f"Successfully converted {len(matches)} blocks to {output_path}")
