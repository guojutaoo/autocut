import re

content = open('outputs/input/01.srt', 'r', encoding='utf-8').read()
pattern = re.compile(r'(\d+)\s*\n(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\s*\n(.*?)(?=\n\s*\d+\s*\n|\Z)', re.DOTALL)
matches = pattern.findall(content)

for m in matches:
    if m[0] == '157':
        print("Block 157 matched text:")
        print(repr(m[3]))
