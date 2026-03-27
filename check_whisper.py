try:
    import whisper
    print("whisper found")
except ImportError:
    print("whisper not found")
