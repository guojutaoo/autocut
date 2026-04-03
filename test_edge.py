import asyncio
import edge_tts

async def main():
    communicate = edge_tts.Communicate("你好啊<break time=\"1.0s\"/>我很好", "zh-CN-YunjianNeural")
    await communicate.save("test_tts.mp3")

asyncio.run(main())