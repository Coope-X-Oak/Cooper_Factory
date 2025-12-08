import asyncio
import sys
import os
import time

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.bili_service import fetch_video_data
from app.services.subtitle_service import subtitle_service

# Mock logger to file
class Logger(object):
    def __init__(self):
        self.terminal = sys.stdout
        self.log = open("stability_verify.log", "w", encoding="utf-8")
    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
    def flush(self):
        self.terminal.flush()
        self.log.flush()

# sys.stdout = Logger() # Commented out for archive
# sys.stderr = Logger()

async def test_stability():
    bvid = "BV1dQSCBgENY"
    iterations = 5
    print(f"🔥 Starting verification test for {bvid}")
    print(f"🔄 Iterations: {iterations}")

    results = []

    for i in range(iterations):
        print(f"\n[Test #{i+1}] Fetching data...")
        start_time = time.time()
        
        try:
            # We specifically want to check subtitle service isolation too but let's use the main entry
            # to simulate real usage
            sub_content = await subtitle_service.fetch(bvid)
            duration = time.time() - start_time
            
            sub_len = len(sub_content)
            
            # Check correctness
            is_correct = "吸毒" in sub_content or "封存" in sub_content or "蔡雅琪" in sub_content
            if sub_len > 0 and not is_correct:
                status = "❌ WRONG VIDEO"
            elif sub_len == 0:
                status = "⚠️ EMPTY"
            else:
                status = "✅ CORRECT"

            print(f"   Done in {duration:.2f}s | Len: {sub_len} | {status}")
            
            results.append({
                "iter": i+1,
                "len": sub_len,
                "status": status,
                "preview": sub_content[:50].replace('\n', ' ')
            })
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        await asyncio.sleep(1)

    print("\n" + "=" * 50)
    print("📊 Verification Report")
    correct_count = sum(1 for r in results if r['status'] == "✅ CORRECT")
    print(f"Correctness Rate: {correct_count}/{iterations}")
    
    for r in results:
        print(f"#{r['iter']}: {r['status']} (Len={r['len']}) - {r['preview']}...")

if __name__ == "__main__":
    asyncio.run(test_stability())
