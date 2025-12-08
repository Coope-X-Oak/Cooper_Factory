import asyncio
import sys
import os
import time

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.cookie_manager import CookieManager
import httpx

class Logger(object):
    def __init__(self):
        self.terminal = sys.stdout
        self.log = open("cid_stability.log", "w", encoding="utf-8")
    def write(self, message):
        try:
            self.terminal.write(message)
        except:
            pass 
        self.log.write(message)
    def flush(self):
        try:
            self.terminal.flush()
        except:
            pass
        self.log.flush()

# sys.stdout = Logger()
# sys.stderr = Logger()

async def fetch_cid_consistency():
    bvid = "BV1dQSCBgENY" # The problematic video
    iterations = 10
    interval = 3
    
    # Load cookies
    cm = CookieManager()
    cookie_str = cm.get_cookie_header()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.bilibili.com/",
    }
    if cookie_str:
        headers["Cookie"] = cookie_str
        print("✅ Cookies Loaded for test")
    else:
        print("⚠️ No Cookies Loaded (Testing Anonymous)")

    print(f"🔥 Starting CID Consistency Test for {bvid}")
    print(f"   Iterations: {iterations}, Interval: {interval}s")
    print("-" * 60)
    
    results = []
    
    async with httpx.AsyncClient(headers=headers, timeout=10.0, follow_redirects=True) as client:
        for i in range(iterations):
            print(f"\n[#{i+1}] Requesting info...")
            start_t = time.time()
            
            try:
                # 1. View API
                info_url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
                resp_info = await client.get(info_url)
                data_info = resp_info.json()
                
                if data_info['code'] != 0:
                    print(f"   ❌ View API Error: {data_info}")
                    continue
                    
                aid = data_info['data']['aid']
                resp_bvid = data_info['data']['bvid']
                title = data_info['data']['title']
                
                # Check consistency
                view_match = (resp_bvid == bvid)
                
                # 2. Pagelist API
                page_url = f"https://api.bilibili.com/x/player/pagelist?bvid={bvid}&aid={aid}"
                resp_page = await client.get(page_url)
                data_page = resp_page.json()
                
                cid = "N/A"
                if data_page['code'] == 0 and data_page['data']:
                    cid = data_page['data'][0]['cid']
                
                duration = time.time() - start_t
                
                status = "✅" if view_match else "❌ BVID MISMATCH"
                print(f"   CID: {cid:<12} | Title: {title[:20]}... | BVID Match: {view_match}")
                
                results.append({
                    "iter": i+1,
                    "cid": cid,
                    "aid": aid,
                    "resp_bvid": resp_bvid
                })
                
            except Exception as e:
                print(f"   ❌ Exception: {e}")
            
            if i < iterations - 1:
                await asyncio.sleep(interval)

    # Analysis
    print("\n" + "=" * 60)
    print("📊 Consistency Report")
    
    cids = set(r['cid'] for r in results)
    
    if len(cids) == 1:
        print(f"✅ STABLE: All {len(results)} requests returned CID {list(cids)[0]}")
    else:
        print(f"❌ UNSTABLE: Found {len(cids)} different CIDs: {cids}")
        for r in results:
             print(f"   #{r['iter']}: {r['cid']} (BVID: {r['resp_bvid']})")

if __name__ == "__main__":
    asyncio.run(fetch_cid_consistency())
