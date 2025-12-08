import asyncio
import sys
import os
import time

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.bili_service import fetch_video_data

TEST_CASES = [
    ("BV17T2sBmEqn", "有一个朋友说：蔡雅奇是做最高法院大法官的好料子"),
    ("BV1Bx2ZBCEeA", "吸毒者周边的人都是犯罪，不如再进一步"),
    ("BV1mTSYBhEsR", "再说几句：吸毒记录是否该被封存"),
    ("BV1K2ynBmESx", "放弃诲人情结，尊重当事人和当事人家属命运"),
    ("BV1tLbTz4Efi", "有一个法官竟然对我说：你为什么不申请我回避呢"),
]

async def batch_test():
    print(f"🔥 Starting Batch Test for {len(TEST_CASES)} videos")
    print("-" * 60)
    
    results = []
    
    for i, (bvid, title_snippet) in enumerate(TEST_CASES):
        print(f"\n[{i+1}/{len(TEST_CASES)}] Testing {bvid}...")
        print(f"   Target: {title_snippet}...")
        
        start_time = time.time()
        try:
            meta, raw_text = await fetch_video_data(bvid)
            duration = time.time() - start_time
            
            # Subtitle Extraction
            subtitle = ""
            if "【视频字幕(Core)】:" in raw_text:
                subtitle = raw_text.split("【视频字幕(Core)】:\n")[-1].strip()
            
            sub_len = len(subtitle)
            
            if sub_len > 100:
                status = "✅ SUCCESS"
            elif sub_len == 0:
                status = "⚠️ EMPTY"
            else:
                 status = "❓ SHORT"

            print(f"   Result: {status} ({sub_len} chars) in {duration:.2f}s")
            print(f"   Preview: {subtitle[:50].replace(chr(10), ' ')}...")
            
            results.append({
                "bvid": bvid,
                "status": status,
                "length": sub_len,
                "title": meta.get('title', 'Unknown')
            })
            
        except Exception as e:
            print(f"   ❌ FAILED: {e}")
            results.append({
                "bvid": bvid,
                "status": "❌ ERROR",
                "error": str(e)
            })
            
        await asyncio.sleep(2)  # Courtesy delay

    print("\n" + "=" * 60)
    print("📊 Batch Test Report")
    print("=" * 60)
    
    for r in results:
        title = r.get('title', r.get('error', ''))
        print(f"{r['bvid']}: {r['status']} (Len={r.get('length', 0)}) | {title[:40]}")

if __name__ == "__main__":
    asyncio.run(batch_test())
