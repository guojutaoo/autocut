with open('outputs/autocut_project/narrations/narration_00.wav', 'rb') as f:
    header = f.read(12)
    print(f"Header bytes: {header}")
    if header.startswith(b'RIFF'):
        print("This is a RIFF/WAV file.")
    elif header.startswith(b'ID3') or header.startswith(b'\xff\xfb'):
        print("This looks like an MP3 file.")
    else:
        print("Unknown file format.")
