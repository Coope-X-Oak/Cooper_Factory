import asyncio
import sys
import os
import re

# Add backend to sys.path to mimic running from backend root
sys.path.append(os.getcwd())

from app.services.subtitle_service import subtitle_service
from app.services.bili_service import fetch_video_data

async def compare():
    bvid = "BV1dQSCBgENY"
    print(f"Comparing results for {bvid}...")

    # 1. Direct Subtitle Service Call
    print("\n--- 1. Calling subtitle_service.fetch() ---")
    sub_direct = await subtitle_service.fetch(bvid)
    print(f"Direct Length: {len(sub_direct)}")
    
    
    # 2. Bili Service Call (Main Flow)
    print("\n--- 2. Calling bili_service.fetch_video_data() ---")
    meta, raw_text = await fetch_video_data(bvid)
    
    # Extract subtitle from raw_text
    # Pattern mimic parse_raw_data in main.py
    # raw_text += f"【视频字幕(Core)】:\n{subtitle_text}"
    if "【视频字幕(Core)】:" in raw_text:
        sub_via_main = raw_text.split("【视频字幕(Core)】:\n")[-1]
        # In main.py loop, it might continue, but here it's at the end usually
        # But let's follow the simple split since we know how bili_service constructs it
    else:
        sub_via_main = "NOT FOUND"
        
    print(f"Via Main Length: {len(sub_via_main)}")

    # 3. Comparison
    print("\n--- Comparison ---")
    if sub_direct == sub_via_main:
        print("✅ SUCCESS: Results are IDENTICAL.")
        print(f"Line count: {len(sub_direct.splitlines())}")
    else:
        print("❌ FAILURE: Results DIFFER.")
        print(f"Direct start: {sub_direct[:50]}")
        print(f"Main start:   {sub_via_main[:50]}")
        
        # Check if difference is just whitespace
        if sub_direct.strip() == sub_via_main.strip():
             print("⚠️  Warning: Content identical but whitespace differs.")

if __name__ == "__main__":
    try:
        asyncio.run(compare())
    except Exception as e:
        print(f"Error: {e}")
