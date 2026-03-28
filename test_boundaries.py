#!/usr/bin/env python3
"""Test script to debug edge-tts WordBoundary events."""
import asyncio
import edge_tts

async def test_boundaries():
    """Test what chunk types edge-tts returns."""
    text = "你好，这是一个测试。"
    voice = "zh-CN-YunjianNeural"
    
    communicate = edge_tts.Communicate(text, voice)
    
    chunk_types = set()
    word_boundaries = []
    
    async for chunk in communicate.stream():
        kind = chunk.get("type")
        chunk_types.add(kind)
        
        print(f"Chunk type: {kind!r}")
        print(f"Chunk keys: {list(chunk.keys())}")
        
        if kind and "boundary" in kind.lower():
            word_boundaries.append(chunk)
            print(f"  -> Boundary: {chunk}")
        
        print()
    
    print(f"\nAll chunk types: {chunk_types}")
    print(f"Word boundaries found: {len(word_boundaries)}")

if __name__ == "__main__":
    asyncio.run(test_boundaries())
