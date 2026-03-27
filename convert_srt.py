import re
import os

srt_path = 'outputs/input/01.srt'
output_path = 'transcript_for_llm.txt'

with open(srt_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Regular expression to match SRT blocks
pattern = re.compile(r'(\d+)\s*\n(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\s*\n(.*?)(?=\n\s*\d+\s*\n|\Z)', re.DOTALL)
matches = pattern.findall(content)

with open(output_path, 'w', encoding='utf-8') as f:
    for m in matches:
        start = m[1].replace(',', '.')
        end = m[2].replace(',', '.')
        text = m[3].strip().replace('\n', ' ')
        if text:
            f.write(f'[{start} - {end}] {text}\n')
