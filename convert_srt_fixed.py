import os

def convert_srt():
    srt_path = 'outputs/input/01.srt'
    output_path = 'transcript_for_llm.txt'
    
    with open(srt_path, 'r', encoding='utf-8') as f:
        lines = f.read().strip().split('\n')
        
    blocks = []
    current_block = []
    for line in lines:
        if line.strip() == '':
            if current_block:
                blocks.append(current_block)
                current_block = []
        else:
            current_block.append(line)
    if current_block:
        blocks.append(current_block)
        
    with open(output_path, 'w', encoding='utf-8') as f:
        for block in blocks:
            if len(block) >= 3:
                time_line = block[1]
                text = ' '.join(block[2:])
                if '-->' in time_line:
                    start, end = time_line.split('-->')
                    start = start.strip().replace(',', '.')
                    end = end.strip().replace(',', '.')
                    f.write(f'[{start} - {end}] {text}\n')

if __name__ == '__main__':
    convert_srt()
