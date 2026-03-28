"""测试 edge-tts 的 WordBoundary 功能"""
import asyncio
import json
import os

# 设置日志级别
import logging
logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] %(message)s')

try:
    import edge_tts
    print(f"edge-tts version: {edge_tts.__version__ if hasattr(edge_tts, '__version__') else 'unknown'}")
except ImportError:
    print("edge-tts not installed")
    exit(1)

async def test_boundaries():
    text = "你好，这是一个测试。"
    voice = "zh-CN-XiaoxiaoNeural"
    
    communicate = edge_tts.Communicate(text, voice)
    
    chunk_types = set()
    boundaries = []
    audio_size = 0
    
    print("Starting TTS stream...")
    async for chunk in communicate.stream():
        kind = chunk.get("type")
        chunk_types.add(kind)
        
        if kind == "audio":
            data = chunk.get("data")
            if data:
                audio_size += len(data)
        elif kind in ("word boundary", "sentence boundary", "WordBoundary", "SentenceBoundary"):
            print(f"Found boundary: type={kind}, offset={chunk.get('offset')}, duration={chunk.get('duration')}, text={chunk.get('text') or chunk.get('word')}")
            boundaries.append({
                "type": kind,
                "offset": chunk.get("offset"),
                "duration": chunk.get("duration"),
                "text": chunk.get("text") or chunk.get("word") or chunk.get("boundary_text"),
            })
        else:
            # 打印其他类型的 chunk
            print(f"Other chunk type: {kind}, keys: {list(chunk.keys())}")
    
    print(f"\n=== 测试结果 ===")
    print(f"Chunk types seen: {chunk_types}")
    print(f"Boundaries collected: {len(boundaries)}")
    print(f"Audio data size: {audio_size} bytes")
    
    if boundaries:
        print(f"\nBoundaries details:")
        for b in boundaries:
            print(f"  - {b}")
        return True
    else:
        print("\n没有收集到任何 boundaries!")
        print("\n可能的原因:")
        print("1. edge-tts 版本不支持 WordBoundary")
        print("2. 需要使用特定的 voice")
        print("3. 需要设置特定的 output_format")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_boundaries())
    exit(0 if result else 1)
